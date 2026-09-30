# Alertes de la stack d'observabilité

Les alertes sur **notre infra de télémétrie** (Logstash, Redis, agents Fleet, Elasticsearch) :
elles signalent que la chaîne de logs et de métriques est en panne ou aveugle,
pas que les utilisateurs sont touchés. Les pannes visibles des utilisateurs sont
dans [alertes-applicatives](alertes-applicatives.md). Hors alertes 6
(webhook Scalingo), 11 et 12 (AutoOps), ce sont des **Kibana Rules** qui notifient via Mattermost
(`#o11y-production`, `#o11y-staging`).

**Création** : les alertes 1 à 5 et 7 à 10 sont versionnées dans
[`rules/2-rules-stack-observabilite.console`](rules/2-rules-stack-observabilite.console),
qui reprend les tableaux et bodies de cette page, à rejouer dans Dev Tools.

> **Contexte** : les scénarios de panne et leurs indicateurs sont documentés dans
> [`runbooks/runbook-logstash.md`](../runbooks/runbook-logstash.md). Dashboards
> associés : [routine-surveillance](../routine-surveillance.md). Seuils de
> service (SLO) : [sli-slo](sli-slo.md).

---

## Récapitulatif des alertes

| #  | Signal                                        | Index / source                                  | Condition                                                | Fréquence  | Throttle | Sévérité    |
| -- |-----------------------------------------------|-------------------------------------------------|----------------------------------------------------------|------------|----------|-------------|
| 1a | DLQ non vide — prod                           | `logs-logstash-dlq-prod-default`                | `Is above 0` / 5 min                                     | 1 min      | 6h       | 🚨 Critical |
| 1b | DLQ non vide — staging/perf                   | `logs-logstash-dlq-staging/perf-default`        | `Is above 0` / 5 min                                     | 5 min      | 6h       | ⚠️Warning  |
| 2a | Erreurs traitement — prod                     | `logs-logstash-errors-prod-default`             | `Is above 0` / 24 h                                      | 1 h        | 1 / jour, 9 h 30 | ⚠️Warning  |
| 2b | Erreurs traitement — staging/perf             | `logs-logstash-errors-staging/perf-default`     | `Is above 0` / 5 min                                     | 5 min      | 6h       | ⚠️Warning  |
| 3a | Silence logs applicatifs — prod               | `logs-prod-default`                             | `Is below or equals 0` / 5 min                           | 2 min      | 6h       | 🚨 Critical |
| 3b | Silence logs router — prod                    | `logs-router-prod-default`                      | `Is below or equals 0` / 5 min                           | 2 min      | 6h       | 🚨 Critical |
| 3c | Silence logs applicatifs — staging/perf       | `logs-staging/perf-default`                     | `Is below or equals 0` / 5 min                           | 5 min      | 6h       | ⚠️Warning  |
| 3d | Silence logs router — staging/perf            | `logs-router-staging/perf-default`              | `Is below or equals 0` / 5 min                           | 5 min      | 6h       | ⚠️Warning  |
| 4a | Backpressure ingest — prod                    | `metrics-logstash.pipeline-default`             | `Min` `≥ 1` / 15 min, par nœud                           | 2 min      | 6h       | 🚨 Critical |
| 4b | Backpressure ingest — staging/perf            | `metrics-logstash.pipeline-default`             | `Min` `≥ 1` / 15 min, par nœud                           | 5 min      | 6h       | ⚠️Warning  |
| 5a | Heap JVM élevé — prod                         | `metrics-logstash.node-default`                 | `Min` `≥ 90` / 15 min, par nœud                          | 2 min      | 6h       | 🚨 Critical |
| 5b | Heap JVM élevé — staging/perf                 | `metrics-logstash.node-default`                 | `Min` `≥ 90` / 15 min, par nœud                          | 5 min      | 6h       | ⚠️Warning  |
| 6  | Restart conteneur                             | Scalingo webhook                                | `app_crashed_repeated/app_restarted`                     | —          | —        | 🚨 Critical |
| 7a | Backlog Redis `logstash:ingest` — prod        | `metrics-redis.key-default`                     | `Min` `Is above 1 000` / 15 min                          | 2 min      | 6h       | 🚨 Critical |
| 7b | Backlog Redis `logstash:ingest` — staging/perf| `metrics-redis.key-default`                     | `Min` `Is above 1 000` / 15 min                          | 5 min      | 6h       | ⚠️Warning  |
| 8a | Elastic Agent en défaut — prod                | status_change + `metrics-elastic_agent.*beat-*` | offline/unenrolled/unhealthy ou > 25 err. output / 5 min | 1 min      | 6h       | 🚨 Critical |
| 8b | Elastic Agent en défaut — staging             | status_change + `metrics-elastic_agent.*beat-*` | offline/unenrolled/unhealthy ou > 25 err. output / 5 min | 1 min      | 6h       | ⚠️Warning  |
| 9a | Mémoire conteneur Logstash — prod             | `logs-scalingo.container_stats-default`         | `Max` `≥ 95 %` / 5 min, par conteneur                    | 1 min      | 6h       | 🚨 Critical |
| 9b | Mémoire conteneur Logstash — staging/perf     | `logs-scalingo.container_stats-default`         | `Max` `≥ 95 %` / 5 min, par conteneur                    | 5 min      | 6h       | ⚠️Warning  |
| 10 | ILM en échec ou policy sans suppression       | historique ILM (`ilm-history-7`)                | étape en échec ou policy par défaut / 24 h               | 1 h        | 1 / jour, 9 h 30 | ⚠️Warning  |
| 11 | Disque des nœuds Elasticsearch                | AutoOps (Elastic Cloud)                         | préavis 75 %, paliers 85 / 90 / 95 %, cluster red       | —          | —        | 🚨 Critical |
| 12 | Saturation de l'indexation Elasticsearch      | AutoOps (Elastic Cloud)                         | management queue ou index queue haute                    | —          | —        | 🚨 Critical |

---

## Alerte 1 — Dead Letter Queue non vide

**Objectif** : signaler des **logs non indexés pour une cause que Logstash n'a pas
détectée**. Un log applicatif qui n'arrive pas dans les logs consultables
(`logs-prod-default`…) est mis de côté dans un index de diagnostic. Ici, Logstash
l'a traité sans erreur, mais son enregistrement a échoué en fin de pipeline, le
plus souvent refusé par Elasticsearch (par exemple un conflit de mapping). La cause
exacte est dans `logstash.dlq.reason`. Les erreurs que Logstash détecte lui-même
relèvent de l'[alerte 2](#alerte-2--index-erreurs-de-traitement-non-vide).

Session Discover : onglet « Logs non indexés : Échec de process Logstash indéterminé ».

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
> - `metrics-logstash.node-default` — stats nœud : JVM heap, events in/out
> - `metrics-logstash.pipeline-default` — stats pipeline : queue depth, workers, batch
> - `metrics-logstash.plugins-default` — stats plugins : bulk requests ES, erreurs output
> - `metrics-logstash.health_report-default` — état de santé global du nœud
>
> Data view à créer dans Kibana : index pattern `metrics-logstash*`, timestamp `@timestamp`.

### 1a — DLQ prod (Critical)

| Paramètre               | Valeur                                                                                                                                                                                   |
| ----------------------- |------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `Logstash - Prod - Détection présence event dans DLQ`                                                                                                                                    |
| **Type**                | Elasticsearch query rule                                                                                                                                                                 |
| **Index**               | `logs-logstash-dlq-prod-default`                                                                                                                                                         |
| **Condition**           | `Is above` `0`                                                                                                                                                                           |
| **Fenêtre**             | 5 min                                                                                                                                                                                    |
| **Fréquence**           | 1 min                                                                                                                                                                                    |
| **Sévérité**            | Critical                                                                                                                                                                                 |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                               |
| **Action**              | Connecteur Kibana **Mattermost-o11y-production** — voir body ci-dessous                                                                                                            |
| **Related dashboards**  | `[Metrics Logstash] Elasticsearch output plugin info` |
| **Investigation guide** | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue) |

**Body du webhook** (champ "Body" dans l'onglet Message de l'action) :
```json
{
  "text": "🚨 **Logs de prod non indexés : échec de process Logstash indéterminé** — des logs de prod ne sont pas consultables dans Kibana, sans erreur détectée par Logstash.",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)" },
        { "title": "À vérifier", "value": "Le Discover [[Pass Emploi] Logs de Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/97e2d85f-7bd2-49df-86b3-2ffc290bbe69), liste les logs avec le motif de rejet d'Elasticsearch (mapping, document trop gros…)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)" }
      ]
    }
  ]
}
```

### 1b — DLQ staging / perf (Warning)

| Paramètre               | Valeur                                                                                                                                                                                     |
| ----------------------- |--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `Logstash - Hors-Prod - Détection présence event dans DLQ`                                                                                                                                 |
| **Type**                | Elasticsearch query rule                                                                                                                                                                   |
| **Index**               | `logs-logstash-dlq-staging-default,logs-logstash-dlq-perf-default`                                                                                                                         |
| **Condition**           | `Is above` `0`                                                                                                                                                                             |
| **Fenêtre**             | 5 min                                                                                                                                                                                      |
| **Fréquence**           | 5 min                                                                                                                                                                                      |
| **Sévérité**            | Warning                                                                                                                                                                                    |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                 |
| **Action**              | Connecteur Kibana **Mattermost-o11y-staging** — voir body ci-dessous                                                                                                                 |
| **Related dashboards**  | `[Metrics Logstash] Elasticsearch output plugin info` |
| **Investigation guide** | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)   |

**Body du webhook** :
```json
{
  "text": "⚠️ **Logs hors prod non indexés : échec de process Logstash indéterminé** — des logs de staging/perf ne sont pas consultables dans Kibana, sans erreur détectée par Logstash.",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)" },
        { "title": "À vérifier", "value": "Le Discover [[Pass Emploi] Logs Hors-Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/e5bec6b4-0ae3-47b1-8bb5-2e9bf77493a4), les logs désignent le motif de rejet d'Elasticsearch (mapping, document trop gros…)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)" }
      ]
    }
  ]
}
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

**Objectif** : signaler des **logs non indexés à cause d'une erreur de transformation
que Logstash a détectée**. Un log applicatif qui n'arrive pas dans les logs
consultables est mis de côté dans un index de diagnostic. Ici, Logstash n'a pas
réussi à le mettre au bon format : il l'a marqué (`_mutate_error`,
`_jsonparsefailure`, `_rubyexception`…) et rangé dans `logs-logstash-errors-*`.
Une hausse signale une régression du pipeline de transformation.

Session Discover : onglet « Logs non indexés : Erreur de transformation Logstash ».

### 2a — Erreurs prod (Warning, bilan quotidien)

| Paramètre               | Valeur                                                                                                                                                                                                         |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**           | `Logstash - Prod - Détection erreurs pipeline process`                                                                                                                                                         |
| **Type**                | Elasticsearch query rule                                                                                                                                                                                       |
| **Index**               | `logs-logstash-errors-prod-default`                                                                                                                                                                            |
| **Condition**           | `Is above` `0`                                                                                                                                                                                                 |
| **Fenêtre**             | 24 h                                                                                                                                                                                                           |
| **Fréquence**           | 1 h                                                                                                                                                                                                            |
| **Sévérité**            | Warning                                                                                                                                                                                                        |
| **Notification**        | Une fois par jour : `On check intervals` / `Run when: Query matched`, avec `If alert is generated during timeframe` tous les jours de `09:30` à `10:30` (`Europe/Paris`) (onglet Actions → Settings) |
| **Action**              | Connecteur Kibana **Mattermost-o11y-production** — voir body ci-dessous                                                                                                                                  |
| **Related dashboards**  | — |
| **Investigation guide** | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue) |

Une erreur de transformation perd un log, pas la chaîne : elle se traite dans la
journée, pas à chaud. La règle compte les erreurs des 24 dernières heures à chaque
exécution, et seule l'exécution qui tombe entre 9 h 30 et 10 h 30 notifie : un
message par jour, à l'arrivée de l'équipe, week-end compris (lu le lundi). Kibana
ne planifie pas une règle à heure fixe : c'est la plage horaire de l'action qui
fait ce travail.

**Body du webhook** :
```json
{
  "text": "⚠️ **Logs de prod non indexés : erreur de transformation Logstash — bilan des 24 h** — {{context.value}} logs de prod ne sont pas consultables dans Kibana.",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "À vérifier", "value": "Le Discover [[Pass Emploi] Logs de PROD - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/f10de9e3-0fdd-4761-9d44-bacc96504e17), `tags` et `message` désignent le traitement et le log en échec" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)" }
      ]
    }
  ]
}
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
| **Action**              | Connecteur Kibana **Mattermost-o11y-staging** — voir body ci-dessous                                                                                                                                     |
| **Related dashboards**  | — |
| **Investigation guide** | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue) |

**Body du webhook** :
```json
{
  "text": "⚠️ **Logs hors prod non indexés : erreur de transformation Logstash** — des logs de staging/perf ne sont pas consultables dans Kibana.",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "À vérifier", "value": "Le Discover [[Pass Emploi] Logs Hors-Prod - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/716175ed-b2a0-4fe1-8f9d-1892d04dbe92), `tags` et `message` désignent le traitement et le log en échec" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)" }
      ]
    }
  ]
}
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
| **Action 1 (alerte)**     | Connecteur Kibana **Mattermost-o11y-production** — `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings) — voir body ci-dessous                  |
| **Action 2 (résolution)** | Connecteur Kibana **Mattermost-o11y-production** — `On status changes` / `Run when: Recovered` (onglet Actions → Settings) — voir body ci-dessous                                                    |
| **Related dashboards**    | `[Metrics Logstash] Logstash Overview` |
| **Investigation guide**   | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash) |

**Body du webhook — Action 1 (alerte)** :
```json
{
  "text": "🚨 **Silence Logstash** — aucun log dans `logs-prod-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)" },
        { "title": "Dashboard", "value": "[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)" }
      ]
    }
  ]
}
```

**Body du webhook — Action 2 (résolution)** :
```json
{
  "text": "✅ **Silence Logstash résolu** — les logs sont revenus dans `logs-prod-default`.",
  "attachments": [
    {
      "color": "#2eb886",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Résolue à", "value": "`{{date}}`", "short": true }
      ]
    }
  ]
}
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
| **Action 1 (alerte)**     | Connecteur Kibana **Mattermost-o11y-production** — `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings) — voir body ci-dessous                  |
| **Action 2 (résolution)** | Connecteur Kibana **Mattermost-o11y-production** — `On status changes` / `Run when: Recovered` (onglet Actions → Settings) — voir body ci-dessous                                                    |
| **Related dashboards**    | `[Metrics Logstash] Logstash Overview` |
| **Investigation guide**   | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash) |

**Body du webhook — Action 1 (alerte)** :
```json
{
  "text": "🚨 **Silence Logstash** — aucun log router dans `logs-router-prod-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)" },
        { "title": "Dashboard", "value": "[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)" }
      ]
    }
  ]
}
```

**Body du webhook — Action 2 (résolution)** :
```json
{
  "text": "✅ **Silence Logstash résolu** — les logs router sont revenus dans `logs-router-prod-default`.",
  "attachments": [
    {
      "color": "#2eb886",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Résolue à", "value": "`{{date}}`", "short": true }
      ]
    }
  ]
}
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
| **Action**              | Connecteur Kibana **Mattermost-o11y-staging** — voir body ci-dessous                                                                                                                                  |
| **Related dashboards**  | `[Metrics Logstash] Logstash Overview` |
| **Investigation guide** | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash) |

**Body du webhook** :
```json
{
  "text": "⚠️ **Silence Logstash** — aucun log dans `logs-staging-default` ou `logs-perf-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)" },
        { "title": "Dashboard", "value": "[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)" }
      ]
    }
  ]
}
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
| **Action**              | Connecteur Kibana **Mattermost-o11y-staging** — voir body ci-dessous                                                                                                                                  |
| **Related dashboards**  | `[Metrics Logstash] Logstash Overview` |
| **Investigation guide** | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash) |

**Body du webhook** :
```json
{
  "text": "⚠️ **Silence Logstash** — aucun log router dans `logs-router-staging-default` ou `logs-router-perf-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)" },
        { "title": "Dashboard", "value": "[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)" }
      ]
    }
  ]
}
```

> **Corrélation** : si les deux alertes (3a+3b ou 3c+3d) se déclenchent simultanément,
> c'est un crash Logstash ou un arrêt de l'app Scalingo. Si seulement l'alerte
> applicatifs se déclenche (router continue), c'est une quarantaine du drain applicatif.

---

## Alerte 4 — Backpressure (inputs bloqués sur la queue)

**Objectif** : détecter un pipeline qui n'absorbe plus son entrée **avant** que des
logs ne se perdent. `queue_backpressure.current` mesure le temps que les **inputs**
passent bloqués à pousser dans la queue mémoire du pipeline, faute de workers
disponibles. La valeur **se cumule sur les threads d'input** : elle va de 0 au nombre
de threads, soit 4 sur `ingest` (`LOGSTASH_INGEST_THREADS`) et 1 sur `process`
(un seul input Redis). Il monte dès que l'aval ralentit (ES pour `process`, Redis
pour `ingest`).

**Seul `ingest` est alerté** : c'est son input HTTP qui répond au drain Scalingo, et
un drain qui attend finit en quarantaine. Sur `process`, l'input Redis bloqué est
attendu : Redis absorbe, et un backlog qui ne se vide pas relève de l'alerte 7.

> **Champ surveillé** : `logstash.pipeline.total.flow.queue_backpressure.current`
> dans le data stream `metrics-logstash.pipeline-default`.
>
> **Calcul par nœud** (`Grouped over` `logstash.pipeline.host.name`) : sans
> regroupement, la règle prend un seul minimum sur tous les conteneurs `ingest`,
> et un conteneur bloqué passe inaperçu tant qu'un autre ne l'est pas.
>
> **Seuil : minimum ≥ 1 sur 15 min** (mesuré sur la prod, 30 jours au 02/10/2026).
> Par tranche de 5 min, le maximum ne distingue rien : sur `ingest`, p95 3,28, p99 et
> max à 4, avec 18 % des tranches au-dessus de 0.5. Ce sont des à-coups de quelques
> secondes. Le minimum sur 15 min, lui, est bimodal : p99 à 0,009, et les seules
> tranches au-dessus de 1 (22 sur 2 805) sont aussi à 4, soit les 4 threads bloqués
> en continu. Le seuil de 1, un thread bloqué en permanence, ne retient que ces cas.
>
> Ces 22 tranches tombent toutes sur des incidents : les après-midi des 03/09, 07/09
> et 08/09, puis la nuit du 14 au 15/09 (de 20 h 45 à 8 h 30), après le crash de Redis.
> Aucun faux positif sur la période.
>
> Les rejets du drain (429/499) ne sont pas observables dans Kibana : les router logs
> des apps Logstash ne sont pas drainés vers ES. Pour les voir, passer par les logs
> Scalingo de l'app (cf. [runbook](../runbooks/runbook-logstash.md#playbook-de-diagnostic-de-lingestion)).
>
> **Indicateur de diagnostic complémentaire** (non alerté) :
> `logstash.pipeline.total.queues.events` — nombre d'events en attente dans la queue.
> À consulter dans le dashboard `[Metrics Logstash] Pipelines Overview` pour
> confirmer l'accumulation une fois l'alerte déclenchée.

### 4a — Backpressure prod (Critical)

| Paramètre                 | Valeur                                                                                                                                                                                                   |
|---------------------------| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**             | `Logstash - Prod - Détection backpressure ingest (inputs bloqués)`                                                                                                                                       |
| **Type**                  | Elasticsearch query rule                                                                                                                                                                                 |
| **Index**                 | `metrics-logstash.pipeline-default`                                                                                                                                                                      |
| **KQL filter**            | `logstash.pipeline.name: ingest and logstash.pipeline.host.name: pass-emploi-logstash-prod-*`                                                                                                            |
| **Aggregation**           | `Min` de `logstash.pipeline.total.flow.queue_backpressure.current`                                                                                                                                       |
| **Regroupement**          | `Grouped over` `top 10` de `logstash.pipeline.host.name` : un calcul par nœud                                                                                                                             |
| **Condition**             | `Is above or equals` `1`                                                                                                                                                                                 |
| **Fenêtre**               | 15 min                                                                                                                                                                                                   |
| **Fréquence**             | 2 min                                                                                                                                                                                                    |
| **Sévérité**              | Critical                                                                                                                                                                                                 |
| **Action 1 (alerte)**     | Connecteur Kibana **Mattermost-o11y-production** — `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings) — voir body ci-dessous               |
| **Action 2 (résolution)** | Connecteur Kibana **Mattermost-o11y-production** — `On status changes` / `Run when: Recovered` (onglet Actions → Settings) — voir body ci-dessous                                               |
| **Related dashboards**    | `[Metrics Logstash] Logstash Single Pipeline View`, `[Metrics Logstash] Input plugin Info`, `[Metrics Logstash] Output plugin info` |
| **Investigation guide**   | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-1--backpressure-elasticsearch) |

**Body du webhook — Action 1 (alerte)** :
```json
{
  "text": "🚨 **Backpressure Logstash prod** — le pipeline `ingest` a au moins un thread HTTP bloqué en continu depuis 15 min (`queue_backpressure ≥ 1`) : l'écriture dans Redis ne suit plus, le drain Scalingo attend.",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Nœud", "value": "`{{context.group}}`", "short": true },
        { "title": "À vérifier", "value": "Le statut et la mémoire de Redis dans le dashboard Scalingo, puis le temps d'écriture de l'output `redis` dans Output plugin info" },
        { "title": "Dashboard", "value": "[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-1--backpressure-elasticsearch)" }
      ]
    }
  ]
}
```

**Body du webhook — Action 2 (résolution)** :
```json
{
  "text": "✅ **Backpressure Logstash prod résolue** — le pipeline `ingest` n'a plus de thread bloqué en continu.",
  "attachments": [
    {
      "color": "#2eb886",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Résolue à", "value": "`{{date}}`", "short": true }
      ]
    }
  ]
}
```

### 4b — Backpressure staging / perf (Warning)

| Paramètre               | Valeur                                                                                                                                                                                                   |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule name**           | `Logstash - Hors-Prod - Détection backpressure ingest (inputs bloqués)`                                                                                                                                  |
| **Type**                | Elasticsearch query rule                                                                                                                                                                                 |
| **Index**               | `metrics-logstash.pipeline-default`                                                                                                                                                                      |
| **KQL filter**          | `logstash.pipeline.name: ingest and logstash.pipeline.host.name: (pass-emploi-logstash-staging-* OR pass-emploi-logstash-perf-*)`                                                                        |
| **Aggregation**         | `Min` de `logstash.pipeline.total.flow.queue_backpressure.current`                                                                                                                                       |
| **Regroupement**        | `Grouped over` `top 10` de `logstash.pipeline.host.name` : un calcul par nœud                                                                                                                             |
| **Condition**           | `Is above or equals` `1`                                                                                                                                                                                 |
| **Fenêtre**             | 15 min                                                                                                                                                                                                   |
| **Fréquence**           | 5 min                                                                                                                                                                                                    |
| **Sévérité**            | Warning                                                                                                                                                                                                  |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                                                         |
| **Action**              | Connecteur Kibana **Mattermost-o11y-staging** — voir body ci-dessous                                                                                                                               |
| **Related dashboards**  | `[Metrics Logstash] Logstash Single Pipeline View`, `[Metrics Logstash] Input plugin Info`, `[Metrics Logstash] Output plugin info` |
| **Investigation guide** | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-1--backpressure-elasticsearch) |

**Body du webhook** :
```json
{
  "text": "⚠️ **Backpressure Logstash staging/perf** — le pipeline `ingest` a au moins un thread HTTP bloqué en continu depuis 15 min (`queue_backpressure ≥ 1`).",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Nœud", "value": "`{{context.group}}`", "short": true },
        { "title": "Dashboard", "value": "[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-1--backpressure-elasticsearch)" }
      ]
    }
  ]
}
```

---

## Alerte 5 — Heap JVM élevé (risque GC agressif)

**Objectif** : détecter un heap JVM Logstash que le GC n'arrive plus à libérer, signe
de pauses stop-the-world (scénario 2 du runbook) puis d'un `OutOfMemoryError`. La
mémoire totale du conteneur, qui déclenche l'OOM-kill Scalingo, n'est pas couverte
ici : c'est l'[alerte 9](#alerte-9--mémoire-du-conteneur-logstash-oom-kill-scalingo).

> **Champ surveillé** : `logstash.node.stats.jvm.mem.heap_used_percent`
> dans le data stream `metrics-logstash.node-default`.
>
> **Seuil : minimum ≥ 90 % sur 15 min** (mesuré sur la prod, 30 jours au 02/10/2026).
> Avec `-Xmx256m`, le heap monte à 93 % avant chaque GC (médiane du maximum par
> tranche de 15 min), sur `ingest` comme sur `process` : un seuil sur le maximum
> sonnerait en permanence. Le minimum, c'est-à-dire ce qui reste après le GC, ne
> dépasse jamais 84 % (p99 83 % sur `process`, 82 % sur `ingest`). À 90 %, le GC
> ne libère plus que 10 % d'un heap de 256 Mo.
>
> **Calcul par nœud** (`Grouped over` `host.name`) : sans regroupement, la règle
> prend un seul minimum sur tous les nœuds prod, `ingest` et `process`
> confondus ; un nœud saturé passe inaperçu tant qu'un autre respire.
> Vérifié nœud par nœud sur 7 jours au 05/10/2026 : aucune tranche de 15 min
> au-dessus de 90 %, mais le minimum de `process-prod-worker-2` est monté à
> 89 %. Marge mince, à surveiller.

### 5a — Heap élevé prod (Critical)

| Paramètre               | Valeur                                                                                                                                                                   |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Rule name**           | `Logstash - Prod - Détection heap JVM élevé`                                                                                                                             |
| **Type**                | Elasticsearch query rule                                                                                                                                                 |
| **Index**               | `metrics-logstash.node-default`                                                                                                                                          |
| **KQL filter**          | `host.name: (pass-emploi-logstash-prod-* OR pass-emploi-logstash-process-prod-*)`                                                                                        |
| **Aggregation**         | `Min` de `logstash.node.stats.jvm.mem.heap_used_percent`                                                                                                                 |
| **Regroupement**        | `Grouped over` `top 10` de `host.name` : un calcul par nœud                                                                                                               |
| **Condition**           | `Is above or equals` `90`                                                                                                                                                 |
| **Fenêtre**             | 15 min                                                                                                                                                                   |
| **Fréquence**           | 2 min                                                                                                                                                                    |
| **Sévérité**            | Critical                                                                                                                                                                 |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                         |
| **Action**              | Connecteur Kibana **Mattermost-o11y-production** — voir body ci-dessous                                                                                            |
| **Related dashboards**  | `[Metrics Logstash] Single Node Overview` |
| **Investigation guide** | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-2--gel-gc-jvm) |

**Body du webhook** :
```json
{
  "text": "🚨 **Heap JVM Logstash prod** — le heap reste au-dessus de 90 % depuis 15 min : le GC ne libère plus, pauses stop-the-world et `OutOfMemoryError` en vue.",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Nœud", "value": "`{{context.group}}`", "short": true },
        { "title": "À vérifier", "value": "`LS_JAVA_OPTS` : doit être `-Xms256m -Xmx256m`" },
        { "title": "Dashboard", "value": "[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Single Node Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9d450b10-4680-11ee-9ddc-919f87fe352d)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-2--gel-gc-jvm)" }
      ]
    }
  ]
}
```

### 5b — Heap élevé staging / perf (Warning)

| Paramètre               | Valeur                                                                                                                                                                   |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Rule name**           | `Logstash - Hors-Prod - Détection heap JVM élevé`                                                                                                                        |
| **Type**                | Elasticsearch query rule                                                                                                                                                 |
| **Index**               | `metrics-logstash.node-default`                                                                                                                                          |
| **KQL filter**          | `host.name: (pass-emploi-logstash-staging-* OR pass-emploi-logstash-process-staging-* OR pass-emploi-logstash-perf-* OR pass-emploi-logstash-process-perf-*)`                                                                                             |
| **Aggregation**         | `Min` de `logstash.node.stats.jvm.mem.heap_used_percent`                                                                                                                 |
| **Regroupement**        | `Grouped over` `top 10` de `host.name` : un calcul par nœud                                                                                                               |
| **Condition**           | `Is above or equals` `90`                                                                                                                                                 |
| **Fenêtre**             | 15 min                                                                                                                                                                   |
| **Fréquence**           | 5 min                                                                                                                                                                    |
| **Sévérité**            | Warning                                                                                                                                                                  |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                         |
| **Action**              | Connecteur Kibana **Mattermost-o11y-staging** — voir body ci-dessous                                                                                               |
| **Related dashboards**  | `[Metrics Logstash] Single Node Overview` |
| **Investigation guide** | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-2--gel-gc-jvm) |

**Body du webhook** :
```json
{
  "text": "⚠️ **Heap JVM Logstash staging/perf** — le heap reste au-dessus de 90 % depuis 15 min : le GC ne libère plus.",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Nœud", "value": "`{{context.group}}`", "short": true },
        { "title": "Dashboard", "value": "[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Single Node Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9d450b10-4680-11ee-9ddc-919f87fe352d)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-2--gel-gc-jvm)" }
      ]
    }
  ]
}
```

---

## Alerte 6 — Restart du conteneur Logstash (Scalingo webhook)

**Objectif** : être alerté d'un restart du conteneur Logstash (OOM-kill ou crash).

**Configuration dans le dashboard Scalingo** (hors repo — action manuelle) :

Répéter l'opération pour chaque app Logstash :

| App Scalingo                           | Canal Mattermost   |
| -------------------------------------- | ------------------ |
| `pass-emploi-logstash-prod`            | `#o11y-production` |
| `pass-emploi-logstash-process-prod`    | `#o11y-production` |
| `pass-emploi-logstash-staging`         | `#o11y-staging`    |
| `pass-emploi-logstash-process-staging` | `#o11y-staging`    |
| `pass-emploi-logstash-perf`            | `#o11y-staging`    |
| `pass-emploi-logstash-process-perf`    | `#o11y-staging`    |

Pour chaque app :

1. Aller sur l'app dans le dashboard Scalingo.
2. **Settings → Notifications → Add notification**.
3. Choisir le type **Webhook**.
4. Événements à surveiller : `app_restarted`, `app_crashed_repeated`, `app_stopped`.
   Pas `app_crashed` : Scalingo ne l'envoie qu'aux 2ᵉ, 5ᵉ et 12ᵉ crashs ;
   `app_crashed_repeated` part à chaque crash.
5. URL du webhook : URL du webhook entrant Mattermost du canal correspondant.

> **Note** : le throttle ne s'applique pas aux webhooks Scalingo — chaque événement
> `app_crashed_repeated` / `app_restarted` est une notification unitaire envoyée par Scalingo.

**Payload Scalingo** (exemple pour un restart OOM) :
```json
{
  "app": { "name": "pass-emploi-logstash-prod" },
  "event_type": "app_crashed_repeated",
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
et la liste se vide en quelques minutes, même après les pics de :00 et :30 (cf.
seuil ci-dessous). Un backlog durable signale que le pipeline `process` ne consomme plus Redis : redémarrage ou blocage
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
> **Seuil : minimum > 1 000 sur 15 min** (mesuré sur la prod du 14/09 au
> 30/09/2026, par tranche de 5 min). En nominal, la liste fait le yo-yo : p50 77,
> p95 1 875, p99 11 606. Les pics tombent les jours ouvrés, de 8 h 30 à 17 h,
> presque tous à :00 ou :30, avec une médiane de 5 259 et un p90 de 14 095, et
> se vident dans la tranche de 5 min. Un `Max` déclenche donc chaque demi-heure.
> Le `Min` ne retient que la liste qui ne redescend pas : sur la période, seul
> l'incident du 14/09 (90 min, jusqu'à 180 799) et le 21/09 à 10 h 50 (15 min,
> 11 500) y passent. L'alerte part 15 à 17 min après le début de la coupure ;
> le 14/09, la saturation est arrivée ~1 h 20 après.

### 7a — Backlog Redis prod (Critical)

| Paramètre                 | Valeur                                                                                                                                                                                     |
|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Rule name**             | `Redis - Prod - Backlog logstash:ingest anormal`                                                                                                                                           |
| **Type**                  | Elasticsearch query rule                                                                                                                                                                   |
| **Index**                 | `metrics-redis.key-default`                                                                                                                                                                |
| **KQL filter**            | `redis.key.name: "logstash:ingest" and agent.name: pass-emploi-elastic-agent-prod-*`                                                                                                       |
| **Aggregation**           | `Min` de `redis.key.length`                                                                                                                                                                |
| **Condition**             | `Is above` `1000`                                                                                                                                                                         |
| **Fenêtre**               | 15 min                                                                                                                                                                                     |
| **Fréquence**             | 2 min                                                                                                                                                                                      |
| **Sévérité**              | Critical                                                                                                                                                                                   |
| **Action 1 (alerte)**     | Connecteur Kibana **Mattermost-o11y-production** — `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings) — voir body ci-dessous |
| **Action 2 (résolution)** | Connecteur Kibana **Mattermost-o11y-production** — `On status changes` / `Run when: Recovered` (onglet Actions → Settings) — voir body ci-dessous                                    |
| **Related dashboards**    | `[Metrics Redis] Keys`, `[Metrics Logstash] Logstash Single Pipeline View`, `[Metrics Logstash] Elasticsearch output plugin info` |
| **Investigation guide**   | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-5--backlog-redis-logstashingest) |

**Body du webhook — Action 1 (alerte)** :
```json
{
  "text": "🚨 **Backlog Redis prod** — la liste `logstash:ingest` reste au-dessus de 1 000 événements depuis 15 min. Le pipeline `process` ne consomme plus Redis (redémarrage ou blocage de `pass-emploi-logstash-process-prod`, ou backpressure ES sévère).",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "À vérifier", "value": "Les logs de `pass-emploi-logstash-process-prod` sur Scalingo" },
        { "title": "À vérifier", "value": "Le statut Redis dans le dashboard Scalingo" },
        { "title": "Dashboard", "value": "[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)" },
        { "title": "Dashboard", "value": "[[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-5--backlog-redis-logstashingest)" }
      ]
    }
  ]
}
```

**Body du webhook — Action 2 (résolution)** :
```json
{
  "text": "✅ **Backlog Redis prod résorbé** — la liste `logstash:ingest` est redescendue sous 1 000 événements. Le pipeline `process` a reconnecté et vide le backlog.",
  "attachments": [
    {
      "color": "#2eb886",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Résolue à", "value": "`{{date}}`", "short": true },
        { "title": "⚠️ Attention", "value": "Les logs accumulés pendant la coupure vont apparaître dans Kibana avec un timestamp d'origine — vérifier l'absence de trou dans les index `logs-prod-default` et `logs-router-prod-default`" }
      ]
    }
  ]
}
```

### 7b — Backlog Redis staging / perf (Warning)

| Paramètre               | Valeur                                                                                                          |
|-------------------------|-----------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `Redis - Hors-Prod - Backlog logstash:ingest anormal`                                                           |
| **Type**                | Elasticsearch query rule                                                                                        |
| **Index**               | `metrics-redis.key-default`                                                                                     |
| **KQL filter**          | `redis.key.name: "logstash:ingest" and agent.name: (pass-emploi-elastic-agent-staging-* or pass-emploi-elastic-agent-perf-*)` |
| **Aggregation**         | `Min` de `redis.key.length`                                                                                     |
| **Condition**           | `Is above` `1000`                                                                                              |
| **Fenêtre**             | 15 min                                                                                                          |
| **Fréquence**           | 5 min                                                                                                           |
| **Sévérité**            | Warning                                                                                                         |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)      |
| **Action**              | Connecteur Kibana **Mattermost-o11y-staging** — voir body ci-dessous                                                                                                                                                    |
| **Related dashboards**  | `[Metrics Redis] Keys`, `[Metrics Logstash] Logstash Single Pipeline View`, `[Metrics Logstash] Elasticsearch output plugin info` |
| **Investigation guide** | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-5--backlog-redis-logstashingest) |

**Body du webhook** :
```json
{
  "text": "⚠️ **Backlog Redis staging/perf** — la liste `logstash:ingest` reste au-dessus de 1 000 événements depuis 15 min. Le pipeline `process` ne consomme plus Redis.",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "À vérifier", "value": "Les logs de `pass-emploi-logstash-process-staging` / `pass-emploi-logstash-process-perf` sur Scalingo" },
        { "title": "Dashboard", "value": "[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)" },
        { "title": "Dashboard", "value": "[[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)" },
        { "title": "Dashboard", "value": "[[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-5--backlog-redis-logstashingest)" }
      ]
    }
  ]
}
```

---

## Alerte 8 — Elastic Agent en défaut

**Objectif** : détecter qu'un Elastic Agent a décroché, quelle qu'en soit la
forme. Un agent en défaut, c'est une **supervision aveugle** : les alertes 4, 5
et 7 lisent ses métriques et ne peuvent plus se déclencher — le silence d'un
agent ressemble à une infra saine. Contexte :
[pilotage.md](../pilotage.md#savoir-quun-agent-a-décroché).

| Défaut détecté                                                                                                                 | Signal                                 | Source                                     |
|--------------------------------------------------------------------------------------------------------------------------------|----------------------------------------|--------------------------------------------|
| **offline** — ne contacte plus Fleet Server depuis 5 min (seuil fixe Fleet)                                                    | `health_status == "offline"`           | `logs-elastic_agent.status_change-default` |
| **unenrolled** — retiré de Fleet ([post-mortem du 11/09/2026](../post-mortems/postmortem-2026-09-unenrolled-elastic-agent.md)) | `health_status == "unenrolled"`        | idem                                       |
| **unhealthy** — tourne, mais un composant est en erreur ou dégradé                                                             | `health_status == "unhealthy"`         | idem                                       |
| **erreurs d'output** — tourne, mais ses écritures vers ES échouent (peut rester `Healthy`)                                     | > 25 erreurs d'écriture sur la fenêtre | `metrics-elastic_agent.*beat-*`            |

> **Règle maison, reprise des règles natives Fleet.** Elle regroupe en une
> requête les modèles `[Elastic Agent] Offline status`, `Unenrolled status`,
> `Unhealthy status` et `Output errors` livrés depuis la 9.2
> ([doc Elastic](https://www.elastic.co/docs/reference/fleet/alert-templates)) —
> deux règles au lieu de huit, le filtre d'environnement écrit une seule fois.
> Le seuil reprend celui du modèle : > 5 erreurs d'output/min (soit 25 sur la
> fenêtre). Le modèle `Restarts` n'est pas repris : il compte le message
> `Starting…elastic-agent…`, de niveau INFO, que nos agents (logging level
> WARNING) n'envoient pas. Les exclusions `agentless` des
> modèles sont inutiles ici : le filtre d'environnement les écarte déjà.
> **Requête testée le 2026-09-30** sur perf (filtre `"*-perf-*"`, 30 j) : les 8
> agents perf remontent en `offline` / `unhealthy` / `unenrolled`. La branche
> erreurs d'output n'a pu être vérifiée qu'à vide (0 erreur sur la période).
>
> **Filtre d'environnement obligatoire** : les agents perf sont **volontairement
> désactivés** (réduction des coûts d'infra) mais restent enrôlés — sans filtre,
> chaque arrêt de perf déclenche l'alerte. Perf n'a **pas** de règle. Le
> discriminant est le hostname Scalingo, dérivé du nom de l'app
> (`pass-emploi-{logstash,logstash-process,elastic-agent}-<env>-{web,worker}-<n>`),
> porté par `hostname` dans le journal de statut et par `agent.name` dans les
> métriques d'agent — d'où le `COALESCE` (vérifié le 2026-09-30). L'ordre compte : le journal de statut porte aussi un `host.name`,
> qui ne désigne pas forcément l'agent — `hostname` doit rester en tête.
> Toute nouvelle app agent doit respecter
> ce nommage `…-<env>-…`, sinon elle échappe à l'alerte.
>
> **Deux `STATS`** : le compteur `output.write.errors` est cumulatif **par
> composant** ; le delta max − min se calcule par composant avant d'être agrégé
> par agent, sinon on soustrairait les compteurs de deux composants différents.
> Un redémarrage remet le compteur à 0 : si l'agent avait des erreurs avant, le
> delta peut déclencher une fois.
>
> **Transition, pas état** : les statuts viennent du **journal des changements
> de statut** (un document par agent et par transition). La règle se déclenche
> sur la transition puis passe `Recovered` au bout de la fenêtre, **même si
> l'agent est toujours en défaut** — d'où l'absence de message de résolution.
> L'état courant se lit dans Kibana → Fleet → Agents.

### 8a — Elastic Agent en défaut prod (Critical)

| Paramètre                 | Valeur                                                                                                                                                                                                                                                                                                         |
|---------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Rule name**             | `Elastic Agent - Prod - Agent en défaut`                                                                                                                                                                                                                                                                       |
| **Type**                  | Elasticsearch query rule (ES\|QL)                                                                                                                                                                                                                                                                              |
| **Requête ES\|QL**        | voir ci-dessous — l'alerte part dès qu'elle renvoie au moins une ligne (une par agent en défaut)                                                                                                                                                                                                               |
| **Fenêtre**               | 5 min                                                                                                                                                                                                                                                                                                          |
| **Fréquence**             | 1 min                                                                                                                                                                                                                                                                                                          |
| **Sévérité**              | Critical                                                                                                                                                                                                                                                                                                       |
| **Action 1 (alerte)**     | Connecteur Kibana **Mattermost-o11y-production** — `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings) — voir body ci-dessous                                                                                                                     |
| **Action 2 (résolution)** | **Aucune** — voir note « Transition, pas état » ci-dessus                                                                                                                                                                                                                                                      |
| **Related dashboards**    | `[Elastic Agent] Concerning Agents`, `[Elastic Agent] Overview`, `[Elastic Agent] Agent metrics` |
| **Investigation guide**   | Voir [pilotage des agents](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/pilotage.md) et [post-mortem — agent UNENROLLED](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/post-mortems/postmortem-2026-09-unenrolled-elastic-agent.md) |

**Requête ES|QL** :
```
FROM logs-elastic_agent.status_change-default, metrics-elastic_agent.*beat-*
| EVAL host = COALESCE(hostname, agent.name)
| WHERE host LIKE "*-prod-*"
| WHERE health_status IN ("offline", "unenrolled", "unhealthy")
     OR beat.stats.libbeat.output.write.errors IS NOT NULL
| STATS statuts = VALUES(health_status),
        erreurs = MAX(TO_LONG(beat.stats.libbeat.output.write.errors))
                - MIN(TO_LONG(beat.stats.libbeat.output.write.errors))
  BY host, component.id
| STATS statuts = VALUES(statuts), erreurs_output = MAX(erreurs) BY host
| WHERE statuts IS NOT NULL OR erreurs_output > 25
```

**Body du webhook — Action 1 (alerte)** :
```json
{
  "text": "🚨 **Elastic Agent en défaut — prod** — les alertes Logstash/Redis (4, 5, 7) peuvent être aveugles.",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Détail", "value": "{{context.message}}" },
        { "title": "offline", "value": "vérifier l'app Scalingo (conteneur arrêté, restart)" },
        { "title": "unenrolled", "value": "cas du post-mortem du 11/09 → `ELASTIC_AGENT_ID_SUFFIX`" },
        { "title": "unhealthy / erreurs d'output", "value": "Kibana → Fleet → Agents → composants en erreur, output ES de la policy" },
        { "title": "Dashboard", "value": "[[Elastic Agent] Concerning Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824)" },
        { "title": "Dashboard", "value": "[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)" },
        { "title": "Dashboard", "value": "[[Elastic Agent] Agent metrics](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395)" },
        { "title": "Fleet", "value": "[Fleet → Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/fleet/agents)" },
        { "title": "Doc", "value": "[Pilotage des agents](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/pilotage.md)" }
      ]
    }
  ]
}
```

### 8b — Elastic Agent en défaut staging (Warning)

| Paramètre               | Valeur                                                                                                                                                                                                                                                                                                         |
|-------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `Elastic Agent - Staging - Agent en défaut`                                                                                                                                                                                                                                                                    |
| **Type**                | Elasticsearch query rule (ES\|QL)                                                                                                                                                                                                                                                                              |
| **Requête ES\|QL**      | voir ci-dessous — l'alerte part dès qu'elle renvoie au moins une ligne (une par agent en défaut)                                                                                                                                                                                                               |
| **Fenêtre**             | 5 min                                                                                                                                                                                                                                                                                                          |
| **Fréquence**           | 1 min                                                                                                                                                                                                                                                                                                          |
| **Sévérité**            | Warning                                                                                                                                                                                                                                                                                                        |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                                                                                                                                                                     |
| **Action**              | Connecteur Kibana **Mattermost-o11y-staging** — voir body ci-dessous                                                                                                                                                                                                                                     |
| **Related dashboards**  | `[Elastic Agent] Concerning Agents`, `[Elastic Agent] Overview`, `[Elastic Agent] Agent metrics` |
| **Investigation guide** | Voir [pilotage des agents](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/pilotage.md) et [post-mortem — agent UNENROLLED](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/post-mortems/postmortem-2026-09-unenrolled-elastic-agent.md) |

**Requête ES|QL** :
```
FROM logs-elastic_agent.status_change-default, metrics-elastic_agent.*beat-*
| EVAL host = COALESCE(hostname, agent.name)
| WHERE host LIKE "*-staging-*"
| WHERE health_status IN ("offline", "unenrolled", "unhealthy")
     OR beat.stats.libbeat.output.write.errors IS NOT NULL
| STATS statuts = VALUES(health_status),
        erreurs = MAX(TO_LONG(beat.stats.libbeat.output.write.errors))
                - MIN(TO_LONG(beat.stats.libbeat.output.write.errors))
  BY host, component.id
| STATS statuts = VALUES(statuts), erreurs_output = MAX(erreurs) BY host
| WHERE statuts IS NOT NULL OR erreurs_output > 25
```

**Body du webhook** :
```json
{
  "text": "⚠️ **Elastic Agent en défaut — staging** — les alertes Logstash/Redis (4, 5, 7) peuvent être aveugles.",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Détail", "value": "{{context.message}}" },
        { "title": "offline", "value": "vérifier l'app Scalingo (conteneur arrêté, restart)" },
        { "title": "unenrolled", "value": "cas du post-mortem du 11/09 → `ELASTIC_AGENT_ID_SUFFIX`" },
        { "title": "unhealthy / erreurs d'output", "value": "Kibana → Fleet → Agents → composants en erreur, output ES de la policy" },
        { "title": "Dashboard", "value": "[[Elastic Agent] Concerning Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824)" },
        { "title": "Dashboard", "value": "[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)" },
        { "title": "Dashboard", "value": "[[Elastic Agent] Agent metrics](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395)" },
        { "title": "Fleet", "value": "[Fleet → Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/fleet/agents)" },
        { "title": "Doc", "value": "[Pilotage des agents](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/pilotage.md)" }
      ]
    }
  ]
}
```

---

## Alerte 9 — Mémoire du conteneur Logstash (OOM-kill Scalingo)

**Objectif** : prévenir avant que Scalingo ne tue un conteneur Logstash qui atteint
sa limite mémoire. L'OOM-kill provoque les redémarrages en série (alerte 6, qui
arrive après coup) et, sur `ingest`, la quarantaine du drain. L'alerte 5 ne voit
que le heap : le reste de la mémoire du process (Netty, JRuby, metaspace, threads)
et l'Elastic Agent co-localisé lui échappent (cf.
[garde-fous JVM / Scalingo](../infrastructure.md#garde-fous-jvm--scalingo)).

> **Source** : data stream `logs-scalingo.container_stats-default`, alimenté
> chaque minute par l'API Scalingo (intégration Custom API de l'agent dédié, cf.
> [collecte](../collecte/metriques/stack-observabilite.md)). Champ :
> `scalingo.memory.pct` (utilisation / limite, de 0 à 1).
>
> **Seuil : maximum ≥ 95 % sur 5 min, par conteneur**. Mesuré du 02/10/2026
> à 19 h (début de la collecte) au 05/10/2026, par tranche de 5 min : `ingest`
> plafonne à 78 % (p99 77,9 %) ; `process` monte plus haut, p99 89,6 % et
> maximum 92,8 % sur `worker-2`. À 95 %, il reste ~100 Mo sur 2 Go avant le kill.
> Le `Max` et non le `Min` : la mémoire d'un conteneur Logstash est quasi plate,
> et un pic suffit à le tuer. **Seuil à recaler sur 30 jours de données**
> (début novembre 2026).

### 9a — Mémoire conteneur prod (Critical)

| Paramètre                 | Valeur                                                                                                                                                                                     |
|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Rule name**             | `Logstash - Prod - Mémoire conteneur proche de la limite Scalingo`                                                                                                                         |
| **Type**                  | Elasticsearch query rule                                                                                                                                                                   |
| **Index**                 | `logs-scalingo.container_stats-default`                                                                                                                                                    |
| **KQL filter**            | `scalingo.app: (pass-emploi-logstash-prod or pass-emploi-logstash-process-prod)`                                                                                                           |
| **Aggregation**           | `Max` de `scalingo.memory.pct`                                                                                                                                                             |
| **Regroupement**          | `Grouped over` `top 10` de `host.name` : un calcul par conteneur                                                                                                                           |
| **Condition**             | `Is above or equals` `0.95`                                                                                                                                                                |
| **Fenêtre**               | 5 min                                                                                                                                                                                      |
| **Fréquence**             | 1 min                                                                                                                                                                                      |
| **Sévérité**              | Critical                                                                                                                                                                                   |
| **Action 1 (alerte)**     | Connecteur Kibana **Mattermost-o11y-production** — `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings) — voir body ci-dessous |
| **Action 2 (résolution)** | Connecteur Kibana **Mattermost-o11y-production** — `On status changes` / `Run when: Recovered` (onglet Actions → Settings) — voir body ci-dessous                                    |
| **Related dashboards**    | `[Pass Emploi] Supervision Stack d'Observabilité`                                                                                                                                          |
| **Investigation guide**   | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash) |

**Body du webhook — Action 1 (alerte)** :
```json
{
  "text": "🚨 **Mémoire conteneur Logstash prod** — un conteneur dépasse 95 % de sa limite Scalingo : OOM-kill et redémarrage imminents.",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Conteneur", "value": "`{{context.group}}`", "short": true },
        { "title": "À vérifier", "value": "Le heap (alerte 5) et le backlog Redis (alerte 7) : un `process` qui rattrape un backlog consomme plus. `LS_JAVA_OPTS` doit rester `-Xms256m -Xmx256m`" },
        { "title": "Dashboard", "value": "[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)" }
      ]
    }
  ]
}
```

**Body du webhook — Action 2 (résolution)** :
```json
{
  "text": "✅ **Mémoire conteneur Logstash prod** — tous les conteneurs sont repassés sous 95 % de leur limite.",
  "attachments": [
    {
      "color": "#2eb886",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Résolue à", "value": "`{{date}}`", "short": true }
      ]
    }
  ]
}
```

### 9b — Mémoire conteneur staging / perf (Warning)

| Paramètre               | Valeur                                                                                                                                                                  |
|-------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `Logstash - Hors-Prod - Mémoire conteneur proche de la limite Scalingo`                                                                                                 |
| **Type**                | Elasticsearch query rule                                                                                                                                                |
| **Index**               | `logs-scalingo.container_stats-default`                                                                                                                                 |
| **KQL filter**          | `scalingo.app: (pass-emploi-logstash-staging or pass-emploi-logstash-process-staging or pass-emploi-logstash-perf or pass-emploi-logstash-process-perf)`                |
| **Aggregation**         | `Max` de `scalingo.memory.pct`                                                                                                                                          |
| **Regroupement**        | `Grouped over` `top 10` de `host.name` : un calcul par conteneur                                                                                                        |
| **Condition**           | `Is above or equals` `0.95`                                                                                                                                             |
| **Fenêtre**             | 5 min                                                                                                                                                                   |
| **Fréquence**           | 5 min                                                                                                                                                                   |
| **Sévérité**            | Warning                                                                                                                                                                 |
| **Throttle**            | `On custom action intervals` / `Run every 6 hours` / `Run when: Query matched` (onglet Actions → Settings)                                                              |
| **Action**              | Connecteur Kibana **Mattermost-o11y-staging** — voir body ci-dessous                                                                                                    |
| **Related dashboards**  | `[Pass Emploi] Supervision Stack d'Observabilité`                                                                                                                       |
| **Investigation guide** | Voir [runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash) |

**Body du webhook** :
```json
{
  "text": "⚠️ **Mémoire conteneur Logstash staging/perf** — un conteneur dépasse 95 % de sa limite Scalingo : OOM-kill imminent.",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Conteneur", "value": "`{{context.group}}`", "short": true },
        { "title": "Dashboard", "value": "[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)" },
        { "title": "Runbook", "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)" }
      ]
    }
  ]
}
```

---

## Alerte 10 — ILM en échec ou policy sans suppression

**Objectif** : signaler un index de nos flux qui n'applique pas sa rétention. Soit
une étape ILM a échoué (index bloqué), soit l'index est sur une policy par défaut
d'Elastic, sans phase `delete` : il grossit sans jamais être supprimé. Cas vécu :
les métriques Fleet et les logs Elastic Agent sur `metrics@lifecycle` /
`logs@lifecycle` jusqu'au 2026-10-05, faute des briques `@custom`.

> **Source** : l'historique ILM (data stream caché `ilm-history-7`), une ligne par
> étape exécutée : `index`, `policy`, `success`. ES|QL ne voit ce data stream
> caché que par ses index : `FROM .ds-ilm-history-7-*`.
>
> **Calibrage** (30 jours au 2026-10-06) : 0 étape en échec ; 112 étapes sur
> `metrics@lifecycle` et 17 sur `logs@lifecycle`, toutes antérieures à la
> correction du 2026-10-05. L'alerte aurait sonné dès le premier jour.
>
> **Limite** : un index rattaché à une policy qui n'existe pas n'écrit rien dans
> l'historique et échappe à l'alerte (cf. [runbook ILM, scénario 3](../runbooks/runbook-ilm.md#scénario-3--policy-inexistante-non-alerté)).
>
> **Bilan quotidien** : rien d'urgent, l'index grossit ou attend. Même réglage que
> l'[alerte 2a](#2a--erreurs-prod-warning-bilan-quotidien) : fenêtre de 24 h, un
> message par jour à 9 h 30, un seul pour tous les index concernés.

### 10 — ILM en échec ou policy sans suppression (Warning, bilan quotidien)

| Paramètre               | Valeur                                                                                                                                                                                                         |
|-------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `Elasticsearch - ILM en échec ou policy sans suppression`                                                                                                                                                      |
| **Type**                | Elasticsearch query rule (ES\|QL)                                                                                                                                                                              |
| **Requête ES\|QL**      | voir ci-dessous — l'alerte part dès qu'elle renvoie une ligne                                                                                                                                                  |
| **Fenêtre**             | 24 h                                                                                                                                                                                                           |
| **Fréquence**           | 1 h                                                                                                                                                                                                            |
| **Sévérité**            | Warning                                                                                                                                                                                                        |
| **Notification**        | Une fois par jour : `On check intervals` / `Run when: Query matched`, avec `If alert is generated during timeframe` tous les jours de `09:30` à `10:30` (`Europe/Paris`) (onglet Actions → Settings) |
| **Action**              | Connecteur Kibana **Mattermost-o11y-production** — voir body ci-dessous                                                                                                                                        |
| **Related dashboards**  | — |
| **Investigation guide** | Voir [runbook ILM](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-ilm.md) |

**Requête ES|QL** :
```
FROM .ds-ilm-history-7-*
| WHERE index LIKE "*.ds-logs-*" OR index LIKE "*.ds-metrics-*"
     OR index LIKE "*.ds-traces-*" OR index LIKE "*.ds-heartbeat-*"
| EVAL policy_par_defaut = policy IN ("logs", "metrics", "logs@lifecycle", "metrics@lifecycle", "metricbeat")
                           OR policy LIKE "*-default_policy"
| WHERE success == false OR policy_par_defaut
| STATS index_en_echec = COUNT_DISTINCT(index) WHERE success == false,
        index_policy_par_defaut = COUNT_DISTINCT(index) WHERE policy_par_defaut,
        policies = VALUES(policy), exemples = VALUES(index)
| WHERE index_en_echec > 0 OR index_policy_par_defaut > 0
| EVAL exemples = MV_SLICE(exemples, 0, 9)
```

**Body du webhook** :
```json
{
  "text": "⚠️ **Rétention ILM — bilan des 24 h** — des index n'appliquent pas leur rétention : étape ILM en échec ou policy par défaut sans suppression.",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Détail", "value": "{{context.message}}" },
        { "title": "À vérifier", "value": "Le Discover [[Pass Emploi] Historique ILM - Index hors rétention](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/3f3c69ef-e515-4be4-b679-eff837c92ecb), liste les index concernés. Deux cas : l'index ne sera jamais supprimé (il porte une policy d'Elastic par défaut au lieu de la nôtre), ou ILM est bloqué sur cet index (`success` à `false`)" },
        { "title": "Runbook", "value": "[Runbook ILM](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-ilm.md)" }
      ]
    }
  ]
}
```

---

## Alerte 11 — Disque des nœuds Elasticsearch (AutoOps)

**Objectif** : prévenir avant qu'un nœud Elasticsearch plein ne bloque l'écriture,
et donc l'ingestion de tous les logs. Elasticsearch durcit son comportement en
trois paliers de remplissage (*watermarks*) : 85 % (plus de nouveaux shards),
90 % (des shards quittent le nœud), 95 % (écriture bloquée). Le détail de chaque
palier et quoi faire : [runbook disque](../runbooks/runbook-disque-elasticsearch.md).

> **Pourquoi AutoOps** : il collecte d'office l'état disque des nœuds d'un
> déploiement Elastic Cloud et fournit un événement par palier. Une règle Kibana
> demanderait d'abord de collecter ces métriques : la supervision de la stack
> (`.monitoring-*`) ne tourne pas.
>
> **Configuration hors repo** (console Elastic Cloud → AutoOps → *Notifications
> settings*), comme l'alerte 6 : à refaire à la main sur un nouveau déploiement.
> Le cluster est unique et porte tous les environnements : connecteurs et filtres
> ne sont pas nommés par environnement.
>
> **Nœud frozen** : disque à ~90 % en permanence (cache des searchable snapshots),
> soumis à des seuils à part. Il ne doit pas déclencher ces événements ; à
> vérifier au premier événement reçu (champ « Nœuds concernés »).

### 11 — Configuration dans AutoOps (Critical)

**Événements** : filtre `Disque et santé Elasticsearch` de l'onglet *Filter settings* qui envoie ces 5 événements
du déploiement `Pass Emploi` au connecteur ci-dessous. Un événement garde ses
réglages par défaut tant qu'on ne lui crée pas de réglage personnalisé (*custom
event settings*) : seul le statut red en a un.

| Événement AutoOps | Réglage personnalisé | Déclenchement |
|---|---|---|
| The disk capacity is about to reach low watermark | aucun (défaut : 10 points sous le palier) | 75 %, préavis |
| The low disk watermark has been exceeded | aucun | 85 % |
| The high disk watermark has been exceeded | aucun | 90 % |
| The flood stage disk watermark has been exceeded | aucun | 95 % |
| The cluster status is red | `Minimum duration of the red status` = **300** s (ignore les passages en rouge des maintenances Elastic Cloud) ; exclusions par défaut `partial-*`, `restored-*` conservées (index frozen et restaurés, brièvement rouges au montage) | shard principal indisponible depuis 5 min |

Écartés : *The cluster status is yellow* (une copie de secours manque, à chaque
maintenance Elastic Cloud ; la perte réelle est couverte par le statut red) et
*Your cluster version is outdated* (sans urgence, répété jusqu'à la montée de
version).

> ⚠️ Le réglage « … percent before … watermark » est une **marge en points sous le
> palier**, pas un seuil absolu : 85 sur l'événement flood stage le déclencherait
> à 10 %, en permanence.

**Connecteur** (onglet *Connector settings*) : type **Webhook**, nom
`Mattermost o11y production - Monitoring disque et santé Elasticsearch`, URL du webhook entrant Mattermost de
`#o11y-production` (secret : ne pas la versionner), méthode `POST`, en-tête
`Content-Type: application/json`. Tester avec **Run to test** avant **Save**.

**Body du webhook** :
```json
{
  "text": "🚨 **AutoOps — ${TITLE}** (${SEVERITY}, ${STATUS}) — ${RESOURCE_NAME}",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Détail", "value": "${MESSAGE}" },
        { "title": "Description", "value": "${DESCRIPTION}" },
        { "title": "Nœuds concernés", "value": "${AFFECTED_NODES}", "short": true },
        { "title": "Index concernés", "value": "${AFFECTED_INDICES}", "short": true },
        { "title": "Début", "value": "`${START_TIME}`", "short": true },
        { "title": "Fin", "value": "`${END_TIME}`", "short": true },
        { "title": "À vérifier", "value": "[L'événement dans AutoOps](${EVENT_LINK})" },
        { "title": "Runbook", "value": "[Disque des nœuds Elasticsearch](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-disque-elasticsearch.md)" }
      ]
    }
  ]
}
```

---

## Alerte 12 — Saturation de l'indexation Elasticsearch (AutoOps)

**Objectif** : voir Elasticsearch ralentir **avant** que Logstash ne se bloque.
Quand les files internes d'Elasticsearch saturent, l'indexation ralentit, les
workers `process` de Logstash attendent, puis `ingest` se bloque et le drain
Scalingo part en quarantaine (cause racine de l'incident de juillet 2026, cf.
[runbook Logstash, scénario 1](../runbooks/runbook-logstash.md#scénario-1--backpressure-elasticsearch)).
Cette alerte précède l'[alerte 4](#alerte-4--backpressure-inputs-bloqués-sur-la-queue).

> **Configuration hors repo**, comme l'[alerte 11](#alerte-11--disque-des-nœuds-elasticsearch-autoops) :
> console Elastic Cloud → AutoOps → *Notifications settings*. Connecteur et
> filtre distincts de l'alerte 11, pour que le message pointe vers le bon runbook.
>
> **Écartés** : *Slow search detected* (personne d'autre que l'équipe et nos
> règles n'interroge Elasticsearch, et les recherches sur le frozen sont lentes
> par nature) et *Long running index task* (déclenché par les fusions et
> snapshots d'ILM à chaque passage en frozen).

### 12 — Configuration dans AutoOps (Critical)

**Événements** : filtre `Saturation indexation Elasticsearch` de l'onglet
*Filter settings*, déploiement `Pass Emploi`, vers le connecteur ci-dessous.

| Événement AutoOps | Réglages (par défaut, sans réglage personnalisé) | Ce qu'il signale |
|---|---|---|
| The management queue size is high | `High management queue activity threshold` = 5 ; `How many successive samplings…` = 3 | la file des opérations internes (rollovers, fusions, ILM) sature |
| The index queue is high | `Write queue threshold` = 30 ; `How many successive samplings…` = 3 | la file des écritures d'un nœud n'absorbe plus le flux de Logstash |

Les 3 mesures successives au-dessus du seuil ignorent les montées brèves de ces
files aux pics de logs (:00 et :30). En cas de bruit, augmenter d'abord ce nombre
de mesures (réglage personnalisé), avant de toucher aux seuils.

**Connecteur** (onglet *Connector settings*) : type **Webhook**, nom
`Mattermost o11y production - Monitoring indexation Elasticsearch`, même URL de webhook
entrant que l'alerte 11 (secret : ne pas la versionner), méthode `POST`, en-tête
`Content-Type: application/json`. Tester avec **Run to test** avant **Save** : les
variables `${…}` arrivent non remplies au test, c'est normal.

**Body du webhook** :
```json
{
  "text": "🚨 **AutoOps — ${TITLE}** (${SEVERITY}, ${STATUS}) — ${RESOURCE_NAME}",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Détail", "value": "${MESSAGE}" },
        { "title": "Description", "value": "${DESCRIPTION}" },
        { "title": "Nœuds concernés", "value": "${AFFECTED_NODES}", "short": true },
        { "title": "Index concernés", "value": "${AFFECTED_INDICES}", "short": true },
        { "title": "Début", "value": "`${START_TIME}`", "short": true },
        { "title": "Fin", "value": "`${END_TIME}`", "short": true },
        { "title": "À vérifier", "value": "[L'événement dans AutoOps](${EVENT_LINK}), puis la backpressure Logstash dans le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)" },
        { "title": "Runbook", "value": "[Backpressure Elasticsearch](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-1--backpressure-elasticsearch)" }
      ]
    }
  ]
}
```

---

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
> ES ralentit / heap monte           → Alerte 5a       ← intervenir ici
>   → queue process se remplit       → Logstash process rejette les events
>     → backlog Redis croît          → Alerte 7a          ← filet inter-services
>       → ingest ne peut plus écrire → Alerte 4a (ingest bloqué)
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
>    situation ne devienne critique (ex : un heap qui ne redescend plus sous 90 % laisse
>    le temps d'agir avant l'`OutOfMemoryError`).
> 5. **Les alertes de silence** (alerte 3) sont des filets de sécurité de dernier
>    recours — elles signalent que tous les mécanismes d'anticipation ont échoué.
>    Leur déclenchement doit être traité comme une urgence maximale.
