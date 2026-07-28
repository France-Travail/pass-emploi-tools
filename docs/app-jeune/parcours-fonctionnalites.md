# App Jeune — Parcours & Fonctionnalités

> **Reference.** Description fonctionnelle de la future app jeune : parcours
> d'entrée, pages/fonctionnalités, et matrice profils → accès. Sous-chantier de
> [`README.md`](./README.md) ; complète
> [`utilisateurs-authentification.md`](./utilisateurs-authentification.md)
> (couches 1→2 : publics et modes d'authent) en décrivant **ce que chaque
> profil peut faire** (matière première de la couche 3 : droits).
>
> **Statut : WIP.** Première capture (2026-07-10) issue du produit, **non
> exhaustive et à fiabiliser** — les points incertains sont marqués `à confirmer`.
> Mise à jour 2026-07-28 : le **parcours d'entrée invité** est décrit d'après
> l'implémentation en cours, il ne relève plus du prévisionnel.

## Parcours d'entrée (première utilisation)

```
1. Tuto d'entrée        → page(s) très courte(s) expliquant l'appli
2. Authentification     → « sans compte » (invité) | FT Connect | OIDC MILO
3. Questionnaire        → plusieurs étapes, renseigné par le jeune
4. Plan d'action        → personnalisé d'après le questionnaire
5. Accès à l'app        → navigation dans les pages ci-dessous
```

### Variante invité (implémentée)

L'invité s'authentifie **avant** le questionnaire : le bouton « sans compte »
déclenche la connexion invité, qui lui donne un JWT (voir
[`utilisateurs-authentification.md`](./utilisateurs-authentification.md)). Il
enchaîne ensuite directement sur le questionnaire, **sans CGU ni tutoriel**.

Le questionnaire fait **8 étapes** : prénom, date de naissance, commune
d'habitation, situation, objectifs, domaine, commune de recherche (+ rayon),
freins — puis un écran de chargement pendant la génération du plan.

Deux propriétés à connaître :

- **Les réponses sont stockées localement sur l'appareil**, pas envoyées à
  l'API. Le questionnaire est reprenable, et rien n'est conservé côté serveur.
- **La recherche de commune interroge `geo.api.gouv.fr` directement depuis le
  mobile**, sans passer par `pass-emploi-api`. C'est une dépendance externe
  bloquante dans le parcours d'entrée : sans elle, l'étape « où tu habites »
  n'aboutit pas, et il n'y a pas de repli.

La génération du plan d'action qui suit fait l'objet de son propre
sous-chantier : [`plan-action.md`](./plan-action.md).

## Pages de l'app

> Liste non exhaustive, descriptions `à confirmer`.

| Page | Contenu |
|---|---|
| **Accueil** | [Plan d'action](./plan-action.md) personnalisé avec cases à cocher ; les actions peuvent rediriger vers des liens externes ou des deeplinks |
| **Agenda** | RDV à venir (accompagnés) ; actions terminées ; **compteur d'heures** en haut d'écran ; création d'actions par le jeune |
| **Chat** | Messagerie conseiller ↔ jeune, pour les accompagnés (comme actuellement) |
| **Événements** | Événements Mission Locale (comme actuellement) ou externes |
| **Offres** | Comme actuellement : emploi, alternance, immersion, service civique, formation en alternance |
| **Notifications** | Centre de notifications |
| **Profil** | Infos du jeune ; déconnexion |

## Matrice profils → accès aux fonctionnalités

> Les profils renvoient à la matrice publics→modes de
> [`utilisateurs-authentification.md`](./utilisateurs-authentification.md).

| Profil | Mode d'authent | Accès | À creuser |
|---|---|---|---|
| CEJ, AIJ, Avenir Pro | OIDC MILO / FT Connect | **Tout** | — |
| Autres publics actuels CEJ/Pass Emploi (RSA rénové, REN intensif, …) | FT Connect | Tout **sauf compteur d'heures et chat** `à confirmer` | Censés migrer vers Parcours Emploi (app interne FT) mais rien n'empêche qu'ils se connectent. Les considère-t-on comme accompagnés (hors CEJ/PACEA) ou comme invités ? → à trancher avec le métier |
| Accompagnés hors FT/MILO (ex. associations) — **post-MVP** | Identifiant FT (espace candidat) | Tout **sauf compteur d'heures** | Agenda, création d'actions et chat incertains (« orange » sur les maquettes : pour plus tard ?) |
| Non accompagné avec compte FT (espace candidat) | FT Connect (espace candidat) | Comme invité | — |
| Nouveau public non FT (lycéens, collégiens, étudiants, NEET, tout venant) | **Mode invité** (« sans compte ») | Tout **sauf agenda, création d'actions, compteur d'heures, chat** | Mode invité livré ; accès **fermé par défaut, ouvert route par route** (voir [`utilisateurs-authentification.md`](./utilisateurs-authentification.md)) |

Lecture en creux : les fonctionnalités discriminantes sont **agenda, création
d'actions, compteur d'heures, chat** — réservées (en tout ou partie) aux
accompagnés. Accueil/plan d'action, questionnaire, événements, offres sont
ouverts à tous, y compris l'invité.

## Questions ouvertes `TODO`

- **Typologie des profils** : deux axes candidats plutôt qu'une énumération —
  *connecté / non connecté* (a un compte et une session authentifiée) ×
  *accompagné / non accompagné* (a un conseiller). À valider : ces deux axes
  suffisent-ils à dériver tous les droits de la matrice ci-dessus ?
- **Règle de détermination de la typologie** : hypothèse de départ — si un
  conseiller inscrit le jeune dans le dispositif via son n° MILO ou FT alors
  *accompagné*, sinon *non accompagné* — **même s'il possède un compte FT/MILO**.
  À confirmer côté produit et à raccorder à la couche 3 (représentation API).
- **Publics migrants Parcours Emploi** : statut exact (accompagné hors
  CEJ/PACEA vs invité) et droits associés — en cours d'instruction avec le métier.