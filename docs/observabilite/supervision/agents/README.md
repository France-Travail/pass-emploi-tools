# Intégrations Fleet de l'agent dédié

Ce que supervise l'Elastic Agent dédié (`pass-emploi-elastic-agent-<env>`) :
intégrations Fleet, requêtes du package SQL, programmes CEL et leurs tests.
L'app Scalingo elle-même (déploiement, variables, `start.sh`) est décrite dans
[`elastic-agent/README.md`](../../../../elastic-agent/README.md).

## Architecture

```
pass-emploi-elastic-agent-perf   ← cette app (1 seule instance)
  └── Elastic Agent Fleet
        ├── Intégration Redis → Redis Logstash (redis-logstash-<env>)
        ├── Intégration Redis → Redis de l'api (redis-api-prod : info, keyspace, key sur les files Bull)
        ├── Intégration Redis → Redis de connect (redis-connect-prod : info, keyspace)
        ├── Intégration PostgreSQL → base de l'api (postgresql-api-prod : database, activity, bgwriter)
        ├── SQL Input ×3 → statistiques des requêtes, des index, des tables de la base de l'api
        ├── Intégration Custom API (CEL) → API Scalingo /stats (mémoire des conteneurs)
        └── Intégration Custom API (CEL) → API des bases Scalingo /metrics (instances des bases)
```

## Générer, pousser, vérifier

Les intégrations des bases (Redis, PostgreSQL, SQL Input, métriques des
instances) sont **générées** : ne pas les modifier dans Fleet, sinon la
prochaine poussée écrase la modification et « verifier » la signale.

| Je veux… | Je fais… |
|---|---|
| superviser une base de plus | une entrée dans [`bases.json`](bases.json) (`postgresql`, `redis`, ou `redis-bull` pour un Redis avec les files Bull), puis générer et pousser |
| changer une requête SQL, un programme CEL, un réglage | le fichier dans `integrations/`, [`requetes-sql.json`](requetes-sql.json) ou `modeles/`, puis générer et pousser |
| réparer la collecte après un mot de passe changé par Scalingo | pousser, sans rien modifier |
| savoir si Fleet a divergé du repo | vérifier |

```bash
cd docs/observabilite/supervision/agents
python3 -I generer-integrations.py                      # génère generated/<env>/, sans réseau ni secret
python3 -I generer-integrations.py pousser --env perf   # SCALINGO_API_TOKEN, KIBANA_URL, KIBANA_FLEET_API_KEY
python3 -I generer-integrations.py verifier --env prod  # KIBANA_URL, ES_API_KEY (lecture)
```

- **Générer** écrit un fichier par intégration dans `generated/<env>/`, à
  commiter ; les repères `@@…@@` (hôtes, mots de passe, identifiants d'addon,
  quotas des plans, date de l'autorité) y restent.
- **Pousser** lit dans Scalingo l'hôte, le port, l'utilisateur et le mot de
  passe de chaque base (`SCALINGO_POSTGRESQL_URL`, `SCALINGO_REDIS_URL` de
  l'app), son addon, son plan, son réglage *Force TLS* et la date de l'autorité
  de certification, remplit les repères à la volée et crée ou met à jour chaque
  intégration par son nom. Les mots de passe vont dans les secrets Fleet ; rien
  de secret n'est écrit ni affiché. Une base illisible dans Scalingo est
  signalée et sautée, les autres sont poussées. **Rien n'est jamais supprimé.**
- **Vérifier** compare Fleet aux fichiers générés (hors valeurs remplies à la
  poussée) et liste, sans échouer, les intégrations de la policy que le script
  ne gère pas (stack d'observabilité : Redis de Logstash, mémoire des
  conteneurs, System).

Clés : `SCALINGO_API_TOKEN`, le token Bitwarden « API Token Scalingo pour
Elastic » (son compte doit être collaborateur des apps qui portent les bases) ;
`KIBANA_FLEET_API_KEY`, une clé de courte durée qui peut écrire dans Fleet,
créée au moment de pousser :

```
POST /_security/api_key
{
  "name": "pousser-integrations-bases",
  "expiration": "1h",
  "role_descriptors": { "fleet": { "applications": [
    { "application": "kibana-.kibana", "privileges": ["feature_fleet.all", "feature_fleetv2.all"], "resources": ["*"] }
  ] } }
}
```

Les intégrations de la stack d'observabilité, elles, restent configurées dans
Kibana → Fleet (cf. [pilotage](../../pilotage.md)).
## Policy Fleet recommandée

Créer une policy Fleet dédiée (ex: `pass-emploi-elastic-agent-perf`) avec :
- Intégration **Redis**, une par Redis : *Hosts* `hôte:port` (lus dans `SCALINGO_REDIS_URL` de l'app qui porte le Redis), mot de passe dans *Password* (secret Fleet), bloc *SSL* seulement si le Redis a *Force TLS* (cf. « Ajout d'un nouveau Redis à monitorer »).
  - Redis de l'api : `key` sur les files Bull `bull:JobQueue:{wait,active,delayed,failed,completed}` (`limit: 1` par motif ; jamais `pattern: '*'`, qui parcourrait toutes les clés) ;
  - Redis de connect : `key` désactivé (une clé par grant d'authentification, nombre non borné) : la croissance se lit dans `keyspace` et la mémoire.
  - **Désactiver « Collect Redis slow logs »** : cet input n'a pas d'option TLS
    dans le package (`hosts` + `password` seulement), or le Redis Scalingo
    n'accepte que TLS → `error sending slowlog get: EOF` toutes les ~10 s.
- Intégration **System** (optionnel) : métriques système du container
- Intégration **Custom API** : mémoire des conteneurs Scalingo (ci-dessous)

## PostgreSQL et statistiques SQL

Policy `pass-emploi-elastic-agent-<env>`, une intégration PostgreSQL et trois
SQL Input, toutes sur la même URL et le même utilisateur (cf. « PostgreSQL :
connexion vérifiée ») :

| Intégration | Package | Dataset | Réglages |
|---|---|---|---|
| `postgresql-api-<env>` | PostgreSQL | `postgresql.database`, `.activity`, `.bgwriter` (1 min) | **`statement` désactivé** : une ligne par requête suivie à chaque relevé (≈ 5 000 en prod) ; les requêtes passent par le SQL Input, limité au top 200 ×2. Logs désactivés : pas de fichier de log dans le conteneur |
| `postgresql-statements-<env>` | SQL Input | `sql.postgresql_statements` | requête de [`integrations/postgresql/statements.sql`](integrations/postgresql/statements.sql) |
| `postgresql-index-stats-<env>` | SQL Input | `sql.postgresql_index_stats` | requête de [`integrations/postgresql/index_stats.sql`](integrations/postgresql/index_stats.sql) |
| `postgresql-table-stats-<env>` | SQL Input | `sql.postgresql_table_stats` | requête de [`integrations/postgresql/table_stats.sql`](integrations/postgresql/table_stats.sql) |
| `postgresql-index-hygiene-<env>` | SQL Input | `sql.postgresql_index_hygiene` | requête de [`integrations/postgresql/index_hygiene.sql`](integrations/postgresql/index_hygiene.sql), *Period* `1h` |
| `postgresql-activite-<env>` | SQL Input | `sql.postgresql_activite` | requête de [`integrations/postgresql/activite.sql`](integrations/postgresql/activite.sql), *Period* `1m` |

Pour les SQL Input : type **Metrics** (le dataset doit donner
`metrics-sql.<dataset>-default`, sinon ni rétention ni dashboards), driver
`postgres`, *Period* `10m` (sauf mention dans le tableau), *SSL Configuration* vide, requête collée au format
YAML, avec le format de réponse `table` :

```bash
f=statements; { echo "- query: |"; sed 's/^/    /' docs/observabilite/supervision/agents/integrations/postgresql/$f.sql; echo "  response_format: table"; }
```

Une requête modifiée se vérifie d'abord sur une base, en lecture seule :
[`integrations/postgresql/verifier.sh`](integrations/postgresql/verifier.sh),
dans un conteneur ponctuel de l'app qui porte la base.

## Ajout d'un nouveau Redis à monitorer

**TLS selon le réglage du Redis** : un Redis Scalingo avec *Force TLS* n'accepte
que TLS (bloc `ssl.certificate_authorities` dans l'intégration, cf.
`logs/README.md`) ; **sans *Force TLS*, il n'accepte que le clair** : laisser le
champ *SSL* vide, sinon `TLS handshake timeout` (cas des Redis de l'api et de
connect, qui n'ont pas *Force TLS*). Réglage d'un addon :
`scalingo --app <app> addons-info <addon_id>`.

1. Lire l'hôte et le port du Redis, sans afficher le mot de passe :
   `scalingo --app <app> env-get SCALINGO_REDIS_URL | sed -E 's#^.*@##'`
2. Ajouter une intégration Redis dans la policy Fleet de l'agent : *Hosts* =
   `hôte:port`, *Password* = le mot de passe de cette URL, *SSL* selon le réglage
   ci-dessus. Aucune variable à poser sur l'app de l'agent.

## Mémoire des conteneurs Scalingo (intégration Custom API)

La mémoire **totale** d'un conteneur (heap + hors-heap + agent + cache noyau),
celle sur laquelle Scalingo tue le conteneur, n'est mesurable que par l'API
Scalingo : l'agent co-localisé ne lit pas le cgroup, et la somme des RSS des
processus la sous-estime de ~500 Mo. L'agent dédié interroge donc
`GET /v1/apps/<app>/stats` chaque minute, sans rien ajouter dans les conteneurs
Logstash ([garde-fou 6](../../infrastructure.md#garde-fous-jvm--scalingo)).

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
  ([stockage/metriques](../../stockage/metriques/README.md)).

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
MITO=<chemin de mito> python3 -I -m unittest discover -s docs/observabilite/supervision/agents/integrations/tests -v
```

| Champ produit                                                   | Source `/metrics`                                         |
|-----------------------------------------------------------------|-----------------------------------------------------------|
| `scalingo.database.nom`, `.app`, `.addon_id`                    | state (`bases`) ; `nom` aussi sur les documents `error.message` |
| `scalingo.database.instance`                                    | `instances_metrics.<id>.instance_id`                      |
| `scalingo.database.role`                                        | `donnees` si l'instance a des données sur disque (`real_disk_size` > 0), sinon `auxiliaire` (composants de haute disponibilité, 128 Mio) |
| `scalingo.database.data_size.bytes`                             | `database_stats.data_size`, si l'API la donne (absente pour certaines bases) |
| `scalingo.database.connexions_max`                              | state, si le plan en fixe                                 |
| `scalingo.database.ca_expire_le`                                | state (`ca_expire_le`) : expiration de l'autorité de certification des bases, si fournie |
| `scalingo.cpu.usage`                                            | `cpu.usage_in_percents` de l'instance (%)                 |
| `scalingo.memory.usage.bytes`, `.limit.bytes`, `.highest.bytes` | `memory_usage`, `memory_limit`, `max_memory_usage`        |
| `scalingo.memory.pct`                                           | `memory_usage / memory_limit` (0–1)                       |
| `scalingo.swap.usage.bytes`                                     | `swap_usage`                                              |
| `scalingo.disk.usage.bytes`, `.inclus.bytes`, `.pct`            | `real_disk_size` de l'instance, quota du plan, rapport (0–1) |
