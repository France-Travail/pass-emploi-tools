# Observabilité du chantier perf — instrumentation requise

> **Reference.** Sous-chantier du [chantier perf](./README.md). Les SLI/SLO
> (seuil commun, I1-I5) sont définis dans
> [`observabilite/supervision/sli-slo.md`](../observabilite/supervision/sli-slo.md) ;
> ce fichier-ci pose **ce que l'app jeune doit émettre** pour qu'on puisse les
> mesurer.

## Spec d'instrumentation app jeune

L'app n'existe pas encore : ces exigences se posent **avant** le développement,
pour ne pas courir après l'observabilité ensuite. La spec exige des **signaux
observables** (quoi mesurer), pas des `event.action` précis : le mécanisme se
choisit à la conception, selon que l'étape traverse l'api ou non (non tranché
à ce jour — certaines étapes pourraient l'éviter pour la soulager).

| Étape du parcours | Signal requis | Notes |
|---|---|---|
| Tuto d'entrée affiché | vue + identifiant de corrélation (voir ci-dessous) | côté client uniquement |
| Login | existant dans connect : `login_initiated` / `login_redirected` / `login_completed` / `login_failed` (`labels.idp`, `error.type`) | manque la **durée de bout en bout** du flow |
| Étape de questionnaire validée | n° d'étape + `event.outcome` | pour localiser où le funnel casse |
| Plan d'action généré | `event.outcome` + `event.duration` (SLI ≤ 10 s), appel IA tracé en `external_api_call` | — |
| Plan d'action affiché | vue côté client | le « généré » serveur ne prouve pas que le jeune l'a vu |

Règle de choix du mécanisme :

- **L'étape est un use case api** → la convention existante **suffit** :
  `handler_executed` + `log.logger` + `event.outcome`/`event.duration`. Pas de
  nouvel `event.action` ; on documente dans [sli-slo.md](../observabilite/supervision/sli-slo.md)
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
(limite documentée dans [investigation-incident.md](../observabilite/runbooks/investigation-incident.md)). Or le funnel
d'entrée est précisément pré-authentification — et le **mode invité le reste
toujours**. Il faut un **identifiant de corrélation** dès le premier écran
(ex. `installationId` mobile), propagé sur tous les événements du funnel.
À raccorder au chantier [mode invité](../app-jeune/utilisateurs-authentification.md)
(l'identifiant d'observabilité et l'identifiant fonctionnel de l'invité peuvent
être le même sujet).

## Mise en œuvre

- SLI, seuils et requêtes du funnel login : [supervision/sli-slo.md](../observabilite/supervision/sli-slo.md) ;
  alertes : [applicatives](../observabilite/supervision/alertes-applicatives.md) et
  [stack d'observabilité](../observabilite/supervision/alertes-stack-observabilite.md) ;
  définitions de rétention versionnées sous [`stockage/`](../observabilite/stockage/README.md).
- Le dashboard de tir de perf (phase 2 du chantier) et le dashboard de pilotage
  jour J dérivent des mêmes SLI — mêmes requêtes, fenêtres différentes.
