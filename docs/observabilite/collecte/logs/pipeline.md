# Pipeline `ingest` — recevoir sans traiter

Premier des deux pipelines Logstash (architecture découplée depuis 2026-07,
buffer Redis depuis 2026-09 — cf.
[ADR-002](../../../decisions/ADR-002-buffer-redis-logstash.md)). Tourne dans
`pass-emploi-logstash-<env>` (process `web`, `INGEST_ENABLED=true`).

Fichiers de référence :
- `logs/pipeline-ingest.conf` — input HTTP → liste Redis `logstash:ingest`, **zéro filtre**.
- `logs/config/pipelines-ingest.yml` — paramètres du pipeline.
- `logs/start.sh` — sélectionne les pipelines selon `INGEST_ENABLED` / `PROCESS_ENABLED`.

## Principe

Le pipeline `ingest` acquitte le drain en ~1 ms (écriture Redis). Le pipeline
`process` lit Redis à son rythme et fait tout le traitement. Un hoquet ES ou GC
côté `process` n'affecte plus l'ACK → **plus de quarantaine du drain**
(cf. [drain-scalingo.md](drain-scalingo.md)).

**RÈGLE D'OR** : ne jamais ajouter de filtre dans `pipeline-ingest.conf`.
Chaque filtre ajouté rallonge l'ACK et risque de réintroduire la quarantaine.

## Paramètres clés

| Variable | Défaut | Rôle |
|---|---|---|
| `LOGSTASH_INGEST_THREADS` | `4` | Threads Netty de l'input HTTP |
| `LOGSTASH_INGEST_WORKERS` | `1` | Workers — augmenter si l'écriture Redis est le goulot |
| `LOGSTASH_INGEST_REDIS_BATCH_EVENTS` | `250` | Événements par RPUSH. Sans `batch => true`, l'output `redis` fait un RPUSH par événement |

`pipeline.ordered: false` (supprime l'overhead de synchronisation). Liste
complète des variables : [`logs/README.md`](../../../../logs/README.md#variables-denvironnement).

## Quand Redis ne se vide plus

Si `process` ou ES sont indisponibles, `ingest` continue d'acquitter et la liste
Redis grossit **sans aucun symptôme côté drain** — invisible sans l'alerte 7
([supervision/alertes](../../supervision/alertes-stack-observabilite.md)). Saturation Redis possible
en < 50 min à 256 Mo. Procédure : [runbook scénario 5](../../runbooks/runbook-logstash.md).
