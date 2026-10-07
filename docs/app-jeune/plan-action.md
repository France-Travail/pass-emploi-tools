# App Jeune — Plan d'action

> **Reference.** Comment le plan d'action de fin d'onboarding est produit : le
> domaine `plan-action` de `pass-emploi-api`, son référentiel de solutions, le
> générateur qui suggère, et le mapping vers le mobile. Sous-chantier de
> [`README.md`](./README.md) ; c'est l'**étape 4 du parcours d'entrée** décrit
> dans [`parcours-fonctionnalites.md`](./parcours-fonctionnalites.md), pour le
> public invité défini dans
> [`utilisateurs-authentification.md`](./utilisateurs-authentification.md).
>
> **Statut : WIP.** Ouvert le 2026-07-28. Le générateur est encore le **POC
> externe**, hors SLA ; son internalisation est le chantier suivant.
>
> **Décision (2026-09-17) : le service de génération sera internalisé**, mais
> **doit rester décorrélé** du reste de l'API.
> **Forme tranchée et livrée (2026-09-23)** : le générateur est derrière le port
> `PlanAction.Generateur` (`domain/plan-action/plan-action.ts`), et l'adaptateur
> du POC (`infrastructure/clients/plan-action-client.ts`) est délibérément
> jetable. Passer à un générateur interne — ou revenir plus tard à un service
> externe — se fait en changeant **une ligne de binding NestJS**, sans toucher
> au domaine, aux handlers ni au schéma.

## Ce qu'est le plan d'action

Au bout du questionnaire invité, l'app affiche une **suggestion de plan
d'action** : 3 à 5 objectifs, chacun regroupant des actions cochables. Chaque
action pointe vers un service public — un lien externe, un deeplink interne à
l'app, ou un simple conseil sans navigation.

C'est le contenu de la page **Accueil**, et la première valeur rendue au jeune
qui vient de répondre à 8 questions.

## Les trois briques

| Brique | Rôle | Où |
|---|---|---|
| **Générateur** | Suggère, à partir d'un profil, des titres d'objectifs et des **identifiants de solutions** | Aujourd'hui [`bayesimpact/1jeune-des-solutions`](https://github.com/bayesimpact/1jeune-des-solutions) — **hors orga France-Travail** — derrière le port `PlanAction.Generateur` |
| **Référentiel** | Détient le contenu réel des solutions (libellé, type, URL, écran, service) | `pass-emploi-api`, tables `referentiel_plan_action_service` et `referentiel_plan_action_solution`, synchronisées depuis un document **Grist** édité par le métier |
| **Domaine `plan-action`** | Réconcilie la suggestion contre le référentiel, attribue les identifiants, persiste | `pass-emploi-api`, `domain/plan-action/` |

La séparation tient en une phrase : **le générateur choisit, le référentiel
dit ce que les choses sont, le domaine décide de ce qui existe chez nous.**

### Pourquoi le mobile n'appelle pas le générateur directement

> **Absorber les changements sans toucher au code de l'app.** Le générateur est
> un POC : son contrat et ses énumérations vont bouger pendant la recette.
> Chaque évolution absorbée côté API est une **livraison mobile évitée** — et une
> livraison mobile coûte un cycle de validation sur les stores.

Bénéfices annexes : le token d'accès au service reste côté serveur (jamais
embarqué dans l'app), les appels sortants sont instrumentés comme les autres
partenaires, et on peut changer de générateur sans que le mobile s'en aperçoive.

### Pourquoi un référentiel à nous, et pas celui du POC

Jusqu'au 2026-09-23, le contenu des actions venait du POC et se retrouvait en
base **en effet de bord de chaque sauvegarde** : le référentiel n'avait pas de
source de vérité, et les identifiants du POC étaient nos clés primaires.

Désormais le référentiel est **notre donnée**, éditée par le métier dans Grist et
importée par un cron. Trois conséquences :

- **Le contenu survit au générateur.** Changer de générateur ne change pas ce
  qu'est une solution.
- **Le métier édite sans livraison.** Corriger une URL ou un libellé est une
  édition Grist plus un import.
- **Un plan relu des mois après reste juste** : les tâches pointent vers le
  référentiel, dont le contenu est maintenu.

## Le service de génération (POC)

### Comment il produit un plan

Il travaille sur **son propre référentiel de solutions** — une solution étant une
action concrète rattachée à un service public — généré depuis les exports du
tableur métier « Parcours et solutions », complétés de lignes écrites à la main.

> **À ne pas confondre avec le nôtre.** Depuis le 2026-09-23, `pass-emploi-api`
> a son référentiel, importé de Grist. Seuls les **identifiants** du POC nous
> parviennent, et ils sont résolus contre le nôtre : une solution que le POC
> propose mais que notre référentiel ne connaît pas (ou qui y est désactivée) est
> **écartée du plan**. Les deux référentiels descendent du même tableur métier,
> ce qui rend les identifiants communs — mais rien ne le garantit
> structurellement, d'où les compteurs de surveillance décrits plus bas.

```
profil du jeune
   │
   ├─ filtre d'éligibilité      ← déterministe, sans IA
   │    thème (objectif ou frein) ET mode d'authentification
   │    ET situation ET âge ET territoire
   │
   ├─ génération (Gemini sur Vertex AI, endpoint EU)
   │    l'IA choisit et regroupe des *identifiants* de solutions,
   │    et rédige les titres et la phrase d'accueil
   │
   └─ matérialisation depuis le référentiel
        chaque identifiant est remplacé par la solution réelle
```

**Invariant central : l'IA ne produit jamais de contenu, seulement des
identifiants.** Les libellés, URL et services viennent tous du référentiel, et
tout identifiant inconnu est supprimé silencieusement. Il est donc
structurellement impossible d'obtenir une action inventée ou une URL
hallucinée : le pire cas est un plan plus pauvre, jamais un plan faux.

L'éligibilité, elle, est **du code pur** : ce n'est pas l'IA qui décide à quoi un
jeune a droit.

### Propriétés à connaître avant de brancher

- **Sans état.** Le service ne persiste rien. Les cases cochées sont toujours à
  `false` en sortie.
- **Non idempotent.** Deux appels identiques peuvent rendre deux plans
  différents (appel LLM).
- **Répond toujours.** Si le LLM est injoignable ou incohérent, un plan
  déterministe est construit à la place, signalé par `generator: "fallback"`.
  Utile pour interpréter la qualité d'un plan en recette.
- **Latence de 1 à 8 s** selon le modèle. C'est ce qui justifie l'étape `loader`
  du questionnaire mobile.
- **Hors SLA.** Pas de rate limiting, pas d'engagement de disponibilité — voir
  [Risques](#risques-assumés).

Le contrat détaillé (champs, énumérations, exemples) est documenté dans le repo
du service, `apps/api/docs/integration.md`. Ne pas le recopier ici : il bougera.

## Notre référentiel (Grist)

Un document **Grist** édité par le métier est importé dans deux tables par le job
`MAJ_REFERENTIEL_PLAN_ACTION`, planifié **le 1er de chaque mois à 5h**
(`0 5 1 * *`).

| Table | Contenu |
|---|---|
| `referentiel_plan_action_service` | Les services publics (nom, description). Identité = l'identifiant de ligne Grist, ce qui survit à un renommage |
| `referentiel_plan_action_solution` | Les solutions : libellé, type, URL ou écran d'app, service rattaché, et les critères d'éligibilité (situations, authentifications, territoires, âge, domaine) |

Le job est calqué sur `MAJ_REFERENTIEL_AGENCES_FT` et en reprend les garde-fous :

- **Aucune suppression, jamais** : une solution retirée du Grist est
  **désactivée** (`active = false`). C'est ce qui permet aux plans déjà
  sauvegardés de continuer à résoudre leurs tâches.
- **Plafond de désactivation** : au-delà d'un pourcentage/nombre configurable,
  l'import échoue plutôt que de vider le référentiel sur un export tronqué.
- **`dryRun`** : calcule le diff et applique le plafond, puis annule la
  transaction. À lancer avant le premier import réel d'un environnement.
- **Compteurs d'anomalies** dans `SuiviJob.resultat` : services non résolus,
  doublons, solutions écartées, valeurs non reconnues.

> **Invariant à connaître avant d'écrire une purge.**
> `plan_action_tache.id_solution` référence le référentiel, et la résolution ne
> rend que les solutions **actives**. L'ensemble tient uniquement parce que
> l'import désactive sans jamais supprimer. Ajouter une purge des solutions
> inactives casserait la sauvegarde en production sur violation de clé étrangère.

## Le domaine dans `pass-emploi-api`

### Principes

- **Persistance partitionnée par profil, pas pass-through pur.** L'invité
  garde son plan **en local** côté mobile (comme les réponses du
  questionnaire) ; un jeune **connecté** voit son plan **persisté côté API**
  (`PlanActionSqlRepository`, table `plan_action` + `plan_action_objectif` +
  `plan_action_tache`). Le handler
  (`GenererPlanActionCommandHandler.handle`) décide via `estInvite(structure)`
  : c'est un test technique, pas encore une politique nommée — à surveiller si
  le partitionnement se complexifie (autre profil, autre critère que la
  structure).
- **Autorisé à l'invité.** L'invité dispose d'un JWT normal (structure
  `INVITE`) : c'est une route authentifiée classique, ouverte via
  l'autorisation dédiée à l'invité. Pas d'endpoint public.
- **L'identité du plan est la nôtre.** Le générateur ne rend que des
  identifiants de solutions ; `PlanAction.Factory` attribue des uuid au plan, à
  chaque objectif et à chaque tâche. Un identifiant venu du générateur n'est
  jamais une clé primaire — c'est ce qui rend le générateur remplaçable sans
  migration, et une tâche adressable donc cochable.
- **Réconciliation systématique, quel que soit le générateur.** Le handler
  résout les identifiants suggérés contre le référentiel avant de construire le
  plan : les inconnus sont écartés, et si **rien** ne subsiste la génération rend
  **502** (le payload du jeune est valide, la panne est la nôtre). Cette
  validation restera en place avec un générateur interne : le générateur
  *choisit*, le domaine *valide*.
- **Le référentiel ne s'écrit que dans son job.** Aucune génération, aucune
  sauvegarde de plan n'a le droit d'y écrire.

### Trace analytique

Un **événement d'engagement** est émis à chaque génération, via le mécanisme
existant (`EvenementService` appelé depuis le hook `monitor()` des handlers).

- Il est écrit **hors du chemin de réponse** : aucun impact sur la latence ni sur
  le succès de l'appel.
- La table porte déjà `structure` : distinguer un plan généré pour un **invité**
  d'un plan généré pour un accompagné ne demande **aucune colonne
  supplémentaire**.
- L'identifiant utilisateur est le **pseudonyme fabriqué à la connexion invité**,
  sans lien avec une identité civile. **Aucune réponse du questionnaire n'est
  journalisée.**

L'événement mesure le volume, pas le contenu. Mesurer la **complétion** devient
possible pour les jeunes connectés maintenant que leur plan est persisté
(`plan_action_tache.terminee`), mais rien ne l'exploite encore — l'endpoint de
cochage n'existe pas.

### Surveillance de la dérive des référentiels

Deux compteurs sont posés dans les logs de chaque génération :

| Label | Ce qu'il mesure |
|---|---|
| `plan_action_ids_recus` | Identifiants de solutions suggérés par le générateur |
| `plan_action_ids_inconnus` | Ceux que notre référentiel ne connaît pas ou a désactivés |

C'est la mesure de l'alignement entre le référentiel du POC et le nôtre —
hypothèse structurante jamais mesurée avant la mise en service. Avec un
générateur interne, `plan_action_ids_inconnus` devrait toujours valoir **0** : une
valeur non nulle signalerait alors un bug de l'algorithme, pas une dérive.

### Mapping du contrat

Le mobile envoie ses réponses dans son vocabulaire ; l'API en compose un
`PlanAction.Profil`, que l'adaptateur du POC traduit ensuite dans le contrat du
service. Ce second passage disparaîtra avec l'adaptateur.

| Réponse mobile | Champ service | Conversion |
|---|---|---|
| `dateNaissance` | `age` | calcul côté API |
| `situation` | `situation` | correspondance 1:1 |
| `objectifs` | `goals` | slugs anglais |
| `freins` | `obstacles` | slugs anglais, **avec pertes** (voir backlog) |
| `domaine` / `domaineInconnu` | `domain` | texte libre, ou `null` si le jeune ne sait pas |
| `habitation`, `villeRecherche`, `rayonKm` | `location` | voir ci-dessous |
| — | `authProvider` | dérivé de la structure de l'utilisateur |
| `prenom` | `firstName` | **à trancher**, voir ci-dessous |

#### Localisation

Le questionnaire collecte **deux communes distinctes** : `habitation` (où le
jeune vit) et `villeRecherche` (+ un rayon en km), cette dernière préremplie
depuis la première. Les communes viennent de `geo.api.gouv.fr`, interrogé
**directement par le mobile**, et sont stockées avec leur **code INSEE** et les
coordonnées du centre.

Le service, lui, n'a **qu'un seul** objet `location` et ne distingue pas les deux
notions. Décision : **l'app transmet les deux à l'API**, qui n'en relaie
qu'une pour l'instant. Le choix devient ainsi un réglage interne à l'API,
ajustable en recette **sans livraison mobile**.

Pour choisir, ce que les champs font réellement côté service :

| Champ | Effet réel |
|---|---|
| `city` | Contexte transmis au LLM pour formuler le plan. Aucun effet sur l'éligibilité |
| `radiusKm` | **Accepté mais pas encore exploité.** Envoyé quand même : le POC l'utilisera |
| `territory` | **Seul champ à effet déterministe** : code département (`"75"`, `"972"`) |

Le `territory` se dérive du code INSEE : les 2 premiers caractères, ou les 3
premiers si le code commence par `97`.

> **Piège.** Le filtre territorial porte sur la **solution**, pas sur le jeune :
> une solution rattachée à un territoire est **exclue quand le profil n'en
> déclare aucun**. Ne pas envoyer `territory` retire donc des solutions au lieu
> d'être neutre. Aujourd'hui une seule solution du référentiel est concernée
> (un dispositif ultramarin), mais la colonne du tableur a vocation à se
> remplir : envoyer le bon format dès maintenant rend ce remplissage
> transparent pour l'API.

#### Prénom

Le service s'en sert uniquement pour composer la phrase d'accueil. Le
transmettre revient à envoyer une donnée nominative à un service tiers hébergé
hors infrastructure France Travail, pour un simple affichage.

**Recommandation : ne pas le transmettre** — le service rend une phrase
générique, et le mobile personnalise avec le prénom qu'il détient déjà en local.
Le POC reste alors anonyme de bout en bout, ce qui simplifie l'analyse d'impact
si le POC est validé. `TODO` à confirmer.

## Backlog de recette

Le questionnaire mobile était **plus riche que le référentiel** : des freins et
objectifs déclarés par le jeune n'avaient aucune solution en face.

**Comblé par le Grist (2026-09-23)** côté référentiel : absence de permis et
absence de transport sont désormais deux contraintes distinctes, et manque
d'expérience, barrière de la langue et vie quotidienne existent. Le profil envoyé
au générateur conserve par ailleurs le **vocabulaire du questionnaire**
(`besoins`/`contraintes` non typés sur le référentiel), pour ne pas perdre
`AUTRE` et `RIEN_NE_ME_BLOQUE` en chemin.

**Reste à vérifier en recette** : que le générateur exploite réellement ces
nouvelles valeurs. Le POC a son propre référentiel — une solution présente chez
nous ne sert à rien s'il ne la propose jamais. C'est `plan_action_ids_recus`
rapporté au contenu attendu qui le dira.

| Écart restant | Effet |
|---|---|
| Colonne « domaine » polluée par un artefact d'export | Sans effet — le champ n'est lu par personne |
| Colonne « territoire » quasi vide | Une seule solution filtrée territorialement |

Ces écarts sont de la **matière produit**, pas de la dette technique : un jeune
qui déclare un frein et ne reçoit aucune solution dessus, c'est précisément le
signal que le POC doit produire.

## Risques assumés

- **Deux dépendances externes non maîtrisées dans le parcours d'entrée** : le
  service de génération, et `geo.api.gouv.fr` appelé en direct par le mobile
  (sans lequel l'étape « où tu habites » est bloquante — il n'y a pas de repli).
- **Le service est un POC exposé à tous les invités.** Pas de rate limiting, pas
  de SLA. L'appel sortant pose un **timeout explicite** (504 en cas de
  dépassement, 502 pour les autres échecs) ; l'étape `loader` du mobile doit
  prévoir une sortie en cas d'erreur.
- **Volumétrie** : la génération est le premier écran après le questionnaire,
  donc appelée par *chaque* invité. À raccorder au [chantier
  perf](../perf/README.md) avant toute mise en service large.

## Questions ouvertes `TODO`

- **Prénom transmis ou non** (voir ci-dessus).
- **Quelle commune relayer** : habitation ou ville de recherche.
- ~~**Persistance du plan.** Écartée pour le POC.~~ **Tranché (2026-09-17)** :
  persistance partitionnée par profil — invité en local mobile, connecté côté
  API. Voir [Principes](#principes) ci-dessus.
- **Devenir du plan à la transition invité → inscrit** — dépend du sujet plus
  large de la transition, non traité (voir
  [`utilisateurs-authentification.md`](./utilisateurs-authentification.md)).
  Question qui se pose différemment maintenant que les deux profils ont des
  lieux de stockage distincts : y a-t-il une migration du plan local vers l'API
  à l'inscription, ou le jeune nouvellement inscrit régénère-t-il un plan ?
- ~~**Industrialisation si le POC est validé.**~~ **Tranché (2026-09-23)** : le
  générateur est derrière le port `PlanAction.Generateur`, le référentiel est à
  nous. Internaliser revient à écrire une implémentation du port et à changer le
  binding. Reste ouvert : la logique de sélection elle-même (quelles règles
  choisissent quelles solutions), et le fait qu'un générateur interne aura besoin
  d'une lecture du référentiel **par critères** — le repository ne sait
  aujourd'hui que résoudre des identifiants.
- **Trois ruptures de contrat à confirmer avec l'équipe mobile** : l'identifiant
  d'action devient celui de la **tâche** (et non plus celui de la solution),
  `DestinationActionPlan` passe de 3 à 5 valeurs (`offres-emploi` et `aller-vers`
  arrivent du Grist — à confirmer que l'app sait les ouvrir), et `genereLe`
  change de format (`…Z` → `…+00:00`).
