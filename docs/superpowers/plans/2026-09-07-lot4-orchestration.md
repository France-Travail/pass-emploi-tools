# Lot 4 — Orchestration du tir depuis la CI : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Déclencher un tir de perf complet — réveil de l'environnement, seed,
tir, verdict SLO, archivage — depuis GitHub Actions, sans geste manuel.

**Architecture:** Un workflow `perf-api.yml` en `workflow_dispatch`, portant les
5 étapes retenues pour v1 (le restore d'image de base est hors périmètre, cf.
Global Constraints). Il n'appelle aucune logique nouvelle : il enchaîne le CLI
Scalingo, `psql` sur les scripts de `perf/seed/`, et la cible `tir` du
`perf/Makefile`. Deux régimes d'injecteur (`scalingo`, `runner`) partagent
seed, simulation et verdict — seul l'endroit d'exécution change.

**Tech Stack:** GitHub Actions, CLI Scalingo, `psql`, Gatling 3 / Scala,
Temurin 21, `jq`.

**Spec:** [`docs/superpowers/specs/2026-09-01-harnais-tir-perf-design.md`](../specs/2026-09-01-harnais-tir-perf-design.md) (§7 Orchestration, §8 lot 4)

## Global Constraints

- **Le restore d'image de base est hors périmètre v1.** Le design le place en
  étape 2 (§7.1) ; sa mécanique n'est pas décidée (§10.3) et le fond de charge
  n'existe pas. Le workflow enchaîne donc `garde-fou → seed → tir → verdict →
  archivage`. L'étape s'insérera plus tard derrière un input `restore-image`,
  sans redécoupage. **Conséquence à écrire dans la doc :** un tir de ce workflow
  tourne sur une base ne contenant que le pool semé — bon pour valider la
  chaîne, pas pour juger un p95.
- **Aucune modification de code applicatif** dans `pass-emploi-api` ni
  `pass-emploi-connect` (D2 du design). Uniquement de la configuration.
- **Région Scalingo : `osc-secnum-fr1`.** Apps :
  `pass-emploi-connect-perf`, `pass-emploi-api-perf`, `mock-externes-perf`,
  `pass-emploi-logstash-perf`, et `gatling-perf` (injecteur, one-off).
- **Les secrets vivent dans l'environnement GitHub `Performance`**, jamais au
  niveau repo. Tout job qui lit un secret déclare `environment: Performance`.
  C'est déjà la convention de `logstash-perf.yml:42`.
- **`pool_size ≥ 5 × MAX_USERS`** (lot 0, `perf/seed/README.md`). En-dessous,
  les mêmes lignes restent chaudes en cache PostgreSQL et le tir mesure le
  cache. Le workflow refuse de tirer si la règle est violée.
- **`pool_prefix` se passe à psql sans guillemets** : `-v pool_prefix=perf-ft-`.
  Les scripts interpolent avec `:'pool_prefix'`, qui quote lui-même.
- **Le marqueur d'environnement de perf reste manuel**, posé une fois par
  environnement (`perf/seed/marquer-environnement.sql`). Le workflow ne le pose
  jamais : c'est le garde-fou anti-prod, et un workflow qui sait le poser sait
  le poser sur la prod.
- **Français** pour les noms d'étapes, messages et commentaires, comme les
  workflows existants. Commentaires réservés au non-évident (CLAUDE.md).

---

## État vérifié avant d'écrire ce plan

Ce que le harnais expose déjà, et sur quoi le workflow s'appuie tel quel :

| Brique | Interface | Fichier |
|---|---|---|
| Tir Scalingo | `make tir MAX_USERS=… RAMP_DURATION_IN_SECONDS=… HOLD_DURATION_IN_SECONDS=… TIR_SIMULATION=…` | `perf/Makefile:44-58` |
| Compilation | `make compile` → `./gradlew compileGatlingScala` | `perf/Makefile:25` |
| Seed | `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v pool_size=N -v pool_prefix=P -f seed.sql` | `perf/seed/seed.sql` |
| Vérification du seed | `psql … -v pool_size=N -f verifier.sql` | `perf/seed/verifier.sql` |
| Santé `api-perf` | `GET /health` | `pass-emploi-api/src/infrastructure/routes/health.controller.ts:17` |
| Santé `connect-perf` | `GET /health` | `pass-emploi-connect/src/app.controller.ts:29` |
| Santé `mock-externes-perf` | `GET /idp/protocol/openid-connect/certs` (pas de route de santé dédiée) | `perf/mock-externes/app.py:123` |
| Env de l'injecteur | `CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`, `CONNECT_URL`, `API_URL` portées par l'app `gatling-perf` | `perf/.env.template` |

**Deux conséquences structurantes :**

1. **Aucun secret nouveau pour les identifiants OIDC.** Ils sont déjà sur l'app
   `gatling-perf` et se lisent avec `scalingo env-get`. Les dupliquer en secrets
   GitHub créerait deux sources de vérité qui divergeraient au premier
   changement de client OIDC.
2. **De même pour `POOL_SIZE` / `POOL_PREFIX`** : ils sont portés par
   `mock-externes-perf`. Le workflow les **lit sur le mock** au lieu de les
   redéclarer, ce qui rend impossible le désappariement seed ↔ mock — la panne
   décrite dans `perf/seed/README.md` (`UTILISATEUR_INEXISTANT` au login).

## Contrainte GitHub à connaître avant de tester

`workflow_dispatch` n'est déclenchable que si le fichier de workflow existe sur
la **branche par défaut** (`master`). Tant que `perf-api.yml` ne vit que sur
`new-tests-perf`, ni l'UI ni `gh workflow run` ne le voient.

Contournement retenu pour la durée du lot, retiré en Task 8 : un déclencheur
`push` temporaire limité à la branche et au fichier. Chaque `git push` de la
tâche en cours vaut donc exécution réelle — c'est le seul test de bout en bout
qui a du sens ici (`act` ne rejouerait ni Scalingo, ni les secrets, ni le tir).

```yaml
  # TEMPORAIRE — retiré en fin de lot 4 : workflow_dispatch exige que le
  # fichier soit sur la branche par défaut, ce qui interdit de tester avant
  # d'avoir mergé. Un push sur la branche de dev tient lieu de déclencheur.
  push:
    branches: [new-tests-perf]
    paths: ['.github/workflows/perf-api.yml']
```

---

## Structure de fichiers

- Modifier : `.github/workflows/perf-env-shutdown.yml` — `environment: Performance` (fait, à committer)
- Modifier : `.github/workflows/perf-env-wakeup.yml` — idem
- Créer : `.github/workflows/perf-api.yml` — le workflow d'orchestration, tout le lot
- Modifier : `perf/README.md` — section « Tirer depuis la CI »
- Modifier : `docs/perf/harnais.md` — l'orchestration et ses limites v1
- Modifier : `docs/perf/README.md:69` — statut du sous-chantier « Harnais de tir »

Un seul fichier de workflow : les six étapes partagent l'environnement réveillé
et le contexte du tir. Les découper en workflows appelants/appelés ajouterait du
passage de paramètres pour aucune réutilisation réelle.

---

### Task 1 : Extinction et réveil — finir et committer

**Files:**
- Modify: `.github/workflows/perf-env-shutdown.yml`
- Modify: `.github/workflows/perf-env-wakeup.yml`

**Interfaces:**
- Produces : le secret `SCALINGO_API_TOKEN` résolu dans l'environnement
  `Performance` — toutes les tâches suivantes en dépendent.

- [ ] **Step 1 : Poser le secret `SCALINGO_API_TOKEN`**

Créer un token API dans le profil Scalingo (idéalement un compte de service
dédié : ce token peut scaler et supprimer des apps), puis, **dans un terminal
personnel** — pas via un outil qui écrirait le token dans un transcript :

```sh
gh secret set SCALINGO_API_TOKEN --env Performance --repo France-Travail/pass-emploi-tools
```

- [ ] **Step 2 : Vérifier que le secret est visible**

```sh
gh api repos/France-Travail/pass-emploi-tools/environments/Performance/secrets --jq '.secrets[].name'
```

Attendu : `SCALINGO_API_TOKEN` dans la liste, à côté des `LOGSTASH_PERF_*`.

- [ ] **Step 3 : Vérifier `environment: Performance` sur les deux jobs**

```sh
grep -n 'environment: Performance' .github/workflows/perf-env-*.yml
```

Attendu : une occurrence par fichier. Sans elle, `secrets.SCALINGO_API_TOKEN`
vaut la chaîne vide et `scalingo login` échoue.

- [ ] **Step 4 : Commit**

```sh
git add .github/workflows/perf-env-shutdown.yml .github/workflows/perf-env-wakeup.yml
git commit -m "feat(perf): éteint et rallume les apps perf hors heures d'usage"
```

- [ ] **Step 5 : Déclencher le réveil à la main et vérifier**

`workflow_dispatch` exigeant la branche par défaut, ce test n'est possible
qu'une fois la branche mergée, **ou** en le lançant depuis l'onglet Actions
après merge. À défaut, vérifier le geste équivalent en local :

```sh
scalingo --region osc-secnum-fr1 --app pass-emploi-api-perf scale web:1
scalingo --region osc-secnum-fr1 --app pass-emploi-api-perf ps
```

Attendu : le conteneur remonte **à sa taille d'avant** (Scalingo conserve la
taille dans la formation, seul le nombre change). Vérifier en particulier que
`pass-emploi-logstash-perf` revient en XL : un Logstash sous-dimensionné
provoque un blackout du drain et un tir aveugle (`docs/blackout-logs/`).

---

### Task 2 : Squelette de `perf-api.yml` et compilation sur PR

Premier livrable testable : une PR touchant `perf/**` casse si la simulation ne
compile plus. Aucune interaction avec Scalingo, donc aucun secret.

**Files:**
- Create: `.github/workflows/perf-api.yml`

**Interfaces:**
- Produces : les inputs du `workflow_dispatch`, consommés par toutes les tâches
  suivantes : `injecteur`, `max_users`, `ramp_duration_in_seconds`,
  `hold_duration_in_seconds`, `p95_threshold_ms`, `failed_percent_threshold`,
  `simulation`, `arret_apres_tir`.

- [ ] **Step 1 : Écrire le fichier**

```yaml
# Tir de performance sur l'environnement dédié : réveil, seed, tir, verdict,
# archivage. Le mode d'emploi manuel équivalent est dans perf/README.md.
#
# Hors périmètre v1 : le restore de l'image de base PostgreSQL (fond de
# charge). Un tir de ce workflow porte donc sur une base ne contenant que le
# pool semé — cf. docs/perf/harnais.md.
#
# Prérequis (environnement GitHub « Performance ») :
#   SCALINGO_API_TOKEN   token API Scalingo
#
# Le marqueur d'environnement de perf (perf/seed/marquer-environnement.sql)
# est posé à la main, une fois par base. Ce workflow ne le pose jamais : c'est
# le garde-fou anti-prod du seed.

name: Perf - Tir API

on:
  workflow_dispatch:
    inputs:
      injecteur:
        description: "Où s'exécute Gatling"
        type: choice
        options: [scalingo, runner]
        default: scalingo
      max_users:
        description: "Utilisateurs virtuels au palier (pool_size >= 5 x max_users)"
        default: "20"
      ramp_duration_in_seconds:
        description: "Durée de la montée en charge"
        default: "60"
      hold_duration_in_seconds:
        description: "Durée du palier"
        default: "120"
      p95_threshold_ms:
        description: "Seuil SLO I3 : p95 en millisecondes"
        default: "5000"
      failed_percent_threshold:
        description: "Seuil SLO I1 : pourcentage de requêtes en échec toléré"
        default: "1.0"
      simulation:
        description: "Simulation Gatling à jouer"
        default: passemploi.test.LoginEtAccueilFranceTravailSimulation
      arret_apres_tir:
        description: "Rescaler les apps à 0 en fin de tir"
        type: boolean
        default: false

  pull_request:
    paths:
      - 'perf/**'
      - '.github/workflows/perf-api.yml'

  # TEMPORAIRE — retiré en fin de lot 4 : workflow_dispatch exige que le
  # fichier soit sur la branche par défaut, ce qui interdit de tester avant
  # d'avoir mergé. Un push sur la branche de dev tient lieu de déclencheur.
  push:
    branches: [new-tests-perf]
    paths: ['.github/workflows/perf-api.yml']

env:
  SCALINGO_REGION: osc-secnum-fr1
  APPS: pass-emploi-connect-perf pass-emploi-api-perf mock-externes-perf pass-emploi-logstash-perf
  GATLING_APP: gatling-perf
  MOCK_APP: mock-externes-perf
  API_APP: pass-emploi-api-perf

jobs:
  # Sur PR : pas de tir (destructeur, et il monopolise l'environnement), mais
  # on vérifie que la simulation compile — pour ne pas le découvrir le jour où
  # on en a besoin.
  compile:
    name: Compilation de la simulation
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '21'
          cache: gradle

      - name: Compiler
        working-directory: perf
        run: make compile
```

- [ ] **Step 2 : Valider la syntaxe YAML**

```sh
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/perf-api.yml'))" && echo OK
```

Attendu : `OK`. Si `actionlint` est installé, le lancer aussi — il attrape les
erreurs de contexte GitHub qu'un parseur YAML laisse passer.

- [ ] **Step 3 : Vérifier que la compilation passe en local**

```sh
cd perf && make compile
```

Attendu : `BUILD SUCCESSFUL`. Si ça échoue en local, le job échouera aussi —
inutile de consommer un run.

- [ ] **Step 4 : Commit**

```sh
git add .github/workflows/perf-api.yml
git commit -m "feat(perf): squelette du workflow de tir, compilation sur PR"
```

---

### Task 3 : Réveil de l'environnement et attente de santé

Un tir déclenché à 21h tombe sur un environnement scalé à 0 par
`perf-env-shutdown.yml`. Le workflow ne doit pas dépendre du cron de 8h : il
réveille lui-même, puis **attend** — un conteneur scalé n'est pas un conteneur
qui répond, et tirer sur une app en cours de boot mesure le boot.

**Files:**
- Modify: `.github/workflows/perf-api.yml`

**Interfaces:**
- Consumes : les inputs de Task 2.
- Produces : le job `tir` avec ses apps réveillées et saines ; la variable
  d'environnement de job `DEBUT` (horodatage ISO 8601 UTC du début de fenêtre),
  consommée par Task 6 pour l'archivage.

- [ ] **Step 1 : Ajouter le job `tir` et ses deux premières étapes**

À la suite du job `compile` :

```yaml
  tir:
    name: Tir de performance
    if: github.event_name != 'pull_request'
    runs-on: ubuntu-latest
    environment: Performance
    steps:
      - uses: actions/checkout@v4

      - name: Vérifier les secrets requis
        env:
          SCALINGO_API_TOKEN: ${{ secrets.SCALINGO_API_TOKEN }}
        run: |
          [ -n "$SCALINGO_API_TOKEN" ] || { echo "::error::Secret SCALINGO_API_TOKEN manquant (environnement Performance)"; exit 1; }

      - name: Installer le CLI Scalingo
        run: curl -O https://cli-dl.scalingo.com/install.sh && bash install.sh

      - name: Se connecter à Scalingo
        run: scalingo login --api-token "${{ secrets.SCALINGO_API_TOKEN }}"

      - name: Réveiller les apps
        run: |
          for app in $APPS; do
            echo "::group::$app"
            scalingo --region "$SCALINGO_REGION" --app "$app" scale web:1
            echo "::endgroup::"
          done

      - name: Attendre que les apps répondent
        run: |
          base="https://%s.$SCALINGO_REGION.scalingo.io"
          # mock-externes n'a pas de route de santé dédiée : son JWKS fait
          # office de sonde, et c'est justement ce que connect appelle.
          sondes="pass-emploi-connect-perf|/health pass-emploi-api-perf|/health mock-externes-perf|/idp/protocol/openid-connect/certs"
          for sonde in $sondes; do
            app="${sonde%%|*}"; chemin="${sonde##*|}"
            url="$(printf "$base" "$app")$chemin"
            echo "Sonde $url"
            for essai in $(seq 1 30); do
              code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$url" || true)"
              [ "$code" = "200" ] && { echo "  $app OK apres ${essai} essai(s)"; break; }
              [ "$essai" = "30" ] && { echo "::error::$app ne repond pas (dernier code HTTP : $code)"; exit 1; }
              sleep 10
            done
          done

      - name: Marquer le début de la fenêtre de tir
        run: echo "DEBUT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$GITHUB_ENV"
```

- [ ] **Step 2 : Valider la syntaxe**

```sh
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/perf-api.yml'))" && echo OK
```

- [ ] **Step 3 : Pousser et regarder le run**

```sh
git add .github/workflows/perf-api.yml
git commit -m "feat(perf): réveille l'environnement de perf avant le tir"
git push
gh run watch "$(gh run list --workflow perf-api.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

Attendu : les trois sondes passent. Le job s'arrête après « Marquer le début »
— les étapes suivantes n'existent pas encore.

Si une sonde échoue en 502/503 après 5 minutes, c'est un vrai problème d'app,
pas de workflow : regarder `scalingo --app <app> logs`.

---

### Task 4 : Seed depuis la CI

**Files:**
- Modify: `.github/workflows/perf-api.yml`

**Interfaces:**
- Consumes : `DEBUT`, la session Scalingo, l'input `max_users`.
- Produces : `POOL_SIZE` et `POOL_PREFIX` dans `$GITHUB_ENV`, consommés par
  l'archivage des métadonnées (Task 6).

- [ ] **Step 1 : Vérifier à la main que la base est joignable depuis l'extérieur**

Avant d'écrire l'étape, lever le doute — cette vérification décide de la suite :

```sh
scalingo --region osc-secnum-fr1 --app pass-emploi-api-perf env-get DATABASE_URL
psql "<l'URL obtenue>" -c '\conninfo'
```

- Si la connexion passe : continuer avec les steps ci-dessous.
- Si elle échoue (add-on sans accès internet) : l'alternative est
  `scalingo db-tunnel`, qui exige une clé SSH sur le compte — donc un secret
  `SCALINGO_SSH_KEY` en plus. Activer l'accès internet sur l'add-on est plus
  simple et déjà fait sur cet environnement d'après le commentaire de
  `perf-env-shutdown.yml`. Ne basculer sur le tunnel que si l'accès direct est
  refusé pour de bon.

- [ ] **Step 2 : Ajouter l'étape de seed**

```yaml
      - name: Installer psql
        run: sudo apt-get update && sudo apt-get install -y --no-install-recommends postgresql-client

      # POOL_SIZE et POOL_PREFIX sont lus sur le mock plutôt que redéclarés
      # ici : le sub que le mock tire doit correspondre à un id_authentification
      # semé, sinon le login échoue en UTILISATEUR_INEXISTANT. Une seule
      # source de vérité rend le désappariement impossible.
      - name: Lire les paramètres du pool sur mock-externes
        run: |
          taille="$(scalingo --region "$SCALINGO_REGION" --app "$MOCK_APP" env-get POOL_SIZE)"
          prefixe="$(scalingo --region "$SCALINGO_REGION" --app "$MOCK_APP" env-get POOL_PREFIX)"
          [ -n "$taille" ] || { echo "::error::POOL_SIZE absent de $MOCK_APP"; exit 1; }
          [ -n "$prefixe" ] || { echo "::error::POOL_PREFIX absent de $MOCK_APP"; exit 1; }
          echo "POOL_SIZE=$taille" >> "$GITHUB_ENV"
          echo "POOL_PREFIX=$prefixe" >> "$GITHUB_ENV"
          echo "Pool : $taille identités préfixées $prefixe"

      # Lot 0 : sous 5 identités par utilisateur virtuel, les mêmes lignes
      # restent chaudes en cache PostgreSQL et le tir mesure le cache.
      - name: Vérifier pool_size >= 5 x max_users
        run: |
          minimum=$(( 5 * ${{ inputs.max_users }} ))
          [ "$POOL_SIZE" -ge "$minimum" ] || {
            echo "::error::POOL_SIZE=$POOL_SIZE < $minimum (5 x max_users=${{ inputs.max_users }}) : agrandir le pool sur $MOCK_APP ou baisser max_users"
            exit 1
          }

      - name: Semer le pool
        run: |
          url="$(scalingo --region "$SCALINGO_REGION" --app "$API_APP" env-get DATABASE_URL)"
          echo "::add-mask::$url"
          psql "$url" -v ON_ERROR_STOP=1 \
               -v pool_size="$POOL_SIZE" -v pool_prefix="$POOL_PREFIX" \
               -f perf/seed/seed.sql
          psql "$url" -v ON_ERROR_STOP=1 \
               -v pool_size="$POOL_SIZE" -f perf/seed/verifier.sql
```

> `pool_prefix` se passe **sans guillemets** : `seed.sql` interpole avec
> `:'pool_prefix'`, qui quote lui-même. Des guillemets ici sèmeraient le pool
> sous `'perf-ft-'0`.

> `::add-mask::` avant tout usage de `DATABASE_URL` : elle porte le mot de
> passe, et une commande en échec l'imprimerait dans le log du run.

- [ ] **Step 3 : Pousser et vérifier**

```sh
git add .github/workflows/perf-api.yml
git commit -m "feat(perf): sème le pool depuis la CI, apparié au mock"
git push && gh run watch "$(gh run list --workflow perf-api.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

Attendu : `verifier.sql` annonce `POOL_SIZE` jeunes en base. S'il annonce
`0 jeunes en base`, c'est le piège des guillemets sur `pool_prefix`.

Attendu aussi : le garde-fou du seed **passe** — la base porte son marqueur. S'il
refuse, c'est que le marqueur n'a jamais été posé sur cette base : le poser à la
main (`marquer-environnement.sql`), une fois, et surtout pas depuis le workflow.

---

### Task 5 : Tir et verdict

**Files:**
- Modify: `.github/workflows/perf-api.yml`

**Interfaces:**
- Consumes : les inputs de charge et de seuils, la session Scalingo.
- Produces : `sortie-tir.txt` à la racine du workspace (console du tir), et le
  statut d'échec du job si un SLO est violé.

- [ ] **Step 1 : Ajouter l'étape de tir**

```yaml
      - name: Tirer
        if: inputs.injecteur == 'scalingo'
        working-directory: perf
        run: |
          set -o pipefail
          make tir \
            MAX_USERS='${{ inputs.max_users }}' \
            RAMP_DURATION_IN_SECONDS='${{ inputs.ramp_duration_in_seconds }}' \
            HOLD_DURATION_IN_SECONDS='${{ inputs.hold_duration_in_seconds }}' \
            TIR_SIMULATION='${{ inputs.simulation }}' \
            2>&1 | tee "$GITHUB_WORKSPACE/sortie-tir.txt"
```

Les seuils `P95_THRESHOLD_MS` et `FAILED_PERCENT_THRESHOLD` sont lus par la
simulation depuis l'environnement de l'app `gatling-perf`. Passer les inputs
au conteneur one-off demande de les ajouter à la cible `tir` du Makefile :

- [ ] **Step 2 : Étendre la cible `tir` aux seuils**

Dans `perf/Makefile`, ajouter à la commande `scalingo run` :

```make
	  --env P95_THRESHOLD_MS=$(P95_THRESHOLD_MS) \
	  --env FAILED_PERCENT_THRESHOLD=$(FAILED_PERCENT_THRESHOLD) \
```

avec les valeurs par défaut à côté des autres :

```make
P95_THRESHOLD_MS ?= 5000
FAILED_PERCENT_THRESHOLD ?= 1.0
```

puis les passer depuis le workflow, à la suite des autres variables :

```yaml
            P95_THRESHOLD_MS='${{ inputs.p95_threshold_ms }}' \
            FAILED_PERCENT_THRESHOLD='${{ inputs.failed_percent_threshold }}' \
```

- [ ] **Step 3 : Vérifier localement que la cible accepte les nouvelles variables**

```sh
cd perf && make -n tir P95_THRESHOLD_MS=1234 | grep P95_THRESHOLD_MS
```

Attendu : `--env P95_THRESHOLD_MS=1234` dans la commande affichée. (`make -n`
affiche sans exécuter : aucun tir déclenché.)

- [ ] **Step 4 : Vérifier que le verdict remonte**

Le point à lever : `scalingo run` propage-t-il le code de sortie du conteneur ?
Gatling sort en non-zéro quand une assertion échoue, et c'est **le** mécanisme
de verdict. Le vérifier explicitement, avec un seuil volontairement absurde :

```sh
cd perf && make tir MAX_USERS=2 HOLD_DURATION_IN_SECONDS=10 P95_THRESHOLD_MS=1; echo "code de sortie : $?"
```

Attendu : code de sortie non nul. **Si le code est 0**, ajouter au workflow un
filet de sécurité qui lit la console plutôt que le code :

```yaml
      - name: Verdict
        if: inputs.injecteur == 'scalingo'
        run: |
          grep -qi 'assertion.*failed\|Global: .*failed' sortie-tir.txt && {
            echo "::error::Assertion Gatling en échec — SLO non tenu"
            exit 1
          } || echo "Assertions tenues"
```

- [ ] **Step 5 : Commit et run réel**

```sh
git add .github/workflows/perf-api.yml perf/Makefile
git commit -m "feat(perf): tire depuis la CI et fait remonter le verdict SLO"
git push && gh run watch "$(gh run list --workflow perf-api.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

Attendu : le résumé Gatling (requêtes, p95, taux d'erreur) dans le log du run,
et un job vert si les seuils sont tenus.

---

### Task 6 : Archivage et extinction

**Files:**
- Modify: `.github/workflows/perf-api.yml`

**Interfaces:**
- Consumes : `DEBUT`, `POOL_SIZE`, `POOL_PREFIX`, `sortie-tir.txt`.
- Produces : un artefact `tir-<run_id>` contenant `sortie-tir.txt` et
  `metadonnees.json`.

- [ ] **Step 1 : Ajouter la collecte des métadonnées**

Les métadonnées du §7.3 du design. Le SHA déployé et le plan Scalingo sont
capturés **bruts** : les parser les rendrait fragiles pour un contenu qu'on
relit à l'œil.

```yaml
      - name: Rassembler les métadonnées
        if: always()
        run: |
          fin="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
          for app in $APPS $GATLING_APP; do
            echo "### $app" >> etat-scalingo.txt
            scalingo --region "$SCALINGO_REGION" --app "$app" ps >> etat-scalingo.txt 2>&1 || true
            scalingo --region "$SCALINGO_REGION" --app "$app" deployments 2>&1 | head -3 >> etat-scalingo.txt || true
          done
          jq -n \
            --arg debut "$DEBUT" --arg fin "$fin" \
            --arg injecteur '${{ inputs.injecteur }}' \
            --arg simulation '${{ inputs.simulation }}' \
            --arg max_users '${{ inputs.max_users }}' \
            --arg ramp '${{ inputs.ramp_duration_in_seconds }}' \
            --arg hold '${{ inputs.hold_duration_in_seconds }}' \
            --arg p95 '${{ inputs.p95_threshold_ms }}' \
            --arg echecs '${{ inputs.failed_percent_threshold }}' \
            --arg pool_size "$POOL_SIZE" --arg pool_prefix "$POOL_PREFIX" \
            --arg seed_sha "$(git log -1 --format=%h -- perf/seed)" \
            --arg image_de_base "aucune (hors périmètre v1)" \
            --arg run "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}" \
            --arg verdict '${{ job.status }}' \
            '{fenetre: {debut: $debut, fin: $fin}, injecteur: $injecteur,
              simulation: $simulation,
              charge: {max_users: $max_users, ramp_s: $ramp, hold_s: $hold},
              seuils: {p95_ms: $p95, echecs_pct: $echecs},
              donnees: {pool_size: $pool_size, pool_prefix: $pool_prefix,
                        seed_sha: $seed_sha, image_de_base: $image_de_base},
              run: $run, verdict: $verdict}' > metadonnees.json
          cat metadonnees.json

      - name: Archiver
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: tir-${{ github.run_id }}
          path: |
            sortie-tir.txt
            etat-scalingo.txt
            metadonnees.json
            perf/build/reports/gatling/**
          if-no-files-found: warn
          retention-days: 90
```

> `perf/build/reports/gatling/**` n'existe qu'en régime `runner` (Task 7) : le
> système de fichiers d'un one-off Scalingo est éphémère et le rapport HTML
> meurt avec le conteneur. En régime `scalingo`, l'artefact se réduit à la
> console et aux métadonnées — d'où `if-no-files-found: warn`.

- [ ] **Step 2 : Ajouter l'extinction optionnelle**

```yaml
      # Par défaut on laisse tourner : perf-env-shutdown.yml éteint à 20h de
      # toute façon, et un tir de milieu de journée est presque toujours suivi
      # d'un autre. L'input sert au tir de fin de soirée.
      - name: Éteindre les apps
        if: always() && inputs.arret_apres_tir
        run: |
          for app in $APPS; do
            scalingo --region "$SCALINGO_REGION" --app "$app" scale web:0
          done
```

- [ ] **Step 3 : Pousser et vérifier l'artefact**

```sh
git add .github/workflows/perf-api.yml
git commit -m "feat(perf): archive rapport et métadonnées du tir"
git push && gh run watch "$(gh run list --workflow perf-api.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run download "$(gh run list --workflow perf-api.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

Attendu : `metadonnees.json` lisible, `sortie-tir.txt` contenant le résumé
Gatling, `etat-scalingo.txt` contenant les plans et les derniers déploiements.

---

### Task 7 : Régime `runner`

Même seed, même simulation, même verdict — seul l'endroit d'exécution change
(D6). Son intérêt propre : le rapport HTML complet, que le régime Scalingo ne
peut pas rapatrier. Sa limite, à écrire dans la doc : un runner GitHub mutualisé
ajoute du jitter sur le p95, qui est précisément ce qu'on asserte. **Le régime
de référence reste `scalingo`.**

**Files:**
- Modify: `.github/workflows/perf-api.yml`

**Interfaces:**
- Consumes : les mêmes inputs ; les variables d'env de `gatling-perf`.
- Produces : `perf/build/reports/gatling/**`, ramassé par l'archivage de Task 6.

- [ ] **Step 1 : Ajouter le JDK, conditionné au régime**

À insérer avant l'étape de tir :

```yaml
      - uses: actions/setup-java@v4
        if: inputs.injecteur == 'runner'
        with:
          distribution: temurin
          java-version: '21'
          cache: gradle
```

- [ ] **Step 2 : Ajouter le tir sur runner**

Les identifiants OIDC sont lus sur `gatling-perf` plutôt que dupliqués en
secrets GitHub — une seule source de vérité, qui suit le client OIDC quand il
change.

```yaml
      - name: Tirer sur le runner
        if: inputs.injecteur == 'runner'
        working-directory: perf
        run: |
          set -o pipefail
          for v in CLIENT_ID CLIENT_SECRET REDIRECT_URI CONNECT_URL API_URL; do
            valeur="$(scalingo --region "$SCALINGO_REGION" --app "$GATLING_APP" env-get "$v")"
            [ -n "$valeur" ] || { echo "::error::$v absent de $GATLING_APP"; exit 1; }
            echo "::add-mask::$valeur"
            export "$v=$valeur"
          done
          export MAX_USERS='${{ inputs.max_users }}'
          export RAMP_DURATION_IN_SECONDS='${{ inputs.ramp_duration_in_seconds }}'
          export HOLD_DURATION_IN_SECONDS='${{ inputs.hold_duration_in_seconds }}'
          export P95_THRESHOLD_MS='${{ inputs.p95_threshold_ms }}'
          export FAILED_PERCENT_THRESHOLD='${{ inputs.failed_percent_threshold }}'
          ./gradlew --no-daemon --console=plain -q gatlingRun \
            --simulation '${{ inputs.simulation }}' \
            2>&1 | tee "$GITHUB_WORKSPACE/sortie-tir.txt"
```

> `make run` n'est pas utilisable ici : la cible dépend de `.env`, absent en CI.
> On appelle Gradle directement avec l'environnement déjà exporté.

- [ ] **Step 3 : Élargir l'étape « Verdict » aux deux régimes**

Retirer le `if: inputs.injecteur == 'scalingo'` de l'étape Verdict de Task 5 :
elle lit `sortie-tir.txt`, que les deux régimes produisent.

- [ ] **Step 4 : Lancer un tir en régime runner**

Le déclencheur `push` temporaire ne porte pas d'inputs : `injecteur` prendrait
sa valeur par défaut. Basculer temporairement le défaut sur `runner`, pousser,
observer, puis remettre `scalingo`.

Attendu : le job est vert et l'artefact contient cette fois
`perf/build/reports/gatling/<horodatage>/index.html`.

- [ ] **Step 5 : Commit**

```sh
git add .github/workflows/perf-api.yml
git commit -m "feat(perf): régime runner, avec rapport HTML archivé"
```

---

### Task 8 : Documentation et retrait de l'échafaudage

**Files:**
- Modify: `.github/workflows/perf-api.yml`
- Modify: `perf/README.md`
- Modify: `docs/perf/harnais.md`
- Modify: `docs/perf/README.md:69`

- [ ] **Step 1 : Retirer le déclencheur `push` temporaire**

```sh
grep -n 'TEMPORAIRE' -A 4 .github/workflows/perf-api.yml
```

Supprimer le bloc `push:` et son commentaire. `workflow_dispatch` prend le
relais dès que la branche est mergée dans `master`.

- [ ] **Step 2 : Ajouter « Tirer depuis la CI » à `perf/README.md`**

À placer juste après la section « Tirer depuis Scalingo », en remplaçant la
phrase qui annonce le workflow comme futur (« rapatrier le rapport en artifact
est le travail du futur workflow GitHub Actions ») :

```markdown
## Tirer depuis la CI

`Actions → Perf - Tir API → Run workflow`. Le workflow réveille les apps,
sème le pool, tire et archive.

| Input | Défaut | Ce qu'il change |
|---|---|---|
| `injecteur` | `scalingo` | `runner` archive le rapport HTML complet, mais son p95 porte le jitter d'un runner mutualisé |
| `max_users` | `20` | Refusé si `POOL_SIZE < 5 × max_users` |
| `p95_threshold_ms` / `failed_percent_threshold` | `5000` / `1.0` | Les seuils SLO I3 et I1 assertés |
| `arret_apres_tir` | `false` | Rescale les apps à 0 en fin de tir |

Le rapport, la console et les métadonnées du tir sont dans l'artefact
`tir-<run_id>`, conservé 90 jours.

> Le workflow **ne restaure aucune image de base** : la base ne contient que le
> pool semé. Les chiffres valident la chaîne, pas un p95 de production.
```

- [ ] **Step 3 : Ajouter l'orchestration à `docs/perf/harnais.md`**

Une section « Orchestration », qui dit ce qui est automatisé et ce qui reste à
la main — c'est le livrable d'équipe, pas le mode d'emploi :

```markdown
## Orchestration

Un tir se déclenche depuis GitHub Actions (`Perf - Tir API`), qui enchaîne
réveil de l'environnement, seed, tir, verdict et archivage. Les commandes
équivalentes en manuel sont dans [`perf/README.md`](../../perf/README.md).

Trois gestes restent **délibérément** hors du workflow :

| Geste | Pourquoi |
|---|---|
| Poser le marqueur d'environnement de perf | C'est le garde-fou anti-prod du seed. Un workflow qui sait le poser sait le poser sur la production. |
| Restaurer l'image de base PostgreSQL | Mécanique non décidée, et le fond de charge n'existe pas encore. **Tant qu'elle manque, un tir porte sur une base ne contenant que le pool semé.** |
| Choisir les seuils SLO | Ils viennent de l'atelier SLO, pas d'un défaut de workflow. |

Les apps de perf sont éteintes la nuit et le week-end par
`perf-env-shutdown.yml` et rallumées à 8h par `perf-env-wakeup.yml`. Le
workflow de tir ne s'appuie pas sur ce cron : il réveille lui-même et attend
que les sondes de santé répondent.
```

- [ ] **Step 4 : Basculer le statut du sous-chantier dans `docs/perf/README.md`**

Remplacer la cellule de statut de la ligne « Harnais de tir » par :

```
WIP — tir déclenchable depuis la CI (réveil, seed, tir, verdict, archivage). Reste : image de base PostgreSQL (fond de charge), sans laquelle un tir ne juge pas un p95.
```

Et ajouter à l'historique :

```markdown
- **2026-09-07** — lot 4 livré : le tir se déclenche depuis GitHub Actions, sur
  environnement dédié réveillé à la demande. Limite assumée : pas de fond de
  charge en base tant que l'image de base n'existe pas.
```

- [ ] **Step 5 : Commit**

```sh
git add .github/workflows/perf-api.yml perf/README.md docs/perf/harnais.md docs/perf/README.md
git commit -m "docs(perf): orchestration du tir depuis la CI"
```

---

## Points à lever pendant l'implémentation

1. **`scalingo run` propage-t-il le code de sortie du conteneur ?** Décide si le
   verdict tient au code de retour ou à la lecture de la console (Task 5 Step 4).
2. **La base de perf est-elle joignable depuis un runner GitHub ?** Décide entre
   `psql` direct et `db-tunnel` + clé SSH (Task 4 Step 1).
3. **`scale web:1` restitue-t-il la taille de conteneur ?** À vérifier surtout
   sur `pass-emploi-logstash-perf` : un XL revenu en S donne un blackout du
   drain et un tir aveugle (Task 1 Step 5).
4. **`mock-externes` régénère-t-il sa clé de signature au réveil ?** Si la clé
   n'est pas persistée, chaque scale-up en fabrique une nouvelle — sans
   conséquence tant que tous les workers partagent la même (corrigé par
   `605abf3`), mais un JWT émis avant le réveil ne validerait plus.

## Hors périmètre de ce lot

Restore de l'image de base, journal versionné des tirs
(`docs/perf/journal-des-tirs.md`, §7.3), tir programmé la nuit, corrélation
APM/logs au-delà de la fenêtre horodatée, scénarios autres que login + accueil FT.
