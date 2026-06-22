# Contexte Global Pass Emploi

> **Doc transverse — source de vérité partagée.** Versionnée dans `pass-emploi-tools`.
> Importée automatiquement par les `CLAUDE.md` des repos via
> `@../pass-emploi-tools/docs/CONTEXTE-TRANSVERSE.md` (chargement garanti au démarrage).
> Ne **pas** dupliquer ce contenu dans un CLAUDE.md d'app.
>
> Index des gros sujets transverses (invariants + réf. stable, toujours chargé) ↓.
> Règles de doc d'équipe : `pass-emploi-tools/docs/CONVENTIONS-DOC.md`.

@./SUJETS-TRANSVERSES.md

## Vue d'ensemble

**Pass Emploi** (anciennement CEJ - Contrat d'Engagement Jeune) est une plateforme numérique développée pour accompagner
les bénéficiaires dans leur parcours d'insertion professionnelle.

**Note :** Le projet s'appelle maintenant "pass-emploi" mais l'ancienne dénomination "CEJ" reste présente dans certaines
parties du code legacy.

## Architecture Globale

### Schéma des interactions

```
                                    ┌─────────────────────┐
                                    │   IDPs Externes     │
                                    │  ┌───────────────┐  │
                                    │  │ France Travail│  │
                                    │  │    (OIDC)     │  │
                                    │  ├───────────────┤  │
                                    │  │     MILO      │  │
                                    │  │    (OIDC)     │  │
                                    │  ├───────────────┤  │
                                    │  │   Conseil     │  │
                                    │  │Départemental  │  │
                                    │  └───────────────┘  │
                                    └──────────┬──────────┘
                                               │
                                               ▼
┌──────────────────┐              ┌─────────────────────────┐
│                  │   Auth       │                         │
│  pass_emploi_app │◄────────────►│   pass-emploi-connect   │
│  (App Mobile)    │   OIDC       │   (Auth Broker OIDC)    │
│  Flutter         │              │   NestJS + Redis        │
│                  │              │                         │
└────────┬─────────┘              └─────────────┬───────────┘
         │                                      │
         │                                      │ Auth
         │ API                                  ▼
         │                        ┌─────────────────────────┐
         │                        │                         │
         └───────────────────────►│    pass-emploi-api      │
                                  │    (Backend API)        │
┌──────────────────┐   API        │    NestJS + PostgreSQL  │
│                  │◄────────────►│    + Redis              │
│  pass-emploi-web │              │                         │
│  (Web Conseiller)│              └─────────────┬───────────┘
│  Next.js         │                            │
│                  │◄───────────────────────────┘
└──────────────────┘      Firebase (Chat temps réel)
         │
         │ Auth OIDC
         ▼
┌───────────────────┐
│pass-emploi-connect│
└───────────────────┘
```

### Les repositories

| Repository              | Rôle                            | Stack                        | Public cible           |
|-------------------------|---------------------------------|------------------------------|------------------------|
| **pass-emploi-api**     | Backend API REST                | NestJS, PostgreSQL, Redis    | -                      |
| **pass-emploi-web**     | Application web conseiller      | Next.js 15, React 19         | Conseillers            |
| **pass-emploi-connect** | Service d'authentification OIDC | NestJS, oidc-provider, Redis | -                      |
| **pass_emploi_app**     | Application mobile              | Flutter                      | Bénéficiaires (jeunes) |
| **pass-emploi-tools**   | Outillage / infra logs mutualisée (Logstash, templates Elasticsearch versionnés) | Logstash, ES `.console` | - |
| **pass-emploi-auth**    | Keycloak (IdP), configuré via Terraform, packagé buildpack Scalingo | Keycloak, Terraform | - |
| **pass-emploi-analytics** | Pipeline de données / suivi analytics (ex. taux de pénétration) | Make | - |

## Dispositifs d'accompagnement

### CEJ (Contrat d'Engagement Jeune)

| Critère        | Valeur                                                 |
|----------------|--------------------------------------------------------|
| **Public**     | Jeunes 16-25 ans (29 ans si RQTH)                      |
| **Durée**      | 6-18 mois                                              |
| **Intensité**  | 15-20h/semaine minimum                                 |
| **Allocation** | Jusqu'à 561,68€/mois                                   |
| **Structures** | France Travail + Missions Locales                      |
| **Objectif**   | Emploi durable, apprentissage ou formation qualifiante |

### PACEA (Parcours Contractualisé d'Accompagnement)

| Critère        | Valeur                         |
|----------------|--------------------------------|
| **Public**     | Jeunes 16-25 ans               |
| **Durée**      | Maximum 24 mois                |
| **Intensité**  | Modulable                      |
| **Allocation** | Ponctuelle (jusqu'à 6x RSA/an) |
| **Structures** | Missions Locales               |
| **Objectif**   | Autonomie et emploi            |

## Acteurs et structures

### Types d'utilisateurs

- **Bénéficiaire / Jeune** : Utilisateur accompagné (app mobile)
- **Conseiller** : Accompagne les bénéficiaires (app web)
- **Superviseur** : Supervise plusieurs conseillers

### Structures (organisations)

| Structure                 | Code           | Description           |
|---------------------------|----------------|-----------------------|
| **France Travail**        | `POLE_EMPLOI`  | Ex-Pôle Emploi        |
| **Mission Locale**        | `MILO`         | Accompagnement jeunes |
| **Conseil Départemental** | `CONSEIL_DEPT` | RSA, BRSA             |
| **Pass Emploi**           | `PASS_EMPLOI`  | Structure générique   |

**Note :** Un conseiller peut appartenir à plusieurs structures et travailler sur plusieurs dispositifs simultanément.

## Glossaire

| Terme                    | Définition                                                 |
|--------------------------|------------------------------------------------------------|
| **Pass Emploi**          | Nom actuel du projet                                       |
| **CEJ**                  | Contrat d'Engagement Jeune (ancienne dénomination)         |
| **Bénéficiaire / Jeune** | Utilisateur accompagné par un conseiller                   |
| **Conseiller**           | Professionnel qui accompagne les bénéficiaires             |
| **Portefeuille**         | Ensemble des bénéficiaires suivis par un conseiller        |
| **Action**               | Tâche assignée à un bénéficiaire (atelier, démarche, etc.) |
| **Rendez-vous**          | RDV planifié entre conseiller et bénéficiaire              |
| **Démarche**             | Action spécifique France Travail                           |
| **Session MILO**         | Activité collective en Mission Locale                      |
| **MILO**                 | Mission Locale                                             |
| **France Travail**       | Nouveau nom de Pôle Emploi                                 |
| **RQTH**                 | Reconnaissance Qualité Travailleur Handicapé               |
| **SNP**                  | Situation Non Professionnelle                              |
| **BRSA**                 | Bénéficiaire RSA                                           |
| **PACEA**                | Parcours Contractualisé d'Accompagnement                   |

## Conventions partagées

### Stack commune

| Technologie         | Version    | Notes                             |
|---------------------|------------|-----------------------------------|
| **Node.js**         | 22.14.0    | Fichier `.nvmrc` dans chaque repo |
| **Package Manager** | Yarn 4.x   | Jamais npm                        |
| **TypeScript**      | 4.9+ / 5.x | Mode strict                       |

### Linting & Formatting

Tous les repos partagent des conventions similaires :

**Prettier :**

```json
{
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2,
  "useTabs": false
}
```

**ESLint :**

- Pas de `console.log` → utiliser le logger
- Pas de `process.env` direct → utiliser la config centralisée
- Pas de `any` sans justification

### Secrets & Variables d'environnement

**Outil : dotvault**

```bash
# Déchiffrer
npx dotvault decrypt

# Chiffrer après modification
npx dotvault encrypt
```

- Clé vault : demander à l'équipe ou Vaultwarden/Dashlane
- Fichier chiffré : `.vault` ou `.environment` (commité)
- Template : `.env.local.template` ou `.environment.template`

### Déploiement

**Plateforme : Scalingo**

- **Staging** : déploiement automatique sur push `develop`
- **Production** : déploiement automatique sur push `master`
- **Review Apps** : création automatique sur PR

### Release

Process similaire dans tous les repos :

```bash
yarn release:patch  # ou :minor / :major
git push --tags && git push origin develop
git checkout master && git merge develop && git push
```

## Fonctionnalités principales

| Fonctionnalité       | Description                               | Repos concernés          |
|----------------------|-------------------------------------------|--------------------------|
| **Messagerie**       | Chat temps réel conseiller ↔ bénéficiaire | api, web, app (Firebase) |
| **Offres d'emploi**  | Proposition et recherche d'offres         | api, web, app            |
| **Actions**          | Gestion des tâches/démarches              | api, web, app            |
| **Rendez-vous**      | Planification et suivi RDV                | api, web, app            |
| **Sessions MILO**    | Activités collectives                     | api, web                 |
| **Suivi des heures** | Comptabilisation activités                | api, web                 |

## Intégrations externes

| Service                | Usage                          | Repo principal    |
|------------------------|--------------------------------|-------------------|
| **France Travail API** | Offres d'emploi, profils       | api               |
| **MILO API**           | Sessions, événements, dossiers | api               |
| **Firebase**           | Messagerie temps réel          | api, web, app     |
| **Diagoriente**        | Métiers favoris                | api               |
| **Immersion Facile**   | Immersions professionnelles    | api               |
| **Service Civique**    | Engagements civiques           | api               |
| **Elastic APM**        | Monitoring                     | api, web, connect |
| **Matomo**             | Analytics web                  | web               |

## Liens utiles

### Repositories

- [pass-emploi-api](https://github.com/France-Travail/pass-emploi-api)
- [pass-emploi-web](https://github.com/France-Travail/pass-emploi-web)
- [pass-emploi-connect](https://github.com/France-Travail/pass-emploi-connect)
- [pass_emploi_app](https://github.com/France-Travail/pass_emploi_app)
- pass-emploi-tools (outillage / infra logs mutualisée)
- pass-emploi-auth (Keycloak / IdP)
- pass-emploi-analytics (pipeline données / analytics)

### Documentation officielle des dispositifs

- [CEJ - Ministère du Travail](https://travail-emploi.gouv.fr/le-contrat-dengagement-jeune-cej)
- [CEJ - France Travail](https://www.francetravail.fr/actualites/a-laffiche/2022/le-contrat-dengagement-jeune-cej.html)
- [PACEA - Ministère du Travail](https://travail-emploi.gouv.fr/le-parcours-contractualise-daccompagnement-vers-lemploi-et-lautonomie-pacea)
- [1 jeune 1 solution](https://www.1jeune1solution.gouv.fr/)
