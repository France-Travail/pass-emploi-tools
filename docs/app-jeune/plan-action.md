# App Jeune — Plan d'action

> **Reference.** Comment le plan d'action de fin d'onboarding est produit :
> le service externe qui le génère, le proxy `pass-emploi-api` qui l'expose au
> mobile, et le mapping entre les deux. Sous-chantier de
> [`README.md`](./README.md) ; c'est l'**étape 4 du parcours d'entrée** décrit
> dans [`parcours-fonctionnalites.md`](./parcours-fonctionnalites.md), pour le
> public invité défini dans
> [`utilisateurs-authentification.md`](./utilisateurs-authentification.md).
>
> **Statut : WIP.** Ouvert le 2026-07-28. Le service de génération est un **POC**
> destiné à valider la pertinence métier ; le branchement est en cours.

## Ce qu'est le plan d'action

Au bout du questionnaire invité, l'app affiche une **suggestion de plan
d'action** : 3 à 5 objectifs, chacun regroupant des actions cochables. Chaque
action pointe vers un service public — un lien externe, un deeplink interne à
l'app, ou un simple conseil sans navigation.

C'est le contenu de la page **Accueil**, et la première valeur rendue au jeune
qui vient de répondre à 8 questions.

## Les deux briques

| Brique | Rôle | Repo |
|---|---|---|
| **Service de génération** | Produit le plan à partir d'un profil | [`bayesimpact/1jeune-des-solutions`](https://github.com/bayesimpact/1jeune-des-solutions) — **hors orga France-Travail** |
| **Proxy** | Expose le plan au mobile, adapte le contrat | `pass-emploi-api` |

### Pourquoi un proxy, et pas un appel direct

Le mobile pourrait appeler le service de génération directement. On passe
quand même par `pass-emploi-api` pour une raison principale :

> **Absorber les changements sans toucher au code de l'app.** Le service est un
> POC : son contrat, son référentiel et ses énumérations vont bouger pendant la
> recette. Chaque évolution absorbée par le proxy est une **livraison mobile
> évitée** — et une livraison mobile coûte un cycle de validation sur les
> stores. Le mobile parle un contrat stable, exprimé dans son propre vocabulaire ;
> le proxy traduit.

Bénéfices annexes : le token d'accès au service reste côté serveur (jamais
embarqué dans l'app), les appels sortants sont instrumentés comme les autres
partenaires, et on peut basculer vers un autre générateur sans que le mobile
s'en aperçoive.

## Le service de génération (POC)

### Comment il produit un plan

Il travaille sur un **référentiel de solutions** — une solution étant une action
concrète rattachée à un service public. Le référentiel est généré depuis les
exports du tableur métier « Parcours et solutions », complétés de lignes écrites
à la main.

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

## Le proxy dans `pass-emploi-api`

### Principes

- **Pass-through.** Le plan est relayé, **rien n'est persisté** côté API. Le
  mobile stocke le plan et les cases cochées en local, comme il stocke déjà les
  réponses du questionnaire.
- **Autorisé à l'invité.** L'invité dispose d'un JWT normal (structure
  `INVITE`) : c'est une route authentifiée classique, ouverte via
  l'autorisation dédiée à l'invité. Pas d'endpoint public.
- **Traduction uniquement.** Le handler convertit, il ne décide pas. Toute
  logique métier qui s'y installerait est un signal qu'elle manque au service.

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

C'est la seule trace : on mesure le volume, pas le contenu ni l'usage réel des
actions. Mesurer la complétion supposerait de persister le plan — écarté pour
l'instant.

### Mapping du contrat

Le mobile envoie ses réponses dans son vocabulaire ; le proxy compose le profil
attendu par le service.

| Réponse mobile | Champ service | Conversion |
|---|---|---|
| `dateNaissance` | `age` | calcul côté proxy |
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
notions. Décision : **l'app transmet les deux au proxy**, et le proxy n'en relaie
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
> transparent pour le proxy.

#### Prénom

Le service s'en sert uniquement pour composer la phrase d'accueil. Le
transmettre revient à envoyer une donnée nominative à un service tiers hébergé
hors infrastructure France Travail, pour un simple affichage.

**Recommandation : ne pas le transmettre** — le service rend une phrase
générique, et le mobile personnalise avec le prénom qu'il détient déjà en local.
Le POC reste alors anonyme de bout en bout, ce qui simplifie l'analyse d'impact
si le POC est validé. `TODO` à confirmer.

## Backlog de recette

Le questionnaire mobile est **plus riche que le référentiel du service** — le
mobile étant la référence de ce que veut le métier, ces écarts sont à combler
**côté service**, dont l'équipe a les droits d'édition. À traiter après le
branchement, pendant les recettes fonctionnelles.

| Écart | Effet aujourd'hui |
|---|---|
| Deux freins mobile distincts (absence de permis / absence de transport) s'écrasent sur un seul frein service | Perte d'information |
| Deux freins mobile sans équivalent (manque d'expérience, barrière de la langue) | Le jeune ne reçoit **rien** sur un frein qu'il a déclaré |
| Un objectif mobile sans équivalent (vie quotidienne) | Idem |
| Colonne « domaine » du référentiel polluée par un artefact d'export | Sans effet — le champ n'est lu par personne |
| Colonne « territoire » quasi vide | Une seule solution filtrée territorialement |

Ces écarts sont de la **matière produit**, pas de la dette technique : un jeune
qui déclare un frein et ne reçoit aucune solution dessus, c'est précisément le
signal que le POC doit produire.

## Risques assumés

- **Deux dépendances externes non maîtrisées dans le parcours d'entrée** : le
  service de génération, et `geo.api.gouv.fr` appelé en direct par le mobile
  (sans lequel l'étape « où tu habites » est bloquante — il n'y a pas de repli).
- **Le service est un POC exposé à tous les invités.** Pas de rate limiting, pas
  de SLA. Le proxy doit poser un **timeout explicite** et remonter un échec
  propre ; l'étape `loader` du mobile doit prévoir une sortie en cas d'erreur.
- **Volumétrie** : la génération est le premier écran après le questionnaire,
  donc appelée par *chaque* invité. À raccorder au [chantier
  perf](../perf/README.md) avant toute mise en service large.

## Questions ouvertes `TODO`

- **Prénom transmis ou non** (voir ci-dessus).
- **Quelle commune relayer** : habitation ou ville de recherche.
- **Persistance du plan.** Écartée pour le POC. Deviendra nécessaire pour
  mesurer la complétion des actions, et pour qu'un plan survive à un changement
  d'appareil.
- **Devenir du plan à la transition invité → inscrit** — dépend du sujet plus
  large de la transition, non traité (voir
  [`utilisateurs-authentification.md`](./utilisateurs-authentification.md)).
- **Industrialisation si le POC est validé** : le service reste-t-il externe, ou
  est-il repris dans l'infrastructure France Travail ?
