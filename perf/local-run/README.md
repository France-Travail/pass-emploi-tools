# Run local du harnais accueil FT

Fait tourner `connect` et `api` **natifs** (`yarn start`, pas de docker compose
pour eux) contre `mock-externes` et l'`apidb` locale, pour valider la
simulation Gatling sans attendre les environnements Scalingo dédiés
(`connect-perf` / `api-perf`).

Ne remplace pas un tir de perf : la machine locale, le mock en local et
l'absence d'APM ne donnent aucun chiffre exploitable contre les SLO. Sert
uniquement à valider le **parcours** — l'enchaînement des 7 étapes de
`LoginEtAccueilFranceTravailSimulation` (`perf/README.md`, § Le login, étape
par étape) et l'appariement pool ↔ seed.

## Pourquoi des fichiers à part, et pas les `.environment`

`connect` et `api` chargent leur `.environment` chiffré via
`ConfigModule.forRoot({ envFilePath: '.environment' })`, qui ne définit que ce
qui n'est **pas déjà** dans `process.env`. Sourcer ces fichiers avant
`yarn start` surcharge donc juste ce qu'il faut, sans toucher aux fichiers
`dotvault` versionnés des deux repos.

## Pourquoi pas de vault ici

`connect.sh` et `api.sh` sont **committés en clair**, pas de `.template` à
copier ni de valeur à saisir : toutes leurs valeurs sont déjà publiques,
reprises telles quelles des `docker-compose.yml` versionnés de `connect` et
`api`, ou de `mock-externes`. Rien à chiffrer.

Le seul secret du parcours — `CLIENT_APP_SECRET` de `connect`, partagé avec
l'app mobile réelle en staging — reste dans le vault `dotvault` de
`pass-emploi-connect`. Il va dans `perf/.env` (déjà gitignoré, jamais
`connect.sh`/`api.sh`), lu depuis `pass-emploi-connect/.environment` après
`dotvault decrypt` — jamais dupliqué en clair dans `tools`.

## Tout lancer d'un coup

Un seul Makefile pour tout le chantier perf : `perf/Makefile`. Les targets de
run local y sont ajoutées à côté de celles de Gatling (`accueilFT`, `loginFT`,
…) — pas de Makefile séparé ici, pour ne pas avoir à sauter d'un répertoire à
l'autre.

```sh
cd perf
make start     # mock-externes, apidb+migrations, marqueur+seed, connect, api
make status    # vérifie que les 3 process tournent
make logs      # suit les 3 logs (Ctrl-C n'arrête rien, juste le suivi)
make loginFT   # Gatling, une fois connect et api up
make stop      # arrête mock-externes, connect, api
```

Suppose `pass-emploi-connect` et `pass-emploi-api` clonés en frères de ce repo
(convention du projet). Sinon : `make start CONNECT_DIR=… API_DIR=…`.

`seed/README.md` présente la pose du marqueur comme un geste **manuel**, hors
du workflow de tir — c'est vrai pour le seed réel, qui vise `$DATABASE_URL` et
peut donc pointer n'importe où. `make start` l'automatise ici sans rouvrir
cette brèche : son adresse est codée en dur sur l'apidb Docker locale, jamais
un `DATABASE_URL` externe.

Chaque process est lancé via `setsid`, dans son propre groupe : `stop` tue le
groupe entier (`kill -- -PID`), pas que le process de tête, donc les enfants
que `yarn start` peut spawner (nest, node) partent avec. `mock`/`connect`/`api`
libèrent aussi leur port (`fuser -k`) avant de spawner, donc `make start` se
répare tout seul après un arrêt sale (terminal fermé, crash) sans `make stop`
préalable.

`perf/.env` (Gatling) est déjà renseigné : `CONNECT_URL=http://localhost:5050`,
`CLIENT_ID`/`CLIENT_SECRET`/`REDIRECT_URI` repris de `CLIENT_APP_*` dans
`pass-emploi-connect/.environment` — à re-synchroniser si ce secret roule.

## Lancer une seule brique

Chaque étape est aussi un target isolé : `make mock`, `make apidb`,
`make seed`, `make connect`, `make api` — toujours depuis `perf/`.

## Écarts connus, à lever à l'usage

- `perf/.env.template` indique encore `CONNECT_URL=http://localhost:8081` —
  `connect` écoute en réalité sur **5050** par défaut. À corriger dans le
  template une fois ce port confirmé en environnement Scalingo.
- `IDP_FT_JEUNE_REALM` doit être **non-vide** en local (`connect.sh` met
  `"perf"`) : le schéma Joi de `connect` (`configuration.schema.ts`) exige
  `realm` non vide, alors que le code qui l'utilise (`idp.service.ts`) ne
  l'ajoute à la requête que s'il est *truthy* — chaîne vide et schéma
  required-non-empty sont contradictoires côté `connect`. `mock-externes`
  ignore les query params qu'il ne déclare pas, donc la valeur elle-même
  n'a pas d'importance.
- L'accueil jeune peut appeler Firebase réel (`FIREBASE_SECRET_KEY` du
  `.environment` de l'api) — à surveiller au premier run, pas encore mocké.

## Diagnostic

| Symptôme | Cause probable |
|---|---|
| `EAI_AGAIN redis` au démarrage de `connect` | `REDIS_URL` pointe encore sur l'hôte docker `redis` au lieu de `localhost:6777` |
| `connect` rejette l'`id_token` du mock | `IDP_FT_JEUNE_ISSUER` ≠ `IDP_ISSUER` du mock |
| Login en échec `UTILISATEUR_INEXISTANT` | Seed pas rejoué, ou `POOL_PREFIX`/`POOL_SIZE` désaccordés entre le mock et le seed |
| 401 côté API après un login réussi | `OIDC_ISSUER_URL` de l'api pointe encore sur le mock au lieu de `connect` local |
