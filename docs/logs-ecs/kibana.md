# Use cases Kibana — transverse

Traduit le socle de logs ECS en requêtes / dashboards / alertes actionnables.
Conventions : [conventions](./conventions.md). Exemples spécifiques d'un repo :
son fichier dédié (api : [couverture-api](./couverture-api.md)).

## Pré-requis

Les logs sortent dans **deux familles de data streams** :

- `logs-<env>-default` — logs applicatifs (code + pino-http)
- `logs-router-<env>-default` — logs router Scalingo (`event.action: request_routed`)

Pour corréler edge + app par `http.request.id`, la **data view doit matcher les
deux** : `logs-*-default-*` les couvre.

## Trois axes

| Axe | Question type | Champs pivots |
|---|---|---|
| **Investigation incident** | « Pourquoi cet utilisateur a un problème là maintenant ? » | `user.id`, `trace.id`, `http.request.id`, `log.level: error` |
| **Reporting métier** | « Combien d'actions métier cette semaine par structure ? » | `log.logger`, `event.outcome`, `user.structure` |
| **Monitoring tech** | « Un partenaire est-il en panne ? » | `log.logger`, `event.outcome: failure`, `event.duration` |

## Investigation incident

Point de départ : un `user.id` ou un timestamp.

| Action | KQL |
|---|---|
| Tous ses logs récents | `user.id: "<id>"` |
| Uniquement les erreurs | `user.id: "<id>" AND log.level: error` |
| Une requête HTTP (edge + app) | `http.request.id: "<id>"` |
| Bout en bout d'une session | `trace.id: "<id>"` |
| Échecs handler | `event.action: handler_executed AND event.outcome: failure` |
| Latence réseau vs code | comparer `event.duration` de `request_routed` vs `request_completed` sur le même `http.request.id` |

**Limite** : un flux **non authentifié** (login) n'a ni `user.id` ni `trace.id`
qui le traverse → pivoter sur `client.ip` + fenêtre temporelle, ou **reproduire
en live** en tailant les logs.

**Dashboard « Investigation utilisateur »** — data view `logs-*-default-*`,
filtre global `user.id` : timeline `event.action`, compteurs par `event.action`,
latences `external_api_call`, corrélation router ↔ app par `http.request.id`.

## Reporting métier

| Métrique | KQL |
|---|---|
| Actions métier réussies | `event.action: handler_executed AND event.outcome: success` |
| Échecs par handler | `… AND event.outcome: failure` (group by `log.logger`) |
| Activité par structure | filtre/agrégation sur `user.structure` |

**Dashboard « Activité métier »** — filtres `user.structure`, `user.type` ;
compteurs des handlers clés, évolution temporelle, heatmap structure × handler.

## Monitoring technique

| Signal | KQL | Seuil |
|---|---|---|
| Pic d'échecs partenaire | `event.action: external_api_call AND log.logger: "<Client>" AND event.outcome: failure` | > 5–10/min sur 5min |
| Pic d'auth refusées | `event.action: auth_failed` | > baseline × 3 sur 10min |
| Erreurs serveur 5xx | `event.action: request_failed AND http.response.status_code >= 500` | > 1/min sur 5min |

**Dashboard « Santé tech »** — taux d'échec par partenaire, latence p50/p95/p99,
top `error.type`, ratio `auth_failed`, count `request_failed` par status.

## Alertes prioritaires (Watcher)

- `external_api_call` `failure` sur un partenaire — rate élevé → Slack #ops.
- `request_failed` 5xx — rate > 1/min sur 5min.
- ratio `auth_failed` > baseline × 3 → problème IDP / keycloak.
