# Observabilité — index

Outillage de supervision de pass-emploi : logs, métriques, traces. La doc suit
le **cycle de vie de la télémétrie**, chaque étape déclinée par télémétrie
(`logs`, `metriques`, `traces`) — un sous-répertoire n'existe que s'il a du
contenu. Chaque `<étape>/<télémétrie>/README.md` donne la vue d'ensemble de
l'archi et pointe vers les sujets plus précis.

```
format ──► collecte ──► process ──► stockage ──► exploitation (routine, supervision, runbooks)
```

## Vue d'ensemble et sujets transverses

| Fichier | Question à laquelle il répond |
|---|---|
| [infrastructure.md](infrastructure.md) | Quelles briques, où, dans quelles versions, avec quels garde-fous de dimensionnement ? |
| [pilotage.md](pilotage.md) | Comment Fleet pilote les Elastic Agents (enrôlement, policies, identité) ? |

## Cycle de vie par télémétrie

| Étape | logs | metriques | traces |
|---|---|---|---|
| **format** — ce que l'app émet | [format/logs](format/logs/README.md) | — | — |
| **collecte** — transport jusqu'au premier buffer | [collecte/logs](collecte/logs/README.md) | [collecte/metriques](collecte/metriques/README.md) | [collecte/traces](collecte/traces/README.md) |
| **process** — transformation avant indexation | [process/logs](process/logs/README.md) | — (écriture directe) | — (APM Server) |
| **stockage** — data streams, mapping, rétention | [stockage/logs](stockage/logs/README.md) | [stockage/metriques](stockage/metriques/README.md) | [stockage/traces](stockage/traces/README.md) |

Principes et import des templates ES : [stockage/README.md](stockage/README.md).

## Exploitation

| Fichier | Usage |
|---|---|
| [routine-surveillance.md](routine-surveillance.md) | Ce qu'on regarde régulièrement : reporting métier, santé tech, dashboards |
| [supervision/sli-slo.md](supervision/sli-slo.md) | Les promesses de service (I1-I5, seuil commun) et leurs requêtes |
| [supervision/alertes-applicatives.md](supervision/alertes-applicatives.md) | Alertes sur les pannes visibles des utilisateurs (partenaires, 5xx, auth) |
| [supervision/alertes-stack-observabilite.md](supervision/alertes-stack-observabilite.md) | Alertes sur notre infra de télémétrie (Logstash, Redis, agents Fleet) |
| [runbooks/investigation-incident.md](runbooks/investigation-incident.md) | Enquêter sur un incident applicatif (KQL par `user.id`, `trace.id`…) |
| [runbooks/runbook-logstash.md](runbooks/runbook-logstash.md) | Diagnostiquer une panne de la chaîne de logs (5 scénarios + playbook) |
| [post-mortems/](post-mortems/) | Récits d'incidents : [5xx Logstash (06/2026)](post-mortems/postmortem-2026-06-logstash-5xx.md), [blackout logs (07/2026)](post-mortems/postmortem-2026-07-blackout-logs.md), [agent UNENROLLED (09/2026)](post-mortems/postmortem-2026-09-unenrolled-elastic-agent.md) |

## Décisions d'architecture

- [ADR-002 — Migration du buffer Logstash : PQ disque → Redis](../decisions/ADR-002-buffer-redis-logstash.md)
- [ADR-003 — Pertinence de l'usage des Log Drains Scalingo](../decisions/ADR-003-usage-log-drain-scalingo.md)

Tirs de charge applicatifs (harnais, scénarios, instrumentation requise) :
[docs/perf/](../perf/README.md).
