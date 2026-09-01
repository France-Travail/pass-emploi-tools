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

Seules les dépendances **hors de notre contrôle** sont mockées. `connect` et
`api` sont réels : ce sont eux qu'on mesure.

```
Gatling ──► connect-perf ──► mock-externes   (IdP France Travail)
         └► api-perf ──────► mock-externes   (APIs partenaires FT)
                          ├► connect-perf    (validation du JWT — le vrai)
                          └► PostgreSQL      (vraies données)
```

1. **Login** — Gatling passe par `connect`, qui délègue à l'IdP mocké et
   récupère un `sub` tiré dans le pool. `connect` prend nom/prénom/email via
   `/peconnect-coordonnees` (pas via le `userinfo`), puis enregistre
   l'utilisateur auprès de l'API et émet le JWT.
2. **Validation du JWT** — l'API vérifie la signature contre le JWKS de
   `connect`, découvert via `OIDC_ISSUER_URL` et mis en cache après le 1er appel.
3. **Autorisation** — le jeune `idJeune` doit exister en **base** : aucune
   auto-création pour un bénéficiaire FT, un jeune inconnu fait échouer le login.
4. **Token exchange** — l'API échange le JWT du jeune contre un token IDP
   France Travail auprès de `connect`.
5. **Fan-out parallèle** — 3 appels France Travail mockés (démarches,
   prestations, rendez-vous agenda) + 3 lectures en base réelles (alertes,
   favoris, campagne).
6. **Agrégation** — compteurs de la semaine, prochain rendez-vous, réponse JSON.

## Prérequis pour tirer

1. **Un environnement cible dédié** — ne JAMAIS tirer sur la production.
2. **`mock-externes` lancé**, avec `connect` et l'API branchés dessus : voir
   [`mock-externes/README.md`](./mock-externes/README.md) pour les variables des
   deux côtés.
3. **Les jeunes du pool semés en base**, avec un `id_authentification` égal au
   `sub` que rend le mock (`{POOL_PREFIX}{i}`).

> **État d'avancement.** `mock-externes` est en place (lot 1). La simulation
> Gatling se logue encore avec un `USER_TOKEN` fourni à la main : le login via
> `connect` arrive au lot 3, et fera disparaître cette variable. Voir
> [`docs/superpowers/specs/2026-09-01-harnais-tir-perf-design.md`](../docs/superpowers/specs/2026-09-01-harnais-tir-perf-design.md).

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
