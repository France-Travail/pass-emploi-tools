# Tests de performance

Harnais Gatling du chantier perf (démarche et SLO : [`docs/perf/`](../docs/perf/README.md)).

## Simulations

| Simulation                       | Cible           | Description                                                       |
| -------------------------------- | --------------- | ----------------------------------------------------------------- |
| `AccueilFranceTravailSimulation` | pass-emploi-api | Page d'accueil jeune France Travail                               |
| `LogstashIngestSimulation`       | Logstash        | Non-régression du pipeline d'ingestion (CI : `logstash-perf.yml`) |
| `ConnectionSimulation`           | Keycloak        | Parcours de login                                                 |
| `PremierScenario`                | pass-emploi-api | Scénario conseiller historique (2022)                             |

## Le workflow accueil FT, étape par étape

Chaque requête Gatling (`GET /jeunes/:idJeune/pole-emploi/accueil?maintenant=<ISO8601>`,
`Authorization: Bearer <JWT du jeune>`) traverse :

```
Gatling ──► pass-emploi-api ──► api-simulator (mocks)   ──► PostgreSQL (vraies données)
```

1. **Validation du JWT** — l'API vérifie la signature du token contre les clés
   publiques du Keycloak (JWKS découvert via `OIDC_ISSUER_URL`, mocké par
   l'api-simulator, résultat mis en cache après le 1er appel).
2. **Autorisation** — le jeune `idJeune` doit exister en **base** et
   correspondre à l'utilisateur du JWT.
3. **Token exchange** — l'API échange le JWT du jeune contre un token IDP
   France Travail (`POST /issuer/protocol/openid-connect/token`, mocké).
4. **Fan-out parallèle** — 3 appels France Travail mockés (démarches,
   prestations, rendez-vous agenda) + 3 lectures en base réelles (alertes,
   favoris, campagne).
5. **Agrégation** — compteurs de la semaine, prochain rendez-vous, réponse JSON.

Le simulateur sort les partenaires de l'équation : le tir mesure l'API et sa
base, pas France Travail.

## Prérequis pour tirer

1. **Un environnement cible dédié** — ne JAMAIS tirer sur la production.
2. **api-simulator lancé** et l'API branchée dessus (2 variables
   `.environment`) : voir [`api-simulator/README.md`](./api-simulator/README.md),
   y compris la contrainte sur l'émetteur du JWT.
3. **Le jeune en base** (défaut : Alban336, `ca5014cb-9bb5-4d8e-befb-596ee59c4d7b`)
   et un **JWT valide non expiré** de ce jeune dans `USER_TOKEN`.

## Setup

> JDK version 11+
> Scala version 2.13

## Run locally

```sh
make accueilFT        # tir accueil FT (crée .env depuis .env.template au 1er lancement)
make report         # ouvre le dernier rapport HTML
```

Le Makefile source `.env` à chaque lancement — pas de `source .env` à faire
(ni à oublier) : modifier le fichier suffit. Au premier lancement, renseigner
`USER_TOKEN` dans le `.env` créé.

Autres cibles :

```sh
make run SIMULATION=passemploi.test.ConnectionSimulation   # une autre simulation
make compile                                               # compilation seule
```

## Run with docker

### Build

```sh
docker build -t gatling .
```

### Run all simulations

```sh
docker run gatling
```

### Run a simulation

```sh
docker run gatling passemploi.test.AccueilFranceTravailSimulation
```
