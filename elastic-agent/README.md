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
        ├── Intégration Custom API (CEL) → API Scalingo /stats (mémoire des conteneurs)
        └── Intégration Custom API (CEL) → API des bases Scalingo /metrics (instances des bases)
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
| `POSTGRESQL_CA_CERT_BASE64` | — | Certificat de l'autorité des bases Scalingo, en base64 ; écrit au démarrage dans `/app/certs/postgresql-ca.pem` pour l'intégration PostgreSQL (cf. ci-dessous) |

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

## PostgreSQL : connexion vérifiée

L'intégration PostgreSQL (et le package SQL) vérifient le certificat du serveur :

```
postgres://<hôte>:<port>/<base>?sslmode=verify-full&sslrootcert=/app/certs/postgresql-ca.pem
```

L'utilisateur et le mot de passe vont dans les champs *Username* et *Password*
(secret Fleet), jamais dans l'URL. Contrairement à Redis, dont le certificat se
colle dans un champ YAML, PostgreSQL attend un **chemin de fichier** : `start.sh`
l'écrit depuis `POSTGRESQL_CA_CERT_BASE64`.

Le certificat est le même pour toutes les bases et les deux régions, public :

```bash
curl -s https://db-api.osc-secnum-fr1.scalingo.com/api/ca_certificate | base64 -w0
```

Test du démarrage : `bash elastic-agent/tests/test_start.sh` (Docker).

## Ajout d'un nouveau Redis à monitorer

**TLS selon le réglage du Redis** : un Redis Scalingo avec *Force TLS* n'accepte
que TLS (bloc `ssl.certificate_authorities` dans l'intégration, cf.
`logs/README.md`) ; **sans *Force TLS*, il n'accepte que le clair** : laisser le
champ *SSL* vide, sinon `TLS handshake timeout` (constaté le 2026-10-30 sur les
Redis de l'api et de connect, qui n'ont pas *Force TLS*). Réglage d'un addon :
`scalingo --app <app> addons-info <addon_id>`.

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
| Secret CEL evaluation state                | `api_token: <token API Scalingo, Bitwarden « API Token Scalingo pour Elastic »>`                     |

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

## Métriques des instances de bases (intégration Custom API)

CPU, mémoire, swap et disque des instances PostgreSQL et Redis, que les
intégrations PostgreSQL et Redis ne voient pas (Scalingo gère ces instances).
L'API des bases de Scalingo les donne par
`GET https://db-api.osc-secnum-fr1.scalingo.com/api/databases/<addon_id>/metrics`,
avec un jeton propre à chaque base.

Programme versionné : [`integrations/scalingo-database-stats.cel`](integrations/scalingo-database-stats.cel).
Il échange le token API contre un JWT, demande pour chaque base son jeton
(`POST /v1/apps/<app>/addons/<addon_id>/token`), puis ses métriques, et émet un
document par instance : chaque base est un cluster, 2 nœuds de données et des
instances auxiliaires. Une base en erreur émet un document `error.message` à son
nom ; les autres continuent.

Le compte qui porte le token doit être **collaborateur** (pas *limited*) sur
chaque app qui porte une base : un collaborateur limité ne lit pas les
métriques des bases.

Installation : comme la mémoire des conteneurs, avec ces valeurs :

| Champ                        | Valeur                                       |
|------------------------------|----------------------------------------------|
| Integration name             | `scalingo-database-stats-<env>`              |
| Dataset name                 | `scalingo.database_stats`                    |
| Resource URL                 | `https://api.osc-secnum-fr1.scalingo.com`    |
| Resource Interval            | `1m`                                         |
| Secret CEL evaluation state  | `api_token: <Bitwarden « API Token Scalingo pour Elastic »>` |

*Initial CEL evaluation state* (prod) :

```yaml
auth_url: https://auth.scalingo.com/v1/tokens/exchange
db_api_url: https://db-api.osc-secnum-fr1.scalingo.com
bases:
  - {app: pass-emploi-api-prod, addon_id: ad-a402741f-8751-409c-b602-a645998335ef, nom: postgresql-api-prod, disque_inclus_octets: 171798691840, connexions_max: 480}
  - {app: pass-emploi-api-prod, addon_id: ad-a1a0483d-c0b0-4e75-afb8-d53afb90bc9c, nom: redis-api-prod, disque_inclus_octets: 171798691840}
  - {app: pass-emploi-connect-prod, addon_id: ad-82bc06a9-c3b8-431e-acd7-c62382fcda2c, nom: redis-connect-prod, disque_inclus_octets: 21474836480}
```

`disque_inclus_octets` et `connexions_max` recopient la description du plan de
l'addon (`GET https://api.osc-secnum-fr1.scalingo.com/v1/addon_providers/<postgresql|redis>/plans`) :
à mettre à jour si le plan change. Le disque inclus est un quota facturé au-delà,
pas une limite qui bloque la base.

**Tests** : contre un faux Scalingo local, avec [`mito`](https://github.com/elastic/mito)
(sans release binaire : `go install github.com/elastic/mito/cmd/mito@latest`) :

```bash
MITO=<chemin de mito> python3 -I -m unittest discover -s elastic-agent/integrations/tests -v
```

| Champ produit                                                   | Source `/metrics`                                         |
|-----------------------------------------------------------------|-----------------------------------------------------------|
| `scalingo.database.nom`, `.app`, `.addon_id`                    | state (`bases`)                                           |
| `scalingo.database.instance`                                    | `instances_metrics.<id>.instance_id`                      |
| `scalingo.database.role`                                        | `donnees` si l'instance a des données sur disque (`real_disk_size` > 0), sinon `auxiliaire` (composants de haute disponibilité, 128 Mio) |
| `scalingo.database.data_size.bytes`                             | `database_stats.data_size`, si l'API la donne (absente pour certaines bases) |
| `scalingo.database.connexions_max`                              | state, si le plan en fixe                                 |
| `scalingo.cpu.usage`                                            | `cpu.usage_in_percents` de l'instance (%)                 |
| `scalingo.memory.usage.bytes`, `.limit.bytes`, `.highest.bytes` | `memory_usage`, `memory_limit`, `max_memory_usage`        |
| `scalingo.memory.pct`                                           | `memory_usage / memory_limit` (0–1)                       |
| `scalingo.swap.usage.bytes`                                     | `swap_usage`                                              |
| `scalingo.disk.usage.bytes`, `.inclus.bytes`, `.pct`            | `real_disk_size` de l'instance, quota du plan, rapport (0–1) |
