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

## Déploiement

L'app Scalingo est linkée au repo `pass-emploi-tools`. Ce repo étant un
monorepo, c'est **`PROJECT_DIR=logs`** qui dit au buildpack quel sous-dossier
builder — sans elle le build échoue (`PROJECT_DIR: 'logs' is not a valid
directory` si elle pointe ailleurs). Même mécanisme que `mock-externes-perf`
(`PROJECT_DIR=perf/mock-externes`).

### Dimensionnement — 2 Go minimum

Logstash et Elastic Agent tournent **dans le même conteneur** (cf. `start.sh`).
Il faut donc au moins un conteneur **XL (2 Go)** : Logstash à lui seul consomme
plusieurs centaines de Mo de non-heap (metaspace, code cache, buffers directs)
en plus de son heap, et l'agent Go tourne à côté avec son propre `GOMEMLIMIT`.
Sur un conteneur plus petit, le boot est tué par l'OOM killer
(`Killed ... memory quota exceeded`) quel que soit le heap configuré.

> ⚠️ **Poule et œuf sur une app neuve** : Scalingo refuse `scale` tant qu'aucun
> déploiement n'a réussi, et le vrai code ne peut pas booter dans la taille par
> défaut. Débloquer en déployant une archive placeholder qui boote
> (`scalingo --app <app> deploy <archive>.tar.gz`, avec un `Procfile` trivial
> dans un dossier `<projet>/logs/` — l'archive doit avoir un répertoire racine
> qui enveloppe le tout), puis `scale web:1:XL`, puis redéployer le vrai code.

## Variables d'environnement

### Logstash

| Variable                   | Description                                                                              |
|----------------------------|------------------------------------------------------------------------------------------|
| `PROJECT_DIR`              | Sous-dossier du monorepo à builder — toujours `logs` (cf. Déploiement)                   |
| `LOGSTASH_VERSION`         | Version de Logstash à installer (ex: `9.4.5`)                                            |
| `ENVIRONMENT`              | Environnement de fallback (`prod`, `staging`, `perf`…) si non détecté via appname        |
| `ELASTICSEARCH_URL`        | URL du cluster Elasticsearch, credentials inclus (ex: `https://user:password@host:port`) |
| `USER`                     | Utilisateur HTTP pour l'authentification du drain Scalingo                               |
| `PASSWORD`                 | Mot de passe HTTP pour l'authentification du drain Scalingo                              |
| `LS_JAVA_OPTS`             | Options JVM, heap compris (ex: `-Xms1g -Xmx1g` dans un conteneur XL)                     |
| `LOGSTASH_INGEST_THREADS`  | Threads Netty du pipeline ingest (optionnel, défaut : `4`)                               |

> **Le heap se règle via `LS_JAVA_OPTS`, pas `JAVA_OPTS`.** Le lanceur Logstash
> ignore explicitement le second (`warning: ignoring JAVA_OPTS=…; pass JVM
> parameters via LS_JAVA_OPTS`). Garder `-Xmx` ≤ ~1 Go dans un conteneur 2 Go
> pour laisser la place au non-heap et à Elastic Agent.

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
