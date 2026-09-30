# Traces distribuées — APM

Le SDK **Elastic APM** est intégré dans les apps NestJS (api, web, connect). Il
envoie directement à l'**APM Server** d'Elastic Cloud — **sans passer par
Logstash** — qui assure à la fois la collecte, le traitement et l'écriture dans
ES. Rien à opérer de notre côté entre le SDK et le stockage : il n'existe donc
pas de `process/traces/`.

## Ce qui est capturé

| Donnée | Data stream | Nature | Rétention |
|---|---|---|---|
| **Traces** de chaque requête HTTP (latence, erreurs, dépendances — spans, transactions) | `traces-apm-default` | durée d'une requête | 30 j |
| **Traces RUM** (navigateur) | `traces-apm.rum-default` | durée d'une requête | 30 j |
| **Errors** non catchées | `logs-apm.error-default` | événement discret → rangé avec les **logs** | 90 j |
| Métriques APM | `metrics-apm.*` | mesures périodiques, **auto-gérées** par Elastic | 90 j (non versionné) |

Rétentions et templates : [stockage/traces](../../stockage/traces/README.md)
(et [stockage/logs](../../stockage/logs/README.md) pour `logs-apm.error`).

## Corrélation avec les logs

Le SDK propage `trace.id` dans les logs ECS émis pendant une requête
(cf. [format/logs/conventions](../../format/logs/conventions.md)) : pivot
`trace.id` pour passer d'une trace APM à ses logs, cf.
[runbooks/investigation-incident](../../runbooks/investigation-incident.md).

## Dépendance

L'intégration APM d'Elastic doit être installée (fournit `apm@mappings`,
`traces@mappings`, `*-fallback@ilm`… — référencés seulement, jamais versionnés
ici). Version pilotée par le plan Elastic Cloud (cf.
[infrastructure.md](../../infrastructure.md#versions)).
