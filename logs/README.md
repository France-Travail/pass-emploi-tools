# Logstash + Elastic Agent — pass-emploi-tools/logs

Application Scalingo déployant **Logstash** et **Elastic Agent** en mode colocalisé :
- Logstash reçoit les drains de logs des apps Scalingo (api, connect, web) et les ingère dans Elasticsearch
- Elastic Agent monitore Logstash via l'API locale (`/_node/stats` sur le port 9600) et envoie les métriques à Fleet

## Buildpacks

Définis dans `.buildpacks`, dans cet ordre :

```
https://github.com/France-Travail/elastic-agent-buildpack
https://github.com/France-Travail/logstash-buildpack
```

## Architecture

```
[Service Logstash INGEST]          [Redis]          [Service Logstash PROCESS]
  INGEST_ENABLED=true                               PROCESS_ENABLED=true

  pipeline-ingest.conf             list             pipeline-process.conf
  HTTP input (drain Scalingo)  →  logstash:ingest  →  filtres lourds → ES
  ACK ~1ms                                            + DLQ → pipeline dlq
```

Redis remplace la Persistent Queue disque comme buffer inter-services.
Par défaut (aucune variable définie), les deux pipelines tournent dans le même service (comportement identique à l'ancienne architecture mono-service).

## Variables d'environnement

### Logstash — activation des pipelines

| Variable          | Description                                                                                                                                               |
|-------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `INGEST_ENABLED`  | Mettre à `true` pour n'activer que le pipeline `ingest` (HTTP → Redis). Par défaut (non définie) : tous les pipelines sont actifs.                        |
| `PROCESS_ENABLED` | Mettre à `true` pour n'activer que les pipelines `process` + `dead_letter_queue` (Redis → ES). Par défaut (non définie) : tous les pipelines sont actifs. |

### Logstash — configuration

| Variable                      | Description                                                                                                                        |
|-------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| `LOGSTASH_VERSION`            | Version de Logstash à installer (ex: `9.4.5`)                                                                                      |
| `ENVIRONMENT`                 | Environnement de fallback (`prod`, `staging`, `perf`…) si non détecté via appname                                                  |
| `ELASTICSEARCH_URL`           | URL du cluster Elasticsearch, credentials inclus (ex: `https://user:password@host:port`)                                           |
| `USER`                        | Utilisateur HTTP pour l'authentification du drain Scalingo                                                                         |
| `PASSWORD`                    | Mot de passe HTTP pour l'authentification du drain Scalingo                                                                        |
| `REDIS_HOST`                  | Hôte Redis (ex: `my-redis.scalingo.com`)                                                                                           |
| `REDIS_PORT`                  | Port Redis (optionnel, défaut : `6379`)                                                                                            |
| `REDIS_PASSWORD`              | Mot de passe Redis                                                                                                                 |
| `LOGSTASH_INGEST_THREADS`     | Threads Netty du pipeline ingest (optionnel, défaut : `4`)                                                                         |
| `LOGSTASH_INGEST_WORKERS`     | Workers du pipeline `ingest` (optionnel, défaut : `1`) — augmenter si l'écriture Redis est le goulot                               |
| `LOGSTASH_PROCESS_WORKERS`    | Workers du pipeline `process` (optionnel, défaut : `1`) — augmenter si le traitement ES est le goulot                              |
| `LOGSTASH_PROCESS_BATCH_SIZE` | Taille des batches du pipeline `process` (optionnel, défaut : `250`) — réduire temporairement (ex: `50`) en cas de backpressure ES |
| `LOGSTASH_DLQ_WORKERS`        | Workers du pipeline `dead_letter_queue` (optionnel, défaut : `1`)                                                                  |

### Elastic Agent (Fleet)

| Variable                    | Description                                                                            |
|-----------------------------|----------------------------------------------------------------------------------------|
| `ELASTIC_AGENT_VERSION`     | Version d'Elastic Agent à installer (ex: `9.4.5`) — doit être ≤ version du cluster ES  |
| `ELASTIC_AGENT_FLAVOR`      | Flavor OCI : `basic` (défaut), `servers`, `complete`                                   |
| `FLEET_ENROLL`              | Mettre à `1` pour activer l'enrollment Fleet                                           |
| `FLEET_URL`                 | URL du Fleet Server (ex: `https://xxx.fleet.eu-west-1.aws.elastic-cloud.com:443`)      |
| `FLEET_ENROLLMENT_TOKEN`    | Token d'enrollment Fleet                                                               |
| `FLEET_REPLACE_TOKEN`       | Token de remplacement pour les redéploiements                                          |
| `ELASTIC_AGENT_TAGS`        | Tags Fleet (ex: `scalingo,pass-emploi-logstash`)                                       |
| `ELASTIC_AGENT_GO_OPTS`     | Options Go runtime (ex: `GOMEMLIMIT=256MiB`)                                           |

> **`ELASTIC_AGENT_ID` n'est pas à configurer dans Scalingo.** Il est dérivé automatiquement
> dans `start.sh` à partir du `HOSTNAME` du container (`uuid5(NAMESPACE_DNS, HOSTNAME)`),
> ce qui garantit un UUID stable et unique par instance (`web-1`, `web-2`…) sans configuration manuelle.

Pour la configuration Fleet complète (création de la policy, enrollment tokens, etc.), voir le
[README du buildpack elastic-agent](https://github.com/France-Travail/elastic-agent-buildpack).
