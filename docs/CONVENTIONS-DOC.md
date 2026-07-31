# Convention de documentation transverse

> Comment on range et on charge la documentation partagée entre les repos Pass
> Emploi. But : que la connaissance transverse soit **versionnée, partagée, et
> retrouvée de façon fiable** sans noyer chaque contexte de travail.

## Deux couches, deux audiences

| Couche | Où | Pour qui | Nature |
|---|---|---|---|
| **Stable / référence** | repo `pass-emploi-tools/docs/` (versionné) | équipe + tout outil | conventions, décisions, archi — curé, durable |
| **Vivant / travail** | notes personnelles (hors repo) | l'auteur | findings, WIP, débats ouverts, observations datées |

**Règle de direction des liens :**
- versionné → versionné : OK
- personnel → versionné : OK (le pont se fait côté personnel)
- **versionné → personnel : interdit** (un coéquipier n'a pas ces notes)

Quand un élément de la couche vivante se stabilise et devient utile à l'équipe,
on le **promeut** dans la doc versionnée.

## Faut-il documenter ? (test de durabilité)

Avant d'ajouter à la doc versionnée, un seul test : **« est-ce encore vrai après
3 refactos ? »**

- **Oui** (invariant, décision d'archi, vérité structurelle d'un outil) → doc versionnée.
- **Non** (incident daté, ligne de code précise, valeur courante, WIP) → git / code / notes perso.

Objectif : éviter la sur-documentation qui se périme et fait perdre confiance dans
la doc. Une doc qu'on n'ose plus croire ne vaut pas mieux que pas de doc.

## Où vit quoi

- **Contexte global du projet** (vue d'ensemble, glossaire, dispositifs, repos) :
  [`docs/CONTEXTE-TRANSVERSE.md`](./CONTEXTE-TRANSVERSE.md), source de vérité unique.
- **Index des sujets transverses durables** :
  [`docs/SUJETS-TRANSVERSES.md`](./SUJETS-TRANSVERSES.md) — routeur invariant +
  référence stable par sujet.
- **Doc détaillée d'un sujet** : un sous-dossier `docs/<sujet>/` (ex. `docs/logs-ecs/`).
- Un sujet est **possédé** par le repo le plus naturel ; l'infra/outillage transverse
  et les docs transverses vivent dans `pass-emploi-tools`.

## Chargement par l'outillage (CLAUDE.md / @import)

Les repos sont clonés en **frères** dans un dossier parent commun. Le contexte
global est tiré dans chaque `CLAUDE.md` de repo via un import relatif :

```
@../pass-emploi-tools/docs/CONTEXTE-TRANSVERSE.md
```

`CONTEXTE-TRANSVERSE.md` importe à son tour `SUJETS-TRANSVERSES.md`. Conséquence :
l'index des sujets (invariants + pointeurs) est **toujours présent**, mais la doc
détaillée d'un sujet n'est lue **qu'à la demande**.

> **La règle de lecture vit dans l'index lui-même**, pas ici : voir « Règle de
> chargement » en tête de [`SUJETS-TRANSVERSES.md`](./SUJETS-TRANSVERSES.md).
> Ce fichier-ci n'est **jamais chargé** en session — une règle de consommation
> écrite ici ne se déclenche pas. Ne la dupliquer sous aucun prétexte : la faire
> évoluer dans l'index.

- **Toujours chargé** (petit) : contexte global + index des sujets + invariants.
- **À la demande** (volumineux) : `docs/<sujet>/`.

Ne **pas** mettre la doc détaillée d'un sujet en import permanent : ça pollue
chaque session. L'invariant dans l'index suffit à garantir qu'on sait qu'une norme
existe et où la trouver.

## Ajouter un nouveau gros sujet transverse durable

1. Créer `docs/<sujet>/` (un `README.md` index + les fichiers de référence).
2. Ajouter une entrée dans [`SUJETS-TRANSVERSES.md`](./SUJETS-TRANSVERSES.md) :
   **ouvrir quand** + **invariant** + **référence stable**. Rien de personnel.
   - Le **« ouvrir quand »** se formule en *situations et questions* (« on parle
     de X », « on cherche à savoir si Y »), pas en actions de code. Sans lui, le
     sujet ne se charge que si quelqu'un est sur le point de modifier du code —
     donc jamais sur une question d'analyse, de conception ou d'organisation.
   - La **référence** doit **nommer les fichiers** du sous-dossier, pas seulement
     son `README.md` : un routeur qui pointe vers un routeur s'arrête au premier
     palier.
3. Garder le style **team-facing** : lisible sans contexte de session, pas de
   jargon interne, liens relatifs entre docs.