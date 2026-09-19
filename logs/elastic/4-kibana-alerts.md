# Alertes Kibana — supervision Logstash

Définitions des alertes de supervision de la chaîne d'ingestion Logstash.
À configurer dans **Kibana → Stack Management → Rules**.

> **Contexte** : les 4 scénarios de panne et leurs indicateurs sont documentés dans
> [`docs/logs-ecs/runbook-astreinte-logstash.md`](../../docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md).
> Les dashboards Fleet Logstash sont listés ici :
> https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/integrations/detail/logstash-2.11.3/assets

---

## Récapitulatif des alertes

| #  | Signal                                        | Index / source                              | Condition                        | Fréquence | Throttle | Sévérité    |
| -- |-----------------------------------------------|---------------------------------------------|----------------------------------|-----------|----------|-------------|
| 1a | DLQ non vide — prod                           | `logs-logstash-dlq-prod-default`            | `Is above 0` / 5 min             | 1 min     | 6h       | 🚨 Critical |
| 1b | DLQ non vide — staging/perf                   | `logs-logstash-dlq-staging/perf-default`    | `Is above 0` / 5 min             | 5 min     | 6h       | ⚠️ Warning   |
| 2a | Erreurs traitement — prod                     | `logs-logstash-errors-prod-default`         | `Is above 0` / 5 min             | 1 min     | 6h       | 🚨 Critical |
| 2b | Erreurs traitement — staging/perf             | `logs-logstash-errors-staging/perf-default` | `Is above 0` / 5 min             | 5 min     | 6h       | ⚠️ Warning   |
| 3a | Silence logs applicatifs — prod               | `logs-prod-default`                         | `Is below or equals 0` / 5 min   | 2 min     | 6h       | 🚨 Critical |
| 3b | Silence logs router — prod                    | `logs-router-prod-default`                  | `Is below or equals 0` / 5 min   | 2 min     | 6h       | 🚨 Critical |
| 3c | Silence logs applicatifs — staging/perf       | `logs-staging/perf-default`                 | `Is below or equals 0` / 5 min   | 5 min     | 6h       | ⚠️ Warning   |
| 3d | Silence logs router — staging/perf            | `logs-router-staging/perf-default`          | `Is below or equals 0` / 5 min   | 5 min     | 6h       | ⚠️ Warning   |
| 4a | Backpressure — workers bloqués — prod         | `metrics-logstash.pipeline-default`         | `Is above 0.5` / 5 min           | 2 min     | 6h       | 🚨 Critical |
| 4b | Backpressure — workers bloqués — staging/perf | `metrics-logstash.pipeline-default`         | `Is above 0.5` / 5 min           | 5 min     | 6h       | ⚠️ Warning   |
| 5a | Heap JVM élevé — prod                         | `metrics-logstash.node-default`             | `Is above 85` / 5 min            | 2 min     | 6h       | 🚨 Critical |
| 5b | Heap JVM élevé — staging/perf                 | `metrics-logstash.node-default`             | `Is above 85` / 5 min            | 5 min     | 6h       | ⚠️ Warning   |
| 6  | Restart conteneur                             | Scalingo webhook                            | `app_crashed/app_restarted`      | —         | —        | 🚨 Critical |
| 7a | Backlog Redis `logstash:ingest` — prod        | `metrics-redis.key-default`                 | `Is above 1 000` / 5 min         | 2 min     | 6h       | 🚨 Critical |
| 7b | Backlog Redis `logstash:ingest` — staging/perf| `metrics-redis.key-default`                 | `Is above 1 000` / 5 min         | 5 min     | 6h       | ⚠️ Warning   |

---

## Alerte 1 — Dead Letter Queue non vide

**Objectif** : détecter toute perte silencieuse d'événements dans la DLQ du pipeline
`process`. Tout event dans la DLQ signale un rejet non récupérable (conflit de mapping,
erreur de transformation) qui n'a **pas** été indexé dans `logs-*`.

> **Note** : la taille de la DLQ (`queue_size_in_bytes`) n'est **pas** exposée dans
> les data streams de métriques Elastic Agent (`metrics-logstash.*`). L'alerte se
> base donc directement sur la présence de documents dans l'index `logs-logstash-dlq-*`,
> alimenté par le pipeline `dead_letter_queue` de Logstash.
>
> ⚠️ **L'index `logs-logstash-dlq-*` n'existe que si au moins un event a été rejeté
> en DLQ** (Logstash crée le data stream à la première écriture). L'alerte Kibana
> `COUNT(*) > 0` fonctionne même si l'index n'existe pas encore : Kibana retourne 0
> → pas d'alerte. Elle se déclenche dès que l'index est créé avec des documents.
> En revanche, la **data view** de diagnostic ne peut être créée qu'une fois le data
> stream existant. Pour l'anticiper, créer les data streams vides via Dev Tools
> (le nom `logs-logstash-dlq-*` matche le template `logs` qui impose l'API data stream) :
> ```
> PUT _data_stream/logs-logstash-dlq-prod-default
> PUT _data_stream/logs-logstash-dlq-staging-default
> PUT _data_stream/logs-logstash-dlq-perf-default
> ```

> **Data streams de métriques Logstash** (intégration Elastic Agent) :
> - `metrics-logstash.node-default` — stats nœud : JVM heap, GC, events in/out
> - `metrics-logstash.pipeline-default` — stats pipeline : queue depth, workers, batch
> - `metrics-logstash.plugins-default` — stats plugins : bulk requests ES, erreurs output
> - `metrics-logstash.health_report-default` — état de santé global du nœud
>
> Data view à créer dans Kibana : index pattern `metrics-logstash*`, timestamp `@timestamp`.

### 1a — DLQ prod (Critical)

| Paramètre               | Valeur                                                                                                                                                                                                        |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**           | `Logstash - Prod - Détection présence event dans DLQ`                                                                                                                                                         |
| **Type**                | Elasticsearch query rule                                                                                                                                                                                      |
| **Index**               | `logs-logstash-dlq-prod-default`                                                                                                                                                                              |
| **Condition**           | `Is above` `0`                                                                                                                                                                                                |
| **Fenêtre**             | 5 min                                                                                                                                                                                                         |
| **Fréquence**           | 1 min                                                                                                                                                                                                         |
| **Sévérité**            | Critical                                                                                                                                                                                                      |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                                                              |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production** — voir body ci-dessous                                                                                                                                 |
| **Related dashboards**  | `[Metrics Logstash] Pipeline Health Report`                                                                                                                                                                   |
| **Investigation guide** | Voir [runbook scénario — Rejet de mapping / DLQ](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue) |

**Body du webhook** (champ "Body" dans l'onglet Message de l'action) :
```json
{"text": "🚨 **DLQ Logstash prod non vide** — des events de prod ont été perdus silencieusement.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)"}
```

### 1b — DLQ staging / perf (Warning)

| Paramètre               | Valeur                                                                                                                                                                                                         |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**           | `Logstash - Hors-Prod - Détection présence event dans DLQ`                                                                                                                                                     |
| **Type**                | Elasticsearch query rule                                                                                                                                                                                       |
| **Index**               | `logs-logstash-dlq-staging-default,logs-logstash-dlq-perf-default`                                                                                                                                             |
| **Condition**           | `Is above` `0`                                                                                                                                                                                                 |
| **Fenêtre**             | 5 min                                                                                                                                                                                                          |
| **Fréquence**           | 5 min                                                                                                                                                                                                          |
| **Sévérité**            | Warning                                                                                                                                                                                                        |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                                                               |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-staging** — voir body ci-dessous                                                                                                                                     |
| **Related dashboards**  | `[Metrics Logstash] Pipeline Health Report`                                                                                                                                                                    |
| **Investigation guide** | Voir [runbook scénario — Rejet de mapping / DLQ](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)  |

**Body du webhook** :
```json
{"text": "⚠️ **DLQ Logstash staging/perf non vide** — des events hors prod ont été rejetés.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)"}
```

**KQL de diagnostic dans Discover** (data view `logs-logstash-dlq-*`) :
```
service.environment: "prod"
```
Champs clés : `logstash.dlq.reason` (cause du rejet ES), `event.original` (payload
complet de l'event fautif en JSON stringifié).

> **Noms réels des index** (définis dans `pipeline-dlq-logstash.conf`) :
> - `logs-logstash-dlq-prod-default`
> - `logs-logstash-dlq-staging-default`
> - `logs-logstash-dlq-perf-default`

---

## Alerte 2 — Index erreurs de traitement non vide

**Objectif** : détecter toute régression dans le pipeline de transformation Logstash.
Les events dans `logs-logstash-errors-*` sont des logs qui ont déclenché une erreur
Logstash (`_mutate_error`, `_jsonparsefailure`, `_rubyexception`…) et n'ont **pas**
été indexés dans leur data stream cible.

### 2a — Erreurs prod (Critical)

| Paramètre               | Valeur                                                                                                                                                                                                         |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**           | `Logstash - Prod - Détection erreurs pipeline process`                                                                                                                                                         |
| **Type**                | Elasticsearch query rule                                                                                                                                                                                       |
| **Index**               | `logs-logstash-errors-prod-default`                                                                                                                                                                            |
| **Condition**           | `Is above` `0`                                                                                                                                                                                                 |
| **Fenêtre**             | 5 min                                                                                                                                                                                                          |
| **Fréquence**           | 1 min                                                                                                                                                                                                          |
| **Sévérité**            | Critical                                                                                                                                                                                                       |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                                                               |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production** — voir body ci-dessous                                                                                                                                  |
| **Related dashboards**  | `[Metrics Logstash] Pipeline Health Report`                                                                                                                                                                    |
| **Investigation guide** | Voir [runbook scénario — Rejet de mapping / DLQ](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)  |

**Body du webhook** :
```json
{"text": "🚨 **Erreurs de traitement Logstash sur prod** — des logs de prod n'ont pas été indexés.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)"}
```

### 2b — Erreurs staging / perf (Warning)

| Paramètre               | Valeur                                                                                                                                                                                                         |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**           | `Logstash - Hors-Prod - Détection erreurs pipeline process`                                                                                                                                                    |
| **Type**                | Elasticsearch query rule                                                                                                                                                                                       |
| **Index**               | `logs-logstash-errors-staging-default,logs-logstash-errors-perf-default`                                                                                                                                       |
| **Condition**           | `Is above` `0`                                                                                                                                                                                                 |
| **Fenêtre**             | 5 min                                                                                                                                                                                                          |
| **Fréquence**           | 5 min                                                                                                                                                                                                          |
| **Sévérité**            | Warning                                                                                                                                                                                                        |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                                                               |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-staging** — voir body ci-dessous                                                                                                                                     |
| **Related dashboards**  | `[Metrics Logstash] Pipeline Health Report`                                                                                                                                                                    |
| **Investigation guide** | Voir [runbook scénario — Rejet de mapping / DLQ](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)  |

**Body du webhook** :
```json
{"text": "⚠️ **Erreurs de traitement Logstash sur staging/perf** — des logs hors prod n'ont pas été indexés.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)"}
```

**KQL de diagnostic dans Discover** (data view `logs-logstash-errors-*`) :
```
*
```
Trier par `@timestamp` desc. Les champs `tags` indiquent la cause
(`_mutate_error`, `_jsonparsefailure`, `_rubyexception`…).

> **Noms réels des index** (définis dans `pipeline-process.conf`) :
> - `logs-logstash-errors-prod-default`
> - `logs-logstash-errors-staging-default`
> - `logs-logstash-errors-perf-default`

---

## Alerte 3 — Absence de logs (quarantaine drain ou crash Logstash)

**Objectif** : détecter une quarantaine du drain Scalingo ou un crash Logstash.
L'absence de logs dans les index applicatifs et router pendant > 5 min est le signal
d'un arrêt complet de l'ingestion (scénario 4 du runbook).

### 3a — Absence dans `logs-prod-default`

| Paramètre                 | Valeur                                                                                                                                                                                                      |
|---------------------------| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**             | `Logstash - Prod - Détection absence ingestion logs applicatifs`                                                                                                                                            |
| **Type**                  | Elasticsearch query rule                                                                                                                                                                                    |
| **Index**                 | `logs-prod-default`                                                                                                                                                                                         |
| **Condition**             | `Is below or equals` `0`                                                                                                                                                                                    |
| **Fenêtre**               | 5 min                                                                                                                                                                                                       |
| **Fréquence**             | 2 min                                                                                                                                                                                                       |
| **Sévérité**              | Critical                                                                                                                                                                                                    |
| **Action 1 (alerte)**     | Connecteur Kibana **Mattermost-monitoring-production** — `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings) — voir body ci-dessous                  |
| **Action 2 (résolution)** | Connecteur Kibana **Mattermost-monitoring-production** — `On status changes` / `Run when: Recovered` (onglet Actions → Settings) — voir body ci-dessous                                                    |
| **Related dashboards**    | `[Metrics Logstash] Logstash Overview`                                                                                                                                                                      |
| **Investigation guide**   | Voir [runbook scénario — Crash du conteneur Logstash](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-4--crash-du-conteneur-logstash)  |

**Body du webhook — Action 1 (alerte)** :
```json
{"text": "🚨 **Silence Logstash** — aucun log dans `logs-prod-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-4--crash-du-conteneur-logstash)"}
```

**Body du webhook — Action 2 (résolution)** :
```json
{"text": "✅ **Silence Logstash résolu** — les logs sont revenus dans `logs-prod-default`.\n- Règle : `{{rule.name}}`\n- Résolue à : `{{date}}`"}
```

### 3b — Absence dans `logs-router-prod-default`

| Paramètre                 | Valeur                                                                                                                                                                                                      |
|---------------------------| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**             | `Logstash - Prod - Détection absence ingestion logs router`                                                                                                                                                 |
| **Type**                  | Elasticsearch query rule                                                                                                                                                                                    |
| **Index**                 | `logs-router-prod-default`                                                                                                                                                                                  |
| **Condition**             | `Is below or equals` `0`                                                                                                                                                                                    |
| **Fenêtre**               | 5 min                                                                                                                                                                                                       |
| **Fréquence**             | 2 min                                                                                                                                                                                                       |
| **Sévérité**              | Critical                                                                                                                                                                                                    |
| **Action 1 (alerte)**     | Connecteur Kibana **Mattermost-monitoring-production** — `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings) — voir body ci-dessous                  |
| **Action 2 (résolution)** | Connecteur Kibana **Mattermost-monitoring-production** — `On status changes` / `Run when: Recovered` (onglet Actions → Settings) — voir body ci-dessous                                                    |
| **Related dashboards**    | `[Metrics Logstash] Logstash Overview`                                                                                                                                                                      |
| **Investigation guide**   | Voir [runbook scénario — Crash du conteneur Logstash](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-4--crash-du-conteneur-logstash)  |

**Body du webhook — Action 1 (alerte)** :
```json
{"text": "🚨 **Silence Logstash** — aucun log router dans `logs-router-prod-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-4--crash-du-conteneur-logstash)"}
```

**Body du webhook — Action 2 (résolution)** :
```json
{"text": "✅ **Silence Logstash résolu** — les logs router sont revenus dans `logs-router-prod-default`.\n- Règle : `{{rule.name}}`\n- Résolue à : `{{date}}`"}
```

### 3c — Absence dans `logs-staging-default` / `logs-perf-default`

| Paramètre               | Valeur                                                                                                                                                                                                      |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**           | `Logstash - Hors-Prod - Détection absence ingestion logs applicatifs`                                                                                                                                       |
| **Type**                | Elasticsearch query rule                                                                                                                                                                                    |
| **Index**               | `logs-staging-default,logs-perf-default`                                                                                                                                                                    |
| **Condition**           | `Is below or equals` `0`                                                                                                                                                                                    |
| **Fenêtre**             | 5 min                                                                                                                                                                                                       |
| **Fréquence**           | 5 min                                                                                                                                                                                                       |
| **Sévérité**            | Warning                                                                                                                                                                                                     |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                                                            |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-staging** — voir body ci-dessous                                                                                                                                  |
| **Related dashboards**  | `[Metrics Logstash] Logstash Overview`                                                                                                                                                                      |
| **Investigation guide** | Voir [runbook scénario — Crash du conteneur Logstash](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-4--crash-du-conteneur-logstash)  |

**Body du webhook** :
```json
{"text": "⚠️ **Silence Logstash** — aucun log dans `logs-staging-default` ou `logs-perf-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-4--crash-du-conteneur-logstash)"}
```

### 3d — Absence dans `logs-router-staging-default` / `logs-router-perf-default`

| Paramètre               | Valeur                                                                                                                                                                                                      |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**           | `Logstash - Hors-Prod - Détection absence ingestion logs router`                                                                                                                                            |
| **Type**                | Elasticsearch query rule                                                                                                                                                                                    |
| **Index**               | `logs-router-staging-default,logs-router-perf-default`                                                                                                                                                      |
| **Condition**           | `Is below or equals` `0`                                                                                                                                                                                    |
| **Fenêtre**             | 5 min                                                                                                                                                                                                       |
| **Fréquence**           | 5 min                                                                                                                                                                                                       |
| **Sévérité**            | Warning                                                                                                                                                                                                     |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                                                            |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-staging** — voir body ci-dessous                                                                                                                                  |
| **Related dashboards**  | `[Metrics Logstash] Logstash Overview`                                                                                                                                                                      |
| **Investigation guide** | Voir [runbook scénario — Crash du conteneur Logstash](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-4--crash-du-conteneur-logstash)  |

**Body du webhook** :
```json
{"text": "⚠️ **Silence Logstash** — aucun log router dans `logs-router-staging-default` ou `logs-router-perf-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-4--crash-du-conteneur-logstash)"}
```

> **Corrélation** : si les deux alertes (3a+3b ou 3c+3d) se déclenchent simultanément,
> c'est un crash Logstash ou un arrêt de l'app Scalingo. Si seulement l'alerte
> applicatifs se déclenche (router continue), c'est une quarantaine du drain applicatif.

---

## Alerte 4 — Backpressure Elasticsearch (workers bloqués sur la queue)

**Objectif** : détecter une backpressure ES **avant** que la queue ne soit profonde.
`queue_backpressure.current` mesure le ratio de temps que les workers passent bloqués
à attendre que la Persistent Queue accepte de nouveaux events (0 = pas de backpressure,
1 = 100 % du temps bloqué). Il monte dès que ES commence à ralentir, bien avant que
`queues.events` ne s'accumule.

> **Champ surveillé** : `logstash.pipeline.total.flow.queue_backpressure.current`
> dans le data stream `metrics-logstash.pipeline-default`.
>
> **Seuil de 0.5** : les workers sont bloqués > 50 % du temps sur la queue.
> En régime normal ce champ est proche de 0. À ajuster après observation du régime
> nominal sur prod.
>
> **Indicateur de diagnostic complémentaire** (non alerté) :
> `logstash.pipeline.total.queues.events` — nombre d'events en attente dans la queue.
> À consulter dans le dashboard `[Metrics Logstash] Pipeline Health Report` pour
> confirmer l'accumulation une fois l'alerte déclenchée.

### 4a — Backpressure prod (Critical)

| Paramètre                 | Valeur                                                                                                                                                                                                   |
|---------------------------| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**             | `Logstash - Prod - Détection backpressure ES (workers bloqués)`                                                                                                                                          |
| **Type**                  | Elasticsearch query rule                                                                                                                                                                                 |
| **Index**                 | `metrics-logstash.pipeline-default`                                                                                                                                                                      |
| **KQL filter**            | `logstash.pipeline.host.name: (pass-emploi-logstash-prod-* OR pass-emploi-logstash-process-prod-*)`                                                                                                      |
| **Aggregation**           | `Max` de `logstash.pipeline.total.flow.queue_backpressure.current`                                                                                                                                       |
| **Condition**             | `Is above` `0.5`                                                                                                                                                                                         |
| **Fenêtre**               | 5 min                                                                                                                                                                                                    |
| **Fréquence**             | 2 min                                                                                                                                                                                                    |
| **Sévérité**              | Critical                                                                                                                                                                                                 |
| **Action 1 (alerte)**     | Connecteur Kibana **Mattermost-monitoring-production** — `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings) — voir body ci-dessous               |
| **Action 2 (résolution)** | Connecteur Kibana **Mattermost-monitoring-production** — `On status changes` / `Run when: Recovered` (onglet Actions → Settings) — voir body ci-dessous                                               |
| **Related dashboards**    | `[Metrics Logstash] Pipeline Health Report`                                                                                                                                                              |
| **Investigation guide**   | Voir [runbook scénario — Backpressure Elasticsearch](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-1--backpressure-elasticsearch) |

**Body du webhook — Action 1 (alerte)** :
```json
{"text": "🚨 **Backpressure Logstash prod** — workers bloqués > 50 % du temps sur la queue (`queue_backpressure > 0.5`). Elasticsearch ne consomme plus assez vite.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- Vérifier `logstash.pipeline.total.queues.events` dans Pipeline Health Report\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-1--backpressure-elasticsearch)"}
```

**Body du webhook — Action 2 (résolution)** :
```json
{"text": "✅ **Backpressure Logstash prod résolue** — `queue_backpressure` est retombé sous 0.5.\n- Règle : `{{rule.name}}`\n- Résolue à : `{{date}}`"}
```

### 4b — Backpressure staging / perf (Warning)

| Paramètre               | Valeur                                                                                                                                                                                                   |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**           | `Logstash - Hors-Prod - Détection backpressure ES (workers bloqués)`                                                                                                                                     |
| **Type**                | Elasticsearch query rule                                                                                                                                                                                 |
| **Index**               | `metrics-logstash.pipeline-default`                                                                                                                                                                      |
| **KQL filter**          | `logstash.pipeline.host.name: (pass-emploi-logstash-staging-* OR pass-emploi-logstash-perf-*)`                                                                                                           |
| **Aggregation**         | `Max` de `logstash.pipeline.total.flow.queue_backpressure.current`                                                                                                                                       |
| **Condition**           | `Is above` `0.5`                                                                                                                                                                                         |
| **Fenêtre**             | 5 min                                                                                                                                                                                                    |
| **Fréquence**           | 5 min                                                                                                                                                                                                    |
| **Sévérité**            | Warning                                                                                                                                                                                                  |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                                                         |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-staging** — voir body ci-dessous                                                                                                                               |
| **Related dashboards**  | `[Metrics Logstash] Pipeline Health Report`                                                                                                                                                              |
| **Investigation guide** | Voir [runbook scénario — Backpressure Elasticsearch](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-1--backpressure-elasticsearch) |

**Body du webhook** :
```json
{"text": "⚠️ **Backpressure Logstash staging/perf** — workers bloqués > 50 % du temps sur la queue (`queue_backpressure > 0.5`).\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-1--backpressure-elasticsearch)"}
```

---

## Alerte 5 — Heap JVM élevé (risque GC agressif)

**Objectif** : détecter un heap JVM Logstash > 85 %, signe d'un GC agressif imminent
pouvant provoquer des pauses stop-the-world (scénario 2 du runbook) ou un OOM-kill.

> **Champ surveillé** : `logstash.node.stats.jvm.mem.heap_used_percent`
> dans le data stream `metrics-logstash.node-default`.

### 5a — Heap élevé prod (Critical)

| Paramètre               | Valeur                                                                                                                                                                   |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Rule name**           | `Logstash - Prod - Détection heap JVM élevé`                                                                                                                             |
| **Type**                | Elasticsearch query rule                                                                                                                                                 |
| **Index**               | `metrics-logstash.node-default`                                                                                                                                          |
| **KQL filter**          | `host.name: (pass-emploi-logstash-prod-* OR pass-emploi-logstash-process-prod-*)`                                                                                        |
| **Aggregation**         | `Max` de `logstash.node.stats.jvm.mem.heap_used_percent`                                                                                                                 |
| **Condition**           | `Is above` `85`                                                                                                                                                          |
| **Fenêtre**             | 5 min                                                                                                                                                                    |
| **Fréquence**           | 2 min                                                                                                                                                                    |
| **Sévérité**            | Critical                                                                                                                                                                 |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                         |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production** — voir body ci-dessous                                                                                            |
| **Related dashboards**  | `[Metrics Logstash] Node Health Report`                                                                                                                                  |
| **Investigation guide** | Voir [runbook scénario — Gel GC JVM](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-2--gel-gc-jvm) |

**Body du webhook** :
```json
{"text": "🚨 **Heap JVM Logstash prod > 85 %** — GC agressif imminent ou risque OOM-kill.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- Vérifier `LS_JAVA_OPTS` : doit être `-Xms1g -Xmx1g`\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-2--gel-gc-jvm)"}
```

### 5b — Heap élevé staging / perf (Warning)

| Paramètre               | Valeur                                                                                                                                                                   |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Rule name**           | `Logstash - Hors-Prod - Détection heap JVM élevé`                                                                                                                        |
| **Type**                | Elasticsearch query rule                                                                                                                                                 |
| **Index**               | `metrics-logstash.node-default`                                                                                                                                          |
| **KQL filter**          | `host.name: (pass-emploi-logstash-staging-* OR pass-emploi-logstash-perf-*)`                                                                                             |
| **Aggregation**         | `Max` de `logstash.node.stats.jvm.mem.heap_used_percent`                                                                                                                 |
| **Condition**           | `Is above` `85`                                                                                                                                                          |
| **Fenêtre**             | 5 min                                                                                                                                                                    |
| **Fréquence**           | 5 min                                                                                                                                                                    |
| **Sévérité**            | Warning                                                                                                                                                                  |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                         |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-staging** — voir body ci-dessous                                                                                               |
| **Related dashboards**  | `[Metrics Logstash] Node Health Report`                                                                                                                                  |
| **Investigation guide** | Voir [runbook scénario — Gel GC JVM](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-2--gel-gc-jvm) |

**Body du webhook** :
```json
{"text": "⚠️ **Heap JVM Logstash staging/perf > 85 %** — GC agressif imminent.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-2--gel-gc-jvm)"}
```

---

## Alerte 6 — Restart du conteneur Logstash (Scalingo webhook)

**Objectif** : être alerté d'un restart du conteneur Logstash (OOM-kill ou crash).

**Configuration dans le dashboard Scalingo** (hors repo — action manuelle) :

Répéter l'opération pour chaque app Logstash :

| App Scalingo                  | Canal Mattermost                    |
| ----------------------------- | ----------------------------------- |
| `pass-emploi-logstash-prod`   | `Mattermost-monitoring-production`  |
| `pass-emploi-logstash-perf`   | `Mattermost-monitoring-staging`     |

Pour chaque app :

1. Aller sur l'app dans le dashboard Scalingo.
2. **Settings → Notifications → Add notification**.
3. Choisir le type **Webhook**.
4. Événements à surveiller : `app_restarted`, `app_crashed`, `app_stopped`.
5. URL du webhook : URL du webhook entrant Mattermost du canal correspondant.

> **Note** : le throttle ne s'applique pas aux webhooks Scalingo — chaque événement
> `app_crashed` / `app_restarted` est une notification unitaire envoyée par Scalingo.

**Payload Scalingo** (exemple pour un restart OOM) :
```json
{
  "app": { "name": "pass-emploi-logstash-prod" },
  "event_type": "app_crashed",
  "event": {
    "container_type": "web",
    "reason": "OOM"
  }
}
```

> **Alternative** : utiliser l'alerte 3 (absence de logs) comme proxy indirect du
> crash — un crash Logstash se traduit immédiatement par un silence dans
> `logs-prod-default`. Les deux alertes sont complémentaires : le webhook Scalingo
> donne la **cause** (OOM), l'alerte 3 donne l'**effet** (silence logs).

---

## Alerte 7 — Backlog Redis `logstash:ingest` (pipeline PROCESS découplé)

**Objectif** : détecter une accumulation anormale d'événements dans la liste Redis
`logstash:ingest`, buffer inter-services entre le pipeline `ingest` et le pipeline
`process`. En régime normal, le pipeline `process` consomme la liste en temps réel
et sa longueur reste proche de 0 (0–250 éléments en régime normal). Un backlog
signale que le pipeline `process` ne consomme plus Redis : redémarrage ou blocage
de `pass-emploi-logstash-process-prod`, coupure réseau Redis, ou backpressure ES
sévère côté `process`.

> **Incident de référence — 14/09/2026** : `pass-emploi-logstash-process-prod` a
> subi plusieurs redémarrages inexpliqués dans la soirée, provoquant l'accumulation
> de ~180 000 événements jusqu'à saturer les 256 Mo de Redis → crash du cluster Redis
> à 20:37 (HAProxy DOWN). **Cause racine inconnue** — logs archivés Scalingo
> inaccessibles à date. Le lendemain matin, l'app s'est rétablie et a vidé le
> backlog — aucun log perdu, mais indexation tardive (~13h de retard).
>
> **Source** : data stream `metrics-redis.key-default` (intégration Redis Elastic
> Agent, collectée par `pass-emploi-elastic-agent-prod`). Champ : `redis.key.length`.
>
> **Seuil de 1 000** : en régime normal rétabli, la liste oscille entre 25 et 250
> éléments par fenêtre de 30 secondes (mesuré le 15/09/2026 après l'incident Redis).
> 1 000 représente ~4× le pic max observé → pas de faux positif sur les micro-pics.
> En cas de coupure réelle, la liste atteint 1 000 en quelques dizaines de secondes
> au débit prod → alerte déclenchée en moins de 2 minutes (fréquence de l'alerte 7a).

### 7a — Backlog Redis prod (Critical)

| Paramètre                 | Valeur                                                                                                                                                                                     |
|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Rule name**             | `Redis - Prod - Backlog logstash:ingest anormal`                                                                                                                                           |
| **Type**                  | Elasticsearch query rule                                                                                                                                                                   |
| **Index**                 | `metrics-redis.key-default`                                                                                                                                                                |
| **KQL filter**            | `redis.key.name: "logstash:ingest"`                                                                                                                                                        |
| **Aggregation**           | `Max` de `redis.key.length`                                                                                                                                                                |
| **Condition**             | `Is above` `1000`                                                                                                                                                                         |
| **Fenêtre**               | 5 min                                                                                                                                                                                      |
| **Fréquence**             | 2 min                                                                                                                                                                                      |
| **Sévérité**              | Critical                                                                                                                                                                                   |
| **Action 1 (alerte)**     | Connecteur Kibana **Mattermost-monitoring-production** — `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings) — voir body ci-dessous |
| **Action 2 (résolution)** | Connecteur Kibana **Mattermost-monitoring-production** — `On status changes` / `Run when: Recovered` (onglet Actions → Settings) — voir body ci-dessous                                    |
| **Related dashboards**    | Intégration Redis Kibana → dashboard **[Metrics Redis] Keys** → graphe **Lists length** → clé `db0 › logstash:ingest`                                                                      |
| **Investigation guide**   | Voir [runbook scénario — Backlog Redis logstash:ingest](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-5--backlog-redis-logstashingest) |

**Body du webhook — Action 1 (alerte)** :
```json
{"text": "🚨 **Backlog Redis prod** — la liste `logstash:ingest` dépasse 1 000 événements. Le pipeline `process` ne consomme plus Redis (redémarrage ou blocage de `pass-emploi-logstash-process-prod`, ou backpressure ES sévère).\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- Vérifier les logs de `pass-emploi-logstash-process-prod` sur Scalingo\n- Vérifier le statut Redis dans le dashboard Scalingo\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-5--backlog-redis-logstashingest)"}
```

**Body du webhook — Action 2 (résolution)** :
```json
{"text": "✅ **Backlog Redis prod résorbé** — la liste `logstash:ingest` est retombée sous 1 000 événements. Le pipeline `process` a reconnecté et vide le backlog.\n- Règle : `{{rule.name}}`\n- Résolue à : `{{date}}`\n- ⚠️ Les logs accumulés pendant la coupure vont apparaître dans Kibana avec un timestamp d'origine — vérifier l'absence de trou dans les index `logs-prod-default` et `logs-router-prod-default`"}
```

### 7b — Backlog Redis staging / perf (Warning)

| Paramètre               | Valeur                                                                                                          |
|-------------------------|-----------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `Redis - Hors-Prod - Backlog logstash:ingest anormal`                                                           |
| **Type**                | Elasticsearch query rule                                                                                        |
| **Index**               | `metrics-redis.key-default`                                                                                     |
| **KQL filter**          | `redis.key.name: "logstash:ingest"`                                                                             |
| **Aggregation**         | `Max` de `redis.key.length`                                                                                     |
| **Condition**           | `Is above` `1000`                                                                                              |
| **Fenêtre**             | 5 min                                                                                                           |
| **Fréquence**           | 5 min                                                                                                           |
| **Sévérité**            | Warning                                                                                                         |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)      |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-staging** — voir body ci-dessous                                                                                                                                                    |
| **Related dashboards**  | Intégration Redis Kibana → dashboard **[Metrics Redis] Keys** → graphe **Lists length** → clé `db0 › logstash:ingest`                                                                                                        |
| **Investigation guide** | Voir [runbook scénario — Backlog Redis logstash:ingest](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-5--backlog-redis-logstashingest) |

**Body du webhook** :
```json
{"text": "⚠️ **Backlog Redis staging/perf** — la liste `logstash:ingest` dépasse 1 000 événements. Le pipeline `process` ne consomme plus Redis.\n- Règle : `{{rule.name}}`\n- Déclenchée à : `{{date}}`\n- Vérifier les logs de `pass-emploi-logstash-process-staging` / `pass-emploi-logstash-process-perf` sur Scalingo\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/ingestion-logs/runbook-astreinte-logstash.md#scénario-5--backlog-redis-logstashingest)"}
```

> **Note** : si staging et perf partagent le même Redis (addon lié à
> `pass-emploi-logstash-process-perf`), une seule alerte 7b suffit. Si chaque
> environnement a son propre Redis, dupliquer l'alerte avec un KQL filter sur
> `service.environment: "staging"` ou `"perf"`.

---

## Philosophie des alertes

> **Principe directeur : anticiper, pas réagir.**
>
> Une alerte doit se déclencher **avant** que le problème soit avéré et visible par
> les utilisateurs. Une alerte qui se déclenche au moment où les logs sont déjà perdus
> ou les 429 déjà renvoyés est une alerte de réaction — elle est trop tardive pour
> éviter l'impact.
>
> **Chaîne causale type (backpressure ES) :**
> ```
> ES ralentit / heap monte           → Alertes 4a / 5a  ← intervenir ici
>   → queue process se remplit       → Logstash process rejette les events
>     → backlog Redis croît          → Alerte 7a          ← filet inter-services
>       → ingest ne peut plus écrire → Logstash ingest rejette les drains
>         → 429 sur les apps         → (signal de réaction — pas alerté)
>           → drain en quarantaine   → Alertes 3a/3b (filet de sécurité final)
>             → silence total        → trop tard, perte avérée
> ```
>
> **Chaîne causale type (redémarrage/blocage de `process` ou coupure réseau Redis) :**
> ```
> process tombe ou perd Redis       → pipeline process ne consomme plus
>   → backlog Redis croît           → Alerte 7a          ← intervenir ici
>     → pipeline ingest continue    → (pas de 429, drain OK — invisible sans alerte 7)
>       → saturation Redis possible → crash Redis si le backlog dépasse 256 Mo
> ```
> L'incident du 14/09/2026 illustre ce scénario : ~180 000 événements accumulés
> pendant ~13h, saturation Redis → crash à 20:37. Cause racine inconnue (logs
> archivés). Sans l'alerte 7, l'incident serait passé inaperçu jusqu'au lendemain.
>
> **Règles pour toute nouvelle alerte :**
>
> 1. **Préférer les indicateurs internes Logstash** (métriques Fleet) aux indicateurs
>    externes (codes HTTP, logs applicatifs) — les métriques internes reflètent l'état
>    du système avant que l'impact ne soit visible côté client.
> 2. **Éviter les compteurs cumulatifs** (`bulk_requests.with_errors`,
>    `collection_time_in_millis`, `events.out`…) — ils ne redescendent jamais à 0 et
>    ne sont pas alertables directement. Les utiliser uniquement comme indicateurs de
>    diagnostic dans les dashboards et le runbook.
> 3. **Préférer les indicateurs de niveau** (`queue.events_count`,
>    `heap_used_percent`…) — ils reflètent l'état courant du système et permettent
>    de définir un seuil d'alerte clair.
> 4. **Calibrer le seuil pour laisser une marge d'intervention** : l'alerte doit se
>    déclencher assez tôt pour qu'une action corrective soit possible avant que la
>    situation ne devienne critique (ex : heap > 85 % laisse le temps d'agir avant
>    l'OOM-kill à 100 %).
> 5. **Les alertes de silence** (alerte 3) sont des filets de sécurité de dernier
>    recours — elles signalent que tous les mécanismes d'anticipation ont échoué.
>    Leur déclenchement doit être traité comme une urgence maximale.
