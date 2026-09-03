# Harnais de tir de performance

> Ce qu'est le harnais, ce qu'il mesure vraiment, et les invariants à respecter
> avant de le modifier. Les commandes et le mode d'emploi vivent à côté du code :
> [`perf/README.md`](../../perf/README.md).

## Ce qu'il mesure

Un parcours **de bout en bout**, joué par Gatling : login France Travail réel via
`pass-emploi-connect`, puis page d'accueil du bénéficiaire servie par
`pass-emploi-api`.

`connect` et `api` sont **réels** — ce sont eux l'objet de la mesure. Seul ce
qu'on ne peut pas atteindre est remplacé.

```
Gatling ──► connect ──► mock-externes   (IdP France Travail)
         └► api ───────► mock-externes   (APIs partenaires FT)
                      ├► connect         (validation du JWT — le vrai)
                      └► PostgreSQL      (vraies données, semées)
```

## Ce qui est simulé, et pourquoi

La distinction est importante, parce qu'elle dit ce qui est **provisoire** :

| Dépendance | Traitement | Raison |
|---|---|---|
| **IdP + APIs France Travail** | mocké | Contrainte subie : pas d'environnement de perf côté partenaire. À lever si FT en ouvre un. |
| **MILO** | hors périmètre v1 | Même raison. |
| **Firebase** | credentials factices en local | Choix provisoire de simplicité. C'est **notre** dépendance : un projet dédié serait plus fidèle qu'un mock. Question ouverte. |
| **`connect`, `api`, PostgreSQL** | réels | Ce sont les systèmes mesurés. |

Le principe n'est pas « mocker les tiers » mais **mocker ce qu'on ne peut pas
tirer**. Chaque mock éloigne la mesure de la vérité : c'est un coût consenti,
pas un objectif.

## Les quatre pièces

| Pièce | Où | Rôle |
|---|---|---|
| **`mock-externes`** | [`perf/mock-externes/`](../../perf/mock-externes/README.md) | Se fait passer pour l'IdP FT et ses APIs partenaires. Signe ses propres `id_token` avec une paire RSA générée au démarrage — aucune clé d'un environnement réel. Sans état : l'identité tirée au sort est encodée dans le `code`, jamais partagée entre workers. |
| **Le seed** | [`perf/seed/`](../../perf/seed/README.md) | Crée en base le pool de bénéficiaires que le mock tire au sort, aux volumétries mesurées en production. Idempotent, protégé par un marqueur anti-prod. |
| **La simulation** | [`perf/src/gatling/`](../../perf/README.md) | Suit la chaîne de redirections **à la main**, étape nommée par étape — ce qui donne un temps de réponse par saut, et rend tout écart immédiatement lisible. |
| **Le run local** | [`perf/local-run/`](../../perf/local-run/README.md) | Fait tourner `connect` et `api` en natif contre le mock, pour valider le parcours sans environnement dédié. |

## Invariants

À connaître **avant** de toucher au harnais.

- **Le `sub` fait foi.** Le mock rend un `sub` de la forme `{POOL_PREFIX}{i}` ;
  il doit correspondre à l'`id_authentification` d'un bénéficiaire présent en
  base. `POOL_PREFIX` et `POOL_SIZE` doivent valoir **exactement** ce qu'a semé
  le seed, sans quoi le login échoue.
- **L'API ne crée aucun bénéficiaire France Travail inconnu.** Elle répond
  `UTILISATEUR_INEXISTANT`. Le seed est donc un **prérequis dur**, pas une
  commodité : sans lui, rien ne se joue.
- **Le seed est destructeur**, et son garde-fou ne repose pas sur le nom de la
  base (les bases Scalingo ont des noms générés) mais sur un **marqueur posé à
  la main**, une fois, sur la base de tir. Ce geste reste manuel et hors du
  workflow de tir : c'est ce qui garantit qu'aucune automatisation ne peut le
  satisfaire par accident.
- **Le pool doit être large devant la charge** — au moins **5 × `MAX_USERS`**.
  Trop petit, les mêmes lignes restent chaudes en cache PostgreSQL et le tir
  mesure le cache, pas la base.
- **Toute variable portant une URL publique doit être surchargée.** `connect`
  construit ses redirections à partir de sa configuration ; si une seule garde
  sa valeur d'origine, le tir **sort vers le vrai domaine** au milieu de la
  chaîne de login, sans erreur visible côté Gatling. C'est le piège le plus
  coûteux à diagnostiquer du harnais.
- **Un client de charge n'est pas un navigateur.** Gatling pose spontanément des
  en-têtes de navigateur (`Origin`) qu'`oidc-provider` confronte aux origines
  autorisées du client, et rejette. Le protocole HTTP de la simulation doit
  rester calé sur ce que fait un **client mobile natif**.

## Ce que le harnais ne dit pas

- **Un run local ne produit aucun verdict SLO.** Machine de dev, mock en local,
  pas d'APM : les temps mesurés valident le *parcours*, jamais la tenue en
  charge. Le verdict suppose les environnements dédiés.
- **Aucune cible chiffrée n'est encore posée.** Le harnais sait tirer ; il ne
  sait pas encore contre quoi juger. Voir le sous-chantier « Estimation de
  trafic » dans [`README.md`](./README.md) — sans lui, même un tir sur
  environnement dédié produit des chiffres sans conclusion.
- **Le périmètre est le parcours accueil FT.** Web conseiller, jobs et crons,
  messagerie, notification push massive et parcours MILO sont hors périmètre v1
  — tous de vrais scénarios de charge, que l'architecture accueille sans
  redécoupage.

## Références

- [`perf/README.md`](../../perf/README.md) — mode d'emploi, étapes du login
- [`perf/local-run/README.md`](../../perf/local-run/README.md) — run local
- [`perf/mock-externes/README.md`](../../perf/mock-externes/README.md) — contrat du mock
- [`perf/seed/README.md`](../../perf/seed/README.md) — jeu de données
- [`volumetrie-prod.md`](./volumetrie-prod.md) — volumétries de production mesurées
- [`observabilite.md`](./observabilite.md) — SLI/SLO
