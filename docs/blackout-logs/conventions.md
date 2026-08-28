# Conventions & garde-fous — ingestion des logs (drain → Logstash → ES)

> **Type** : référence (Diataxis). Les invariants durables de la chaîne d'ingestion
> de logs mutualisée : signatures de panne, garde-fous JVM/Scalingo, playbook de
> diagnostic. Sert aussi de **contexte de reprise** pour une session outillée.
>
> Récit de l'incident qui a produit ces règles : [postmortem-2026-07.md](./postmortem-2026-07.md).
> Conventions ECS du logging applicatif (autre sujet) :
> [../logs-ecs/](../logs-ecs/README.md).

## La chaîne (modèle mental)

```
apps (api / web / connect)  ──drain HTTP Scalingo──►  Logstash mutualisé  ──bulk──►  Elastic Cloud
   stdout                    (POST, par app)          (4× XL, pipelines)              (index logs-*)
```

- Infra : `pass-emploi-tools/logs/` — app Scalingo `pass-emploi-logstash-prod`,
  région `osc-secnum-fr1`, buildpacks custom dans `pass-emploi-tools` (répertoires `logstash/` et `elastic-agent/`).
- Chaque app source a **son propre drain** (indépendant) vers l'app logstash ; le
  **router Scalingo** répartit sur les instances logstash.
- **Architecture 2 pipelines** (depuis 2026-07) : pipeline `ingest` (ACK rapide,
  zéro filtre) + pipeline `process` (filtres + ES). Voir section dédiée ci-dessous.

## Les 2 modes de panne — signatures

| | **Mode A — blackout TOTAL** | **Mode B — trou d'UNE app** |
|---|---|---|
| Portée | toutes les apps ensemble | une seule (la plus grosse : api) |
| Cause | contre-pression **output ES** | **quarantaine du drain Scalingo** |
| Où | dans Logstash (output bloqué) | **en amont** de Logstash (drain) |
| Signature | **0 % CPU sur TOUS les conteneurs**, mémoire plate, 429 sur toutes les apps | une app à **0 pendant ~5 min pile**, autres continues, bouffée de **499** avant |
| Fix | **persistent queue** + scaling | découpler recevoir/traiter (cf. x10) ; atténué par + d'instances |

## Garde-fous durables (ne pas se faire avoir)

1. **Conteneur XL Scalingo = 2 Go** (pas 4). Donc **`-Xmx` ≤ ~1-1,2 Go** : Logstash
   consomme ~0,8-1 Go **hors heap** (Netty/direct memory, JRuby, metaspace, threads)
   + l'OS. **`-Xmx2g` sur XL 2 Go = 100 % du conteneur → OOM-kill → restart →
   blackout.**
2. **Heap piloté UNIQUEMENT par la var d'env Scalingo `JAVA_OPTS`**, jamais
   `LS_JAVA_OPTS`. Le wrapper du buildpack (`bin/logstash`) fait :
   ```
   if JAVA_OPTS contient "-Xms" : LS_JAVA_OPTS="$JAVA_OPTS"        (pas de -Xms128m)
   sinon                        : LS_JAVA_OPTS="-Xms128m $JAVA_OPTS"
   puis: unset JAVA_OPTS
   ```
   → une var `LS_JAVA_OPTS` posée en env est **toujours écrasée** ; le `-Xms` de
   `jvm.options` est **inerte** (le buildpack force `-Xms128m` sauf si `JAVA_OPTS`
   contient `-Xms`). Heap fixe → `JAVA_OPTS="-Xms1g -Xmx1g"`.
3. **Quarantaine du drain Scalingo** = **10 lignes consécutives** refusées → drain
   quarantiné **5 min** (aucun log envoyé), escalade **10/15/20 min**. Frappe la
   **plus grosse** app en premier (api ≈ 59 % du volume, ~5-6× web/connect) : elle
   atteint 10 refus consécutifs le plus vite. Un hoquet Logstash d'1 s = blackout de
   5 min pour api. *(Amplification énorme — c'est le mode B.)*
4. **Persistent queue** (`queue.type: persisted`) = buffer **disque** (pas RAM),
   sous `/app` (writable, éphémère). `queue.max_bytes` = plafond avant contre-pression
   (~64 Mo au repos). C'est le **filet du mode A**. ⚠️ Éphémère : survit aux blips ES,
   pas à un restart ; le fsync peut rallonger l'ACK → à surveiller vs les 499.
5. **`scalingo run` = one-off isolé** : ne voit **pas** le `localhost:9600` de l'app
   web (réseau séparé), voit une autre RAM. Non représentatif pour mesurer heap/API.

## Playbook de diagnostic {#playbook-de-diagnostic}

1. **Travailler sur la donnée du MOMENT T du trou**, pas une fenêtre saine (source
   n°1 de temps perdu dans cet incident).
2. **Router logs = l'arme principale** : le path contient `appname=<source>`.
   Ventiler par app :
   - `grep -oE 'appname=[a-z0-9-]+' F | sort | uniq -c` → volume par app.
   - idem filtré `status=429` / `status=499` → qui est puni.
   - **200/min par app** autour du trou → **quelle app tombe à 0** (une seule = mode B).
   - trous de secondes sans requête → durée réelle du blackout.
3. **GC vs ES** (pics de response time) : activer `JAVA_OPTS="-Xms1g -Xmx1g
   -Xlog:gc,safepoint:stderr:utctime,level,tags"`, lire les logs **de l'app logstash** :
   pic **avec** `Pause … ms` = GC ; pic **sans** = ES (corréler au monitoring Elastic
   Cloud). **Retirer après** (verbeux).
4. **Codes** : **429** = input plein (backpressure) ; **499** = le drain a coupé
   (Logstash trop lent à répondre) ; **0 requête** d'une app = son drain en quarantaine.

## Fausses pistes (écartées — ne pas y retourner sans raison nouvelle)

GC actuel (0 % CPU pendant les trous), OOM (mémoire plate ~1,3 Go), coût de
traitement d'api (durées égales aux autres apps), saturation de volume (le trou api
arrive à bas régime), fsync PQ (pics présents avec ET sans PQ).

## Direction pour tenir à x10 (le vrai chantier)

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

Détail et justification : [postmortem-2026-07.md § 7](./postmortem-2026-07.md#7-next-steps--tenir-à-x10).

## Architecture 2 pipelines (option A — implémentée 2026-07)

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

## État déployé — VOLATILE, vérifier avant d'agir

> ⚠️ Cette section date (≠ invariant). Vérifier l'état réel sur Scalingo avant toute
> action. Au **2026-07-02** :

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
- **Logstash 9.4.5** — buildpack custom dans `pass-emploi-tools/logstash/`.
- **Elastic Agent 9.4.5** — buildpack custom dans `pass-emploi-tools/elastic-agent/`, installé en mode colocalisé pour le monitoring Logstash via Fleet.
- **Heartbeat** — buildpack `SocialGouv/heartbeat-buildpack` (défaut 7.16.1, surchargeable via `HEARTBEAT_VERSION` sur Scalingo). ⚠️ Version à vérifier sur Scalingo.
- **APM** — géré via Fleet/Elastic Cloud, version pilotée par le plan Elastic Cloud (9.1.5).
  ⚠️ **Alignement des versions** : Elastic Cloud est en **9.1.5**, Logstash et Elastic Agent en **9.4.5** —
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
   il faut configurer Fleet. Voir le guide complet : [`elastic-agent/README.md`](../../elastic-agent/README.md).
