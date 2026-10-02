# Pertinence de l'usage des Log Drains Scalingo pour la collecte de logs

* Statut: proposé
* Décideurs: équipe pass-emploi
* Date: 2026-09-23

## Contexte et Définition du Problème

En amont de tout chantier de code, l'équipe explore un mécanisme de collecte de logs
alternatif au couple **Logstash + Log Drains Scalingo**, pour éviter les instabilités
documentées dans [postmortem-2026-07-blackout-logs.md](../observabilite/post-mortems/postmortem-2026-07-blackout-logs.md)
(« Mode B » : quarantaine du drain déclenchée par `pass-emploi-api`).

Mécanisme observé (doc Scalingo, citée dans le post-mortem et reconfirmée par capture
d'écran de la doc à jour) :

> Si une cible de log drain échoue à accepter **10 lignes de logs consécutives**, elle
> est mise en **quarantaine 5 minutes** (aucun log envoyé). Si la cible échoue encore à
> la levée de la quarantaine, la durée augmente progressivement : **10, 15, 20 min…**

Ce mécanisme frappe préférentiellement `pass-emploi-api` (≈59 % du volume total,
5-6× web/connect) : le seuil est exprimé en échecs **consécutifs**, donc atteint
d'autant plus vite que le débit est élevé. Un hoquet Logstash d'~1 seconde suffit à
générer un blackout de 5 minutes sur cette app pendant que web/connect, moins
sollicitées, ne basculent jamais. Preuve empirique : le 2026-07-01, api est tombée à 0
requête/min pendant exactement ~5 minutes (17:37→17:41) pendant que web/connect
continuaient.

L'architecture 2 pipelines (`ingest`/`process`, cf.
[collecte/logs](../observabilite/collecte/logs/README.md)) et la migration
PQ→Redis ([ADR-002](./ADR-002-buffer-redis-logstash.md)) ont déjà réduit la
**fréquence** de déclenchement, en découplant l'ACK HTTP des filtres lourds. Elles ne
l'**éliminent** pas : la quarantaine est une propriété du **drain** (couche plateforme
Scalingo, comptage d'échecs + backoff punitif), pas du receveur Logstash. Le risque est
qualifié de **latent** dans le post-mortem et **s'aggrave mécaniquement** avec la
croissance du débit d'api (cf. [§7 — Next steps, tenir à x10](../observabilite/post-mortems/postmortem-2026-07-blackout-logs.md#7-next-steps--tenir-à-x10)).

**Question** : faut-il changer de mécanisme de collecte de logs (transport du drain,
envoi applicatif direct, broker en amont) pour éliminer structurellement ce risque, ou
rester sur le drain HTTPS actuel et composer avec le risque résiduel ?

## Facteurs de Décision

* **La documentation Scalingo ne distingue pas les types de drain face à la
  quarantaine** — l'encart quarantaine est positionné au niveau générique de la
  configuration des drains (juste après la liste des intégrations HTTPS/Syslog/SaaS),
  sans sous-section « HTTPS » vs « Syslog » séparée. Aucune preuve qu'un changement de
  transport élimine le mécanisme — voir [§ Suites à donner](#suites-à-donner).
* **Dimensionnement de l'équipe** — non calibrée pour opérer une infrastructure de logs
  plus grosse ou plus complexe que l'applicatif qu'elle supervise (contrainte exprimée
  explicitement en session de travail).
* **Préservation du socle légal d'archivage** — Logs Archives Scalingo (1 an,
  LCEN/CPCE/CNIL) est gratuit et automatique tant que les apps continuent d'écrire sur
  `stdout`. Toute option qui réduit ou remplace ce flux le met en péril silencieusement
  (cf. [§ Archivage long terme](#archivage-long-terme--deux-socles-indépendants)).
* **Ne pas déplacer un risque déjà documenté et non mitigé** — [ADR-002](./ADR-002-buffer-redis-logstash.md)
  documente déjà la saturation mémoire Redis (< 50 min) si `logstash-process`/ES
  décroche. Une option qui expose Redis davantage sans le mitiger aggrave un risque
  connu plutôt que de le traiter.
* **Un autoscaler horizontal n'est pas le bon outil pour les deux causes documentées de
  saturation du backlog Redis** — le
  [runbook scénario 5](../observabilite/runbooks/runbook-logstash.md#scénario-5--backlog-redis-logstashingest)
  distingue deux signatures bien différentes, à ne pas confondre :
  - **`process` vivant mais bloqué** (backpressure ES, scénario 1) : *0 % CPU sur tous
    les conteneurs, mémoire plate* — attente I/O bloquante, pas de calcul. Ajouter des
    instances ne débloquerait rien : le goulot est ES, **partagé** par toutes les
    instances.
  - **`process` mort** (crash/redémarrage, cause « inconnue » lors de l'incident de
    référence du 14/09/2026, *« parfois sans saturation mémoire visible »*) : 0 % CPU
    aussi, mais simplement parce qu'il n'y a **plus de process du tout** — un
    scale-out ne répare pas un crash, seul un restart le fait (déjà automatique côté
    Scalingo).

  Dans les deux cas, le levier pertinent est le **monitoring proactif**, pas
  l'autoscale : l'alerte 5a existante (heap JVM qui reste ≥ 90 % sur 15 min) couvre partiellement
  l'anticipation d'un OOM, mais **pas** la mémoire hors-heap (Netty/direct memory,
  JRuby, metaspace) qui peut provoquer un `SIGKILL` du kernel Scalingo sans que le heap
  JVM ne l'annonce (cf.
  [postmortem-2026-06](../observabilite/post-mortems/postmortem-2026-06-logstash-5xx.md)) —
  aucune alerte ne surveille aujourd'hui la RAM **totale** du conteneur
  `logstash-process`, ce qui est un gap distinct de la question de la quarantaine (cf.
  [§ Suites à donner](#suites-à-donner)).
* **Effort déjà investi et rendement démontré** — l'architecture 2 pipelines (2026-07) a
  déjà supprimé la cause structurelle principale (filtres lourds sur le chemin d'ACK) et
  réduit la fréquence des hoquets qui déclenchent la quarantaine.
* **Détection déjà en place** — les alertes Kibana 3a/3b (silence logs applicatifs/
  router, fenêtre 2 min, cf. [`supervision/alertes-stack-observabilite.md`](../observabilite/supervision/alertes-stack-observabilite.md))
  donnent une détection rapide d'un Mode B résiduel, indépendamment de toute nouvelle
  architecture.

## Solutions Étudiées

* Option 0 — Statu quo : drain HTTPS Scalingo + architecture 2 pipelines (`ingest`/`process`) + Redis
* Option 1 — Remplacement du drain HTTPS par un drain Syslog TCP+TLS
* Option 2 — Envoi applicatif direct (shipper in-app dans api/web/connect, pattern APM étendu aux logs)
* Option 3 — Broker (Kafka/Redis) alimenté directement par les apps, en amont de tout Logstash
* Option 4 — Canal de compensation pour signaux critiques uniquement (extension du
  pattern `apmService.captureError`, déjà hors Logstash)

## Résultat de la Décision

Solution retenue : **Option 0 (statu quo)** — conserver le drain HTTPS Scalingo actuel
et l'architecture 2 pipelines (`ingest`/`process` + Redis), sans changement de
transport ni nouveau composant d'infrastructure ; combler le risque résiduel par de la
**détection** (alertes déjà en place) plutôt que par une élimination structurelle
coûteuse. C'est la seule option qui :

1. ne demande **aucune nouvelle surface d'infrastructure** à opérer, cohérente avec le
   dimensionnement actuel de l'équipe ;
2. préserve **gratuitement et sans risque de régression silencieuse** le socle légal
   d'archivage 1 an (Logs Archives Scalingo, lié à `stdout`, indépendant du drain) ;
3. n'ajoute **aucun risque nouveau** documenté et non mitigé — contrairement à l'Option
   3, qui expose davantage un buffer Redis déjà identifié comme fragile par ADR-002.

L'Option 1 (syslog), qui semblait la piste à faible effort la plus prometteuse en début
d'exploration, perd son principal argument : rien dans la documentation Scalingo ne
montre d'exception de transport pour la quarantaine, et son intégration a un coût non
nul (plugin `logstash-input-syslog` absent de [`pipeline-ingest.conf`](../../logs/pipeline-ingest.conf)
aujourd'hui, [simulation Gatling](../../perf/src/gatling/scala/passemploi/test/LogstashIngestSimulation.scala)
à réécrire) pour un gain non démontré.

### Tableau comparatif

| Critère                        | 0 — Statu quo | 1 — Syslog drain | 2 — Shipper direct   | 3 — Broker direct    | 4 — Compensation APM |
|--------------------------------|---------------|------------------|----------------------|----------------------|----------------------|
| Élimine la quarantaine ?       | ❌            | ❌ probable      | ✅                   | ✅ drain / ❌ buffer | ❌                   |
| Nouveau composant à opérer     | ❌            | ⚠️ plugin syslog | ✅ shipper (3 repos) | ✅ consumer + broker | ❌                   |
| Risque documenté non mitigé    | Mode B latent | idem Option 0    | pattern APM *lossy*  | Redis OOM (ADR-002)  | —                    |
| Socle 1 — Logs Archives (1 an) | ✅            | ✅               | ⚠️ conditionnel      | ⚠️ conditionnel      | N/A                  |
| Socle 2 — ES indexé (180 j)    | ⚠️ gap ouvert | ⚠️ idem Option 0 | ✅ sous condition    | ✅ sous condition    | N/A                  |
| Effort                         | Nul           | Faible à moyen   | Élevé                | Élevé                | Nul                  |

Détail de chaque critère : [§ Avantages et Inconvénients des Solutions](#avantages-et-inconvénients-des-solutions)
pour la quarantaine et les risques, [§ Archivage long terme](#archivage-long-terme--deux-socles-indépendants)
pour les deux socles.

## Archivage long terme — deux socles indépendants

Point central de l'arbitrage : il existe **deux socles d'archivage distincts et
indépendants**, dont la confusion fausse l'évaluation des options. Les confondre a été
une erreur de la première version de cette analyse — ils sont donc tracés séparément.

```
                    ┌──► Log Drain ──► Logstash ──► Redis ──► Logstash ──► ES (recherche, 180j — Socle 2)
app (stdout) ──────►│
                    └──► Logs Archives Scalingo (brut, non indexé, 1 an — Socle 1) ← AUTOMATIQUE, ZÉRO CONFIG
```

### Socle 1 — Logs Archives Scalingo (brut, non indexé, 1 an, lié au `stdout`)

Source : [doc.scalingo.com/platform/app/logs](https://doc.scalingo.com/platform/app/logs).
Ce mécanisme capture le `stdout`/`stderr` **au niveau du conteneur Scalingo
lui-même** — c'est une fonctionnalité de plateforme totalement **indépendante du Log
Drain**. Au-delà de 50 Mio par conteneur, les logs basculent automatiquement en
« cold logs », téléchargeables via `scalingo logs-archives` ou le dashboard (non
cherchables, non indexés). Rétention légale : **1 an**, imposée par la LCEN
(art. 6-8.II), le CPCE (art. R10-13.III) et la recommandation CNIL 2021 sur la
journalisation.

| Option                   | Statut                |
|--------------------------|-----------------------|
| **0 — Statu quo**        | ✅ Acquis, effort nul |
| **1 — Syslog drain**     | ✅ Acquis, effort nul |
| **2 — Shipper direct**   | ⚠️ Conditionnel       |
| **3 — Broker direct**    | ⚠️ Conditionnel       |
| **4 — Compensation APM** | N/A                   |

**Détail par option :**

* **0 — Statu quo / 1 — Syslog drain** : le drain lit `stdout` **en parallèle** de Logs
  Archives, il ne le remplace pas — changer le *transport* du drain ne touche pas à
  l'écriture `stdout` elle-même. Le socle légal continue de fonctionner **même pendant
  une quarantaine du drain** : les deux mécanismes sont indépendants. Rien à
  construire : c'est déjà la situation actuelle, simplement non documentée dans nos
  docs internes (depuis documenté dans [`stockage/logs`](../observabilite/stockage/logs/README.md#archivage-hors-es--logs-archives-scalingo)).
* **2 — Shipper direct / 3 — Broker direct** : décision de design à figer
  explicitement. Si le code applicatif continue d'écrire sur `stdout` **en plus** du
  nouveau canal (double-écrit), le socle légal survit gratuitement. S'il est
  réduit/supprimé pour éviter la duplication de volume (tentation naturelle vis-à-vis
  du plafond Scalingo de 16 384 lignes/min/conteneur — cf.
  [§ Suites à donner](#suites-à-donner)), **le socle légal disparaît silencieusement,
  sans garde-fou technique qui alerte dessus**. Complexité : figer et documenter ce
  choix ; assumer un double coût d'écriture si on le préserve.
* **4 — Compensation APM** : rétentions APM (traces 30j, errors 90j —
  [`stockage/traces`](../observabilite/stockage/traces/README.md)) sans rapport avec ce socle — n'en tient pas lieu.

### Socle 2 — Elasticsearch ILM (indexé, cherchable, 180 jours prod)

Source : [`stockage/logs/1-ilm-policies.console`](../observabilite/stockage/logs/1-ilm-policies.console)
et [`stockage/logs/README.md`](../observabilite/stockage/logs/README.md). La policy
`logs-prod-retention` a bien `delete.min_age: 180d` configuré, mais **sans phase
cold/frozen** : *« la phase cold/frozen de l'archive 30→180 j reste à ajouter quand le
tier froid existera (devis) [...] l'appliquer fait croître le flux vers ~1,8 To sur
plusieurs mois »*.

| Option                   | Statut                    |
|--------------------------|---------------------------|
| **0 — Statu quo**        | ⚠️ Gap déjà ouvert        |
| **1 — Syslog drain**     | ⚠️ Identique à l'Option 0 |
| **2 — Shipper direct**   | ✅ Sous condition         |
| **3 — Broker direct**    | ✅ Sous condition         |
| **4 — Compensation APM** | N/A                       |

**Détail par option :**

* **0 — Statu quo / 1 — Syslog drain** : le gap cold/frozen existe déjà,
  **indépendamment de cette décision** — c'est un chantier séparé (devis tier froid), à
  ne pas mélanger avec la question de la quarantaine. Le pipeline `process`/ES en aval
  ne change pas avec l'Option 1 → gap inchangé ; complexité additionnelle *non liée à
  l'archivage* : plugin syslog à intégrer + tests Gatling à réécrire.
* **2 — Shipper direct** : atteignable à condition que le nouveau canal alimente in
  fine le même pipeline `process` (mêmes templates/ILM). Complexité :
  `pipeline-process.conf` dépend aujourd'hui du format posé par le drain Scalingo
  (`?appname=...&hostname=...` en query string, extrait via le filtre `kv`) — un
  shipper applicatif n'aura pas ce format, il faut retoucher le parsing d'entrée.
* **3 — Broker direct** : même retouche de parsing que l'Option 2, **plus** un risque
  propre — si le broker sature (ADR-002, ~50 min), l'alimentation de ce socle est
  retardée pendant la résorption. Pas une perte si le broker ne droppe pas, mais un
  délai qui peut dépasser la fenêtre utile d'investigation d'un incident.
* **4 — Compensation APM** : ne s'y substitue pas — rétentions (30j/90j) bien
  inférieures au besoin d'audit 180j.

## Impacts Positifs

* Zéro nouvelle infrastructure à opérer — cohérent avec le dimensionnement actuel de
  l'équipe.
* Filet légal Logs Archives (1 an) déjà actif sans configuration — documenté dans
  [`stockage/logs`](../observabilite/stockage/logs/README.md#archivage-hors-es--logs-archives-scalingo).
* Permet de concentrer l'effort sur les leviers déjà identifiés et non réalisés :
  mesurer le plafond d'une instance Logstash (req/min avant 429/499), scaler ES,
  déporter du parsing vers les ingest pipelines ES (cf.
  [§7 — Next steps, tenir à x10](../observabilite/post-mortems/postmortem-2026-07-blackout-logs.md#7-next-steps--tenir-à-x10)
  du post-mortem 2026-07).
* Aucune régression sur le socle légal d'archivage (contrairement aux options 2/3, où
  ce socle devient conditionnel à un choix de design).

## Impacts Négatifs

* Le Mode B (quarantaine api) reste un risque **latent qui s'aggrave** avec la
  croissance du débit d'api — non résolu par cette décision, seulement atténué par
  l'architecture 2 pipelines déjà en place.
* Le gap d'archivage indexé 180 j (tier cold/frozen absent) reste ouvert — chantier
  séparé, non traité par cette décision.
* Le plafond d'ingestion Scalingo (16 384 lignes/min et 64 MiB/min par conteneur,
  au-delà duquel les lignes excédentaires sont silencieusement droppées) n'a pas été
  confronté au débit réel de `pass-emploi-api` — risque résiduel non chiffré, distinct
  de la quarantaine et non traité par cette décision.
* L'hypothèse « la quarantaine s'applique aussi au drain Syslog » n'est pas confirmée
  formellement par Scalingo (support ou doc explicite) — c'est une inférence à partir de
  l'absence d'exception documentée, pas une preuve positive. Si elle s'avérait fausse,
  l'Option 1 redeviendrait pertinente à réévaluer.

## Avantages et Inconvénients des Solutions

### Option 0 — Statu quo (drain HTTPS + 2 pipelines + Redis)

* Bien, car zéro nouvelle infrastructure à opérer.
* Bien, car préserve gratuitement le socle légal d'archivage (Logs Archives, 1 an).
* Bien, car l'architecture 2 pipelines a déjà démontré une réduction de la fréquence de
  déclenchement (2026-07).
* Bien, car détection déjà en place (alertes silence-logs 3a/3b).
* Mauvais, car le Mode B reste possible et son risque s'aggrave avec la croissance du
  débit d'api — pas une élimination, une atténuation.

### Option 1 — Drain Syslog TCP+TLS

* Bien, car le transport supporte TCP+TLS avec jeton d'authentification (paramètre
  `--token` documenté) — pas de régression de sécurité par rapport au HTTPS actuel.
* Bien, car ne touche pas à l'écriture `stdout` — Socle 1 (archivage légal) préservé
  sans effort.
* Mauvais, car la documentation Scalingo ne montre aucune exception de la quarantaine
  par type de transport — le gain principal escompté (élimination de la cause) n'est
  pas démontré.
* Mauvais, car nécessite d'intégrer un plugin d'input Logstash absent aujourd'hui
  (`pipeline-ingest.conf` n'a qu'un input `http`) et de réécrire la simulation de
  charge Gatling existante.
* Mauvais, car un investissement d'intégration pour un gain non confirmé est un mauvais
  rapport effort/risque.

### Option 2 — Envoi applicatif direct (shipper in-app)

* Bien, car élimine réellement la dépendance au drain Scalingo et à sa quarantaine.
* Bien, car un pattern de référence existe déjà dans le repo (agent APM, envoi direct à
  Elastic Cloud, hors Logstash) — point de départ de conception clarifié.
* Mauvais, car le pattern de référence (agent APM) est **best-effort/lossy** par
  construction (buffer mémoire non durable, pas de retry garanti) — le rendre fiable
  pour des logs à valeur d'audit légal est un travail de fond, pas une simple
  réutilisation.
* Mauvais, car à construire et maintenir dans **3 repos** (api, web, connect), avec
  obligation de ne jamais bloquer le thread de la requête HTTP.
* Mauvais, car met en péril silencieusement le socle légal d'archivage 1 an si le
  double-écrit `stdout` n'est pas explicitement conservé.
* Mauvais, car retouche nécessaire du parsing d'entrée du pipeline `process` (dépend
  aujourd'hui du format posé par le drain Scalingo).

### Option 3 — Broker (Kafka/Redis) alimenté directement par les apps

* Bien, car élimine la quarantaine côté drain — découplage total, apps → broker sans
  intermédiaire HTTP Scalingo.
* Bien, car l'infra Redis existe déjà (ADR-002) — pas de nouvelle brique de stockage à
  introduire.
* Mauvais, car **déplace** le risque plutôt que de l'éliminer : la saturation mémoire
  Redis (< 50 min sans consommation, cf. ADR-002) reste un mode de panne documenté et
  non mitigé, désormais alimenté par un point d'entrée supplémentaire.
* Mauvais, car le consumer (`logstash-process`) reste exposé aux deux causes
  documentées de non-consommation de Redis
  ([runbook scénario 5](../observabilite/runbooks/runbook-logstash.md#scénario-5--backlog-redis-logstashingest)) :
  process **vivant mais bloqué** sur un goulot ES partagé (un autoscaler horizontal ne
  débloquerait rien), ou process **mort** (crash/OOM — un scale-out ne répare pas un
  crash, seul un restart le fait). L'incident du 14/09/2026 montre que la cause d'un
  tel crash reste parfois **indéterminée** (« parfois sans saturation mémoire
  visible ») faute de monitoring adapté — la mémoire hors-heap (Netty/direct memory)
  n'est surveillée par aucune alerte actuelle, seul le heap JVM l'est (alerte 5a).
* Mauvais, car même logique de mise en péril du socle légal d'archivage que l'Option 2
  si le double-écrit `stdout` n'est pas explicitement tranché.

### Option 4 — Canal de compensation (extension du pattern APM)

* Bien, car réutilise un canal déjà en place et déjà indépendant du drain
  (`apmService.captureError`), donc coût quasi nul.
* Bien, car donne une visibilité en dégradé sur les signaux critiques (erreurs 5xx,
  échecs auth/partenaires) même pendant une quarantaine.
* Mauvais, car n'élimine ni n'atténue la cause — seulement l'impact sur un sous-ensemble
  de signaux.
* Mauvais, car les rétentions APM (traces 30j, errors 90j) sont bien inférieures aux
  besoins d'audit — ne peut pas servir de filet d'archivage de substitution.
* Mauvais, car ne couvre pas les logs applicatifs complets, seulement les erreurs
  capturées explicitement par l'agent APM.

## Suites à donner

* [ ] Confirmer/infirmer auprès du **support Scalingo** si la quarantaine s'applique
      identiquement au drain Syslog TCP+TLS (aucune exception trouvée dans la doc
      publique au 2026-09-23 ; si le comportement diffère, réévaluer l'Option 1).
* [ ] Ajouter une alerte sur la **RAM totale du conteneur** `pass-emploi-logstash-process-<env>`
      (métrique infra Scalingo, distincte du heap JVM déjà couvert par l'alerte 5a) —
      gap identifié en session : la mémoire hors-heap (Netty/direct memory, JRuby,
      metaspace) peut provoquer un `SIGKILL` du kernel Scalingo sans que le heap JVM ne
      l'annonce, ce qui a probablement contribué à l'incident du 14/09/2026 dont la
      cause racine du crash de `logstash-process` est restée indéterminée.
      Collecte préparée le 2026-10-02 (`logs-scalingo.container_stats-*`, API
      Scalingo `/stats`, cf. [`elastic-agent/README.md`](../../elastic-agent/README.md#mémoire-des-conteneurs-scalingo-intégration-custom-api)) ;
      reste l'alerte, à calibrer sur une semaine de données.
* [ ] Vérifier le plafond d'ingestion Scalingo (**16 384 lignes/min** et **64 MiB/min**
      par conteneur) face au débit réel mesuré de `pass-emploi-api` — risque de perte
      silencieuse (`overflow` puis drop) distinct de la quarantaine, non chiffré à date.
* [x] Documenter le socle **Logs Archives** (1 an, lié à `stdout`) — fait dans
      [`stockage/logs`](../observabilite/stockage/logs/README.md#archivage-hors-es--logs-archives-scalingo).
* [ ] Mesurer le **plafond d'une instance Logstash** (req/min avant 429/499) — next step
      déjà identifié dans le
      [post-mortem 2026-07, §7](../observabilite/post-mortems/postmortem-2026-07-blackout-logs.md#7-next-steps--tenir-à-x10),
      non réalisé à date.

## Liens

* [postmortem-2026-07-blackout-logs.md](../observabilite/post-mortems/postmortem-2026-07-blackout-logs.md) — description du Mode B (quarantaine drain), preuve empirique, voir aussi son [§7 — Next steps, tenir à x10](../observabilite/post-mortems/postmortem-2026-07-blackout-logs.md#7-next-steps--tenir-à-x10)
* [drain-scalingo.md](../observabilite/collecte/logs/drain-scalingo.md) — invariant quarantaine ; [infrastructure.md](../observabilite/infrastructure.md) — garde-fous JVM/Scalingo
* [runbook-logstash.md](../observabilite/runbooks/runbook-logstash.md) — signature de la backpressure ES (scénario 1)
* [ADR-002-buffer-redis-logstash.md](./ADR-002-buffer-redis-logstash.md) — risque de saturation mémoire Redis déjà documenté
* [stockage/logs/README.md](../observabilite/stockage/logs/README.md) — rétention ES 180j, gap cold/frozen
* [logs/pipeline-ingest.conf](../../logs/pipeline-ingest.conf) — pipeline d'ingestion actuel (input HTTP uniquement)
* [perf/.../LogstashIngestSimulation.scala](../../perf/src/gatling/scala/passemploi/test/LogstashIngestSimulation.scala) — simulation de charge du drain HTTP actuel
* [Doc Scalingo — Log Drains](https://doc.scalingo.com/platform/app/log-drain)
* [Doc Scalingo — Logs (rétention légale, Logs Archives, limites d'ingestion)](https://doc.scalingo.com/platform/app/logs)
* [Doc Scalingo — Autoscaler](https://doc.scalingo.com/platform/app/autoscaler)
