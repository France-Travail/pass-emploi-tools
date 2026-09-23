# App Jeune — Plan d'action

> **Reference.** Comment le plan d'action de fin d'onboarding est produit à
> partir du questionnaire : le vocabulaire métier, le référentiel de solutions,
> les règles d'éligibilité et de construction, et le contrat exposé au mobile.
> Sous-chantier de [`README.md`](./README.md) ; c'est l'**étape 4 du parcours
> d'entrée** décrit dans
> [`parcours-fonctionnalites.md`](./parcours-fonctionnalites.md), pour les
> publics définis dans
> [`utilisateurs-authentification.md`](./utilisateurs-authentification.md).
>
> **Statut : WIP.** Ouvert le 2026-07-28. Depuis septembre 2026, le plan est
> **calculé dans `pass-emploi-api`** : le service de génération externe (POC
> `bayesimpact/1jeune-des-solutions`) n'est plus appelé.

## Vocabulaire : du questionnaire au plan

Deux notions à ne jamais confondre : ce que le jeune **déclare**, et ce qu'on
lui **propose** pour y répondre.

| | Questionnaire — l'entrée | Plan d'action — la sortie |
|---|---|---|
| **Qui le produit** | Le jeune, pendant l'onboarding | L'API, à partir du questionnaire |
| **Contenu** | Situation, **besoins**, **contraintes**, date de naissance, communes | **Objectifs**, chacun regroupant des **solutions** (les actions cochables) |
| **Domaine API** | `Questionnaire` | `PlanAction` |

- Un **besoin** est ce que le jeune cherche (s'orienter, trouver une
  alternance…). Une **contrainte** est ce qui le freine (pas de permis, fins de
  mois difficiles…).
- Un **objectif** du plan répond à **un** besoin ou lève **une** contrainte.
- Le domaine `PlanAction` dépend de `Questionnaire`, jamais l'inverse : le
  questionnaire existe indépendamment du plan qu'on en tire.

Le contrat mobile, antérieur à ce vocabulaire, parle encore de `goals`,
`obstacles` et `objectives` (voir [Contrat mobile](#contrat-mobile)).

## Ce qu'est le plan d'action

Au bout du questionnaire, l'app affiche un **plan d'action** : des objectifs,
chacun regroupant des actions cochables. Chaque action pointe vers un service
public : un lien externe, un deeplink interne à l'app, ou un simple conseil sans
navigation.

C'est le contenu de la page **Accueil**, et la première valeur rendue au jeune
qui vient de répondre au questionnaire.

## Comment le plan est produit

```
questionnaire du jeune
   │
   ├─ filtre d'éligibilité sur le référentiel de solutions
   │    thème (besoin ou contrainte) ET structure ET situation
   │    ET âge ET territoire
   │
   └─ construction du plan
        un objectif par besoin, puis par contrainte,
        regroupant ses solutions éligibles
```

**Tout est déterministe et sans IA** : mêmes réponses, même plan (seul
l'identifiant du plan change). Le calcul se fait en mémoire, sans appel sortant.

### Le référentiel de solutions

Une solution est une action concrète rattachée à un service public. Elle
**répond à un besoin OU lève une contrainte, jamais les deux**.

- **Source métier** : le tableur Grist « services et solutions », hérité du POC.
  Les noms de champs de ce tableur (`category`, `blocker`, `territory`…) sont
  conservés tels quels dans le code.
- **Stockage** : **provisoire**. Le référentiel est une copie **embarquée au
  build** de l'API, sans synchronisation automatique avec Grist. Il a vocation à
  passer en base.
- **Conséquence** : modifier le référentiel demande un déploiement de l'API,
  mais **jamais une livraison mobile**.

### Règles d'éligibilité

Une solution est proposée au jeune si **toutes** ces conditions sont vraies.
Sur chaque critère, une solution sans valeur (liste vide, borne absente) ne
filtre pas.

| Critère | Règle |
|---|---|
| **Thème** | Son besoin fait partie des besoins du jeune, **ou** sa contrainte fait partie de ses contraintes |
| **Structure** | La structure de l'utilisateur fait partie de celles visées par la solution (l'invité a sa propre structure `INVITE`) |
| **Situation** | La situation du jeune fait partie de celles visées |
| **Âge** | L'âge calculé depuis la date de naissance est dans les bornes. Sans date de naissance, les bornes sont ignorées |
| **Territoire** | Le département du jeune est dans la liste de la solution, ou la solution vise l'outre-mer et le jeune y est |

> **Piège territoire.** Le filtre porte sur la **solution**, pas sur le jeune :
> une solution rattachée à un territoire est **exclue quand le questionnaire ne
> permet pas de calculer un département**. Ne pas transmettre de commune retire
> donc des solutions au lieu d'être neutre.

Le département se dérive du code INSEE de la **ville de recherche**, à défaut de
la **commune de résidence** : les 2 premiers caractères, ou les 3 premiers pour
l'outre-mer (codes `97x` / `98x`). La comparaison ignore la casse, pour la Corse
(`2A` / `2B`).

### Règles de construction

- **Un objectif par besoin, puis un par contrainte**, dans l'ordre des réponses
  du jeune. Un besoin ou une contrainte répété ne produit qu'un objectif.
- **Titres fixes**, un par besoin et par contrainte (« Trouver une alternance »,
  « Me déplacer plus facilement »…).
- **Solutions dans l'ordre du référentiel** : l'ordre des lignes du référentiel
  est l'ordre servi au jeune.
- **Un besoin ou une contrainte sans solution éligible ne produit pas
  d'objectif.**
- La contrainte « rien ne me bloque » est **exclusive** : cochée avec d'autres,
  elle les remplace toutes. Elle n'a jamais de solution, pas plus que « autre ».

## Contrat mobile

Le mobile parle un contrat **stable**, exprimé dans son propre vocabulaire. Les
écarts avec le vocabulaire métier sont **assumés** : renommer un champ du
contrat coûterait une livraison mobile.

### Réponses envoyées par le mobile

| Champ mobile | Dans le questionnaire | Remarque |
|---|---|---|
| `situation` | situation | 1:1 |
| `goals` | besoins | au moins un |
| `obstacles` | contraintes | exclusivité de « rien ne me bloque », dédoublonnage |
| `dateNaissance` | date de naissance | date civile conservée, sans glissement de fuseau |
| `habitation` | commune de résidence | code INSEE + nom |
| `villeRecherche` | commune de recherche | code INSEE + nom, prioritaire pour le territoire |
| `domaine` | — | texte libre, **non exploité** par le calcul, seulement journalisé |
| `rayonKm` | — | **non exploité** |
| — | structure | dérivée du profil de l'utilisateur authentifié |

Les communes viennent de `geo.api.gouv.fr`, interrogé **directement par le
mobile**.

### Plan renvoyé au mobile

- `objectives[]` : `id`, `titre`, `theme` (la valeur du besoin ou de la
  contrainte d'origine), `actions[]`.
- Chaque action : `id`, `libelle`, `type` (`LIEN`, `NAVIGATION` ou `CONSEIL`),
  et selon le cas `url` et `nomService`.
- Les identifiants d'objectifs sont **positionnels** (`objective-1`,
  `objective-2`…) : l'app y rattache les actions cochées.

## Accès et traces

- **Autorisé** au bénéficiaire accompagné et à l'**invité** (JWT normal,
  structure `INVITE`) : route authentifiée classique, pas d'endpoint public.
  L'ensemble est derrière le flag de configuration `appJeuneActif`.
- **Rien n'est persisté** côté API. Le mobile stocke le plan et les cases
  cochées en local, comme il stocke déjà les réponses du questionnaire.
- **Événement d'engagement** `PLAN_ACTION_GENERE`, émis à chaque génération via
  `EvenementService`, **hors du chemin de réponse**. La table porte déjà
  `structure`, ce qui distingue un invité d'un accompagné sans colonne
  supplémentaire. L'identifiant d'un invité est un pseudonyme sans lien avec une
  identité civile.
- **Log applicatif** : les réponses du questionnaire sont journalisées en labels
  ECS : situation, besoins, contraintes et, s'il est renseigné, le domaine visé.
  Les noms des labels suivent le contrat mobile (`plan_action_goals`,
  `plan_action_obstacles`…), pour ne pas casser les tableaux de bord.

On mesure le volume et les choix déclarés, pas l'usage réel des actions :
mesurer la complétion supposerait de persister le plan.

## Backlog de recette

Le questionnaire est **plus riche que le référentiel**. Le questionnaire étant la
référence de ce que veut le métier, ces écarts se comblent **dans le
référentiel**.

| Écart | Effet aujourd'hui |
|---|---|
| Deux contraintes sans solution (« pas de diplôme », « peu d'expérience ») | Le jeune ne reçoit **rien** sur une contrainte qu'il a déclarée |
| Colonne « territoire » quasi vide | Seules les solutions ultramarines sont filtrées territorialement |
| `domaine` et `rayonKm` collectés mais inexploités | Aucun, en attendant une règle métier qui les utilise |

Ces écarts sont de la **matière produit**, pas de la dette technique : un jeune
qui déclare une contrainte et ne reçoit aucune solution dessus, c'est
précisément le signal à remonter au métier.

## Risques assumés

- **`geo.api.gouv.fr` appelé en direct par le mobile** : sans lui, l'étape « où
  tu habites » est bloquante, sans repli.
- **Référentiel désynchronisable** : la copie embarquée ne suit pas les
  modifications faites dans Grist. Toute mise à jour est une opération manuelle
  suivie d'un déploiement.
- **Volumétrie** : la génération est le premier écran après le questionnaire,
  donc appelée par *chaque* nouvel utilisateur. Le calcul est local et léger,
  mais la route reste à raccorder au [chantier perf](../perf/README.md) avant
  toute mise en service large.

## Questions ouvertes `TODO`

- **Référentiel en base** : modèle, back-office d'édition, et devenir de la
  source Grist.
- **Persistance du plan** : écartée pour l'instant. Deviendra nécessaire pour
  mesurer la complétion des actions, et pour qu'un plan survive à un changement
  d'appareil.
- **Devenir du plan à la transition invité → inscrit** : dépend du sujet plus
  large de la transition, non traité (voir
  [`utilisateurs-authentification.md`](./utilisateurs-authentification.md)).
- **Exploitation de `domaine` et `rayonKm`** : collectés sans règle métier qui
  les utilise.
- **Journalisation du domaine** : c'est un texte libre saisi par le jeune,
  journalisé tel quel. À valider au regard des données personnelles.
