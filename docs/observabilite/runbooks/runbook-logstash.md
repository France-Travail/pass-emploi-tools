# Runbook d'astreinte — supervision Logstash

> **Type** : tutoriel (Diataxis). Procédures pas-à-pas pour diagnostiquer et
> résoudre les 5 scénarios de panne de la chaîne d'ingestion Logstash.
>
> Contexte et invariants durables : [collecte/logs](../collecte/logs/README.md),
> [process/logs](../process/logs/README.md), [infrastructure.md](../infrastructure.md).
> Définitions des alertes de la stack d'observabilité : [`supervision/alertes-stack-observabilite.md`](../supervision/alertes-stack-observabilite.md).
> Rétention par télémétrie (logs/traces/métriques) : [`stockage/`](../stockage/README.md).
> Dashboards Fleet Logstash :
> https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/integrations/detail/logstash-2.11.3/assets

## Playbook de diagnostic de l'ingestion

Méthode générale, avant de choisir un scénario ci-dessous. Signatures des modes
de panne A/B : [collecte/logs](../collecte/logs/README.md#les-2-modes-de-panne--signatures).

1. **Travailler sur la donnée du MOMENT T du trou**, pas une fenêtre saine (source
   n°1 de temps perdu lors de l'incident de juillet 2026).
2. **Router logs = l'arme principale** : le path contient `appname=<source>`.
   Ventiler par app :
   - `grep -oE 'appname=[a-z0-9-]+' F | sort | uniq -c` → volume par app.
   - idem filtré `status=429` / `status=499` → qui est puni.
   - **200/min par app** autour du trou → **quelle app tombe à 0** (une seule = mode B).
   - trous de secondes sans requête → durée réelle du blackout.
3. **GC vs ES** (pics de response time) : activer le log GC
   (`-Xlog:gc,safepoint:stderr:utctime,level,tags` dans les options JVM, cf.
   [infrastructure § garde-fous](../infrastructure.md#garde-fous-jvm--scalingo)),
   lire les logs **de l'app logstash** : pic **avec** `Pause … ms` = GC ; pic
   **sans** = ES (corréler au monitoring Elastic Cloud). **Retirer après** (verbeux).
4. **Codes** : **429** = input plein (backpressure) ; **499** = le drain a coupé
   (Logstash trop lent à répondre) ; **0 requête** d'une app = son drain en quarantaine.

**Fausses pistes écartées** (ne pas y retourner sans raison nouvelle) : GC
(0 % CPU pendant les trous), OOM (mémoire plate ~1,3 Go), coût de traitement
d'api (durées égales aux autres apps), saturation de volume (le trou api arrive
à bas régime), fsync PQ (pics présents avec ET sans PQ).

---

## Vue d'ensemble — les 5 scénarios

| #                                                     | Scénario                   | Signal d'entrée                                  | Urgence     |
| ----------------------------------------------------- | -------------------------- | ------------------------------------------------ |-------------|
| [1](#scénario-1--backpressure-elasticsearch)          | Backpressure Elasticsearch | `queue_backpressure > 0.5` + erreurs bulk ES     | ⚠️Warning  |
| [2](#scénario-2--gel-gc-jvm)                          | Gel GC JVM                 | Heap bloqué ≥ 90 % + `events.out` tombe à 0      | ⚠️Warning  |
| [3](#scénario-3--rejet-de-mapping--dead-letter-queue) | Rejet de mapping / DLQ     | DLQ non vide + events dans `logs-logstash-dlq-*` | ⚠️Warning  |
| [4](#scénario-4--crash-du-conteneur-logstash)         | Crash du conteneur         | Alerte restart Scalingo + silence logs           | 🚨 Critical |
| [5](#scénario-5--backlog-redis-logstashingest)        | Backlog Redis              | `redis.key.length` reste > 1 000 sur 15 min, sur `logstash:ingest` | 🚨 Critical |

**Règle d'or du diagnostic** : toujours travailler sur la **donnée du moment T du
trou**, pas sur une fenêtre saine. C'est la source n°1 de temps perdu.

---

## Scénario 1 — Backpressure Elasticsearch

### Indicateurs Kibana

| Métrique                                                                          | Data stream                         | Dashboard Fleet                                     | Signal d'alarme                               |
| --------------------------------------------------------------------------------- |-------------------------------------|-----------------------------------------------------|-----------------------------------------------|
| `logstash.pipeline.total.flow.queue_backpressure.current`                         | `metrics-logstash.pipeline-default` | [Metrics Logstash] Logstash Single Pipeline View (*Time spent pushing to queues*) | `ingest` ≥ 1 en continu sur 15 min → **Alerte Kibana 4a** |
| `logstash.pipeline.total.queues.events`                                           | `metrics-logstash.pipeline-default` | [Metrics Logstash] Pipelines Overview               | Montée continue (diagnostic post-alerte)      |
| `logstash.node.stats.pipelines.process.plugins.outputs.bulk_requests.with_errors` | `metrics-logstash.plugins-default`  | [Metrics Logstash] Elasticsearch output plugin info | Compteur qui monte (confirme rejet ES)        |
| `logstash.node.stats.events.out`                                                  | `metrics-logstash.node-default`     | [Metrics Logstash] Logstash Overview                | Chute ou plateau à 0                          |
| CPU Logstash (Scalingo)                                                           | Dashboard Scalingo                  | Dashboard Scalingo                                  | **0 % sur tous les conteneurs simultanément** |

**Signature caractéristique** : 0 % CPU sur **tous** les conteneurs Logstash en même
temps, mémoire plate. Les workers sont bloqués en attente d'ES (I/O bloquant = pas de
CPU). Des 429 apparaissent sur **toutes** les apps proportionnellement à leur volume.

### KQL de diagnostic

Dans Discover, data view `metrics-logstash*` — confirmer la backpressure :
```
logstash.pipeline.total.flow.queue_backpressure.current > 0
```

Dans Discover, data view `metrics-logstash*` — mesurer l'accumulation dans la queue :
```
logstash.pipeline.total.queues.events > 0
```

Dans Discover, data view `logs-router-*` (pour confirmer les 429 sur toutes les apps) :
```
http.response.status_code: 429
```
Grouper par `service.name` → si les 429 sont répartis sur toutes les apps, c'est le
mode A (backpressure ES). Si concentrés sur une seule app → voir scénario 4.

### Cause racine connue — management queue ES saturée

La backpressure observée en juillet 2026 avait pour cause racine une **saturation de la
management queue Elasticsearch** (file interne qui orchestre les opérations ILM, merges,
rollovers). Quand cette queue est pleine, ES ralentit l'indexation → les workers
`process` de Logstash se bloquent sur les bulk requests → le bus pipeline-to-pipeline
(entre `ingest` et `process`) se remplit → les workers `ingest` se bloquent → l'input
HTTP ralentit → les drains reçoivent des 429 → quarantaine.

> **Important** : la Persistent Queue de `ingest` n'était **pas** pleine (41 MB / 512 MB)
> lors de l'incident. La PQ protège contre les redémarrages, mais pas contre la
> contre-pression en temps réel du bus pipeline-to-pipeline (qui est une
> `LinkedBlockingQueue` en mémoire, séparée de la PQ disque). La PQ non pleine ne
> signifie donc **pas** l'absence de backpressure.

### Actions correctives

1. **Vérifier l'état du cluster ES via AutoOps** :
   Kibana → [AutoOps](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/management/data/auto_ops)
   → onglet **Indexing** → regarder :
   - **Indexing rate** : une chute soudaine (ex. de 5 000 docs/s à ~0) confirme le
     ralentissement ES.
   - **Management queue size** : si elle monte, ES est occupé à traiter des opérations
     internes (merges, rollovers ILM) et ne peut plus indexer normalement.
   - **Recommandations AutoOps** : "Template Optimization", "Empty Indices" — ces
     signaux indiquent un cluster surchargé par trop de shards.

2. **Vérifier la Persistent Queue** : `logstash.pipeline.total.queues.events` dans
   Pipelines Overview. La PQ peut être faible même en cas de backpressure sévère
   (voir note ci-dessus). Se concentrer sur `queue_backpressure.current` plutôt que
   sur la profondeur de la PQ.

3. **Si la management queue ES est saturée** (cause racine) :
   - **Court terme** : vérifier la policy ILM de `logs-prod-default` dans
     Kibana → Stack Management → Index Lifecycle Policies. Si le seuil de rollover
     est ≥ 45 GB, le réduire à **20 GB** pour éviter les gros merges :
     ```
     # Dans la policy ILM → Phase Hot → Rollover
     max_primary_shard_size: 20gb
     ```
     Appliquer la même correction à `logs-router-prod-default`.
   - **Moyen terme** : supprimer les indices vides (signalés par AutoOps "Empty Indices")
     pour réduire le nombre de shards. Chaque index supprimé = 2 shards en moins
     (1 primary + 1 replica). En Dev Tools :
     ```
     # Lister les indices vides sur les data streams gérés par Logstash
     GET _cat/indices/logs-*?v&h=index,docs.count,store.size&s=docs.count:asc
     # Supprimer uniquement les indices à docs.count=0 sur nos data streams
     # ⚠️ Ne jamais toucher aux indices .ds-* système (APM, Fleet, Kibana)
     DELETE logs-perf-default-YYYY.MM.DD-000XXX
     ```

4. **Si ES est sain** mais Logstash bloque : vérifier les logs Logstash sur Scalingo
   (onglet Logs de l'app) pour des `ConnectTimeout` ou `BulkIndexError`.

5. **Si la backpressure persiste malgré ES sain** : scaler le plan Elastic Cloud ou
   réduire temporairement la taille des batches via la variable d'environnement
   Scalingo `LOGSTASH_PROCESS_BATCH_SIZE` (défaut : 250). Réduire à 50 diminue la
   pression sur les bulk requests ES au prix d'un débit légèrement inférieur.
   Remettre à 250 une fois ES stabilisé.

### Références

- [collecte/logs — Mode A](../collecte/logs/README.md#les-2-modes-de-panne--signatures)
- [postmortem-2026-07-blackout-logs.md — §2](../post-mortems/postmortem-2026-07-blackout-logs.md)

---

## Scénario 2 — Gel GC JVM

### Indicateurs Kibana

| Métrique                                                                | Data stream                     | Dashboard Fleet                              | Signal d'alarme               |
| ----------------------------------------------------------------------- | ------------------------------- | -------------------------------------------- | ----------------------------- |
| `logstash.node.stats.jvm.mem.heap_used_percent`                         | `metrics-logstash.node-default` | [Metrics Logstash] Single Node Overview      | reste ≥ 90 % sur 15 min → **Alerte Kibana 5a** |
| `logstash.node.stats.events.out`                                        | `metrics-logstash.node-default` | [Metrics Logstash] Logstash Overview         | Tombe à 0 pendant la pause GC |

**Signature caractéristique** : pic de latence **bimodal** (temps de réponse normal
puis pic soudain), CPU **élevé** pendant le pic (≠ scénario 1 où CPU = 0),
`events.out` tombe à 0 le temps de la pause stop-the-world.

### KQL de diagnostic

Dans Discover, data view `metrics-logstash*` :
```
logstash.node.stats.jvm.mem.heap_used_percent >= 90
```

Les temps de GC ne sont pas collectés : les champs
`logstash.node.stats.jvm.gc.collectors.*` existent dans le mapping mais restent vides.

Pour corréler avec les logs GC (si `-Xlog:gc,safepoint` est activé dans `LS_JAVA_OPTS`) :
dans les logs Scalingo de l'app `pass-emploi-logstash-prod`, chercher les lignes
`Pause` avec une durée en ms.

### Actions correctives

1. **Vérifier le heap utilisé** : dashboard [Metrics Logstash] Single Node Overview →
   graphe *JVM Heap*. En régime normal, il oscille entre ~80 % après GC et ~93 %
   avant GC. S'il ne redescend plus sous 90 %, le GC ne libère plus rien.
2. **Vérifier `LS_JAVA_OPTS`** sur Scalingo : doit contenir `-Xms256m -Xmx256m`.
   ⚠️ Ne pas augmenter le heap : avec 256 Mo, la mémoire totale du conteneur
   plafonne déjà à ~1,7 Go sur les 2 Go d'un XL, le reste étant consommé par
   Netty/direct memory, JRuby, metaspace, threads, l'Elastic Agent et l'OS.
   Sur Scalingo, les conteneurs tournent sans swap : au-delà de la limite du
   conteneur, le kernel envoie un SIGKILL immédiat sans avertissement.
3. **Si le heap est correctement dimensionné** mais les GC sont fréquents : le
   volume d'ingestion dépasse la capacité de traitement. Scaler horizontalement
   (ajouter des instances Logstash sur Scalingo).
4. **Pour diagnostiquer en live** : activer temporairement les logs GC via
   `LS_JAVA_OPTS="-Xms256m -Xmx256m -Xlog:gc,safepoint:stderr:utctime,level,tags"` sur
   Scalingo. **Retirer après le diagnostic** (verbeux : pollue le drain + stockage ES).

### Références

- [infrastructure.md — Garde-fous JVM](../infrastructure.md#garde-fous-jvm--scalingo)
- [postmortem-2026-06-logstash-5xx.md](../post-mortems/postmortem-2026-06-logstash-5xx.md)

---

## Scénario 3 — Rejet de mapping / Dead Letter Queue

### Indicateurs Kibana

| Signal                                             | Source                      | Seuil d'alarme        |
| -------------------------------------------------- | --------------------------- | --------------------- |
| Documents dans `logs-logstash-dlq-prod-default`    | Discover / Alerte Kibana 1a | `count > 0` sur 5 min |
| Documents dans `logs-logstash-errors-prod-default` | Discover / Alerte Kibana 2a | `count > 0` sur 5 min |

> **Note** : la métrique `dead_letter_queue.queue_size_in_bytes` n'est **pas** exposée
> dans les data streams `metrics-logstash.*` d'Elastic Agent. La détection se fait
> uniquement via la présence de documents dans `logs-logstash-dlq-*`.

**Deux types d'erreurs distincts** :

- **DLQ** (`logs-logstash-dlq-*`) : events rejetés par Elasticsearch (conflit de
  mapping, document malformé). Gérés par le pipeline `dead_letter_queue` qui les
  indexe dans `logs-logstash-dlq-{env}-default`.
- **Erreurs de traitement** (`logs-logstash-errors-*`) : events ayant déclenché une
  erreur Logstash pendant les filtres (`_mutate_error`, `_jsonparsefailure`,
  `_rubyexception`…). Indexés dans `logs-logstash-errors-{env}-default` par le
  pipeline `process`.

### KQL de diagnostic

**Investiguer les events DLQ** (data view `logs-logstash-dlq-*`) :
```
service.environment: "prod"
```
Champs clés : `logstash.dlq.reason` (cause du rejet ES), `logstash.dlq.plugin_id`,
`event.original` (payload complet de l'event fautif en JSON stringifié).

**Investiguer les erreurs de traitement** (data view `logs-logstash-errors-*`) :
```
service.environment: "prod"
```
Champs clés : `tags` (type d'erreur Logstash), `message` (log brut fautif).

**Vérifier les `_ignored` dans ES** (Dev Tools) :
```
GET logs-prod-default/_search
{
  "query": { "exists": { "field": "_ignored" } },
  "size": 5
}
```
Des `_ignored` indiquent un dépassement de `total_fields.limit` → prévoir un
`POST logs-prod-default/_rollover`.

### Actions correctives

**Si DLQ non vide (conflit de mapping)** :
1. Identifier le champ fautif via `logstash.dlq.reason` dans `logs-logstash-dlq-*`.
2. Corriger le mapping dans `docs/observabilite/stockage/logs/2-component-templates.console`
   (ajouter le champ dans `logs@custom` ou le template concerné).
3. Appliquer via Kibana Dev Tools et faire un rollover :
   ```
   POST logs-prod-default/_rollover
   ```
4. Les events en DLQ peuvent être **rejoués** : le pipeline `dead_letter_queue`
   les a déjà indexés dans `logs-logstash-dlq-*` pour investigation. Un rejeu
   manuel nécessite de corriger le mapping d'abord.

**Si erreurs de traitement (`_mutate_error`, `_jsonparsefailure`)** :
1. Identifier le log fautif via le champ `message` dans `logs-logstash-errors-*`.
2. **`_jsonparsefailure` avec `message` d'exactement ~16384 octets et se
   terminant en plein milieu d'une valeur** → ligne applicative tronquée par le
   drain Scalingo, pas un bug de pipeline. Rien à corriger côté Logstash : la
   ligne source dépasse 16 Ko et doit être réduite côté app (cf.
   [format/logs/conventions](../format/logs/conventions.md) § « Ne jamais logger une exception
   brute »). Le `context` en tête du `message` tronqué désigne le handler fautif.
3. Sinon, reproduire localement avec le pipeline `process` pour identifier le
   filtre défaillant, corriger `logs/pipeline-process.conf` et déployer.

### Références

- [stockage/logs — Pièges connus](../stockage/logs/README.md#pièges-connus)
- [`logs/pipeline-dlq-logstash.conf`](../../../logs/pipeline-dlq-logstash.conf)
- [`logs/pipeline-process.conf`](../../../logs/pipeline-process.conf)

---

## Scénario 4 — Crash du conteneur Logstash

### Indicateurs Kibana / Scalingo

| Signal                                  | Source                | Description                                           |
|-----------------------------------------|-----------------------| ----------------------------------------------------- |
| Alerte webhook Scalingo                 | Scalingo → Mattermost | `app_crashed_repeated` avec `reason: OOM` ou `reason: SIGKILL` |
| Silence dans `logs-prod-default`        | Alerte Kibana 3a      | `Is below or equals 0` sur 5 min                      |
| Silence dans `logs-router-prod-default` | Alerte Kibana 3b      | `Is below or equals 0` sur 5 min                      |
| Absence de métriques Fleet              | Kibana Fleet → Agents | Agent Elastic Agent passe en `offline`                |

**Signature caractéristique** : les deux alertes 3a et 3b se déclenchent
**simultanément** (silence total = crash Logstash). Si seulement 3a se déclenche
(router continue), c'est une quarantaine du drain applicatif (voir ci-dessous).

### Distinguer crash vs quarantaine drain

| Situation               | Logs router | Logs applicatifs        | Diagnostic                          |
| ----------------------- | ----------- | ----------------------- | ----------------------------------- |
| Crash Logstash          | Silence     | Silence                 | Toute l'ingestion est arrêtée       |
| Quarantaine drain (api) | Continus    | Silence sur **une** app | Drain de l'app en quarantaine 5 min |

Pour confirmer une quarantaine drain, dans Discover data view `logs-router-*` :
```
http.response.status_code: (429 OR 499)
```
Grouper par `service.name` → si les 429/499 sont concentrés sur une seule app
juste avant le silence, c'est une quarantaine drain (scénario B du postmortem).

### KQL de diagnostic (après rétablissement)

Vérifier le trou dans les logs prod (data view `logs-prod-default`) :
```
service.environment: "prod"
```
Zoomer sur la fenêtre temporelle du silence → confirmer l'étendue de la perte.

Vérifier les logs router pour les 429/499 précédant le crash :
```
http.response.status_code: (429 OR 499) AND service.environment: "prod"
```

### Actions correctives

**Si crash OOM** :
1. Vérifier `LS_JAVA_OPTS` sur Scalingo : doit être `-Xms256m -Xmx256m`.
   ⚠️ Augmenter le heap sur XL (2 Go) mène à l'OOM-kill (voir scénario 2).
2. Vérifier la mémoire consommée dans les métriques Scalingo juste avant le crash.
3. Si le heap est correct mais l'OOM persiste : la mémoire hors-heap (Netty/direct
   memory) déborde. Réduire `LOGSTASH_INGEST_THREADS` (défaut : 4) ou scaler le
   plan Scalingo.

**Si crash sans OOM (SIGKILL, erreur JVM)** :
1. Consulter les logs Scalingo de l'app (`pass-emploi-logstash-prod` → onglet Logs)
   pour la stack trace.
2. Vérifier les logs Logstash dans ES (data view `logs-logstash-*`) si l'agent
   Elastic Agent a eu le temps de les envoyer avant le crash.

**Si quarantaine drain** :
1. La quarantaine dure 5 min (puis 10, 15, 20 min en escalade si les rejets
   continuent). Attendre le rétablissement automatique si Logstash est stable.
2. Si les rejets continuent après 5 min : Logstash est toujours en difficulté →
   traiter la cause racine (scénario 1 ou 2).
3. Pour lever manuellement une quarantaine : redémarrer le drain depuis le
   dashboard Scalingo de l'app source (ex: `pass-emploi-api-prod` → Log Drains →
   désactiver/réactiver le drain).

### Références

- [drain-scalingo.md — Quarantaine](../collecte/logs/drain-scalingo.md)
- [postmortem-2026-07-blackout-logs.md — §3 Mode B](../post-mortems/postmortem-2026-07-blackout-logs.md)
- [supervision/alertes-stack-observabilite.md — Alerte 6 (webhook Scalingo)](../supervision/alertes-stack-observabilite.md#alerte-6--restart-du-conteneur-logstash-scalingo-webhook)

---

## Scénario 5 — Backlog Redis `logstash:ingest`

**Contexte** : la chaîne d'ingestion est découpée en deux pipelines sur deux apps
Scalingo distinctes. Le pipeline `ingest` (app `pass-emploi-logstash-*`) reçoit les
logs des drains et les pousse dans la liste Redis `logstash:ingest`. Le pipeline
`process` (app `pass-emploi-logstash-process-*`) consomme cette liste et indexe dans
Elasticsearch. En régime normal, la liste est quasi vide (0–250 éléments) — Redis
est un **buffer de lissage**, pas un stockage durable. Le pipeline `process` consomme
en temps réel et supprime les éléments au fur et à mesure.

Un backlog signale que le pipeline `process` ne consomme plus Redis. Causes possibles :
- **Redémarrage ou blocage de `pass-emploi-logstash-process-prod`** : l'app tombe ou
  se bloque pour une raison inconnue (crash JVM, OOM, blocage réseau…). Le pipeline
  `ingest` continue à écrire dans Redis sans erreur — aucun 429 côté apps.
- **Coupure réseau Redis** : le pipeline `process` perd la connexion Redis
  (`Redis::ConnectionError` / `ECONNRESET`). La reconnexion est automatique.
- **Backpressure ES sévère côté process** : le pipeline `process` est bloqué sur ES
  et ne peut plus consommer Redis assez vite.

> **Incident de référence — 14/09/2026** : `pass-emploi-logstash-process-prod` a
> subi plusieurs redémarrages inexpliqués dans la soirée (parfois sans saturation
> mémoire visible). La liste `logstash:ingest` a grossi jusqu'à saturer les 256 Mo
> de Redis, provoquant le crash du cluster Redis à **20:37** (HAProxy : `No route to
> host`, backend `cluster` DOWN). **Cause racine inconnue** — les logs de l'app
> `pass-emploi-logstash-process-prod` sont archivés chez Scalingo et inaccessibles
> avant rotation. Le lendemain matin, l'app s'est rétablie et a vidé le backlog —
> aucun log perdu, mais indexation tardive (~13h de retard).

### Indicateurs

| Métrique            | Data stream                 | Dashboard                                                                        | Signal d'alarme                |
|---------------------|-----------------------------|----------------------------------------------------------------------------------|--------------------------------|
| `redis.key.length`  | `metrics-redis.key-default` | **[Metrics Redis] Keys** → graphe **Lists length** → clé `db0 › logstash:ingest` | reste > 1 000 sur 15 min → **Alerte Kibana 7a** (des pics à :00 et :30 en journée sont nominaux) |

### Diagnostic

1. **Ouvrir le dashboard `[Metrics Redis] Keys`** → graphe **Lists length** →
   confirmer la croissance de la clé `db0 › logstash:ingest`. Si la liste croît
   continûment sans jamais redescendre, le pipeline `process` ne consomme plus.

2. **Vérifier les logs de `pass-emploi-logstash-process-prod`** (ou `-perf` / `-staging`)
   sur Scalingo → onglet **Logs** → chercher :
   - `Redis::ConnectionError` ou `ECONNRESET` → **coupure réseau Redis** (voir ci-dessous)
   - Pas d'erreur Redis → **backpressure ES** (voir ci-dessous)

3. **Vérifier le statut Redis** dans le dashboard Scalingo de l'app
   `pass-emploi-logstash-process-prod` → onglet **Resources** → add-on Redis →
   statut `running` ou `degraded`.

### Deux signatures et actions correctives

**Signature A — Coupure réseau Redis** (`Redis::ConnectionError` / `ECONNRESET` dans les logs) :

1. Le pipeline `process` se reconnecte automatiquement à Redis dès que la
   connectivité est rétablie. **Aucune action manuelle n'est nécessaire** si la
   reconnexion est en cours.
2. Surveiller la décroissance du backlog dans `[Metrics Redis] Keys` → Lists length.
   La liste doit décroître régulièrement une fois la reconnexion établie.
3. **Après rétablissement complet** (liste revenue à ~0) : vérifier l'absence de
   trou dans les index. Les logs accumulés pendant la coupure réapparaissent dans
   Kibana avec leur **timestamp d'origine** (pas de perte, mais retard d'indexation).
   Dans Discover, data view `logs-prod-default`, zoomer sur la fenêtre de la coupure
   et vérifier la continuité des logs.
4. Si la reconnexion ne se fait pas après plusieurs minutes : redémarrer le conteneur
   `pass-emploi-logstash-process-prod` depuis le dashboard Scalingo.

**Signature B — Backpressure ES** (pas d'erreur Redis, `queue_backpressure > 0.5`) :

1. Ouvrir le dashboard `[Metrics Logstash] Logstash Single Pipeline View` sur le
   pipeline `process` → confirmer que *Time spent pushing to queues* monte.
2. Traiter la cause racine ES → voir **scénario 1**.

### Références

- [supervision/alertes-stack-observabilite.md — Alerte 7](../supervision/alertes-stack-observabilite.md#alerte-7--backlog-redis-logstashingest-pipeline-process-découplé)

---

## Annexe — Commandes de vérification rapide

### État de la chaîne d'ingestion (Dev Tools Kibana)

```
# Volume indexé dans les dernières 5 min (prod)
GET logs-prod-default/_count
{
  "query": {
    "range": { "@timestamp": { "gte": "now-5m" } }
  }
}

# Volume indexé dans les dernières 5 min (staging)
GET logs-staging-default/_count
{
  "query": {
    "range": { "@timestamp": { "gte": "now-5m" } }
  }
}

# Events en DLQ (prod)
GET logs-logstash-dlq-prod-default/_count

# Events en erreur de traitement (prod)
GET logs-logstash-errors-prod-default/_count

# Vérifier les _ignored (dépassement total_fields.limit)
GET logs-prod-default/_search
{
  "query": { "exists": { "field": "_ignored" } },
  "size": 3,
  "_source": ["@timestamp", "service.name", "_ignored"]
}
```

### Liens directs Kibana

| Ressource                                           | URL                                                                                                                            |
|-----------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| Fleet — Agents Logstash                             | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/fleet/agents                                                        |
| Dashboards intégration Logstash                     | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/integrations/detail/logstash-2.11.3/assets                          |
| Stack Management → Rules                            | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/management/insightsAndAlerting/triggersActions/rules                |
| [Metrics Logstash] Logstash Single Pipeline View    | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc      |
| [Metrics Logstash] Pipelines Overview               | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-c0594170-526a-11ee-9ecc-31444cb79548      |
| [Metrics Logstash] Input plugin Info                | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975      |
| [Metrics Logstash] Elasticsearch output plugin info | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086      |
| [Metrics Logstash] Logstash Overview                | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522      |
| [Metrics Logstash] Single Node Overview             | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9d450b10-4680-11ee-9ddc-919f87fe352d      |
| [Metrics Redis] Keys                                | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5         |
| [Elastic Agent] Overview                            | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824 |
| [Elastic Agent] Concerning Agents                   | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824 |

### Liens directs Scalingo

| App                                        | URL                                                                                       |
|--------------------------------------------|-------------------------------------------------------------------------------------------|
| `pass-emploi-logstash-prod` — métriques    | https://dashboard.scalingo.com/apps/osc-secnum-fr1/pass-emploi-logstash-prod/metrics      |
| `pass-emploi-logstash-perf` — métriques    | https://dashboard.scalingo.com/apps/osc-secnum-fr1/pass-emploi-logstash-perf/metrics      |
| `pass-emploi-logstash-process-prod` — logs | https://dashboard.scalingo.com/apps/osc-secnum-fr1/pass-emploi-logstash-process-prod/logs |
| `pass-emploi-logstash-process-perf` — logs | https://dashboard.scalingo.com/apps/osc-secnum-fr1/pass-emploi-logstash-process-perf/logs |

### Data views Kibana — Discover

| Data view                                                    | Index pattern                               | Usage                                           |
| ------------------------------------------------------------ |---------------------------------------------|-------------------------------------------------|
| `logs-prod-default`                                          | `logs-prod-default`                         | Logs applicatifs prod                           |
| `logs-staging-default` / `logs-perf-default`                 | `logs-staging-default`, `logs-perf-default` | Logs applicatifs hors-prod                      |
| Logs Logstash - Dead Letter Queue                            | `logs-logstash-dlq-*`                       | Events rejetés par ES (scénario 3)              |
| Logs Logstash - Index erreurs de traitement Pipeline process | `logs-logstash-errors-*`                    | Events en erreur de transformation (scénario 3) |
