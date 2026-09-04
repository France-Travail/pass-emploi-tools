# elastic-agent

App Scalingo dédiée à Elastic Agent pour le monitoring des ressources partagées
(Redis, PostgreSQL, etc.) via Fleet.

Contrairement aux apps Logstash qui embarquent un Elastic Agent co-localisé pour
monitorer leur propre pipeline, cette app monitore les ressources **partagées entre
plusieurs apps** (ex: un cluster Redis utilisé par plusieurs services).

Un seul agent dédié évite les doublons de métriques qui surviendraient si chaque
instance Logstash monitorait la même ressource.

## Architecture

```
pass-emploi-elastic-agent-perf   ← cette app (1 seule instance)
  └── Elastic Agent Fleet
        ├── Intégration Redis → Redis Logstash (SCALINGO_REDIS_URL)
        └── Intégration Redis → autres Redis si besoin
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

| Variable | Description |
|---|---|
| `FLEET_URL` | URL du Fleet Server (ex: `https://fleet.example.com:8220`) |
| `FLEET_ENROLLMENT_TOKEN` | Token d'enrollment Fleet pour la policy de cet agent |
| `ENVIRONMENT` | Nom de l'environnement (ex: `perf`, `staging`, `prod`) |
| `SCALINGO_REDIS_URL` | URL du Redis à monitorer (injectée automatiquement par Scalingo si l'addon est attaché) |

### Variables optionnelles

| Variable | Défaut | Description |
|---|---|---|
| `ELASTIC_AGENT_GO_OPTS` | `GOMEMLIMIT=512MiB` | Options Go runtime pour Elastic Agent |

### Configuration Scalingo

- **`PROJECT_DIR`** : `elastic-agent` (sous-répertoire du monorepo)
- **Container** : M (512 Mo) — Elastic Agent seul consomme ~200-300 Mo
- **Instances** : **1 seule** — plusieurs instances monteraient les mêmes métriques en doublon

### Policy Fleet recommandée

Créer une policy Fleet dédiée (ex: `pass-emploi-elastic-agent-perf`) avec :
- Intégration **Redis** : `hosts: ["${SCALINGO_REDIS_URL}"]`
- Intégration **System** (optionnel) : métriques système du container

## Ajout d'un nouveau Redis à monitorer

1. Récupérer l'URL du Redis depuis les variables d'env de l'app Scalingo concernée
2. Ajouter la variable d'env dans cette app (ex: `REDIS_URL_APP=redis://...`)
3. Ajouter une nouvelle instance de l'intégration Redis dans la policy Fleet
