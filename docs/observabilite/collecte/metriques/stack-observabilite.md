# Métriques de la stack d'observabilité — Logstash, Redis, hosts

Ce que les Elastic Agents mesurent sur la chaîne de log management elle-même.
Ce sont les indicateurs qui permettent d'**anticiper** une perte de logs avant
qu'elle ne soit visible côté apps (cf. philosophie des
[alertes](../../supervision/alertes-stack-observabilite.md#philosophie-des-alertes)).

## Deux types d'agents, pour éviter les doublons

- **Co-localisés** dans chaque service Logstash (INGEST et PROCESS) : chacun
  mesure **son** Logstash via l'API locale `/_node/stats` (port 9600).
- **Dédié** (`pass-emploi-elastic-agent-<env>`) : mesure les ressources
  **partagées** entre plusieurs apps — aujourd'hui le Redis attaché à
  `pass-emploi-logstash-process-<env>` — et la mémoire des conteneurs Logstash via
  l'API Scalingo ([intégration Custom API](../../../../elastic-agent/README.md#mémoire-des-conteneurs-scalingo-intégration-custom-api)). Un agent co-localisé dans l'un ou l'autre
  service Logstash produirait ces métriques en double.

## Data streams

| Data stream | Contenu | Usage |
|---|---|---|
| `metrics-logstash.node-default` | stats nœud : JVM heap, events in/out (champs GC mappés mais vides) | alerte 5 (heap) |
| `metrics-logstash.pipeline-default` | stats pipeline : queue depth, workers, batch | alerte 4 (backpressure) |
| `metrics-logstash.plugins-default` | stats plugins : bulk requests ES, erreurs output | diagnostic (compteurs cumulatifs, non alertables) |
| `metrics-logstash.health_report-default` | état de santé global du nœud | diagnostic |
| `metrics-redis.{info,key,keyspace}-default` | mémoire, connexions, longueur de `logstash:ingest` (`redis.key.length`) | alerte 7 (backlog) |
| `metrics-system.*-default` | 11 datasets — agent dédié uniquement | diagnostic |
| `logs-scalingo.container_stats-default` | mémoire totale de chaque conteneur Logstash, vue par Scalingo (`scalingo.memory.*`) | dashboard, alerte 9 (mémoire conteneur) |

Data view Kibana : `metrics-logstash*` (timestamp `@timestamp`). La taille de la
DLQ (`queue_size_in_bytes`) n'est **pas** exposée par l'intégration : l'alerte DLQ
lit directement l'index `logs-logstash-dlq-*`.

## Ajouter une ressource partagée à mesurer

1. Récupérer l'URL de la ressource depuis les variables d'env de l'app Scalingo concernée.
2. L'ajouter en variable d'env de `pass-emploi-elastic-agent-<env>` (ex. `REDIS_URL_APP=redis://...`).
3. Ajouter une instance de l'intégration dans la policy Fleet de l'agent dédié
   (Redis TLS : configurer le CA cert dans l'intégration, cf.
   [`logs/README.md`](../../../../logs/README.md#logstash--configuration-optionnelle)).
4. Rejouer le contrôle des rétentions ([pilotage.md](../../pilotage.md#enrôler-un-agent), étape 6).
