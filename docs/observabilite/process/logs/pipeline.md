# Pipelines `process` et `dead_letter_queue` — traiter et indexer

Fichiers de référence :
- `logs/pipeline-process.conf` — Redis → filtres → ES.
- `logs/pipeline-dlq-logstash.conf` — relit la DLQ disque → `logs-logstash-dlq-<env>-default`.
- `logs/config/pipelines-process.yml` — paramètres des deux pipelines.

## Post-traitement mutualisé

`pipeline-process.conf` fait le post-traitement commun aux trois repos : parsing
des logs router (logfmt → ECS `request_routed`), renames/flatten ECS, détection
d'env (par `appname`, `ENVIRONMENT` en fallback), **drops** de bruit
(healthchecks Scalingo, bootstrap NestJS `RouterExplorer` & co, lignes non-JSON
du conteneur `postdeploy`).

Routage en sortie :

| Condition | Data stream |
|---|---|
| tag d'échec de filtre (`_jsonparsefailure`, `_mutate_error`, `_rubyexception`, `_kv_filter_*`, `_dateparsefailure`…) | `logs-logstash-errors-<env>-default` |
| tag `router` | `logs-router-<env>-default` |
| sinon | `logs-<env>-default` (`appname=*-perf` → `logs-perf-default`, purgeable après tir) |

## Frontière in-app / Logstash

Ce qui doit rester **in-app** (pino) et ne peut pas descendre dans Logstash :
émission ECS structurée, **redaction des secrets** (un secret ne doit jamais
sortir du process), propagation `trace.id` / `user.*`. Logstash = post-traitement
générique mutualisé ; l'app = émission + redaction
(cf. [format/logs/conventions](../../format/logs/conventions.md)).

## Dead Letter Queue

Capte les events **rejetés définitivement par ES** (conflit de mapping, document
trop grand) : `dead_letter_queue.max_bytes: 256mb`, `storage_policy: drop_older`,
`retain.age: 2d`, sous `/app/data/dead_letter_queue` (disque éphémère). Le
pipeline `dead_letter_queue` y ajoute la cause Logstash et le payload d'origine
avant indexation. Tout event en DLQ ou en index d'erreurs = alertes 1 et 2
([supervision/alertes](../../supervision/alertes-stack-observabilite.md)), procédure au
[runbook scénario 3](../../runbooks/runbook-logstash.md).

## Paramètres clés

| Variable | Défaut | Rôle |
|---|---|---|
| `LOGSTASH_PROCESS_WORKERS` | `1` | Workers — testé à 4 : moins bon, le goulot est le plan Elastic Cloud (cf. [performances](performances.md)) |
| `LOGSTASH_PROCESS_BATCH_SIZE` | `250` | Défaut Logstash = 125 ; plus grand = moins de round-trips ES. Réduire temporairement (ex. `50`) en backpressure ES |
| `LOGSTASH_DLQ_WORKERS` | `1` | Workers du pipeline `dead_letter_queue` |

`queue.type: memory` (Redis est le vrai buffer), `pipeline.batch.delay: 50`,
`pipeline.ordered: false`.
