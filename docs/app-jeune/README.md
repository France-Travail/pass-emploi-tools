# Chantier « App Jeune » — routeur

> **Statut : WIP.** Chantier de réflexion transverse ouvert le 2026-07-02, mené
> en continu (comme le chantier logs). Doc de référence versionnée ; la couche
> exploratoire / débats non tranchés vit en notes de travail et remonte ici une
> fois stabilisée.
>
> Ce fichier est un **routeur** : la vision, le cadre d'analyse commun, et
> l'index des sous-chantiers. Le détail vit dans les sous-docs.

## Vision

L'application CEJ / Pass Emploi évolue vers une **nouvelle app destinée à tous
les jeunes de France**, pour faciliter et accélérer leur autonomie vers l'emploi
— au sens large : emploi, mais aussi social, logement, etc.

Conséquence structurante : on élargit très fortement la population d'utilisateurs.
On passe de « bénéficiaires accompagnés rattachés à une structure » à un spectre
qui inclut des **jeunes non accompagnés, non inscrits, voire anonymes (mode
invité)**. Cet élargissement casse plusieurs hypothèses du modèle actuel — d'où
ce chantier.

## Cadre d'analyse commun : 3 couches à ne pas confondre

Le code actuel a tendance à **mélanger** ces trois notions (en particulier via
l'enum `Core.Structure` qui porte à la fois un dispositif et une structure
d'appartenance). Tout le chantier consiste à les **séparer** et à tracer les
flèches entre elles.

1. **Public fonctionnel** — le « qui », vu produit : le parcours / dispositif
   (CEJ MILO, RSA rénové, lycéen NEET non inscrit…). Maille métier.
2. **Mode d'authentification technique** — le « comment il prouve son
   identité » : quel IDP, quel flow (OIDC MILO, FT Connect, mode invité…).
   Beaucoup plus **plat** que la couche 1 : plusieurs publics partagent un même
   mode.
3. **Représentation dans l'API** — le « comment je le range pour gérer ses
   droits » : `Authentification.Type`, `Core.Structure`, entité `Jeune`, et les
   **nouvelles entités/attributs** à introduire (notamment pour l'invité).

> **Fait d'architecture clé (à garder en tête partout).** Côté
> `pass-emploi-connect`, pour les bénéficiaires France Travail, le mode
> d'authentification est **unique** (FT Connect). La `structure` n'est **pas** un
> claim renvoyé par l'IDP : elle est **décidée par la porte d'entrée** choisie au
> login (query param `type` : `cej`, `aij`, `brsa`…), et assignée par le
> contrôleur. Autrement dit, la couche 1 est portée par l'app, pas par l'IDP.

## Sous-chantiers

| Sous-chantier | Doc | Statut |
|---|---|---|
| Nouveaux utilisateurs / authentification | [`utilisateurs-authentification.md`](./utilisateurs-authentification.md) | WIP — matrice publics→modes posée ; **mode invité livré** (couche 3 renseignée) ; transition invité→inscrit et candidat FT non accompagné à instruire |
| Parcours & fonctionnalités | [`parcours-fonctionnalites.md`](./parcours-fonctionnalites.md) | WIP — parcours d'entrée, pages, matrice profils→accès posés ; typologie et règle de détermination à trancher |
| Plan d'action | [`plan-action.md`](./plan-action.md) | WIP — archi proxy posée, branchement en cours ; service de génération au stade **POC** |

> **Performances / montée en charge** : sujet transverse à part entière (il
> dépasse l'app jeune et survit à la MES), traité dans le
> [chantier perf](../perf/README.md). La MES de l'app jeune en est le premier
> jalon dimensionnant.

## Historique

- **2026-07-28** — sous-chantier « Plan d'action » ouvert : archi proxy
  `pass-emploi-api` → service de génération externe (POC), mapping de contrat,
  trace analytique. Mise à jour des deux autres sous-chantiers suite à la
  livraison du **mode invité** (connect + api) et à l'implémentation du
  questionnaire invité côté mobile.
- **2026-07-10** — sous-chantier « Parcours & fonctionnalités » ouvert :
  parcours d'entrée (tuto → authent → questionnaire → plan d'action), pages de
  l'app, matrice profils→accès (première capture produit, à fiabiliser).
- **2026-07-06** — le sujet performances est sorti du chantier (périmètre plus
  large que l'app jeune) et promu sujet transverse : [`docs/perf/`](../perf/README.md).
- **2026-07-02** — ouverture du chantier. Cadre 3 couches posé. Matrice
  publics→modes (couches 1→2) rédigée à partir de l'existant `pass-emploi-api`
  (`Core.Structure`) et `pass-emploi-connect` (IDP bénéficiaires).
