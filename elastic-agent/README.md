# elastic-agent

App Scalingo dédiée à Elastic Agent pour le monitoring des ressources partagées
(Redis, PostgreSQL, etc.) via Fleet.

Contrairement aux apps Logstash qui embarquent un Elastic Agent co-localisé pour
monitorer leur propre pipeline, cette app monitore les ressources **partagées entre
plusieurs apps** (ex: un cluster Redis utilisé par plusieurs services).

Un seul agent dédié évite les doublons de métriques qui surviendraient si chaque
instance Logstash monitorait la même ressource.

> **Rétention des métriques dans Elasticsearch** (`metrics-redis.*`,
> `metrics-postgresql.*`, `metrics-sql.postgresql_*`, `logs-scalingo.*`) : [`stockage/metriques/README.md`](../docs/observabilite/stockage/metriques/README.md), section
> `metriques/`. Ce README-ci documente **quoi** superviser (Fleet, intégrations) ;
> l'autre documente **combien de temps** la donnée est gardée (policies ILM).

Ce README documente l'app Scalingo (déploiement, variables, démarrage). La
configuration Fleet (intégrations, requêtes, programmes CEL) est dans
[`docs/observabilite/supervision/agents/`](../docs/observabilite/supervision/agents/README.md).

## Déploiement Scalingo

### Variables d'environnement requises

| Variable                 | Description                                                                             |
|--------------------------|-----------------------------------------------------------------------------------------|
| `FLEET_URL`              | URL du Fleet Server (ex: `https://fleet.example.com:8220`)                              |
| `FLEET_ENROLLMENT_TOKEN` | Token d'enrollment Fleet pour la policy de cet agent                                    |
| `ENVIRONMENT`            | Nom de l'environnement (ex: `perf`, `staging`, `prod`)                                  |

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

## Mémoire des conteneurs Scalingo (intégration Custom API)

Les intégrations Fleet de l'agent (Redis, PostgreSQL, SQL Input, Custom API), leurs requêtes et programmes : [`docs/observabilite/supervision/agents/`](../docs/observabilite/supervision/agents/README.md#mémoire-des-conteneurs-scalingo-intégration-custom-api).
