# App Jeune — Utilisateurs & Authentification

> **Reference.** Recensement des publics de la future app jeune, de leur mode
> d'authentification technique, et (à venir) de leur représentation dans l'API.
> Sous-chantier de [`README.md`](./README.md) — lire le **cadre 3 couches**
> avant.
>
> **Statut : WIP.** Itération 1 (2026-07-02) : couches 1→2 (matrice
> publics→modes). Couche 3 (entités / droits) et mode invité = `TODO` explicites
> en bas.

## Rappel du cadre

| Couche | Question | Où c'est porté aujourd'hui |
|---|---|---|
| 1 — Public fonctionnel | Qui, vu produit (dispositif / parcours) | `Core.Structure` (api) + porte d'entrée choisie au login (connect) |
| 2 — Mode d'authentification | Comment il prouve son identité (IDP, flow) | IDP dans `pass-emploi-connect/src/idp/*` |
| 3 — Représentation API | Comment on le range pour ses droits | `Authentification.Type`, `Core.Structure`, entité `Jeune` |

## Couche 2 — Modes d'authentification existants (bénéficiaires)

Source : `pass-emploi-connect/src/idp/`. Aujourd'hui, côté **bénéficiaire (jeune)**,
il n'existe en réalité que **deux IDP** :

| Mode | IDP connect | Particularité |
|---|---|---|
| **OIDC MILO** | `milo-jeune` | IDP dédié Mission Locale |
| **FT Connect** | `francetravail-jeune` | IDP France Travail **unique** ; la structure est choisie par le path (`cej` / `aij` / `brsa` / …) au login, pas renvoyée par l'IDP |

> À venir dans ce chantier : le **mode invité** (3ᵉ mode), et la question du
> **candidat FT non accompagné** (nouveau path FT Connect ? nouvel IDP ?).

## Matrice publics → modes (couches 1 → 2)

### Publics existants (app actuelle)

| Public fonctionnel | `Core.Structure` | Mode d'authentification |
|---|---|---|
| CEJ MILO | `MILO` | OIDC MILO (`milo-jeune`) |
| CEJ FT | `POLE_EMPLOI` | FT Connect, path `cej` |
| AIJ FT | `POLE_EMPLOI_AIJ` | FT Connect, path `aij` |
| Avenir Pro FT | `AVENIR_PRO` | FT Connect |

### Publics migrant « Pass Emploi → Parcours Emploi » (app interne FT)

> Rien ne les empêche de venir sur la nouvelle app jeune.

| Public fonctionnel | `Core.Structure` | Mode d'authentification |
|---|---|---|
| RSA rénové | `POLE_EMPLOI_BRSA` | FT Connect, path `brsa` |
| REN intensif / FTT-FTX | `FT_ACCOMPAGNEMENT_INTENSIF` | FT Connect |
| Accompagnement global | `FT_ACCOMPAGNEMENT_GLOBAL` | FT Connect |
| Equip'emploi / Equip'recrut | `FT_EQUIP_EMPLOI_RECRUT` | FT Connect |
| Jeunes des conseils départementaux | `CONSEIL_DEPT` | FT Connect |
| « Suivi et guidé » | `TODO` — à confirmer avec le PO | `TODO` |

### Nouveaux publics

| Public fonctionnel | Périmètre | Mode d'authentification | Questions ouvertes |
|---|---|---|---|
| Accompagné hors MILO/FT (ex. assos) | **post-MVP** | `TODO` | Nouvel IDP ? Rattachement à quelle structure ? |
| Candidat FT **inscrit**, non accompagné | MVP | FT Connect (path candidat ?) ou compte candidat FT | Quelle structure ? Quels droits ? |
| **Non-inscrit** demandeur d'emploi FT — collégiens, lycéens, étudiants, NEET.<br>14-25 ans (non handicapé) / 14-30 ans (handicapé) | MVP | **Mode invité** (à définir) | Voir couche 3 ci-dessous : comment authentifier/identifier/stocker, quelle entité |

## Couche 3 — Représentation dans l'API `TODO`

> À instruire aux prochaines itérations. Points de départ identifiés :

- **Tension de fond** : `Core.Structure` (`src/domain/core.ts`) surcharge deux
  notions — *dispositif d'accompagnement* et *structure d'appartenance / IDP*.
  Les nouveaux publics « non accompagné » et « invité » n'entrent proprement
  dans aucune. Question : éclater `Core.Structure`, ou ajouter une dimension ?
- **Hypothèse cassée** : le modèle actuel suppose que *tout jeune a une
  structure + un `idAuthentification` OIDC stable* (cf.
  `Authentification.Utilisateur` dans `src/domain/authentification.ts`). L'invité
  n'a ni l'un ni l'autre.
- **`Authentification.Type`** (`JEUNE` / `CONSEILLER` / `SUPPORT`) : suffit-il, ou
  faut-il un type/sous-type pour l'invité et le candidat non accompagné ?

## Mode invité `TODO`

> Cas le plus structurant. À instruire :

- **Authentifier / identifier** : a-t-on un identifiant stable (device,
  `installationId`, compte anonyme) ou vraiment éphémère ?
- **Stocker les données** : mêmes tables que `Jeune` avec attributs nuls, table
  dédiée, ou stockage volatil ?
- **Représenter dans le code** : nouvelle entité ? extension de `Jeune` ?
- **Transition** : que devient l'invité qui s'inscrit / se fait accompagner
  (récupération de ses données) ?

## Hors scope MVP mais à identifier quand même

Même pour les publics hors MVP, il faut pouvoir les **identifier** à l'entrée
pour les rediriger / gérer leurs droits (où exactement : à trancher plus tard).
