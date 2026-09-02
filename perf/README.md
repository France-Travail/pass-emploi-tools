# Tests de performance

Harnais Gatling du chantier perf (démarche et SLO : [`docs/perf/`](../docs/perf/README.md)).

## Simulations

| Simulation                               | Cible                   | Description                                                       |
| ---------------------------------------- | ----------------------- | ----------------------------------------------------------------- |
| `LoginEtAccueilFranceTravailSimulation`  | connect + pass-emploi-api | **Bout en bout** : login FT réel puis page d'accueil jeune      |
| `AccueilFranceTravailSimulation`         | pass-emploi-api         | Page d'accueil jeune seule, avec un JWT fourni à la main          |
| `LogstashIngestSimulation`               | Logstash                | Non-régression du pipeline d'ingestion (CI : `logstash-perf.yml`) |
| `ConnectionSimulation`                   | Keycloak                | Parcours de login (legacy)                                        |
| `PremierScenario`                        | pass-emploi-api         | Scénario conseiller historique (2022)                             |

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
3. **Les jeunes du pool semés en base** : voir [`seed/README.md`](./seed/README.md).
   Le marqueur d'environnement se pose une fois, à la main ; le seed se rejoue
   avant chaque tir. `pool_prefix` et `pool_size` doivent valoir exactement
   `POOL_PREFIX` et `POOL_SIZE` du mock.

## Le login, étape par étape

`LoginEtAccueilFranceTravailSimulation` suit la chaîne de redirections **à la
main**, sans `followRedirect`. Deux raisons : la redirection finale vise le
schéma d'URL du client mobile, que Gatling ne sait pas suivre ; et le découpage
donne un **temps de réponse par étape**, qui est la matière du SLO I2.

| Étape | Qui répond | Ce qui s'y passe |
|---|---|---|
| 01 authorize | connect | `kc_idp_hint=pe-jeune` → structure `POLE_EMPLOI` |
| 02 interaction | connect | `/francetravail-jeune/connect/{uid}?type=cej` |
| 03 authorize | mock IDP | le mock **tire une identité** dans le pool |
| 04 callback IDP | connect | token exchange, userinfo, coordonnées, `PUT /auth/users` |
| 05 reprise interaction | connect | reprise de l'interaction oidc-provider |
| 06 token | connect | échange du code contre le JWT |
| 07 accueil FT | api | la page mesurée |

L'étape 04 est la plus coûteuse, et **c'est elle qui échoue si le pool n'est pas
semé** : l'API ne crée aucun bénéficiaire France Travail inconnu.

Gatling ne choisit pas l'identité du jeune — le mock l'a tirée au sort. Il la lit
dans le claim `userId` du token, celui-là même que l'API lit pour autoriser
l'appel.

> **État d'avancement.** Lots 1 à 3 en place. La simulation **compile** mais n'a
> pas encore été jouée contre un `connect` réel : le nombre exact de sauts entre
> l'`authorize` et le `token` reste à confirmer au premier tir. Le découpage
> nommé rendra tout écart lisible immédiatement. Voir
> [`docs/superpowers/specs/2026-09-01-harnais-tir-perf-design.md`](../docs/superpowers/specs/2026-09-01-harnais-tir-perf-design.md).

## Setup

> JDK version 11+
> Scala version 2.13

## Run locally

```sh
make loginFT        # tir de bout en bout : login FT réel puis accueil
make accueilFT      # accueil seul, avec un JWT fourni à la main
make report         # ouvre le dernier rapport HTML
```

Le Makefile source `.env` à chaque lancement — pas de `source .env` à faire
(ni à oublier) : modifier le fichier suffit. Le premier lancement crée `.env`
depuis `.env.template` ; le renseigner puis relancer.

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
