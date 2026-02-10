# CI/CD Workflows Réutilisables

Ce répertoire contient les workflows et actions GitHub réutilisables pour le projet Pass Emploi.

---

## Reusable Workflows

### 1. dependabot.yml

**Fonctionnalités :**
- Auto-merge des PRs Dependabot patch/minor (après passage des checks)
- Rebase automatique des PRs stale toutes les 6h
- Détection via user ID 49699333 (Dependabot bot)

**Usage dans un repo :**
```yaml
# .github/workflows/dependabot.yml
name: Dependabot

on:
  pull_request_target:
    types: [opened, synchronize, reopened]
  schedule:
    - cron: '0 */6 * * *'
  workflow_dispatch:

jobs:
  dependabot:
    uses: France-Travail/pass-emploi-tools/.github/workflows/dependabot.yml@master
    secrets: inherit
```

**Secrets requis :**
- `GITHUB_TOKEN` (fourni automatiquement)

---

### 2. security-alerts.yml

**Fonctionnalités :**
- Surveillance toutes les 3h des CVEs high/critical ouvertes
- Alerte Mattermost avec détails (max 10 CVEs affichées)
- Mention @here pour notifier l'équipe

**Usage dans un repo :**
```yaml
# .github/workflows/security-alerts.yml
name: Security Alerts

on:
  schedule:
    - cron: '0 */3 * * *'
  workflow_dispatch:

jobs:
  security-alerts:
    uses: France-Travail/pass-emploi-tools/.github/workflows/security-alerts.yml@master
    with:
      repo-name: 'pass-emploi-api'  # Nom affiché dans le message Mattermost
    secrets: inherit
```

**Secrets requis :**
- `DEPENDABOT_ALERTS_READER` : Token GitHub avec scope `security-events:read`
- `MATTERMOST_WEBHOOK_URL` : URL du webhook Mattermost

---

### 3. security-checks.yml

**Fonctionnalités :**
- Job `sast` : CodeQL (JavaScript/TypeScript) avec queries security-and-quality
- Job `sca` : Dependency Review (sur PR) + Yarn audit (severity high)
- Fail si vulnérabilités high/critical détectées
- Upload automatique des résultats dans GitHub Security

**Usage dans un repo (avec défaut) :**
```yaml
# .github/workflows/security-checks.yml
name: Security Checks

on:
  push:
    branches: [develop, master]
  pull_request:
  schedule:
    - cron: '0 8 * * 1'

jobs:
  security-checks:
    uses: France-Travail/pass-emploi-tools/.github/workflows/security-checks.yml@master
    secrets: inherit
```

**Usage avec commande d'installation custom :**
```yaml
jobs:
  security-checks:
    uses: France-Travail/pass-emploi-tools/.github/workflows/security-checks.yml@master
    with:
      install-command: 'YARN_ENABLE_SCRIPTS=false yarn install --immutable'
    secrets: inherit
```

**Secrets requis :**
- Aucun (utilise `GITHUB_TOKEN` automatiquement)

---

## Composite Actions

### 1. setup-node-yarn

**Description :** Setup Node.js avec cache Yarn et installation des dépendances

**Utilité :** Évite de répéter les étapes de setup dans chaque workflow

**Usage :**
```yaml
steps:
  - uses: France-Travail/pass-emploi-tools/.github/actions/setup-node-yarn@master
    with:
      install-command: 'yarn install --immutable'  # Optionnel (défaut)
```

**Inputs :**
- `install-command` (optionnel) : Commande d'installation (défaut : `yarn install --immutable`)

**Ce que fait cette action :**
1. Checkout du repository
2. Setup Node.js (version depuis `.nvmrc`)
3. Configure le cache Yarn
4. Installe les dépendances

---

### 2. sonarqube-scan

**Description :** Download du rapport de couverture et scan SonarQube

**Utilité :** Standardise le scan SonarQube avec récupération du coverage

**Usage :**
```yaml
jobs:
  sonarqube:
    needs: test  # Doit attendre que les tests soient terminés
    runs-on: ubuntu-latest
    steps:
      - uses: France-Travail/pass-emploi-tools/.github/actions/sonarqube-scan@master
        with:
          sonar-token: ${{ secrets.SONAR_TOKEN }}
```

**Inputs :**
- `sonar-token` (requis) : Token SonarQube

**Prérequis :**
- Un artifact `coverage-report` doit avoir été uploadé par un job précédent (voir exemple ci-dessous)

**Exemple complet avec upload du coverage :**
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - run: yarn test  # Génère coverage/
      - uses: actions/upload-artifact@v7
        with:
          name: coverage-report
          path: coverage/
          retention-days: 1

  sonarqube:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: France-Travail/pass-emploi-tools/.github/actions/sonarqube-scan@master
        with:
          sonar-token: ${{ secrets.SONAR_TOKEN }}
```

---

## Versioning

**Recommandation actuelle :** Utiliser `@master` pour toujours avoir la dernière version

**Alternative (versioning strict) :**
- Utiliser des tags : `@v1.0.0`
- Permet un contrôle précis et des rollbacks
- Nécessite de bumper manuellement les versions dans chaque repo

**Exemple avec tag :**
```yaml
uses: France-Travail/pass-emploi-tools/.github/workflows/security-checks.yml@v1.0.0
```

---

## Repos utilisant ces workflows

- **pass-emploi-web** : Web conseiller (Next.js)
- **pass-emploi-api** : Backend API (NestJS)
- **pass-emploi-connect** : Auth OIDC (NestJS)

---

## Configuration des Repos Appelants

### Prérequis pour Dependabot Auto-Merge

Pour que le workflow `dependabot.yml` fonctionne correctement, chaque repo appelant doit avoir :

**1. Auto-merge activé dans les paramètres du repo**

```
Settings → General → Pull Requests
☑ Allow auto-merge
```

**2. Required checks configurés avant merge sur `develop`**

```
Settings → Branches → Branch protection rules → develop
☑ Require status checks to pass before merging
```

**Checks recommandés (exemple pass-emploi-web) :**
- `SAST (Static Analysis)` - CodeQL security scan
- `SCA (Dependency Audit)` - Dependency Review + Yarn audit
- `Tests` - Tests unitaires avec coverage
- `Lint and Typecheck` - ESLint + TypeScript

**Important :** Sans ces checks configurés, Dependabot pourra activer l'auto-merge mais les PRs ne seront jamais mergées automatiquement (elles attendront indéfiniment que les checks passent).

### Configuration Mattermost

Pour recevoir les alertes de sécurité, configurer le webhook Mattermost dans les secrets du repo :
```
Settings → Secrets and variables → Actions → New repository secret
Name: MATTERMOST_WEBHOOK_URL
Value: https://mattermost.example.com/hooks/...
```

---

## Maintenance

**Pour modifier un workflow ou une action :**

1. Faire les modifications dans ce repo (pass-emploi-tools)
2. Tester via une PR de test
3. Merger sur `main`
4. Les 3 repos appelants utiliseront automatiquement la nouvelle version (si `@master`)

**Breaking changes :**
- Documenter le changement dans ce README
- Notifier l'équipe
- Option : Créer un nouveau tag versionné pour migration progressive

---

## Secrets GitHub à configurer

**Dans chaque repo appelant (web, api, connect) :**
- `SONAR_TOKEN` : Token SonarCloud
- `DEPENDABOT_ALERTS_READER` : Token GitHub avec scope `security-events:read`
- `MATTERMOST_WEBHOOK_URL` : URL du webhook Mattermost

**Secrets automatiques (fournis par GitHub) :**
- `GITHUB_TOKEN` : Token fourni automatiquement par GitHub Actions

---

## Exemples de structure complète

### Exemple : pass-emploi-api

```
.github/workflows/
├── dependabot.yml                  # Appelle le reusable workflow
├── security-alerts.yml             # Appelle le reusable workflow
├── security-checks.yml             # Appelle le reusable workflow
└── tests-and-quality-checks.yml    # Local (trop spécifique)
```

**Contenu de `tests-and-quality-checks.yml` (exemple NestJS + PostgreSQL) :**
```yaml
name: Tests and Quality Checks

on:
  push:
    branches: [develop, master]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: France-Travail/pass-emploi-tools/.github/actions/setup-node-yarn@master
        with:
          install-command: 'YARN_ENABLE_SCRIPTS=false yarn install --immutable'
      - run: yarn lint

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:14-3.2-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
      redis:
        image: redis:8-alpine
        ports:
          - 6767:6379
    env:
      DATABASE_URL: postgres://test:test@localhost:5432/test
      REDIS_URL: redis://localhost:6767
    steps:
      - uses: France-Travail/pass-emploi-tools/.github/actions/setup-node-yarn@master
        with:
          install-command: 'YARN_ENABLE_SCRIPTS=false yarn install --immutable'
      - run: yarn test:ci
      - uses: actions/upload-artifact@v7
        with:
          name: coverage-report
          path: coverage/
          retention-days: 1

  sonarqube:
    needs: test
    runs-on: ubuntu-latest
    if: github.event.pull_request.user.id != 49699333  # Skip Dependabot
    steps:
      - uses: France-Travail/pass-emploi-tools/.github/actions/sonarqube-scan@master
        with:
          sonar-token: ${{ secrets.SONAR_TOKEN }}
```

---

## Support

Pour toute question sur l'utilisation de ces workflows, contacter le Tech Lead ou créer une issue dans pass-emploi-tools.
