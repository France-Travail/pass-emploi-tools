# Contexte Global Pass Emploi

> **Doc transverse — source de vérité partagée.** Versionnée dans `pass-emploi-tools`.
> Importée automatiquement par les `CLAUDE.md` des repos via
> `@../pass-emploi-tools/docs/CONTEXTE-TRANSVERSE.md` (chargement garanti au démarrage).
> Ne **pas** dupliquer ce contenu dans un CLAUDE.md d'app.
>
> Index des gros sujets transverses (invariants + réf. stable, toujours chargé) ↓.
> Règles d'écriture de la doc : « Conventions partagées → Documentation » ci-dessous.
> Mécanique de rangement et de chargement : `pass-emploi-tools/docs/CONVENTIONS-DOC.md`.

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

| Repository | Rôle | Stack | Public cible |
|---|---|---|---|
| [**pass-emploi-api**](https://github.com/France-Travail/pass-emploi-api) | Backend API REST | NestJS, PostgreSQL, Redis | - |
| [**pass-emploi-web**](https://github.com/France-Travail/pass-emploi-web) | Application web conseiller | Next.js, React | Conseillers |
| [**pass-emploi-connect**](https://github.com/France-Travail/pass-emploi-connect) | Service d'authentification OIDC | NestJS, oidc-provider, Redis | - |
| [**pass_emploi_app**](https://github.com/France-Travail/pass_emploi_app) | Application mobile | Flutter | Bénéficiaires (jeunes) |
| **pass-emploi-tools** | Outillage, infra de logs mutualisée, doc transverse | Logstash, Elasticsearch | - |
| **pass-emploi-auth** | Keycloak (IdP), configuré via Terraform | Keycloak, Terraform | - |
| **pass-emploi-analytics** | Pipeline de données / suivi analytics | Make | - |
| [**1jeune-des-solutions**](https://github.com/bayesimpact/1jeune-des-solutions) | Génération du plan d'action (**POC**). Repo **bayesimpact**, hors orga France-Travail | NestJS, Gemini / Vertex AI | Bénéficiaires (jeunes) |

## Dispositifs d'accompagnement

- **CEJ** (Contrat d'Engagement Jeune) : accompagnement intensif des jeunes vers
  l'emploi, porté par France Travail et les Missions Locales —
  [ministère](https://travail-emploi.gouv.fr/le-contrat-dengagement-jeune-cej).
- **PACEA** (Parcours Contractualisé d'Accompagnement) : parcours modulable,
  porté par les Missions Locales —
  [ministère](https://travail-emploi.gouv.fr/le-parcours-contractualise-daccompagnement-vers-lemploi-et-lautonomie-pacea).

Durées, intensités et montants d'allocation : se référer aux sources officielles,
ils changent par voie réglementaire.

## Acteurs et structures

### Types d'utilisateurs

- **Bénéficiaire / Jeune** : Utilisateur accompagné (app mobile)
- **Conseiller** : Accompagne les bénéficiaires (app web)
- **Superviseur** : Supervise plusieurs conseillers

### Organisations

Les bénéficiaires et conseillers relèvent de **France Travail**, d'une **Mission
Locale** ou d'un **Conseil départemental**. Une même organisation porte
plusieurs dispositifs, et un conseiller peut travailler sur plusieurs
dispositifs à la fois : organisation et dispositif sont deux notions distinctes.

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

### Outillage

- **Yarn, jamais npm.** Version de Node : le `.nvmrc` du repo fait foi.
- **TypeScript en mode strict.**
- **Prettier et ESLint** : la config de chaque repo fait foi, ne pas la recopier.
  Esprit commun : pas de `console.log` (logger), pas de `process.env` direct
  (config centralisée), pas de `any`.

### Commentaires — par défaut, on n'en écrit pas

**Le code se documente par ses noms**, pas par des commentaires. Un commentaire
qui décrit *ce que fait* le code est du bruit : il duplique une information déjà
lisible, et il ment dès que le code change sans lui. Si un bout de code a besoin
d'être expliqué, le premier réflexe est de le renommer ou de l'extraire, pas de
le commenter.

**Trois exceptions, et seulement trois :**

1. **Un fait non-évident et indispensable**, que le lecteur ne peut pas déduire
   du code : subtilité de fuseau horaire, contrainte métier contre-intuitive,
   contournement d'un bug externe, invariant garanti ailleurs (ex. « ce `WHERE`
   garantit la non-nullité »). Le test : *est-ce que quelqu'un risque de casser
   ça en toute bonne foi sans ce commentaire ?*
2. **`// TODO:`** — tracer une dette assumée ou une suite de refacto. À rendre
   **actionnable** (quoi migrer, vers quoi, pourquoi ça n'est pas fait maintenant).
3. **Les marqueurs de structure de test** (`// Given` / `// When` / `// Then`) :
   convention de lisibilité, pas des commentaires explicatifs.

Tout le reste — en-têtes de fichier décoratifs, sections « Contexte / Utilité »,
paraphrase d'une ligne, commentaire qui répète le nom de la fonction — est à
supprimer, y compris dans le code existant qu'on touche au passage.

### Documentation — par défaut, on n'en écrit pas

Même test que pour un commentaire, à l'échelle du système : **quelqu'un
risque-t-il de casser ça en toute bonne foi sans cette information ?** Une doc
qui se périme fait plus de dégâts qu'une doc absente : on la croit.

1. **Cinq genres, pas un de plus** :
   - *invariant* : règle métier ou d'archi qui ne doit pas casser, en une phrase
     plus son pourquoi ;
   - *convention* : comment on écrit le code ;
   - *mode d'emploi* : comment se servir d'un outil, dans le README à côté de
     l'outil ;
   - *runbook* : que faire quand ça casse ;
   - *trace datée* : ADR, post-mortem, mesure datée.

   Tout le reste — spec, plan, design, note d'investigation, description du
   fonctionnement — ne se versionne pas. Ce fichier y ajoute seulement le
   contexte d'entrée (glossaire, carte des repos), sans version ni montant.
2. **Aucun nom de code dans un invariant** : ni chemin, ni classe, ni enum, ni
   table, ni route. Si un renommage casse la phrase, c'est un choix
   d'implémentation, et il vit dans le code. Une convention cite ce qu'elle
   impose ; un mode d'emploi ou un runbook, ses commandes et ses variables. La
   doc toujours chargée (ce fichier et l'index des sujets) ne cite **aucune
   variable ni valeur de configuration** : elle renvoie au mode d'emploi qui
   les porte.
3. **Rien qui dépende du temps** : ni statut, ni WIP, ni calendrier, ni `TODO`,
   ni « à confirmer », ni « à ce jour ». C'est le rôle du board. Une trace
   datée est figée, sauf son statut (proposé → accepté → remplacé). Une décision
   qui mérite son pourquoi devient un ADR court, pas un « décidé le » dans une
   doc vivante.
4. **Un fait, un endroit.** Une doc d'outil vit à côté de l'outil et change dans
   la même PR. Une règle appliquée par le code a ses tests pour référence. Un
   routeur ne contient que des liens, une ligne par lien. Deux docs qui disent
   la même chose finissent par se contredire.
5. **Pas d'avance.** On écrit quand c'est tranché, ou quand quelqu'un s'est fait
   piéger. Une question ouverte n'est pas de la doc ; une limite connue (« ce
   tir ne prouve pas X ») en est une.
6. **Doc fausse, on coupe.** Un passage trouvé faux se supprime ; on ne le
   réécrit que s'il passe les règles 1 à 5.

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

> Concerne les **repos Node** (`api`, `web`, `connect`). L'app mobile ne se
> déploie pas : elle se **publie sur les stores** (voir Release ci-dessous).

**Plateforme : Scalingo**

- **Staging** : déploiement automatique sur push de la branche d'intégration (`develop`)
- **Production** : déploiement automatique sur push de la branche de production
- **Review Apps** : création automatique sur PR

### Release

**Deux process distincts** — ne pas supposer qu'ils sont alignés.

#### Repos Node (`api`, `web`, `connect`)

Tag `vX.Y.Z`, livraison par merge dans la branche de production, déploiement continu.

```bash
yarn release:patch  # ou :minor / :major
git push --tags && git push origin develop
git checkout <branche-de-prod> && git merge develop && git push
```

| Repo | Intégration | Production |
|---|---|---|
| `pass-emploi-api` | `develop` | `master` |
| `pass-emploi-web` | `develop` | `master` |
| `pass-emploi-connect` | `develop` | **`main`** |

#### App mobile (`pass_emploi_app`)

Process **différent** : Flutter, pas de yarn, **une seule branche au long cours**
(`main`, pas de `develop`), et **pas de déploiement continu** — la livraison passe
par les stores.

```bash
scripts/release.sh 4.12.3   # bump pubspec.yaml sur main + commit + tag + push --tags
```

- **Version** : `pubspec.yaml`. **Tag sans préfixe `v`** (`4.12.3`, pas `v4.12.3`).
- Le **tag** déclenche le workflow de release (build Android + iOS prod).
- **Correctifs** : branches `release/X.Y.Z` + `scripts/hotfix.sh`, qui tague depuis
  la branche de release puis rebumpe `main` — le report du correctif sur `main` est
  **manuel** (le script se contente d'avertir).
- Le repo build **plusieurs apps** depuis la même base ; le flavor staging/prod
  est déduit du *package name*.

## Liens utiles

- [CEJ - France Travail](https://www.francetravail.fr/actualites/a-laffiche/2022/le-contrat-dengagement-jeune-cej.html)
- [1 jeune 1 solution](https://www.1jeune1solution.gouv.fr/)
