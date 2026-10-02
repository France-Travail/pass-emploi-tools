# elastic-agent

App Scalingo dédiée à Elastic Agent pour le monitoring des ressources partagées
(Redis, PostgreSQL, etc.) via Fleet.

Contrairement aux apps Logstash qui embarquent un Elastic Agent co-localisé pour
monitorer leur propre pipeline, cette app monitore les ressources **partagées entre
plusieurs apps** (ex: un cluster Redis utilisé par plusieurs services).

Un seul agent dédié évite les doublons de métriques qui surviendraient si chaque
instance Logstash monitorait la même ressource.

> **Rétention des métriques dans Elasticsearch** (`metrics-redis.*` — info, key,
> keyspace) : [`stockage/metriques/README.md`](../docs/observabilite/stockage/metriques/README.md), section
> `metriques/`. Ce README-ci documente **quoi** superviser (Fleet, intégrations) ;
> l'autre documente **combien de temps** la donnée est gardée (policies ILM).

## Architecture

```
pass-emploi-elastic-agent-perf   ← cette app (1 seule instance)
  └── Elastic Agent Fleet
        ├── Intégration Redis → Redis Logstash (SCALINGO_REDIS_URL)
        ├── Intégration Redis → autres Redis si besoin
        └── Intégration Custom API (CEL) → API Scalingo /stats (mémoire des conteneurs)
```

## Configuration des intégrations (Fleet)

La configuration de ce que supervise Elastic Agent **n'est pas dans ce repo**.
Elle est gérée centralement dans **Kibana → Fleet → Agent Policies**.

Au démarrage, l'agent (`elastic-agent container`) se connecte au Fleet Server
avec le `FLEET_ENROLLMENT_TOKEN`, télécharge sa policy et applique les
intégrations configurées. Aucun fichier de config local n'est nécessaire.

Pour configurer les intégrations :
1. Aller dans **Kibana → Fleet → Agent Policies**
2. Créer une policy dédiée (ex: `pass-emploi-elastic-agent-perf`)
3. Ajouter les intégrations souhaitées (Redis, PostgreSQL, System...)
4. Générer un **Enrollment Token** pour cette policy
5. Renseigner ce token dans la variable `FLEET_ENROLLMENT_TOKEN` de l'app Scalingo

## Déploiement Scalingo

### Variables d'environnement requises

| Variable                 | Description                                                                             |
|--------------------------|-----------------------------------------------------------------------------------------|
| `FLEET_URL`              | URL du Fleet Server (ex: `https://fleet.example.com:8220`)                              |
| `FLEET_ENROLLMENT_TOKEN` | Token d'enrollment Fleet pour la policy de cet agent                                    |
| `ENVIRONMENT`            | Nom de l'environnement (ex: `perf`, `staging`, `prod`)                                  |
| `SCALINGO_REDIS_URL`     | URL du Redis à monitorer (injectée automatiquement par Scalingo si l'addon est attaché) |

### Variables optionnelles

| Variable                | Défaut              | Description                           |
|-------------------------|---------------------|---------------------------------------|
| `ELASTIC_AGENT_GO_OPTS` | `GOMEMLIMIT=512MiB` | Options Go runtime pour Elastic Agent |

### Configuration Scalingo

- **`PROJECT_DIR`** : `elastic-agent` (sous-répertoire du monorepo)
- **Process** : type **`worker`** — Elastic Agent n'expose pas de port HTTP
- **Container** : L (1 Go). Avec Redis + System, l'agent consomme ~215 Mo ; l'input
  CEL tourne dans un processus `filebeat` séparé et porte le total à ~500 Mo. En M
  (512 Mo), ce processus ne démarrait jamais (`cel-default … missed 3 check-ins and
  will be killed` en boucle, agent *Unhealthy*, 2026-10-02)
- **Instances** : **1 seule** — plusieurs instances monteraient les mêmes métriques en doublon
- **`ELASTIC_AGENT_GO_OPTS`** : `GOMEMLIMIT=256MiB` — limite mémoire Go pour Elastic Agent dans un conteneur M

### Policy Fleet recommandée

Créer une policy Fleet dédiée (ex: `pass-emploi-elastic-agent-perf`) avec :
- Intégration **Redis** : `hosts: ["${SCALINGO_REDIS_URL}"]`
  - **Désactiver « Collect Redis slow logs »** : cet input n'a pas d'option TLS
    dans le package (`hosts` + `password` seulement), or le Redis Scalingo
    n'accepte que TLS → `error sending slowlog get: EOF` toutes les ~10 s.
- Intégration **System** (optionnel) : métriques système du container
- Intégration **Custom API** : mémoire des conteneurs Scalingo (ci-dessous)

## Ajout d'un nouveau Redis à monitorer

1. Récupérer l'URL du Redis depuis les variables d'env de l'app Scalingo concernée
2. Ajouter la variable d'env dans cette app (ex: `REDIS_URL_APP=redis://...`)
3. Ajouter une nouvelle instance de l'intégration Redis dans la policy Fleet

## Mémoire des conteneurs Scalingo (intégration Custom API)

La mémoire **totale** d'un conteneur (heap + hors-heap + agent + cache noyau),
celle sur laquelle Scalingo tue le conteneur, n'est mesurable que par l'API
Scalingo : l'agent co-localisé ne lit pas le cgroup, et la somme des RSS des
processus la sous-estime de ~500 Mo. L'agent dédié interroge donc
`GET /v1/apps/<app>/stats` chaque minute, sans rien ajouter dans les conteneurs
Logstash ([garde-fou 6](../docs/observabilite/infrastructure.md#garde-fous-jvm--scalingo)).

Programme versionné : [`integrations/scalingo-container-stats.cel`](integrations/scalingo-container-stats.cel).
Il échange le token API contre un JWT, appelle `/stats` pour chaque app de la
liste et émet un document par conteneur. Une app arrêtée (`{"stats":[]}`)
n'émet rien ; un HTTP en erreur émet un document `error.message`.

**Kibana → Fleet → policy `pass-emploi-elastic-agent-<env>` → Add integration →
« Custom API using Common Expression Language »** (package `cel`, à ne pas
confondre avec « Custom API », package `httpjson`, qui n'a pas de champ programme) :

| Champ                                      | Valeur                                                                                              |
|--------------------------------------------|-----------------------------------------------------------------------------------------------------|
| Integration name                           | `scalingo-container-stats-<env>`                                                                    |
| Dataset name                               | `scalingo.container_stats` (saisie libre + Entrée : la liste ne propose que les datasets existants) |
| Resource URL                               | `https://api.osc-secnum-fr1.scalingo.com`                                                           |
| Resource Interval                          | `1m`                                                                                                |
| The CEL program to be run for each polling | contenu de `integrations/scalingo-container-stats.cel`                                              |
| Initial CEL evaluation state               | voir ci-dessous                                                                                     |
| Secret CEL evaluation state                | `api_token: <token API Scalingo, Bitwarden « Scalingo — token observabilité »>`                     |

```yaml
auth_url: https://auth.scalingo.com/v1/tokens/exchange
apps:
  - pass-emploi-logstash-<env>
  - pass-emploi-logstash-process-<env>
```

- **Token** : le *Secret CEL evaluation state* (agent ≥ 9.2) est chiffré par
  Fleet et masqué dans les logs. Sur un agent plus ancien, le champ est absent :
  mettre `api_token` dans l'*Initial CEL evaluation state* et l'ajouter aux
  *Redacted fields* — le programme lit les deux.
- **Région** : les apps Logstash sont sur `osc-secnum-fr1` ; un appel sur
  `osc-fr1` répond `404`.
- **Compte** : token porté par un compte personnel le temps que l'administrateur du
  projet Scalingo crée un compte technique, invité en collaborateur *limited* sur
  les seules apps de la liste (un token porte les droits de son compte, pas de
  token restreint à une app). À migrer vers ce compte puis révoquer.
- **Tester le programme hors Fleet** avec [`mito`](https://github.com/elastic/mito)
  (le moteur de l'input CEL) : `mito -data state.json integrations/scalingo-container-stats.cel`,
  où `state.json` contient `url`, `auth_url`, `apps` et `secret.api_token`.
- **Après installation** : créer le template `logs-scalingo.container_stats@custom`
  et rejouer le contrôle des rétentions
  ([stockage/metriques](../docs/observabilite/stockage/metriques/README.md)).

| Champ produit                                                   | Source `/stats`                                                        |
|-----------------------------------------------------------------|------------------------------------------------------------------------|
| `host.name`                                                     | `<app>-<conteneur>`, aligné sur le `host.name` des agents co-localisés |
| `scalingo.app`, `scalingo.container`, `scalingo.container_type` | nom de l'app, `id` (`worker-1`), type (`worker`)                       |
| `scalingo.memory.usage.bytes`, `.limit.bytes`, `.highest.bytes` | `memory_usage`, `memory_limit`, `highest_memory_usage`                 |
| `scalingo.memory.pct`                                           | `memory_usage / memory_limit` (0–1)                                    |
| `scalingo.swap.usage.bytes`, `.highest.bytes`                   | `swap_usage`, `highest_swap_usage`                                     |
| `scalingo.cpu.usage`                                            | `cpu_usage` (%)                                                        |
