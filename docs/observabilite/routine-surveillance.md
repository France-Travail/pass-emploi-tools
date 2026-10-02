# Routine de surveillance — dashboards et requêtes

Ce qu'on regarde **régulièrement**, sans attendre une alerte : l'activité métier
et la santé technique. Pour une question ponctuelle sur un incident, voir
[runbooks/investigation-incident](runbooks/investigation-incident.md) ; pour ce
qui réveille quelqu'un, [alertes applicatives](supervision/alertes-applicatives.md) et
[alertes de la stack d'observabilité](supervision/alertes-stack-observabilite.md) ; pour les
promesses tenues ou non, [supervision/sli-slo](supervision/sli-slo.md).

## Pré-requis

Les logs sortent dans **deux familles de data streams** :

- `logs-<env>-default` — logs applicatifs (code + pino-http)
- `logs-router-<env>-default` — logs router Scalingo (`event.action: request_routed`)

Pour corréler edge + app par `http.request.id`, la **data view doit matcher les
deux** : `logs-*-default-*` les couvre. Conventions des champs :
[format/logs/conventions](format/logs/conventions.md) ; exemples propres à
l'api : [format/logs/couverture-api](format/logs/couverture-api.md).

## Reporting métier

« Combien d'actions métier cette semaine, par structure ? » — champs pivots :
`log.logger`, `event.outcome`, `user.structure`.

| Métrique                | KQL                                                         |
|-------------------------|-------------------------------------------------------------|
| Actions métier réussies | `event.action: handler_executed AND event.outcome: success` |
| Échecs par handler      | `… AND event.outcome: failure` (group by `log.logger`)      |
| Activité par structure  | filtre/agrégation sur `user.structure`                      |

**Dashboard « Activité métier »** — filtres `user.structure`, `user.type` ;
compteurs des handlers clés, évolution temporelle, heatmap structure × handler.

## Santé technique applicative

« Un partenaire est-il en panne ? » — champs pivots : `log.logger`,
`event.outcome: failure`, `event.duration`.

| Signal                  | KQL                                                                                     | Seuil                    |
|-------------------------|-----------------------------------------------------------------------------------------|--------------------------|
| Pic d'échecs partenaire | `event.action: external_api_call AND log.logger: "<Client>" AND event.outcome: failure` | > 5–10/min sur 5min      |
| Pic d'auth refusées     | `event.action: auth_failed`                                                             | > baseline × 3 sur 10min |
| Erreurs serveur 5xx     | `event.action: request_failed AND http.response.status_code >= 500`                     | > 1/min sur 5min         |

Ces trois signaux sont aussi alertés, cf.
[alertes applicatives](supervision/alertes-applicatives.md).

**Dashboard « Santé tech »** — taux d'échec par partenaire, latence p50/p95/p99,
top `error.type`, ratio `auth_failed`, count `request_failed` par status.

## Santé de la stack d'observabilité

| Dashboard                 | Où                                                                                                                                        | Ce qu'on y lit                                                        |
|---------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| **[Pass Emploi] Chaîne de logs** | [dashboard](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d), versionné dans [`supervision/dashboards/chaine-logs.ndjson`](supervision/dashboards/chaine-logs.ndjson) (Saved objects → Import, *Overwrite*) | par environnement : mémoire conteneurs (% limite Scalingo), heap JVM, backpressure, backlog Redis, débit des pipelines |
| Dashboards Fleet Logstash | [assets de l'intégration Logstash](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/integrations/detail/logstash-2.11.3/assets) | débit des pipelines, queue, heap, GC                                  |
| **[Metrics Redis] Keys**  | intégration Redis → graphe **Lists length** → clé `db0 › logstash:ingest`                                                                 | backlog entre INGEST et PROCESS                                       |
| Kibana → Fleet → Agents   | filtrer par tag                                                                                                                           | agents `Healthy` / offline / UNENROLLED (cf. [pilotage](pilotage.md)) |

Signification des métriques : [collecte/metriques/stack-observabilite](collecte/metriques/stack-observabilite.md).
