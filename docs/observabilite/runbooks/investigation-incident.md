# Runbook — investiguer un incident applicatif

« Pourquoi cet utilisateur a un problème, là, maintenant ? » Point de départ :
un `user.id`, un identifiant de requête ou un timestamp. Data view
`logs-*-default-*` (app + router, cf.
[routine-surveillance § Pré-requis](../routine-surveillance.md#pré-requis)).
Pour une panne de la chaîne de logs elle-même : [runbook-logstash](runbook-logstash.md).

Champs pivots : `user.id`, `trace.id`, `http.request.id`, `log.level: error`.

## Requêtes

| Action                        | KQL                                                                                                |
|-------------------------------|----------------------------------------------------------------------------------------------------|
| Tous ses logs récents         | `user.id: "<id>"`                                                                                  |
| Uniquement les erreurs        | `user.id: "<id>" AND log.level: error`                                                             |
| Une requête HTTP (edge + app) | `http.request.id: "<id>"`                                                                          |
| Bout en bout d'une session    | `trace.id: "<id>"` (même pivot dans l'APM, cf. [collecte/traces](../collecte/traces/README.md))    |
| Échecs handler                | `event.action: handler_executed AND event.outcome: failure`                                        |
| Latence réseau vs code        | comparer `event.duration` de `request_routed` vs `request_completed` sur le même `http.request.id` |

## Limite : les flux non authentifiés

Un flux **non authentifié** (login) n'a ni `user.id` ni `trace.id` qui le
traverse → pivoter sur `client.ip` + fenêtre temporelle, ou **reproduire en
live** en tailant les logs. Pour le login, le funnel `login_*` de
`pass-emploi-connect` localise l'étape d'échec (cf.
[supervision/sli-slo](../supervision/sli-slo.md#requêtes-kql-du-funnel-login)).

## Dashboard « Investigation utilisateur »

Data view `logs-*-default-*`, filtre global `user.id` : timeline `event.action`,
compteurs par `event.action`, latences `external_api_call`, corrélation
router ↔ app par `http.request.id`.
