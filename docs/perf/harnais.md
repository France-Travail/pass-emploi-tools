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
| **`mock-externes`** | [`perf/mock-externes/`](../../perf/mock-externes/README.md) | Se fait passer pour l'IdP FT et ses APIs partenaires. Signe ses propres `id_token` avec une paire RSA générée au premier démarrage — aucune clé d'un environnement réel. Sans état de session : l'identité tirée au sort est encodée dans le `code`, jamais partagée entre workers. |
| **Le seed** | [`perf/seed/`](../../perf/seed/README.md) | Crée en base le pool de bénéficiaires que le mock tire au sort, aux volumétries mesurées en production. Idempotent, protégé par un marqueur anti-prod. Un second script (`fond-de-charge.sql`, opt-in, 0 par défaut) sème des bénéficiaires hors du pool, pour pousser les tables au-delà de la taille de prod. |
| **La simulation** | [`perf/src/gatling/`](../../perf/README.md) | Suit la chaîne de redirections **à la main**, étape nommée par étape — ce qui donne un temps de réponse par saut, et rend tout écart immédiatement lisible. |
| **Le run local** | [`perf/local-run/`](../../perf/local-run/README.md) | Fait tourner `connect` et `api` en natif contre le mock, pour valider le parcours sans environnement dédié. |

## Modèle d'injection : ouvert

Les simulations injectent un **débit d'arrivées** (`USERS_PER_SEC`), pas un
nombre d'utilisateurs simultanés.

Ce n'est pas un détail de paramétrage. En modèle **fermé** (un utilisateur
n'entre que quand un autre sort), la charge s'auto-régule : si le système
ralentit, on lui envoie moins de trafic, la latence bouge à peine et c'est le
débit qui s'effondre — un tir peut rester vert en pleine dégradation. En modèle
**ouvert**, les arrivants n'attendent personne : la file grossit et la latence
explose, ce qui est le comportement à reproduire ici, puisque les jeunes
arrivent de l'extérieur (MES, communication, notification push massive).

Corollaire : sous saturation, Gatling crée des utilisateurs que le système
n'absorbe plus. Les simulations posent donc un `maxDuration`, sans quoi un tir
qui part en vrille monopolise l'environnement et noie l'injecteur.

Deux profils partagent ce modèle ouvert (`PROFIL`, input `profil` du
workflow) : `palier` (débit fixe, verdict SLO — le tir de référence) et
`escalier` (débit croissant par paliers, **sans assertion** — un p99 agrégeant
des paliers à des débits différents ne jugerait rien) pour chercher le point
de rupture. La lecture d'un escalier se fait sur le rapport HTML, par seconde.

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
- **Le pool doit couvrir les arrivées du tir**, pas la concurrence — au moins
  **`pool_size ≥ nombre d'arrivées`**, soit `(1 + débit) × ramp / 2 + débit ×
  hold` en profil palier, et `durée_palier × (nb × début + pas × nb × (nb−1)/2)`
  en escalier. La règle antérieure (5 × `USERS_PER_SEC`) dimensionnait contre
  les utilisateurs *concurrents* : un ordre de grandeur trop bas. Ce qui rend
  une ligne chaude en cache PostgreSQL n'est pas d'être lue simultanément mais
  d'être **relue** pendant la fenêtre de tir ; en production chaque arrivée est
  une personne distincte, donc un pool plus petit que le nombre d'arrivées fait
  mesurer `shared_buffers` plutôt que la base. Corollaire assumé : un tir
  sérieux demande un pool de l'ordre de la volumétrie de prod, et le partage
  pool / fond de charge devient un curseur, pas une frontière de nature.
- **Toute variable portant une URL publique doit être surchargée.** `connect`
  construit ses redirections à partir de sa configuration ; si une seule garde
  sa valeur d'origine, le tir **sort vers le vrai domaine** au milieu de la
  chaîne de login, sans erreur visible côté Gatling. C'est le piège le plus
  coûteux à diagnostiquer du harnais.
- **Les workers du mock partagent une seule clé de signature.** Le `certs`
  servi par un worker doit valider un `id_token` signé par n'importe quel autre.
  Une clé par worker n'échoue pas franchement : elle fait passer `1/workers` des
  logins et rejette le reste en `RPError: no valid key found in issuer's
  jwks_uri`, ce qui se lit comme un taux d'erreur sous charge alors que c'est un
  défaut de configuration. La clé transite par `IDP_CLE_PRIVEE_PEM`.
- **Un client de charge n'est pas un navigateur.** Gatling pose spontanément des
  en-têtes de navigateur (`Origin`) qu'`oidc-provider` confronte aux origines
  autorisées du client, et rejette. Le protocole HTTP de la simulation doit
  rester calé sur ce que fait un **client mobile natif**.

## Ce que le harnais ne dit pas

- **Un run local ne produit aucun verdict SLO.** Machine de dev, mock en local,
  pas d'APM : les temps mesurés valident le *parcours*, jamais la tenue en
  charge. Le verdict suppose les environnements dédiés.
- **Le seuil existe, le volume cible non.** Depuis le 2026-09-08 le harnais
  juge contre un seuil commun (p99 < 500 ms, réussite > 99,5 % — cf.
  [`observabilite.md`](./observabilite.md)), assertés sur **toutes** les
  requêtes. Ce qui manque encore est le **débit** à tenir : le sous-chantier
  « Estimation de trafic » dans [`README.md`](./README.md) n'a pas démarré, si
  bien qu'un tir dit « à ce débit, on tient » sans dire si ce débit est celui
  du jour J. En attendant, le profil `escalier` (ci-dessus) tâtonne
  méthodiquement le point de rupture pour établir un état des lieux.
- **Le jeu de données est synthétique, pas un volume de prod.** Pool comme fond
  sèment des bénéficiaires aux distributions mesurées, pas les vraies lignes de
  prod — pas de jointures réelles, pas la distribution croisée entre tables
  qu'un restore de snapshot donnerait. La taille des tables et la pression sur
  les index s'en approchent, elles ne les reproduisent pas.
- **Le périmètre est le parcours accueil FT.** Web conseiller, jobs et crons,
  messagerie, notification push massive et parcours MILO sont hors périmètre v1
  — tous de vrais scénarios de charge, que l'architecture accueille sans
  redécoupage.

## Orchestration

Un tir se déclenche depuis GitHub Actions (`Perf - Tir API`), qui enchaîne
réveil de l'environnement, seed, tir, verdict et archivage. Les commandes
équivalentes en manuel sont dans [`perf/README.md`](../../perf/README.md).

Deux gestes restent **délibérément** hors du workflow :

| Geste | Pourquoi |
|---|---|
| Poser le marqueur d'environnement de perf | C'est le garde-fou anti-prod du seed. Un workflow qui sait le poser sait le poser sur la production. |
| Restaurer un vrai snapshot PostgreSQL de prod | Mécanique non décidée (durée d'un `pg_restore`, anonymisation). Le fond de charge **synthétique** (`fond_size`, opt-in, input du workflow) comble une partie du besoin — vraisemblance du volume, pas de vraies données — mais reste une approximation. |

Les seuils SLO (`p99_threshold_ms`, `success_percent_threshold`) et le débit
(`users_per_sec` ou les paramètres d'escalier) sont, eux, des inputs du
workflow depuis le 2026-09-08 — ils viennent de l'atelier SLO comme valeurs
par défaut, mais un tir peut les faire varier sans toucher au code.

`journal_http` (`INFO` par défaut) est un input de **diagnostic** : à `DEBUG`,
Gatling journalise les réponses en échec, corps compris, pour comprendre
*pourquoi* un tir échoue sans avoir à modifier `logback.xml`. À laisser à `INFO`
pour un tir de mesure — le coût de log fausse la latence, et un tir qui échoue
massivement produit des mégaoctets de corps de réponse.

Les apps de perf sont éteintes la nuit et le week-end par
`perf-env-shutdown.yml` et rallumées à 8h par `perf-env-wakeup.yml`. Le
workflow de tir ne s'appuie pas sur ce cron : il réveille lui-même et attend
que les sondes de santé répondent.

## Ce qu'un résultat doit porter pour être comparable

Les artefacts GitHub expirent (90 jours) : un jour ou l'autre, les résultats
utiles seront versionnés — un journal des tirs, une ligne par tir (piste ouverte
dans [`README.md`](./README.md)). Ce qu'on versionnera devra porter **tous les
paramètres du tir**, pas seulement ses chiffres, sans quoi deux résultats ne se
comparent pas.

`metadonnees.json` est fait pour ça, et contient déjà :

| | |
|---|---|
| **Charge** | `USERS_PER_SEC`, ramp, hold, taille du conteneur de l'injecteur |
| **Seuils** | p99, taux de réussite |
| **Données** | taille et préfixe du pool, SHA du seed, image de base (ou son absence) |
| **Infra** *(non piloté par le workflow)* | taille et statut du conteneur de chaque app, SHA déployé, plans des addons |

La taille de chaque app mesurée (`connect`, `api`, `mock-externes`) est
désormais **pilotée par le tir**, une variable par app (`taille_connect`,
`taille_api`, `taille_mock`, défaut `M`) plutôt qu'une taille commune : rien
n'oblige connect et api à partager la même taille en prod, et viser l'iso-prod
suppose de les régler séparément. `logstash-perf` reste hors de ce pilotage —
sa taille répond à son propre test de charge, pas à ce SLO. `metadonnees.json`
distingue la taille **demandée** par app (`charge.taille_demandee.{connect,
api, mock}`) de la taille **observée** (`infrastructure.<app>.conteneur`) :
les deux devraient coïncider, mais seule la seconde vient de Scalingo — c'est
elle qui fait foi en cas d'écart.

Le `--size` du `make tir` (`TAILLE_INJECTEUR`) est un réglage séparé : il ne
concerne que le conteneur one-off de l'**injecteur**, jamais les apps mesurées.
Un injecteur sous-dimensionné peut devenir lui-même le facteur limitant du tir
— voir `perf/README.md`, § Tirer depuis Scalingo.

## Références

- [`perf/README.md`](../../perf/README.md) — mode d'emploi, étapes du login
- [`perf/local-run/README.md`](../../perf/local-run/README.md) — run local
- [`perf/mock-externes/README.md`](../../perf/mock-externes/README.md) — contrat du mock
- [`perf/seed/README.md`](../../perf/seed/README.md) — jeu de données
- [`volumetrie-prod.md`](./volumetrie-prod.md) — volumétries de production mesurées
- [`observabilite.md`](./observabilite.md) — SLI/SLO
