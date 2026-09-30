# heartbeat

App Scalingo dédiée à **Heartbeat** (Elastic), déployée via le buildpack
[`SocialGouv/heartbeat-buildpack`](https://github.com/SocialGouv/heartbeat-buildpack).
Effectue des pings HTTP périodiques (`@every 5s`) sur les endpoints des apps
Pass Emploi pour détecter les indisponibilités (uptime), et écrit directement
dans Elasticsearch — **hors** Logstash, contrairement aux logs applicatifs.

> **Rétention des données dans Elasticsearch** (`heartbeat-*`, 90 j) :
> [`stockage/metriques/README.md`](../docs/observabilite/stockage/metriques/README.md).
> Ce README-ci documente **quoi** est supervisé (endpoints, config du binaire) ;
> l'autre documente **combien de temps** la donnée est gardée (policy ILM).

## Fonctionnement

`start.sh` génère `heartbeat.yml` à partir de `heartbeat.template.yml` par
substitution des variables d'environnement (`envsubst`), puis lance le binaire
`heartbeat` en mode `-e` (logs sur stderr, pas de fichier).

Monitors définis dans `heartbeat.template.yml` :

| Monitor                  | Type | Fréquence  | Condition de succès |
|---------------------------|------|------------|----------------------|
| `$API_SERVICE_NAME`       | http | `@every 5s`  | status `200`         |
| `$FRONT_SERVICE_NAME`     | http | `@every 5s`  | status `200`         |
| `$AUTH_SERVICE_NAME`      | http | `@every 5s`  | status `200`         |
| Wordpress (doc, 3 pages)  | http | `@every 60s` | status `200`         |

## Variables d'environnement requises

| Variable                 | Description                                              |
|---------------------------|-----------------------------------------------------------|
| `ELASTICSEARCH_HOST`      | Hôte Elasticsearch (Elastic Cloud)                         |
| `ELASTICSEARCH_USER`      | Utilisateur d'écriture Elasticsearch                       |
| `ELASTICSEARCH_PASSWORD`  | Mot de passe associé                                       |
| `API_SERVICE_NAME`        | Nom logique du service API (identifiant + libellé monitor)|
| `API_URL`                 | URL à surveiller pour l'API                                |
| `FRONT_SERVICE_NAME`      | Nom logique du service front                               |
| `FRONT_URL`                | URL à surveiller pour le front                             |
| `AUTH_SERVICE_NAME`        | Nom logique du service d'authentification                 |
| `AUTH_URL`                 | URL à surveiller pour l'auth                               |
| `WORDPRESS_ENABLED`        | `true`/`false` — active le monitor de la doc Wordpress     |

## Déploiement Scalingo

- **Process** : type **`web`** (`Procfile`) — expose un port HTTP (nginx,
  `.buildpacks`) requis par Scalingo pour valider le déploiement.
- **Buildpacks** (dans l'ordre) : `apt-buildpack` (installe `gettext-base` pour
  `envsubst`, cf. `Aptfile`) → `heartbeat-buildpack` → `nginx-buildpack`.
