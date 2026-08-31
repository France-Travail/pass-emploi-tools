# Runbook d'astreinte — supervision Logstash

> **Type** : tutoriel (Diataxis). Procédures pas-à-pas pour diagnostiquer et
> résoudre les 4 scénarios de panne de la chaîne d'ingestion Logstash.
>
> Contexte et invariants durables : [../blackout-logs/conventions.md](../blackout-logs/conventions.md).
> Définitions des alertes Kibana : [`logs/elastic/4-kibana-alerts.md`](../../logs/elastic/4-kibana-alerts.md).
> Dashboards Fleet Logstash :
> https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/integrations/detail/logstash-2.11.3/assets

## Vue d'ensemble — les 4 scénarios

| #                                                     | Scénario                   | Signal d'entrée                                  | Urgence     |
| ----------------------------------------------------- | -------------------------- | ------------------------------------------------ |-------------|
| [1](#scénario-1--backpressure-elasticsearch)          | Backpressure Elasticsearch | `queue_backpressure > 0.5` + erreurs bulk ES     | ⚠️ Warning   |
| [2](#scénario-2--gel-gc-jvm)                          | Gel GC JVM                 | Pic soudain GC + `events.out` tombe à 0          | ⚠️ Warning   |
| [3](#scénario-3--rejet-de-mapping--dead-letter-queue) | Rejet de mapping / DLQ     | DLQ non vide + events dans `logs-logstash-dlq-*` | ⚠️ Warning   |
| [4](#scénario-4--crash-du-conteneur-logstash)         | Crash du conteneur         | Alerte restart Scalingo + silence logs           | 🚨 Critical |

**Règle d'or du diagnostic** : toujours travailler sur la **donnée du moment T du
trou**, pas sur une fenêtre saine. C'est la source n°1 de temps perdu.

---

## Scénario 1 — Backpressure Elasticsearch

### Indicateurs Kibana

| Métrique                                                                          | Data stream                         | Dashboard Fleet                                     | Signal d'alarme                               |
| --------------------------------------------------------------------------------- |-------------------------------------|-----------------------------------------------------|-----------------------------------------------|
| `logstash.pipeline.total.flow.queue_backpressure.current`                         | `metrics-logstash.pipeline-default` | [Metrics Logstash] Pipeline Health Report           | > 0.5 → **Alerte Kibana 4a** (anticipation)   |
| `logstash.pipeline.total.queues.events`                                           | `metrics-logstash.pipeline-default` | [Metrics Logstash] Pipeline Health Report           | Montée continue (diagnostic post-alerte)      |
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
   Pipeline Health Report. La PQ peut être faible même en cas de backpressure sévère
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

- [conventions.md — Mode A](../blackout-logs/conventions.md#les-2-modes-de-panne--signatures)
- [postmortem-2026-07.md — §2](../blackout-logs/postmortem-2026-07.md)

---

## Scénario 2 — Gel GC JVM

### Indicateurs Kibana

| Métrique                                                                | Data stream                     | Dashboard Fleet                              | Signal d'alarme               |
| ----------------------------------------------------------------------- | ------------------------------- | -------------------------------------------- | ----------------------------- |
| `logstash.node.stats.jvm.gc.collectors.old.collection_time_in_millis`   | `metrics-logstash.node-default` | [Metrics Logstash] Single Node Advanced View | Pic soudain (pause > 500 ms)  |
| `logstash.node.stats.jvm.gc.collectors.young.collection_time_in_millis` | `metrics-logstash.node-default` | [Metrics Logstash] Single Node Advanced View | Fréquence élevée              |
| `logstash.node.stats.jvm.mem.heap_used_percent`                         | `metrics-logstash.node-default` | [Metrics Logstash] Node Health Report        | > 85 % → **Alerte Kibana 5a** |
| `logstash.node.stats.events.out`                                        | `metrics-logstash.node-default` | [Metrics Logstash] Logstash Overview         | Tombe à 0 pendant la pause GC |

**Signature caractéristique** : pic de latence **bimodal** (temps de réponse normal
puis pic soudain), CPU **élevé** pendant le pic (≠ scénario 1 où CPU = 0),
`events.out` tombe à 0 le temps de la pause stop-the-world.

### KQL de diagnostic

Dans Discover, data view `metrics-logstash*` :
```
logstash.node.stats.jvm.mem.heap_used_percent > 85
```

Pour corréler avec les logs GC (si `-Xlog:gc,safepoint` est activé dans `LS_JAVA_OPTS`) :
dans les logs Scalingo de l'app `pass-emploi-logstash-prod`, chercher les lignes
`Pause` avec une durée en ms.

### Actions correctives

1. **Vérifier le heap utilisé** : dashboard [Metrics Logstash] Node Health Report →
   `jvm.mem.heap_used_percent`. Si > 85 % en régime normal, le heap est
   sous-dimensionné.
2. **Vérifier `LS_JAVA_OPTS`** sur Scalingo : doit contenir `-Xms1g -Xmx1g`.
   ⚠️ Ne jamais dépasser `-Xmx1g` sur un conteneur XL (2 Go) — le reste est
   consommé par Netty/direct memory, JRuby, metaspace, threads + OS.
   Sur Scalingo, les conteneurs tournent sans swap : quand la mémoire totale
   (heap 1 Go + off-heap ~600 Mo + OS ~200 Mo ≈ 1,8 Go) dépasse la limite du
   conteneur, le kernel envoie un SIGKILL immédiat sans avertissement.
   **`-Xmx2g` sur XL = OOM-kill garanti.**
3. **Si le heap est correctement dimensionné** mais les GC sont fréquents : le
   volume d'ingestion dépasse la capacité de traitement. Scaler horizontalement
   (ajouter des instances Logstash sur Scalingo).
4. **Pour diagnostiquer en live** : activer temporairement les logs GC via
   `LS_JAVA_OPTS="-Xms1g -Xmx1g -Xlog:gc,safepoint:stderr:utctime,level,tags"` sur
   Scalingo. **Retirer après le diagnostic** (verbeux : pollue le drain + stockage ES).

### Références

- [conventions.md — Garde-fous JVM](../blackout-logs/conventions.md#garde-fous-durables-ne-pas-se-faire-avoir)
- [postmortem-logstash-5xx-2026-06.md](./postmortem-logstash-5xx-2026-06.md)

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
2. Corriger le mapping dans `logs/elastic/2-component-templates.console` (ajouter
   le champ dans `logs@custom` ou le template concerné).
3. Appliquer via Kibana Dev Tools et faire un rollover :
   ```
   POST logs-prod-default/_rollover
   ```
4. Les events en DLQ peuvent être **rejoués** : le pipeline `dead_letter_queue`
   les a déjà indexés dans `logs-logstash-dlq-*` pour investigation. Un rejeu
   manuel nécessite de corriger le mapping d'abord.

**Si erreurs de traitement (`_mutate_error`, `_jsonparsefailure`)** :
1. Identifier le log fautif via le champ `message` dans `logs-logstash-errors-*`.
2. Reproduire localement avec le pipeline `process` pour identifier le filtre
   défaillant.
3. Corriger `logs/pipeline-process.conf` et déployer.

### Références

- [infra-elasticsearch.md — Historique incidents](./infra-elasticsearch.md#historique-incidents)
- [`logs/pipeline-dlq-logstash.conf`](../../logs/pipeline-dlq-logstash.conf)
- [`logs/pipeline-process.conf`](../../logs/pipeline-process.conf)

---

## Scénario 4 — Crash du conteneur Logstash

### Indicateurs Kibana / Scalingo

| Signal                                  | Source                | Description                                           |
|-----------------------------------------|-----------------------| ----------------------------------------------------- |
| Alerte webhook Scalingo                 | Scalingo → Mattermost | `app_crashed` avec `reason: OOM` ou `reason: SIGKILL` |
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
1. Vérifier `LS_JAVA_OPTS` sur Scalingo : doit être `-Xms1g -Xmx1g`.
   ⚠️ `-Xmx2g` sur XL (2 Go) = OOM-kill garanti (voir scénario 2).
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

- [conventions.md — Quarantaine drain](../blackout-logs/conventions.md#garde-fous-durables-ne-pas-se-faire-avoir)
- [postmortem-2026-07.md — §3 Mode B](../blackout-logs/postmortem-2026-07.md)
- [4-kibana-alerts.md — Alerte 6 (webhook Scalingo)](../../logs/elastic/4-kibana-alerts.md#alerte-6--restart-du-conteneur-logstash-scalingo-webhook)

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

| Ressource                                           | URL                                                                                                                       |
|-----------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| Fleet — Agents Logstash                             | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/fleet/agents                                                   |
| Dashboards intégration Logstash                     | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/integrations/detail/logstash-2.11.3/assets                     |
| Stack Management → Rules                            | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/management/insightsAndAlerting/triggersActions/rules           |
| [Metrics Logstash] Pipeline Health Report           | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-838aac39-8edd-48b0-95b4-289e42b1e98a |
| [Metrics Logstash] Elasticsearch output plugin info | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086 |
| [Metrics Logstash] Logstash Overview                | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522 |
| [Metrics Logstash] Single Node Advanced View        | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-a42d7060-45e6-11ee-957b-3720c0b0fbc5 |
| [Metrics Logstash] Node Health Report               | https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9a72208d-e446-48b9-8a63-c4256b9aa4e3 |

### Liens directs Scalingo

| App                                     | URL                                                                                     |
|-----------------------------------------| --------------------------------------------------------------------------------------- |
| `pass-emploi-logstash-prod` — métriques | https://dashboard.scalingo.com/apps/osc-secnum-fr1/pass-emploi-logstash-prod/metrics |
| `pass-emploi-logstash-perf` — métriques | https://dashboard.scalingo.com/apps/osc-secnum-fr1/pass-emploi-logstash-perf/metrics |

### Data views Kibana — Discover

| Data view                                                    | Index pattern                               | Usage                                           |
| ------------------------------------------------------------ |---------------------------------------------|-------------------------------------------------|
| `logs-prod-default`                                          | `logs-prod-default`                         | Logs applicatifs prod                           |
| `logs-staging-default` / `logs-perf-default`                 | `logs-staging-default`, `logs-perf-default` | Logs applicatifs hors-prod                      |
| Logs Logstash - Dead Letter Queue                            | `logs-logstash-dlq-*`                       | Events rejetés par ES (scénario 3)              |
| Logs Logstash - Index erreurs de traitement Pipeline process | `logs-logstash-errors-*`                    | Events en erreur de transformation (scénario 3) |
