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

### Log management — flux d'ingestion

Redis remplace la Persistent Queue disque comme buffer inter-services.
Par défaut (aucune variable définie), les deux pipelines tournent dans le même service (comportement identique à l'ancienne architecture mono-service).

> Pour comprendre la décision de migrer de la Persistent Queue vers Redis, voir
> [ADR-002 — Migration du buffer Logstash : PQ disque → Redis](../docs/decisions/ADR-002-buffer-redis-logstash.md).

```mermaid
graph LR
    subgraph apps["Apps Scalingo"]
        api["pass-emploi-api"]
        web["pass-emploi-web"]
        connect["pass-emploi-connect"]
    end

    subgraph ingest_svc["pass-emploi-logstash-#60;env#62;\nINGEST_ENABLED=true"]
        ingest["pipeline ingest\nHTTP input — ACK ~1ms"]
        ea_ingest["Elastic Agent"]
    end

    redis[("Redis\nScalingo")]

    subgraph process_svc["pass-emploi-logstash-process-#60;env#62;\nPROCESS_ENABLED=true"]
        process["pipeline process\nfiltres + ES + DLQ"]
        ea_process["Elastic Agent"]
    end

    es["Elastic Cloud\n(ES + Fleet)"]

    api -->|drain HTTP| ingest
    web -->|drain HTTP| ingest
    connect -->|drain HTTP| ingest
    ingest -->|list logstash:ingest| redis
    redis --> process --> es
    ea_ingest -->|métriques Logstash| es
    ea_process -->|métriques Logstash| es
```

## Déploiement

L'app Scalingo est linkée au repo `pass-emploi-tools`. Ce repo étant un
monorepo, c'est **`PROJECT_DIR=logs`** qui dit au buildpack quel sous-dossier
builder — sans elle le build échoue (`PROJECT_DIR: 'logs' is not a valid
directory` si elle pointe ailleurs). Même mécanisme que `mock-externes-perf`
(`PROJECT_DIR=perf/mock-externes`).

### Nommage des apps Scalingo

L'architecture split INGEST / PROCESS repose sur **3 apps Scalingo distinctes par environnement** :

| App Scalingo                         | Rôle                               | Variable à poser       |
|--------------------------------------|------------------------------------|------------------------|
| `pass-emploi-logstash-<env>`         | Service INGEST (HTTP → Redis)      | `INGEST_ENABLED=true`  |
| `pass-emploi-logstash-process-<env>` | Service PROCESS (Redis → ES)       | `PROCESS_ENABLED=true` |
| `pass-emploi-elastic-agent-<env>`    | Elastic Agent ressources partagées | —                      |

> **Pourquoi garder le nom `pass-emploi-logstash-<env>` pour l'INGEST ?**
> Les apps Scalingo (api, connect, web…) envoient leurs logs via des **Log Drains** configurés
> avec l'URL de cette app. Renommer l'app INGEST aurait nécessité de reconfigurer tous les
> Log Drains sur chaque app — opération risquée et sans valeur ajoutée. Le nom historique est
> donc conservé pour le service INGEST.

> **À quoi sert l'app Scalingo `pass-emploi-elastic-agent-<env>` ?**
> Elle héberge un Elastic Agent dédié qui supervise actuellement le **Redis** attaché à
> `pass-emploi-logstash-process-<env>` via Fleet. Ce Redis étant une ressource partagée entre
> les deux services Logstash, un agent co-localisé dans l'un ou l'autre produirait des métriques
> en doublon — d'où un agent dédié dans une app séparée. Cet agent pourra être configuré pour
> superviser d'autres services Scalingo (bases de données, Redis supplémentaires…) si besoin,
> sans toucher aux apps Logstash.

### Configuration Scalingo (Services Logstash INGEST & PROCESS)

- **`PROJECT_DIR`** : `logs` (sous-répertoire du monorepo)
- **Container** : L minimum (1 Go) — Logstash et Elastic Agent cohabitent dans le même conteneur
- **Process** :
  - `pass-emploi-logstash-<env>` → type **`web`** avec `INGEST_ENABLED=true` (reçoit les drains HTTP sur `$PORT`)
  - `pass-emploi-logstash-process-<env>` → type **`worker`** avec `PROCESS_ENABLED=true` (pas de port exposé)
- **`LS_JAVA_OPTS`** : `-Xms256m -Xmx256m` — heap Logstash dans un conteneur L
- **`ELASTIC_AGENT_GO_OPTS`** : `GOMEMLIMIT=128MiB` — limite mémoire Go pour Elastic Agent

### Dimensionnement — 1 Go minimum

Logstash et Elastic Agent tournent **dans le même conteneur** (cf. `start.sh`).
Il faut donc au moins un conteneur **L (1 Go)** : Logstash à lui seul consomme
plusieurs centaines de Mo de non-heap (metaspace, code cache, buffers directs)
en plus de son heap, et l'agent Go tourne à côté avec son propre `GOMEMLIMIT`.
Sur un conteneur plus petit, le boot est tué par l'OOM killer
(`Killed ... memory quota exceeded`) quel que soit le heap configuré.

> ⚠️ **Poule et œuf sur une app neuve** : Scalingo refuse `scale` tant qu'aucun
> déploiement n'a réussi, et le vrai code ne peut pas booter dans la taille par
> défaut. Débloquer en déployant une archive placeholder qui boote
> (`scalingo --app <app> deploy <archive>.tar.gz`, avec un `Procfile` trivial
> dans un dossier `<projet>/logs/` — l'archive doit avoir un répertoire racine
> qui enveloppe le tout), puis `scale web:1:L`, puis redéployer le vrai code.

## Variables d'environnement

### Logstash — activation des pipelines (optionnel)

Ces deux variables sont **optionnelles**. Si aucune n'est définie, les trois pipelines
(`ingest`, `process`, `dead_letter_queue`) tournent dans le même service — comportement
identique à l'ancienne architecture mono-service.

| Variable          | Défaut | Description                                                                                                                                                |
|-------------------|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `INGEST_ENABLED`  | —      | Mettre à `true` pour n'activer que le pipeline `ingest` (HTTP → Redis). Utile sur le service dédié à la réception des drains.                              |
| `PROCESS_ENABLED` | —      | Mettre à `true` pour n'activer que les pipelines `process` + `dead_letter_queue` (Redis → ES). Utile sur le service dédié au traitement et à l'indexation. |

### Logstash — configuration requise

| Variable            | Description                                                                              |
|---------------------|------------------------------------------------------------------------------------------|
| `PROJECT_DIR`       | Sous-dossier du monorepo à builder — toujours `logs` (cf. Déploiement)                   |
| `LOGSTASH_VERSION`  | Version de Logstash à installer (ex: `9.4.6`)                                            |
| `ENVIRONMENT`       | Environnement de fallback (`prod`, `staging`, `perf`…) si non détecté via appname        |
| `ELASTICSEARCH_URL` | URL du cluster Elasticsearch, credentials inclus (ex: `https://user:password@host:port`) |
| `USER`              | Utilisateur HTTP pour l'authentification du drain Scalingo                               |
| `PASSWORD`          | Mot de passe HTTP pour l'authentification du drain Scalingo                              |
| `REDIS_HOST`        | Hôte Redis (ex: `my-redis.scalingo.com`)                                                 |
| `REDIS_PASSWORD`    | Mot de passe Redis                                                                       |
| `LS_JAVA_OPTS`      | Options JVM, heap compris (ex: `-Xms1g -Xmx1g` dans un conteneur XL)                     |

### Logstash — configuration optionnelle

| Variable                      | Défaut | Description                                                                                                                   |
|-------------------------------|--------|-------------------------------------------------------------------------------------------------------------------------------|
| `REDIS_PORT`                  | `6379` | Port Redis                                                                                                                    |
| `REDIS_CA_CERT_BASE64`        | —      | CA cert Redis encodé en base64 (onglet SSL/TLS de la page Redis Scalingo). Décodé au démarrage vers `/app/certs/redis-ca.pem` |
| `LOGSTASH_INGEST_THREADS`     | `4`    | Threads Netty du pipeline ingest                                                                                              |
| `LOGSTASH_INGEST_WORKERS`     | `1`    | Workers du pipeline `ingest` — augmenter si l'écriture Redis est le goulot                                                    |
| `LOGSTASH_PROCESS_WORKERS`    | `1`    | Workers du pipeline `process` — augmenter si le traitement ES est le goulot                                                   |
| `LOGSTASH_PROCESS_BATCH_SIZE` | `250`  | Taille des batches du pipeline `process` — réduire temporairement (ex: `50`) en cas de backpressure ES                        |
| `LOGSTASH_DLQ_WORKERS`        | `1`    | Workers du pipeline `dead_letter_queue`                                                                                       |

> **Générer `REDIS_CA_CERT_BASE64`** : télécharger le CA cert depuis la page
> Redis Scalingo (onglet "SSL/TLS" → "Download CA cert"), puis encoder :
> ```
> base64 -w 0 ca.pem
> ```
> Copier la sortie (une seule ligne) comme valeur de la variable Scalingo.
>
> **Configurer le CA cert dans l'intégration Kibana** (Collect Redis metrics →
> Settings → Advanced options → SSL Configuration) :
> ```
> echo "ssl.certificate_authorities: |" && sed 's/^/  /' ca.pem
> ```
> Copier la sortie YAML (header + contenu indenté) dans le champ SSL de l'intégration.

> **Le heap se règle via `LS_JAVA_OPTS`, pas `JAVA_OPTS`.** Le lanceur Logstash
> ignore explicitement le second (`warning: ignoring JAVA_OPTS=…; pass JVM
> parameters via LS_JAVA_OPTS`). Garder `-Xmx` ≤ ~1 Go dans un conteneur 2 Go
> pour laisser la place au non-heap et à Elastic Agent.

### Elastic Agent (Fleet) — configuration requise

| Variable                 | Description                                                                           |
|--------------------------|---------------------------------------------------------------------------------------|
| `ELASTIC_AGENT_VERSION`  | Version d'Elastic Agent à installer (ex: `9.4.6`) — doit être ≤ version du cluster ES |
| `FLEET_ENROLL`           | Mettre à `1` pour activer l'enrollment Fleet                                          |
| `FLEET_URL`              | URL du Fleet Server (ex: `https://xxx.fleet.eu-west-1.aws.elastic-cloud.com:443`)     |
| `FLEET_ENROLLMENT_TOKEN` | Token d'enrollment Fleet                                                              |
| `FLEET_REPLACE_TOKEN`    | Token de remplacement pour les redéploiements                                         |

### Elastic Agent (Fleet) — configuration optionnelle

| Variable                  | Défaut              | Description                                                                                                                                               |
|---------------------------|---------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ELASTIC_AGENT_FLAVOR`    | `basic`             | Flavor OCI : `basic`, `servers`, `complete`                                                                                                               |
| `ELASTIC_AGENT_TAGS`      | —                   | ⚠️ Vivement conseillé — tags Fleet (ex: `scalingo,pass-emploi-logstash`) pour filtrer les agents dans l'interface Fleet de Kibana.                         |
| `ELASTIC_AGENT_GO_OPTS`   | `GOMEMLIMIT=256MiB` | Options Go runtime                                                                                                                                        |
| `ELASTIC_AGENT_ID_SUFFIX` | —                   | Versionne un agent pour forcer une nouvelle identité Fleet — voir [post-mortem du 11/09/2026](../docs/observabilite/post-mortems/postmortem-2026-09-unenrolled-elastic-agent.md). |

> **`ELASTIC_AGENT_ID` n'est pas à configurer dans Scalingo.** Il est dérivé automatiquement
> dans `start.sh` à partir du `HOSTNAME` du container (`uuid5(NAMESPACE_DNS, HOSTNAME)`),
> ce qui garantit un UUID stable et unique par instance (`web-1`, `web-2`…) sans configuration manuelle.
> Pour forcer une nouvelle identité Fleet (ex : après perte du `FLEET_REPLACE_TOKEN`), poser
> `ELASTIC_AGENT_ID_SUFFIX=v2` (ou tout suffixe) : l'UUID est alors calculé depuis
> `HOSTNAME:v2` au lieu de `HOSTNAME`.
>
> **L'Elastic Agent démarre en différé** : il attend que Logstash réponde sur le port 9600
> (API interne) avant de se lancer, pour ne pas concurrencer la JVM pendant la phase critique
> de boot (~60 s de timeout Scalingo).

Pour la configuration Fleet complète (création de la policy, enrollment tokens, etc.), voir le
[README du buildpack elastic-agent](https://github.com/France-Travail/elastic-agent-buildpack).
