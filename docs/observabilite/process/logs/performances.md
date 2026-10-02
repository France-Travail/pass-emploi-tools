# Performances du traitement des logs — tests, trajectoire, historique

> Comment on vérifie qu'un changement de config Logstash ne dégrade pas le débit,
> par où la chaîne est passée pour tenir la charge, et **l'historique complet
> des campagnes de tir** (méthode, config, résultats, next steps). Les sections
> datées ne sont **pas** des invariants : vérifier l'état réel sur Scalingo avant
> d'agir. Invariants JVM/Scalingo : [infrastructure.md](../../infrastructure.md).

## Test de non-régression des performances

Le workflow `.github/workflows/logstash-perf.yml` ("Logstash - Test de non régression
des performances") permet de valider, sur un **environnement de performance dédié**
(`pass-emploi-logstash-perf` sur Scalingo), qu'une modification de la config Logstash
ne dégrade pas les performances par rapport à la cible.

Il se déclenche automatiquement sur les PR modifiant `logs/**`, ou manuellement.

**Cible de performance :**
- Gatling (`LogstashIngestSimulation`) envoie des requêtes HTTP directes à Logstash
  (comme le ferait le drain Scalingo) : montée progressive jusqu'à **1 000 logs/s**,
  maintenue **120 secondes**.
- Assertion : `p95 < 500ms` sur le temps de réponse HTTP Logstash, taux d'erreur < 0,1%.

**Livrables disponibles pour analyser les résultats :**
- **Rapport HTML Gatling** : uploadé en artifact GitHub Actions (`gatling-report-<run_id>`,
  rétention 21 jours) — temps de réponse, percentiles, distribution des erreurs.
- **Job Summary GitHub Actions** : métriques ES post-test — nombre de logs indexés,
  histogramme d'indexation par tranche de 1 minute (détecte les tranches à 0 = saturation
  ES), 499 nginx sur le routeur Logstash.
  ⚠️ Les 499 nginx (`logs-router-perf-default`) seront `N/A` tant que le Log Drain
  Scalingo n'est pas configuré sur l'app perf (dashboard Scalingo, hors code).

## Trajectoire de scaling — tenir à x10

Le scaling horizontal ne règle **ni le drain ni ES**. Cause structurelle : les
**filtres lourds tournent sur le chemin d'ACK** de l'input HTTP → ACK lent → 499 →
quarantaine. **Découpler recevoir de traiter** :

- **Option A (natif Logstash, à faire en premier)** : 2 pipelines — `ingest`
  (`http → PQ`, zéro filtre, ACK rapide) + `process` (`PQ → filtres → ES`). Supprime
  la quarantaine à la racine et rend la PQ structurelle.
- **Option B (gros volume)** : broker Kafka/Redis entre apps et Logstash.
- **En parallèle** : scaler ES (data streams/ILM/ingest nodes) ; déporter du parsing
  vers les **ingest pipelines ES** (réduire le coût **par event**, pas le volume).
- **À mesurer** : plafond d'**une** instance (req/min avant 429/499) → marge linéaire
  + seuil de bascule vers l'option A puis B.

Détail et justification : [postmortem-2026-07-blackout-logs.md § 7](../../post-mortems/postmortem-2026-07-blackout-logs.md#7-next-steps--tenir-à-x10).

## Étape 1 — architecture 2 pipelines avec persistent queue (2026-07)

> **Historique** : remplacée en 2026-09 par le buffer Redis entre deux services
> séparés (option B, cf. [ADR-002](../../../decisions/ADR-002-buffer-redis-logstash.md)).
> État actuel : [collecte/logs/pipeline.md](../../collecte/logs/pipeline.md) et [pipeline.md](pipeline.md).

Fichiers de référence :
- `logs/config/pipelines.yml` — définition des 2 pipelines et de leurs paramètres.
- `logs/pipeline-ingest.conf` — pipeline `ingest` : input HTTP → PQ, **zéro filtre**.
- `logs/pipeline-process.conf` — pipeline `process` : PQ → filtres → ES.
- `logs/Procfile` — lance Logstash avec `--path.settings /app/config` (charge `pipelines.yml`).

**Principe** : le pipeline `ingest` ACK le drain en ~1ms (écriture disque PQ).
Le pipeline `process` lit la PQ à son rythme et fait tout le traitement.
Un hoquet ES ou GC dans `process` n'affecte plus l'ACK → **plus de quarantaine**.

**RÈGLE D'OR** : ne jamais ajouter de filtre dans `pipeline-ingest.conf`.
Chaque filtre ajouté rallonge l'ACK et risque de réintroduire la quarantaine.

**Paramètres clés** (voir `pipelines.yml` pour le détail et les commentaires) :
- `ingest` : `queue.type: persisted`, `queue.max_bytes: 512mb`, `pipeline.workers: 1`.
- `process` : `queue.type: memory`, `pipeline.workers: 4`, `pipeline.batch.size: 250`.

Garde-fou de l'époque (PQ) :

- **Persistent queue** (`queue.type: persisted`) = buffer **disque** (pas RAM),
   sous `/app` (writable, éphémère). `queue.max_bytes` = plafond avant contre-pression
   (~64 Mo au repos). C'est le **filet du mode A**. ⚠️ Éphémère : survit aux blips ES,
   pas à un restart ; le fsync peut rallonger l'ACK → à surveiller vs les 499.

## Historique des campagnes

> **Correction (2026-09-30)** : le heap Logstash se règle via **`LS_JAVA_OPTS`** ;
> `JAVA_OPTS` est ignoré par le lanceur. Les mentions de `JAVA_OPTS` dans les
> campagnes ci-dessous sont erronées, cf. [infrastructure.md](../../infrastructure.md#garde-fous-jvm--scalingo).

> Au **2026-07-02** :

- **4× XL** (2 Go), heap **`-Xms1g -Xmx1g`** via `JAVA_OPTS`.
- **PQ retirée** temporairement (test GC-vs-ES) ; `-Xlog:gc,safepoint` activé
  temporairement via `JAVA_OPTS`.
- Plus de perte observée, response time plat au pic (~35k req/min).
- Décisions ouvertes : remettre la PQ (filet mode A), retirer le GC verbeux après
  test, statuer heap `jvm.options` vs `JAVA_OPTS`. Cf. postmortem § 6.

> Au **2026-07-31** (suite tests de charge — voir [ticket Notion](https://app.notion.com/p/ETQ-supports-L2-3-je-collecte-l-int-gralit-de-mes-logs-d-erreurs-dans-la-stack-d-Observabilit-sur-3a07bd17c27a80688f16d492ae4ec8bc?v=3797bd17c27a800aba24000c6809e535&source=copy_link)) :

**Méthode de test :**
- Tests lancés sur deux apps Scalingo dédiées : `pass-emploi-logstash-perf` sur `master`
  (baseline) et sur la branche optimisée — infra iso (3× XL, même plan Elastic Cloud).
- Gatling (`LogstashIngestSimulation`) envoie des requêtes HTTP **directes** à Logstash
  (sans passer par le drain Scalingo) : montée progressive jusqu'à **5 000 logs/s**,
  maintenue **120 secondes**.
- ⚠️ Gatling remonte en **échec** (assertion p95 dépassée) car à 5 000 logs/s ES sature
  et les temps de réponse Logstash augmentent. La fenêtre de mesure ES (TEST_START →
  TEST_END) est donc **plus longue que 120s** : elle inclut le drain post-test de la PQ
  par le pipeline `process` après la fin de Gatling.

**Changements et configurations appliqués :**
- **3× XL** (2 Go), heap **`-Xms1g -Xmx1g`** via `JAVA_OPTS` (variable Scalingo).
- **Logstash 9.4.7** — buildpack custom dans `pass-emploi-tools/logstash/`.
- **Elastic Agent 9.4.7** — buildpack custom dans `pass-emploi-tools/elastic-agent/`, installé en mode colocalisé pour le monitoring Logstash via Fleet.
- **Heartbeat** — buildpack `SocialGouv/heartbeat-buildpack` (défaut 7.16.1, surchargeable via `HEARTBEAT_VERSION` sur Scalingo). ⚠️ Version à vérifier sur Scalingo.
- **APM** — géré via Fleet/Elastic Cloud, version pilotée par le plan Elastic Cloud (9.1.5).
  ⚠️ **Alignement des versions** : Elastic Cloud est en **9.1.5**, Logstash et Elastic Agent en **9.4.7** —
  les versions majeures sont alignées (9.x/9.x), mais il faudra **monter Elastic Cloud à 9.4.x**
  pour être en phase et bénéficier de toutes les fonctionnalités. Heartbeat et APM doivent également être alignés.
- **Java 21** (upgrade depuis Java 11 via buildpack custom).
- **`pipeline.ordered: false`** sur les 2 pipelines (supprime l'overhead de synchronisation).
- **`pipeline.batch.size: 250`** sur le pipeline `process` (défaut Logstash = 125) :
  réduit les round-trips ES → meilleur débit d'indexation.
- **`queue.max_bytes: 512mb`** sur le pipeline `ingest` (défaut Logstash = 1gb) :
  réduit à 512 Mo car le disque Scalingo est éphémère et partagé avec l'app. 512 Mo
  couvre largement un blip ES de quelques minutes au volume actuel (~5 000 logs/s × quelques
  Ko/log). À réévaluer si le volume augmente significativement.
- **`pipeline.workers`** : `ingest` = 1 (fixe), `process` = 1 (configurable via
  `LOGSTASH_PROCESS_WORKERS`). Testé à 4 workers : moins bon (goulot = plan Elastic Cloud,
  pas Logstash).
- `-Xlog:gc,safepoint` retiré de `JAVA_OPTS` (test GC-vs-ES terminé).

**Résultats :** _(tests du 2026-07-31)_

| Métrique                               | **master** (pipeline unique, sans PQ) | **branche** (2 pipelines + PQ) | Évolution       |
|----------------------------------------|---------------------------------------|--------------------------------|-----------------|
| Fenêtre d'exécution                    | 7 min 57 s                            | 10 min 07 s                    | —               |
| Logs indexés dans ES                   | 45 890                                | 71 773                         | **+56%**        |
| Débit moyen d'indexation ES            | ~96 logs/s                            | ~118 logs/s                    | **+23%**        |
| Saturation d'indexation (tranches à 0) | dès 4 min                             | dès 6 min                      | +2 min de tenue |
| CPU max                                | ~55%                                  | ~40%                           | -15%            |
| Mémoire max                            | ~1,4 Go                               | ~1,6 Go                        | +200 Mo (PQ)    |

- **+56% de logs indexés** : la PQ absorbe les pics et le pipeline `process` continue
  à drainer après la fin du test Gatling, là où master perdait les logs pendant la
  saturation ES. La fenêtre de mesure ES est plus longue que 120s pour la branche
  (drain post-test de la PQ).
- **Goulot d'indexation** : les tranches à 0 indiquent que l'indexation s'arrête dès ~4-6 min.
  La cause exacte (ES qui throttle, PQ pleine à 512 Mo, ou Logstash lui-même) n'est pas
  déterminable sans métriques Logstash/ES — voir next step 3.
- **Ce que ça ne résout pas** : si la PQ atteint `queue.max_bytes` (512 Mo), la contre-pression
  remonte jusqu'à l'input HTTP → même risque de quarantaine. Les 499 du drain ne sont pas
  mesurables dans ce test (Gatling envoie en direct, sans drain Scalingo).

**Next steps :**

1. **Compléter le test avec le drain Scalingo** : configurer le Log Drain Scalingo sur
   l'app perf (dashboard Scalingo) pour avoir `logs-router-perf-default` dans ES, et
   mesurer les 499 pour valider l'absence de quarantaine en conditions réelles.

2. **Adaptations possibles si on sature à nouveau** :
   - Augmenter `queue.max_bytes` (si le disque Scalingo le permet) pour absorber des
     blips ES plus longs.
   - Augmenter `pipeline.batch.size` (ex: 500) si ES supporte des bulks plus grands.
   - Scaler le plan Elastic Cloud (candidat probable au goulot — à confirmer avec les métriques, voir next step 3).
   - Déporter du parsing vers les **ingest pipelines ES** pour réduire le coût par event
     dans le pipeline `process`.
   - En dernier recours : broker Kafka/Redis (option B) pour découpler complètement
     le volume d'ingestion du débit ES.

3. **Métriques à surveiller avec la nouvelle architecture** : 
   **Elastic Agent de monitoring installé en mode colocalisé** (buildpack `pass-emploi-tools/elastic-agent/`, lancé 
   via `start.sh`). Pour avoir dans Kibana les métriques Logstash (débit pipelines, taille PQ, latence, alertes), 
   il faut configurer Fleet. Voir [pilotage.md](../../pilotage.md) et [`elastic-agent/README.md`](../../../../elastic-agent/README.md).

> Au **2026-09-14** (migration buffer PQ → Redis, cf. [ADR-002](../../../decisions/ADR-002-buffer-redis-logstash.md)) :
> dimensionnement et risque Redis consignés dans [infrastructure.md](../../infrastructure.md#dimensionnement-au-2026-09-14).
>
> Au **2026-09-23** (maintien du drain Scalingo, cf. [ADR-003](../../../decisions/ADR-003-usage-log-drain-scalingo.md)) :
> décision et suites ouvertes consignées dans [collecte/logs/drain-scalingo.md](../../collecte/logs/drain-scalingo.md#maintien-du-drain--décision-du-2026-09-23).
