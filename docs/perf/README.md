# Chantier « Performances » — routeur

> **Statut : WIP.** Chantier transverse durable ouvert le 2026-07-06. Premier
> jalon dimensionnant : la mise en service de l'app jeune (voir
> [chantier app-jeune](../app-jeune/README.md)), mais le sujet couvre l'ensemble
> de la plateforme (api, web, connect, partenaires) et survit au jour J
> (capacity planning, monitoring continu, runbooks).
>
> Ce fichier est un **routeur** : la démarche d'ensemble et l'index des
> sous-chantiers. Le détail vit dans les sous-docs (à créer au fil de l'eau).

## Pourquoi

L'élargissement des publics de l'app jeune change l'ordre de grandeur du trafic,
avec un événement à fort risque : le **jour J de la MES + communication**
(pic très concentré, premières connexions coûteuses). Sans objectifs chiffrés,
baseline et tirs de charge, on découvre les limites en production.

## Démarche

```
Phase 0 — Alignement métier/produit     → enjeux, trafic attendu, niveau de service (SLO)
Phase 1 — État des lieux                → chemin critique, partenaires, observabilité, baseline
Phase 2 — Conception des tirs           → scénarios, env de perf, jeu de données, outillage
Phase 3 — Campagne de tirs              → itératif : tir → mesure → mitigation → re-tir
Phase 4 — Préparation jour J            → runbooks, mode dégradé, plan Scalingo, dispositif
Phase 5 — Après la MES                  → monitoring continu, capacity planning
```

Principes structurants :

- **Les SLO d'abord.** Un tir sans objectif chiffré ni baseline produit des
  chiffres sans verdict. Les cibles (p95 par parcours, taux d'erreur, capacité
  de login) se définissent avec le métier en phase 0.
- **L'observabilité est un prérequis.** Le dashboard de tir (latences par
  endpoint, saturation DB/Redis, erreurs) se construit **avant** le premier tir,
  en capitalisant sur l'infra logs ECS + Elastic APM existants.
- **Idempotence du harnais.** `reset env → seed données → tir paramétré →
  export résultats`, entièrement scripté, pour pouvoir re-tirer après chaque
  mitigation sans friction.
- **La charge ne vient pas que des utilisateurs.** Jobs, crons, synchros
  partenaires, et surtout **notifications push massives** (réveil synchronisé
  de l'app mobile = pic de login) sont des scénarios à part entière.
- **Les partenaires sont dans le chemin critique.** FT Connect et MILO au
  login : leurs limites, SLA et conditions de tir (autorisation ou mock) sont
  à instruire tôt.
- **Parcours critiques vs dégradables.** Le mode dégradé (feature flags,
  étalement des notifs, kill switch sur la com) préserve login + accueil en
  sacrifiant le reste ; il se conçoit, il ne s'improvise pas.

## Acteurs

| Phase | Acteurs principaux |
|---|---|
| 0 — Alignement | PO, PM, chargées de déploiement, Tech Lead |
| 1 — État des lieux | Tech Lead, devs back/ops, dev mobile |
| 2-3 — Tirs | Tech Lead + devs ; PO pour valider les scénarios |
| 4 — Jour J | Équipe technique + support + chargées de déploiement + Scalingo |

## Sous-chantiers

| Sous-chantier | Doc | Statut |
|---|---|---|
| Observabilité & SLO | [`observabilite.md`](./observabilite.md) | WIP — SLI/SLO I1-I5 actés en atelier (2026-07-10), spec d'instrumentation app jeune posée |
| Estimation de trafic | `TODO` | Non démarré (les SLO qualitatifs sont posés dans `observabilite.md` ; reste le volume attendu) |
| État des lieux partenaires et dépendances | `TODO` | Non démarré — inclut FT Connect, MILO, et le **service IA** de génération du plan d'action (découvert le 2026-07-10, dans le chemin critique du parcours d'entrée) |
| Harnais de tir (env, jeu de données, outillage) | `TODO` | Non démarré |
| Mode dégradé et runbooks incidents | `TODO` | Non démarré |
| Plan Scalingo jour J | `TODO` | Non démarré |

Hors périmètre : le volet sécurité « vol de données » relève d'un audit sécu
séparé. L'anti-bot / rate limiting / anti-DDoS reste ici (protection de la
disponibilité), à instruire avec Scalingo.

## Historique

- **2026-07-10** — atelier SLO mené (Tech Lead + métier) : sous-chantier
  [Observabilité & SLO](./observabilite.md) ouvert avec les indicateurs I1-I5 et
  leurs seuils. Décisions utiles aux autres sous-chantiers : pages
  **dégradables** en pic = événements + compteur d'heures (→ mode dégradé) ;
  web conseiller non prioritaire jour J ; **service IA externe** dans le chemin
  critique (→ partenaires).
- **2026-07-06** — ouverture du chantier. Démarche en 6 phases posée,
  principes structurants et découpage en sous-chantiers.