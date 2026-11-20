# Infra d'observabilité

La chaîne de télémétrie elle-même, suivant le cycle de vie de chaque signal :

```
format ──► collecte ──► process ──► stockage
```

| Fichier | Question |
|---|---|
| [infrastructure.md](infrastructure.md) | Quelles briques, où, dans quelles versions, avec quels garde-fous de dimensionnement ? |
| [pilotage.md](pilotage.md) | Comment Fleet pilote les Elastic Agents ? |
| [alertes-stack-observabilite.md](alertes-stack-observabilite.md) | Quelles alertes sur la chaîne de télémétrie (Logstash, Redis, agents, ILM, AutoOps) ? |

| Étape | logs | métriques | traces |
|---|---|---|---|
| **format** | [standard des logs](../logs.md) ; webhooks : [format/webhooks](format/webhooks/conventions.md) | — | — |
| **collecte** | [collecte/logs](collecte/logs/README.md) ; webhooks : [collecte/webhooks](collecte/webhooks/README.md) | [collecte/metriques](collecte/metriques/README.md) | [collecte/traces](collecte/traces/README.md) |
| **process** | [process/logs](process/logs/README.md) | — (écriture directe) | — (APM Server) |
| **stockage** | [elasticsearch/logs](../../../elasticsearch/logs/README.md) | [elasticsearch/metriques](../../../elasticsearch/metriques/README.md) | [elasticsearch/traces](../../../elasticsearch/traces/README.md) |

Principes et import des templates Elasticsearch : [elasticsearch/README.md](../../../elasticsearch/README.md).

Décisions : [ADR-002](../../decisions/ADR-002-buffer-redis-logstash.md) (buffer Redis),
[ADR-003](../../decisions/ADR-003-usage-log-drain-scalingo.md) (log drain Scalingo),
[ADR-004](../../decisions/ADR-004-notifications-tchap-kibana-workflows.md) (notifications Tchap).
