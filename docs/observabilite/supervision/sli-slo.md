# SLI / SLO — indicateurs cibles

> **Reference.** Définit **les indicateurs qui comptent, leur finalité, et leurs
> seuils**, actés en atelier SLO le 2026-07-10 (Tech Lead + métier) dans le cadre
> du [chantier perf](../../perf/README.md). Les dashboards et alertes se
> construisent **à partir de ce fichier**, pas l'inverse. Instrumentation requise
> pour les mesurer (app jeune) : [perf/observabilite.md](../../perf/observabilite.md).
>
> **Statut : WIP.** SLI posés ; **seuils simplifiés en un seuil commun le
> 2026-09-08** (voir ci-dessous), à confronter à la baseline mesurée (phase 1 du
> chantier perf) et à l'estimation de trafic (sous-chantier SLO/trafic).

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

## Le seuil commun

**Un seul couple de seuils s'applique à tous les parcours mesurés (I1, I2, I3) :**

| | |
|---|---|
| **Latence** | **p99 < 500 ms** par requête |
| **Fiabilité** | **taux de réussite > 99,5 %** |

Décidé le 2026-09-08, en remplacement des seuils différenciés de l'atelier du
2026-07-10 (p95 ≤ 5 s selon les parcours, ≥ 99 % de logins aboutis).

**Pourquoi un seuil unique.** Les seuils différenciés supposaient une maturité
qu'on n'avait pas : ni baseline mesurée, ni estimation de trafic pour les
calibrer. Un seuil commun est plus simple à asserter, à lire dans un verdict de
tir, et surtout **honnête sur ce qu'il vaut** — c'est un point de départ à
réviser quand la baseline existera, pas une promesse négociée par parcours.

**Ce que ça change côté tir.** Le harnais assertait la seule requête d'accueil,
au motif que les seuils variaient. Avec un seuil commun, **toutes les requêtes
sont assertées** (`forAll` en Gatling), y compris chaque saut du login : la
ligne de verdict en échec nomme elle-même l'étape coupable. Voir
[`harnais.md`](../../perf/harnais.md) et `perf/README.md`.

**L'exception, et la seule.** La génération du plan d'action de fin
d'onboarding reste à **≤ 10 s** : elle traverse un service IA externe, au stade
POC et hors SLA (cf. [chantier app-jeune](../../app-jeune/plan-action.md)). Un
seuil à 500 ms y serait un vœu, pas un objectif. L'écran de loading est assumé.

## Les indicateurs (actés en atelier)

Priorités métier jour J : adoption > login > parcours connecté > web conseiller.
L'adoption relève du produit ([pass-emploi-analytics]) ; le reste est ici.

Les colonnes « SLO » ci-dessous renvoient au seuil commun ; seules les
**dimensions** et la **mesurabilité** restent propres à chaque indicateur.

### I1 — Authentification (parcours critique n°1)

| | |
|---|---|
| **SLI** | Part des tentatives de login abouties dans le budget de latence (lenteur = échec, décision métier) |
| **SLO** | Seuil commun : **p99 < 500 ms** par requête, **réussite > 99,5 %**. La première impression est décisive — un jeune qui échoue ne revient pas. |
| **Dimensions** | par **mode d'authentification** (OIDC MILO / FT Connect / mode invité) × par **cause** (nous vs partenaire — une panne MILO se constate, une panne chez nous se corrige) |
| **Mesurable aujourd'hui ?** | **Oui, partiellement** : `pass-emploi-connect` émet `login_initiated` → `login_redirected` → `login_completed` / `login_failed` avec `labels.idp` (le mode) et `login.step` (l'étape d'échec, qui discrimine partenaire — `Callback`, `UserInfo` — de chez nous — `ApiPassEmploi`, `Grant`…). **Manque** : la durée de bout en bout du flow (à corréler via APM ou à instrumenter). |

### I2 — Parcours d'entrée post-authent (questionnaire → plan d'action)

| | |
|---|---|
| **SLI** | Funnel par étape : questionnaire (chaque étape) → génération → affichage du plan d'action. Deux mesures **séparées** : taux d'erreur technique par étape (notre responsabilité) et taux de complétion (produit — l'abandon volontaire ne doit pas polluer le SLO technique) |
| **Seuils** | Seuil commun sur les écrans du questionnaire. **Exception : génération du plan d'action ≤ 10 s** (service **IA externe** dans le chemin critique, écran de loading assumé) |
| **SLO** | Seuil commun. Le taux de **complétion**, lui, reste à fixer quand le funnel sera instrumenté (baseline requise) — c'est un indicateur produit, pas technique. |
| **Mesurable aujourd'hui ?** | **Non** — l'app jeune n'existe pas. Voir la [spec d'instrumentation](../../perf/observabilite.md#spec-dinstrumentation-app-jeune). |

### I3 — Parcours connecté (pages de l'app)

| | |
|---|---|
| **SLI** | Disponibilité + latence p95 par page critique |
| **Pages critiques** | Accueil/plan d'action, offres, chat, agenda — seuil commun |
| **Pages dégradables** (décision métier : sacrifiables en pic) | **Événements**, **compteur d'heures** (lent toléré par conception) — seuils relâchés + candidates au kill switch du mode dégradé |
| **Mesurable aujourd'hui ?** | Oui pour les features reprises de l'app actuelle : endpoints api découpés par `labels.user_journey`, cf. [SLO Kibana](#mise-en-œuvre--slo-kibana). À compléter à la construction de l'app. |

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

## Requêtes KQL du funnel login

Le flux login de `pass-emploi-connect` est instrumenté en funnel :
`login_initiated` → `login_redirected` → `login_completed` / `login_failed`,
avec `labels.idp` (mode d'authent) et `login.step` (étape d'échec — les steps
`Callback`/`UserInfo` pointent le **partenaire**, les autres pointent chez nous).
Sert I1 et I4.

| Métrique                        | KQL                                                                                                                                                |
|---------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| Taux de succès login (par mode) | `event.action: (login_completed OR login_failed)` — ratio `login_completed`, group by `labels.idp`                                                 |
| Affluence (dénominateur jour J) | `event.action: login_initiated` — count par tranche de temps                                                                                       |
| Échecs imputables au partenaire | `event.action: login_failed AND login.step: (Callback OR UserInfo)`                                                                                |
| Échecs chez nous                | `event.action: login_failed AND NOT login.step: (Callback OR UserInfo)`                                                                            |
| Latence des appels IDP          | `event.action: external_api_call AND labels.operation: (token OR userinfo)` — percentiles `event.duration`, group by `log.logger` (le service IDP) |

## Mise en œuvre : SLO Kibana

Les promesses I1 et I3 sont déclarées dans **Kibana → Observability → SLOs**
(licence Platinum). Chaque SLO calcule son budget d'erreur sur **30 jours
glissants** ; les alertes en découlent par burn rate, cf.
[alertes-applicatives § Alertes SLO](alertes-applicatives.md#alertes-slo--la-promesse-est-menacée).

### Le parcours : `labels.user_journey`

L'api pose un parcours métier sur chaque route via le décorateur
`@UserJourney('<parcours>')` : sur le controller par défaut, surchargé par
route. Il sort dans `labels.user_journey` sur tous les logs de la requête, dont
`request_completed` / `request_failed`, cf.
[couverture-api](../format/logs/couverture-api.md#couverture). Le SLO se
découpe par parcours (`Group by`) : une instance, et donc un budget, par
parcours.

Parcours critiques retenus (pages critiques de I3 + étape `ApiPassEmploi` du
login pour I1) :

| Indicateur | Page ou étape            | `labels.user_journey`                                    |
|------------|--------------------------|----------------------------------------------------------|
| I1         | Login, étape api         | `authentification`                                       |
| I3         | Accueil                  | `accueil_jeune_milo`, `accueil_jeune_france_travail`     |
| I3         | Offres                   | `recherche_offres`                                       |
| I3         | Chat                     | `messagerie`                                             |
| I3         | Agenda                   | `agenda`, `mon_suivi_milo`, `mon_suivi_france_travail`   |

> - **`messagerie` ne couvre pas le chat lui-même** : les messages passent par
>   Firebase, hors api. Le parcours mesure les pièces jointes, les listes de
>   diffusion et les notifications de nouveaux messages.
> - **L'accueil Milo a un mode dégradé silencieux** : si Milo ne répond pas,
>   l'accueil renvoie 200 sans sessions (`accueil_sessions_milo_recuperees` en
>   `failure`, cf. [couverture-api](../format/logs/couverture-api.md)). Le SLO
>   de disponibilité le compte comme un succès.
> - **Pages dégradables exclues** (`animations_collectives`, `sessions_milo`,
>   `evenements_emploi`, compteur d'heures) : sacrifiables en pic, décision
>   métier. Les autres parcours restent en couche diagnostic.

### SLO « API — disponibilité des parcours critiques »

| Paramètre            | Valeur                                                                                                    |
|----------------------|-----------------------------------------------------------------------------------------------------------|
| **Type**             | Custom Query                                                                                              |
| **Index**            | `logs-prod-default`, timestamp `@timestamp`                                                               |
| **Query filter**     | voir ci-dessous                                                                                           |
| **Good query**       | `event.action: request_completed and http.response.status_code < 500`                                     |
| **Total query**      | *(vide : tout ce que retient le filtre)*                                                                  |
| **Group by**         | `labels.user_journey`                                                                                     |
| **Time window**      | 30 days, Rolling                                                                                          |
| **Budgeting method** | Occurrences                                                                                               |
| **Target**           | 99.5 %                                                                                                    |

**Query filter** (commun aux deux SLO api) :
```
event.action: (request_completed or request_failed) and labels.user_journey: (authentification or accueil_jeune_milo or accueil_jeune_france_travail or recherche_offres or messagerie or agenda or mon_suivi_milo or mon_suivi_france_travail)
```

Un 4xx est un succès : c'est l'appelant qui se trompe (cf.
[conventions](../format/logs/conventions.md#doctrine--choisir-le-level-test-dactionabilité)).
Les 5xx sortent en `request_completed` avec un status ≥ 500 ; `request_failed`
ne sort que sur une exception remontée jusqu'à pino-http, toujours comptée en
échec.

### SLO « API — latence des parcours critiques »

Même filtre et même découpage ; « p99 < 500 ms » s'écrit « 99 % des requêtes
sous 500 ms ». `event.duration` est en **nanosecondes** (converti par Logstash).

| Paramètre            | Valeur                                         |
|----------------------|------------------------------------------------|
| **Type**             | Custom Query                                   |
| **Index**            | `logs-prod-default`, timestamp `@timestamp`    |
| **Query filter**     | idem SLO disponibilité                         |
| **Good query**       | `event.duration < 500000000`                   |
| **Total query**      | *(vide)*                                       |
| **Group by**         | `labels.user_journey`                          |
| **Time window**      | 30 days, Rolling                               |
| **Budgeting method** | Occurrences                                    |
| **Target**           | 99 %                                           |

### SLO « Login — réussite par mode d'authentification »

I1 de bout en bout, sur le funnel de `pass-emploi-connect`. Pas de SLO de
latence : la durée du flow complet n'est pas instrumentée (cf. I1).

| Paramètre            | Valeur                                                  |
|----------------------|---------------------------------------------------------|
| **Type**             | Custom Query                                            |
| **Index**            | `logs-prod-default`, timestamp `@timestamp`             |
| **Query filter**     | `event.action: (login_completed or login_failed)`       |
| **Good query**       | `event.action: login_completed`                         |
| **Total query**      | *(vide)*                                                |
| **Group by**         | `labels.idp`                                            |
| **Time window**      | 30 days, Rolling                                        |
| **Budgeting method** | Occurrences                                             |
| **Target**           | 99.5 %                                                  |

### Baseline avant création

Le seuil commun n'a pas été confronté à une mesure (cf. statut en tête). Avant
de créer les SLO, mesurer où en est la prod sur 7 jours (Discover, mode ES|QL) :
un parcours déjà sous l'objectif épuise son budget dès le premier jour et
alerte en continu.

```
FROM logs-prod-default
| WHERE @timestamp >= NOW() - 7 days
    AND event.action IN ("request_completed", "request_failed")
| EVAL parcours = COALESCE(labels.user_journey, "(aucun)")
| STATS requetes = COUNT(*),
        echecs = COUNT(*) WHERE event.action == "request_failed" OR http.response.status_code >= 500,
        lentes = COUNT(*) WHERE event.duration >= 500000000,
        p99_ms = PERCENTILE(event.duration, 99) / 1000000
  BY parcours
| EVAL disponibilite = ROUND(100.0 * (requetes - echecs) / requetes, 2),
       sous_500ms = ROUND(100.0 * (requetes - lentes) / requetes, 2)
| SORT requetes DESC
```

```
FROM logs-prod-default
| WHERE @timestamp >= NOW() - 7 days
    AND event.action IN ("login_completed", "login_failed")
| STATS tentatives = COUNT(*), reussis = COUNT(*) WHERE event.action == "login_completed"
  BY labels.idp
| EVAL reussite = ROUND(100.0 * reussis / tentatives, 2)
```

La ligne `(aucun)` mesure les requêtes sans parcours : routes non décorées, ou
rejetées par un guard avant que le parcours ne soit posé.

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

## Historique

- **2026-09-08** — **seuils simplifiés en un seuil commun** (p99 < 500 ms,
  réussite > 99,5 %) pour I1, I2 et I3, en remplacement des seuils différenciés
  du 2026-07-10 : sans baseline ni estimation de trafic, un seuil par parcours
  donnait une fausse précision. Seule exception conservée : la génération du
  plan d'action (≤ 10 s, service IA externe). Le harnais de tir assertait la
  seule requête d'accueil parce que les seuils variaient ; il asserte désormais
  toutes les requêtes.
- **2026-07-10** — atelier SLO (Tech Lead + métier) : priorités jour J, seuils
  I1-I5, pages dégradables, découverte du service IA externe dans le chemin
  critique de la génération du plan d'action.
