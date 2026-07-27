# Observabilité & SLO — indicateurs cibles

> **Reference.** Sous-chantier du [chantier perf](./README.md). Définit **les
> indicateurs qui comptent, leur finalité, et leurs seuils**, actés en atelier
> SLO le 2026-07-10 (Tech Lead + métier). Les dashboards et alertes se
> construisent **à partir de ce fichier**, pas l'inverse.
>
> **Statut : WIP.** SLI/SLO posés ; seuils à confronter à la baseline mesurée
> (phase 1 du chantier perf) et à l'estimation de trafic (sous-chantier SLO/trafic).

## Principe : trois usages, une pyramide

Le piège constaté : beaucoup de dashboards, aucun verdict. On distingue
désormais trois usages, du haut vers le bas :

| Usage | Question | Forme | Volume |
|---|---|---|---|
| **Verdict (SLO)** | « Est-ce qu'on tient la promesse ? » | 5 indicateurs (I1-I5), chacun avec seuil | Volontairement minimal |
| **Pilotage jour J** | « Que se passe-t-il là, maintenant ? » | 1 dashboard temps réel : affluence + I1-I3 en direct | 1 écran |
| **Diagnostic** | « Où ça casse et pourquoi ? » | Dashboards techniques (latence par endpoint, saturation DB/Redis, partenaires) | Librement extensible |

**Règle anti-prolifération** : tout nouvel indicateur de la couche « verdict »
doit nommer sa question, son consommateur et la décision qu'il déclenche. Sinon
il descend en couche diagnostic — ou il n'existe pas.

## Les indicateurs (actés en atelier)

Priorités métier jour J : adoption > login > parcours connecté > web conseiller.
L'adoption relève du produit ([pass-emploi-analytics]) ; le reste est ici.

### I1 — Authentification (parcours critique n°1)

| | |
|---|---|
| **SLI** | Part des tentatives de login abouties **en < 5 s** (lenteur = échec, décision métier) |
| **SLO** | **≥ 99 %** (« ~1 échec sur 100 » : la première impression est décisive, un jeune qui échoue ne revient pas) |
| **Dimensions** | par **mode d'authentification** (OIDC MILO / FT Connect / mode invité) × par **cause** (nous vs partenaire — une panne MILO se constate, une panne chez nous se corrige) |
| **Mesurable aujourd'hui ?** | **Oui, partiellement** : `pass-emploi-connect` émet `login_initiated` → `login_redirected` → `login_completed` / `login_failed` avec `labels.idp` (le mode) et `login.step` (l'étape d'échec, qui discrimine partenaire — `Callback`, `UserInfo` — de chez nous — `ApiPassEmploi`, `Grant`…). **Manque** : la durée de bout en bout du flow (à corréler via APM ou à instrumenter). |

### I2 — Parcours d'entrée post-authent (questionnaire → plan d'action)

| | |
|---|---|
| **SLI** | Funnel par étape : questionnaire (chaque étape) → génération → affichage du plan d'action. Deux mesures **séparées** : taux d'erreur technique par étape (notre responsabilité) et taux de complétion (produit — l'abandon volontaire ne doit pas polluer le SLO technique) |
| **Seuils** | Écrans ≤ **5 s** ; **génération du plan d'action ≤ 10 s** (service **IA externe** dans le chemin critique, écran de loading assumé) |
| **SLO** | À fixer quand le funnel sera instrumenté (baseline requise) |
| **Mesurable aujourd'hui ?** | **Non** — l'app jeune n'existe pas. Voir la spec d'instrumentation ci-dessous. |

### I3 — Parcours connecté (pages de l'app)

| | |
|---|---|
| **SLI** | Disponibilité + latence p95 par page critique |
| **Pages critiques** | Accueil/plan d'action, offres, chat, agenda — p95 ≤ **5 s** |
| **Pages dégradables** (décision métier : sacrifiables en pic) | **Événements**, **compteur d'heures** (lent toléré par conception) — seuils relâchés + candidates au kill switch du mode dégradé |
| **Mesurable aujourd'hui ?** | Partiellement pour les features reprises de l'app actuelle (endpoints api existants, APM) ; à compléter à la construction de l'app. |

### I4 — Affluence (contexte indispensable)

| | |
|---|---|
| **SLI** | Nombre de jeunes entrant dans le funnel / actifs, en temps réel |
| **Seuil** | Aucun — c'est un **dénominateur**, pas un verdict : « zéro erreur de login » ne se lit pas pareil selon que 10 ou 10 000 jeunes arrivent |
| **Mesurable aujourd'hui ?** | Oui pour le login (count `login_initiated`). Adoption/acquisition au sens produit : [pass-emploi-analytics]. |

### I5 — Santé web conseiller (contagion)

| | |
|---|---|
| **SLI** | Taux d'erreur des endpoints conseillers pendant le pic |
| **SLO** | **Aucun** — décision métier : pas prioritaire jour J, les conseillers seront prévenus des perturbations. Simple suivi en couche diagnostic. |
| **Mesurable aujourd'hui ?** | Oui (logs api + APM existants). |

## Spec d'instrumentation app jeune

L'app n'existe pas encore : ces exigences se posent **avant** le développement,
pour ne pas courir après l'observabilité ensuite. La spec exige des **signaux
observables** (quoi mesurer), pas des `event.action` précis : le mécanisme se
choisit à la conception, selon que l'étape traverse l'api ou non (non tranché
à ce jour — certaines étapes pourraient l'éviter pour la soulager).

| Étape du parcours | Signal requis | Notes |
|---|---|---|
| Tuto d'entrée affiché | vue + identifiant de corrélation (voir ci-dessous) | côté client uniquement |
| Login | existant dans connect : `login_initiated` / `login_redirected` / `login_completed` / `login_failed` (`labels.idp`, `login.step`) | manque la **durée de bout en bout** du flow |
| Étape de questionnaire validée | n° d'étape + `event.outcome` | pour localiser où le funnel casse |
| Plan d'action généré | `event.outcome` + `event.duration` (SLI ≤ 10 s), appel IA tracé en `external_api_call` | — |
| Plan d'action affiché | vue côté client | le « généré » serveur ne prouve pas que le jeune l'a vu |

Règle de choix du mécanisme :

- **L'étape est un use case api** → la convention existante **suffit** :
  `handler_executed` + `log.logger` + `event.outcome`/`event.duration`. Pas de
  nouvel `event.action` ; on documente dans [kibana.md](../logs-ecs/kibana.md)
  quel handler porte quel SLI (couplage au nom du handler assumé).
- **L'étape ne passe pas par l'api** (autre service, ou purement côté app) →
  événement dédié conforme à l'invariant ECS (`event.action` au passé +
  `event.outcome`, via `rootLogger`).
- **Point ouvert structurant** : les signaux côté client (tuto, abandon de
  questionnaire, plan d'action *affiché*) supposent un **canal d'observabilité
  mobile** qui n'existe pas aujourd'hui — l'app Flutter n'envoie rien dans
  notre ES. `handler_executed` ne voit que ce qui atteint le serveur : un jeune
  sans réseau, une app qui plante ou un abandon restent invisibles. À instruire
  à la conception de l'app (logs applicatifs mobiles vs analytics produit).

**Point dur connu** : un flux non authentifié n'a ni `user.id` ni `trace.id`
(limite documentée dans [kibana.md](../logs-ecs/kibana.md)). Or le funnel
d'entrée est précisément pré-authentification — et le **mode invité le reste
toujours**. Il faut un **identifiant de corrélation** dès le premier écran
(ex. `installationId` mobile), propagé sur tous les événements du funnel.
À raccorder au chantier [mode invité](../app-jeune/utilisateurs-authentification.md)
(l'identifiant d'observabilité et l'identifiant fonctionnel de l'invité peuvent
être le même sujet).

## Ce qu'on ne mesure PAS (couche verdict)

Exclusions explicites, pour tenir la pyramide :

- **Pas de SLO par public fonctionnel** (CEJ, AIJ, BRSA…) : la déclinaison se
  fait par **mode d'authentification** (3 valeurs), le public reste une simple
  dimension de filtre en diagnostic.
- **Pas de SLO web conseiller** (décision métier jour J) — suivi diagnostic.
- **Pas d'indicateur d'adoption/acquisition ici** : périmètre produit,
  [pass-emploi-analytics].
- **Pas de métriques infra en couche verdict** (CPU, RAM, GC…) : ce sont des
  causes, pas des promesses — couche diagnostic.

## Mise en œuvre

- Requêtes et alertes sur l'existant : [kibana.md](../logs-ecs/kibana.md)
  (section monitoring tech) ; définitions versionnées sous
  [`logs/elastic/`](../../logs/elastic/).
- Le dashboard de tir de perf (phase 2 du chantier) et le dashboard de pilotage
  jour J dérivent des mêmes SLI — mêmes requêtes, fenêtres différentes.

[pass-emploi-analytics]: ../CONTEXTE-TRANSVERSE.md

## Historique

- **2026-07-10** — atelier SLO (Tech Lead + métier) : priorités jour J, seuils
  I1-I5, pages dégradables, découverte du service IA externe dans le chemin
  critique de la génération du plan d'action.
