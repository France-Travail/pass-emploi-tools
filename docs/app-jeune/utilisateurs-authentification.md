# App Jeune — Utilisateurs & Authentification

> **Reference.** Recensement des publics de la future app jeune, de leur mode
> d'authentification technique, et de leur représentation dans l'API.
> Sous-chantier de [`README.md`](./README.md) — lire le **cadre 3 couches**
> avant.
>
> **Statut : WIP.** Itération 1 (2026-07-02) : couches 1→2 (matrice
> publics→modes). Itération 2 (2026-07-28) : le **mode invité est livré**, la
> couche 3 est renseignée pour ce public. Itération 3 (2026-08-03) : matrice
> **publics → droits** posée. Restent ouverts : le candidat FT non accompagné,
> et la **transition invité → inscrit**.
>
> **Calendrier** : bêta septembre/octobre 2026, ouverture à tous novembre 2026.

## Rappel du cadre

| Couche | Question | Où c'est porté aujourd'hui |
|---|---|---|
| 1 — Public fonctionnel | Qui, vu produit (dispositif / parcours) | `Core.Structure` (api) + porte d'entrée choisie au login (connect) |
| 2 — Mode d'authentification | Comment il prouve son identité (IDP, flow) | IDP dans `pass-emploi-connect/src/idp/*` |
| 3 — Représentation API | Comment on le range pour ses droits | `Authentification.Type`, `Core.Structure`, entités `Jeune` et `JeuneInvite` |

## Couche 2 — Modes d'authentification (bénéficiaires)

Source : `pass-emploi-connect/src/idp/`. Côté **bénéficiaire (jeune)**, il existe
désormais **trois** modes :

| Mode | IDP connect | Particularité |
|---|---|---|
| **OIDC MILO** | `milo-jeune` | IDP dédié Mission Locale |
| **FT Connect** | `francetravail-jeune` | IDP France Travail **unique** ; la structure est choisie par le path (`cej` / `aij` / `brsa` / …) au login, pas renvoyée par l'IDP |
| **Invité** | `invite` | **Aucun IDP externe** — voir ci-dessous |

> Reste à trancher : le **candidat FT non accompagné** (nouveau path FT Connect ?
> nouvel IDP ?).

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
| **Non-inscrit** demandeur d'emploi FT — collégiens, lycéens, étudiants, NEET.<br>14-25 ans (non handicapé) / 14-30 ans (handicapé) | MVP | **Mode invité** (`INVITE`) | Livré — voir ci-dessous |

## Publics → droits (couche 3, vue d'ensemble)

Les droits ne se déduisent pas du mode d'authentification (couche 2) ni
directement de `Core.Structure`. Trois questions les déterminent : le
bénéficiaire a-t-il un conseiller **chez nous** (Pass Emploi), a-t-il un
dossier de demandeur d'emploi France Travail, relève-t-il d'une Mission Locale.

| Public | Messagerie | Agenda / création d'actions | Compteur d'heures | Offres |
|---|:--:|:--:|:--:|:--:|
| CEJ MILO | ✅ | ✅ | ✅ | ✅ |
| CEJ / AIJ / Avenir Pro FT | ✅ | ✅ | ❌ | ✅ |
| Migrants Pass Emploi, « suivi et guidé » | ❌ | ✅ | ❌ | ✅ |
| Candidat FT non demandeur d'emploi | ❌ | ❌ | ❌ | ✅ |
| Invité | ❌ | ❌ | ❌ | ✅ |

Le **compteur d'heures** est propre à MiLo, et seulement pour le dispositif CEJ.
L'**agenda et la création d'actions** supposent soit un dossier de demandeur
d'emploi France Travail, soit un rattachement à une Mission Locale.

### Pourquoi les migrants Pass Emploi perdent la messagerie

Ces bénéficiaires ont aujourd'hui un conseiller enregistré. Mais leurs
conseillers migrent vers **Parcours Emploi** (application interne France
Travail) et y perdent l'accès au web conseiller Pass Emploi. En régime établi,
ils n'ont donc **plus de conseiller côté Pass Emploi**, et l'absence de
messagerie en découle d'elle-même — ce n'est pas une restriction propre à ce
public.

La difficulté est la **période de recouvrement** : entre la sortie de l'app
jeune et la fin de la migration de leurs conseillers, ces bénéficiaires ont
encore un conseiller en base sans que la messagerie soit souhaitable.
L'identification se fera comme aux phases de migration précédentes — par les
conseillers concernés — ou à défaut par le dispositif.

### Un bénéficiaire change de public

Le public d'un bénéficiaire n'est pas figé : un candidat pris en accompagnement
par un conseiller devient accompagné ; un accompagné dont le conseiller migre
cesse de l'être. **Le public est un état, pas une identité** — l'identifiant et
les données du bénéficiaire restent les mêmes au fil de ces transitions. Les
invités ont vocation à être poussés vers la création d'un compte France
Travail.

## Mode invité — réalisé

### Principe : une identité fabriquée, pas vérifiée

L'invité **ne revendique aucune identité et ne présente aucune preuve** : il n'y
a donc rien à vérifier, et aucun IDP à interroger. `pass-emploi-connect`
**fabrique** l'identité, la fait enregistrer par l'API, puis termine
l'interaction OIDC — sans le moindre aller-retour réseau vers un fournisseur
d'identité, et sans stocker de token IDP.

Trois choix structurants, à ne pas défaire sans comprendre pourquoi :

- **L'identifiant est généré côté serveur**, jamais fourni par le client : un
  identifiant envoyé par le mobile serait forgeable, donc usurpable.
- **Ce qui rattache durablement l'invité à son appareil, c'est le refresh
  token** — il n'y a pas d'autre ancrage.
- **Un grant OIDC neuf est créé à chaque enregistrement**, jamais celui de
  l'interaction en cours : chaque enregistrement fabrique un identifiant neuf,
  donc réutiliser un grant antérieur y laisserait l'ancien compte et ferait
  échouer l'autorisation.

Conséquence importante pour tout le reste : **l'invité dispose d'un JWT normal**.
Ce n'est pas un utilisateur anonyme au sens HTTP — c'est un utilisateur
authentifié dont l'identité est pseudonyme.

### Couche 3 — représentation dans l'API

| Question | Réponse retenue |
|---|---|
| Public fonctionnel | `Core.Structure.INVITE`, avec un helper de test dédié |
| Type d'utilisateur | `Authentification.Type.JEUNE` — **pas** de nouveau type |
| Stockage | **Table dédiée `jeune_invite`** — ni la table `jeune` avec des colonnes nulles, ni du volatil |
| Contenu stocké | Identifiant, prénom d'affichage, dates de connexion, données d'appareil (push, version, installation, fuseau), acceptation des CGU |
| Autorisation | Autorisation dédiée à l'invité ; l'autorisation « jeune » standard **le rejette explicitement** |

Le modèle d'accès **vise** à être fermé par défaut, ouvert route par route :
une fonctionnalité ne devrait être accessible à l'invité que si elle a été
explicitement ouverte. C'est volontairement conservateur — l'invité n'a pas de
conseiller, pas de structure d'appartenance, et une partie du modèle de droits
existant n'a aucun sens pour lui.

> ⚠️ **Cette fermeture par défaut n'est pas encore effective (vérifié
> 2026-08-03).** Le seul verrou existant est le rejet de l'invité par
> l'autorisation « jeune » standard. Tout cas d'usage qui ne passe pas par elle
> reste accessible à un JWT invité — c'est le cas aujourd'hui pour plusieurs
> endpoints de référentiels et de détail d'offres. Ne pas s'appuyer sur
> « fermé par défaut » comme garantie tant que ce point n'est pas corrigé.

Routes ouvertes à ce jour : configuration de l'application, formulaire de
contact Immersion, prénom d'affichage.

### Ce que ça règle de la tension de fond

`Core.Structure` (`src/domain/core.ts`) surchargeait deux notions — *dispositif
d'accompagnement* et *structure d'appartenance / IDP*. L'invité n'entrait
proprement dans aucune, et le modèle supposait que *tout jeune a une structure
et un identifiant OIDC stable*.

La réponse retenue est **une valeur de structure supplémentaire plus une entité
séparée**, plutôt que l'éclatement de l'enum. C'est un compromis assumé :
l'enum reste surchargée, mais l'entité distincte évite de diluer `Jeune` avec
des colonnes optionnelles.

À réévaluer quand le **candidat FT non accompagné** arrivera : lui a une
identité vérifiée mais pas de conseiller, et n'entre donc ni dans `Jeune` ni
dans `JeuneInvite` tels qu'ils sont aujourd'hui.

## Questions ouvertes `TODO`

- **Transition invité → inscrit.** Que devient un invité qui se crée un compte
  ou se fait accompagner ? Récupère-t-il ses données — réponses au questionnaire,
  [plan d'action](./plan-action.md), progression ? Aujourd'hui **rien n'est
  prévu**, et l'ancrage étant le refresh token, la perte de l'appareil suffit à
  perdre le rattachement. C'est le principal sujet non traité.
- **Candidat FT non accompagné** : structure, droits, entité.
- **Accompagné hors MILO/FT** (post-MVP) : IDP et rattachement.
- **Cycle de vie de l'invité** : purge des invités inactifs, durée de
  conservation.
- **Messagerie des migrants pendant la période de recouvrement** : comment
  identifier fiablement, avant la sortie de l'app jeune, les conseillers déjà
  en cours de migration vers Parcours Emploi.
- **Rangement de « suivi et guidé »** : structure et dispositif à confirmer
  avec le PO (cf. matrice couches 1→2 ci-dessus).

## Hors scope MVP mais à identifier quand même

Même pour les publics hors MVP, il faut pouvoir les **identifier** à l'entrée
pour les rediriger / gérer leurs droits (où exactement : à trancher plus tard).
