# Alertes applicatives

Les alertes sur des pannes **visibles des utilisateurs et impactantes pour le
métier**, en quatre couches :

- **alertes SLO** (S1 à S3) — la promesse de [sli-slo](sli-slo.md) est-elle
  menacée ? Déduites des SLO Kibana ;
- **alertes de diagnostic** (A1 à A3) — pourquoi : un partenaire qui tombe, des
  5xx qui s'accumulent, une vague de refus d'authentification ;
- **événements Scalingo** (A4a, A4b) — ce qui arrive aux apps : crash, arrêt,
  redémarrage, seuil de ressource, mais aussi déploiements et opérations
  d'infra ;
- **jobs** (A5a, A5b) — un job de l'api a planté.

Elles s'appuient sur les logs ECS (`event.action` / `event.outcome`, cf.
[format/logs/conventions](../format/logs/conventions.md)). Les pannes de la
chaîne de télémétrie elle-même sont dans
[alertes-stack-observabilite](alertes-stack-observabilite.md) : si elle est
aveugle (alerte 3 « silence »), ces alertes-ci ne peuvent pas se déclencher.

Toutes notifient via Mattermost (`#monitoring-production`), sauf A4b
(`Mattermost-monitoring-staging`) et A5a / A5b (canaux des jobs,
`jobs-production` / `jobs-staging`) ; A4a et A4b notifient aussi Tchap
(`monitoring-production`, `monitoring-staging`, cf. [workflows/tchap](workflows/tchap/README.md)).

## Récapitulatif

| #  | Signal                     | Index / source      | Condition                                             | Fréquence | Throttle | Sévérité    |
|----|----------------------------|---------------------|-------------------------------------------------------|-----------|----------|-------------|
| S1 | SLO disponibilité api      | SLO Kibana          | burn rate ≥ 6 par parcours critique                   | 1 min     | —        | 🚨 Critical |
| S2 | SLO latence api            | SLO Kibana          | burn rate ≥ 6 par parcours critique                   | 1 min     | —        | 🚨 Critical |
| S3 | SLO réussite login         | SLO Kibana          | burn rate ≥ 6 par mode d'authentification             | 1 min     | —        | 🚨 Critical |
| A1 | Pic d'échecs partenaire    | `logs-prod-default` | `external_api_call` `failure` > 50 / 5 min par domaine (5xx, 429, 4xx, timeout) | 1 min     | 1h       | ⚠️Warning  |
| A2 | Erreurs serveur 5xx        | APM `metrics-apm.transaction.1m-*` | requêtes api + connect en 5xx > 50 / 5 min, par template | 1 min     | 1h       | 🚨 Critical |
| A3 | Pic d'auth refusées        | `logs-prod-default` | `auth_failed` > 3 × même heure sur 7 j, ≥ 20 / 10 min | 5 min     | 1h       | 🚨 Critical |
| A4a | Événements Scalingo — prod | `logs-alertes-scalingo-prod-default` | tout événement d'une app hors stack d'observabilité | 1 min | — | par ligne : 🚨 / ⚠️ / ℹ️ |
| A4b | Événements Scalingo — staging, perf | `logs-alertes-scalingo-{staging,perf}-default` | idem A4a, canal staging | 5 min | — | par ligne : ⚠️ / ℹ️ |
| A5a | Jobs en échec — prod | `logs-prod-default` | `job_crashed`, `job_handler_not_found` | 1 min | — | ❌ par ligne |
| A5b | Jobs en échec — staging, perf | `logs-{staging,perf}-default` | idem A5a, canal jobs-staging | 5 min | — | ❌ par ligne |
| A6 | Erreurs base de données | `logs-prod-default` | `error.type` Sequelize* > 20 / 5 min | 1 min | 1h | 🚨 Critical |

> **Prod uniquement** (sauf A4b) : en staging, ces signaux reflètent les tests
> en cours, pas une panne. A4b garde le fil d'activité Scalingo de staging et de
> perf, déjà publié dans le canal staging.
>
> **Seuils à calibrer** (A1 à A3) : ceux ci-dessous reprennent les intentions de départ
> (5 échecs/min, 1 erreur 5xx/min, 3 × la normale), pas une mesure. Avant
> d'activer une règle, lancer sa requête de calibrage dans Discover (mode
> ES|QL) et placer le seuil au-dessus du `max` observé sur 7 jours.
>
> **Dashboard applicatif** : seules les alertes SLO renvoient vers
> **[Pass Emploi] SLO de Prod** (cf. [routine de surveillance](../routine-surveillance.md#promesses-utilisateurs-slo)) ;
> les alertes de diagnostic renvoient vers Discover et le [runbook d'investigation](../runbooks/investigation-incident.md).

## Alertes SLO — la promesse est menacée

Une règle **SLO burn rate** par SLO de
[sli-slo § Mise en œuvre](sli-slo.md#mise-en-œuvre--slo-kibana). Elle mesure la
vitesse à laquelle le budget d'erreur des 30 jours se consomme, sur une fenêtre
longue et une fenêtre courte : la longue évite de déclencher sur un pic isolé,
la courte fait retomber l'alerte dès que le problème cesse. La règle s'évalue
instance par instance : un parcours ou un mode d'authentification à la fois.

- **S1** — SLO « API — disponibilité des parcours critiques », à ne créer
  qu'avec le correctif api, cf. [sli-slo](sli-slo.md#slo--api--disponibilité-des-parcours-critiques-) ;
- **S2** — SLO « API — latence des parcours critiques » ;
- **S3** — SLO « Login — réussite jeune France Travail » et « Login — réussite par mode d'authentification ».
  Pour « Login — réussite invité » et « Login — réussite conseiller
  départemental », une seule fenêtre longue, notifiée en High : quelques
  tentatives par jour, un échec isolé sur 1 h vaudrait 100 % d'échecs.

| SLO                        | Fenêtre longue / courte | Burn rate | Sens                                   |
|----------------------------|-------------------------|-----------|----------------------------------------|
| Invité (objectif 90 %)     | 72 h / 6 h              | 2         | ≥ 20 % d'échecs sur ~18 tentatives     |
| Conseiller départemental (objectif 95 %) | 168 h / 12 h | 4      | ≥ 20 % d'échecs sur ~10 tentatives     |

**Création** : rejouer [`rules/1-rules-applicatives.console`](rules/1-rules-applicatives.console)
dans Dev Tools, après [`slo/1-slos.console`](slo/1-slos.console).

| Paramètre               | Valeur                                                                                               |
|-------------------------|------------------------------------------------------------------------------------------------------|
| **Rule name**           | `SLO - Prod - <nom du SLO>`                                                                          |
| **Type**                | SLO burn rate                                                                                        |
| **SLO**                 | le SLO visé                                                                                          |
| **Fenêtres**            | valeurs par défaut de Kibana, cf. tableau ci-dessous                                                 |
| **Fréquence**           | 1 min                                                                                                |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production**, groupes `Critical` et `High` uniquement — message dans le bloc de la règle |
| **Related dashboards**  | dans la règle (onglet Related dashboards), mêmes dashboards que le message |
| **Investigation guide** | dans la règle (mêmes étapes que le message) ; runbook : [runbook d'investigation](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md) |

| Groupe   | Fenêtre longue / courte | Burn rate | Sens : budget des 30 j épuisé en… | Notifié ? |
|----------|-------------------------|-----------|-----------------------------------|-----------|
| Critical | 1 h / 5 min             | 14,4      | ~2 jours                          | oui       |
| High     | 6 h / 30 min            | 6         | 5 jours                           | oui       |
| Medium   | 24 h / 2 h              | 3         | 10 jours                          | non — visible sur la page SLO |
| Low      | 72 h / 6 h              | 1         | 30 jours                          | non — visible sur la page SLO |

> **Login jeune France Travail : seuils 3 / 2 / 1,5 / 1.** Avec un objectif de
> 85 %, le burn rate ne peut pas dépasser 6,67 (100 % d'échecs) : les seuils
> par défaut ne se déclencheraient jamais. Critical à 3 = 45 % d'échecs sur 1 h,
> High à 2 = 30 % sur 6 h. Hors incident, le login tourne vers 13 % d'échecs
> (burn rate 0,87) ; la semaine du 2026-09-14 (31 %) aurait déclenché High.

> **Faible trafic** : sur un parcours peu sollicité (la nuit, ou `authentification`
> hors heures de connexion), 1 échec sur 10 requêtes suffit à dépasser un burn
> rate de 14,4 sur 1 h. La règle n'a pas de volume minimum : surveiller la
> première semaine, et sortir du SLO un parcours trop bruyant plutôt que de
> relâcher l'objectif de tous.

**Message et étapes « À vérifier »** : dans le bloc de la règle de [`rules/1-rules-applicatives.console`](rules/1-rules-applicatives.console), qui fait foi ; son Investigation guide reprend les mêmes étapes.

Les variables `context.*` sont celles de la règle SLO burn rate ; vérifier les
noms dans la liste proposée par le bouton d'ajout de variable de l'action.

## Alertes de diagnostic — pourquoi ça casse

Des **Elasticsearch query rules (ES|QL)**. Elles pointent une cause (partenaire,
5xx, IDP), pas le respect d'une promesse : couche diagnostic de
[sli-slo](sli-slo.md#principe--trois-usages-une-pyramide).

**Création** : rejouer [`rules/1-rules-applicatives.console`](rules/1-rules-applicatives.console)
dans Dev Tools, comme les alertes SLO.

### A1 — Pic d'échecs partenaire (Warning)

Compte les appels sortants de l'api en échec (`external_api_call` en
`failure`), **par domaine** du partenaire (`url.domain`), et classe chaque
échec : `5xx`, `429`, `4xx` ou `timeout / réseau` (pas de code HTTP). Nos
propres services (`*.pass-emploi.beta.gouv.fr`) et les statistiques
(`stats.beta.gouv.fr`) ne comptent pas. A1 remplace aussi les 3 anciennes
règles « 🔌 Partenaires » (5xx, timeouts, 429) : 643 alertes à elles quatre en
30 jours au 2026-10-20.

**Pourquoi les logs et pas l'APM** : l'agent APM n'enregistre pas le span d'un
appel qui part en timeout (constaté le 2026-10-20 : 27 590 timeouts Milo en
21 jours dans les logs, aucun span en échec sans code HTTP dans les traces), et
les traces sont échantillonnées (14 630 erreurs 500 France Travail dans les
logs en 30 jours, 1 401 dans les traces en 21 jours). Les logs donnent déjà le
domaine, le code et le message.

| Paramètre               | Valeur                                                                                                             |
|-------------------------|--------------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `API - Prod - Pic d'échecs partenaire`                                                                             |
| **Type**                | Elasticsearch query rule (ES\|QL), `groupBy: all` : une seule alerte tant que l'incident dure                     |
| **Requête ES\|QL**      | voir ci-dessous — l'alerte part dès qu'elle renvoie une ligne (une par partenaire)                                 |
| **Fenêtre**             | 5 min                                                                                                              |
| **Fréquence**           | 1 min                                                                                                              |
| **Sévérité**            | Warning                                                                                                            |
| **Throttle**            | `On custom action intervals` / `Run every 1 hour` / `Run when: Query matched` (onglet Actions → Settings)          |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production**, et Workflow `tchap-alerte-a1` (relance la requête, poste dans le salon monitoring-production) — messages dans le bloc de la règle |
| **Related dashboards**  | dans la règle (onglet Related dashboards), mêmes dashboards que le message |
| **Investigation guide** | dans la règle (mêmes étapes que le message, contacts partenaires) ; runbook : [runbook d'investigation](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md) |

**Requête ES|QL** :
```
FROM logs-prod-default
| WHERE event.action == "external_api_call" AND event.outcome == "failure" AND url.domain IS NOT NULL
| WHERE NOT url.domain LIKE "*pass-emploi.beta.gouv.fr" AND url.domain != "stats.beta.gouv.fr"
| EVAL type = CASE(http.response.status_code == 429, "429", http.response.status_code >= 500, "5xx", http.response.status_code >= 400, "4xx", "timeout / réseau")
| STATS echecs = COUNT(*), types = VALUES(type) BY partenaire = url.domain
| WHERE echecs > 50
| EVAL types = MV_CONCAT(types, ", ")
| SORT echecs DESC
```

**Calibrage** (2026-10-20, 30 jours, par tranche de 5 min) : Milo p99 = 85,
max = 3 352 (le 2026-10-08 à 13 h 20, timeouts et 429) ; France Travail
p99 = 209, max = 852 (des 500 et des timeouts chroniques). Au-dessus de 50 :
Milo 49 heures sur 21 jours, France Travail 32 heures sur 13 jours, donc au plus
81 messages en 30 jours avec le rappel toutes les heures. Les autres
partenaires ne dépassent jamais 18.
```
FROM logs-prod-default
| WHERE @timestamp >= NOW() - 30 days
    AND event.action == "external_api_call" AND event.outcome == "failure" AND url.domain IS NOT NULL
    AND NOT url.domain LIKE "*pass-emploi.beta.gouv.fr" AND url.domain != "stats.beta.gouv.fr"
| STATS n = COUNT(*) BY partenaire = url.domain, tranche = BUCKET(@timestamp, 5 minutes)
| STATS p99 = PERCENTILE(n, 99), max = MAX(n), au_dessus = COUNT(*) WHERE n > 50 BY partenaire
| SORT max DESC
```

**Message et étapes « À vérifier »** : dans le bloc de la règle de [`rules/1-rules-applicatives.console`](rules/1-rules-applicatives.console), qui fait foi ; son Investigation guide reprend les mêmes étapes.

### A2 — Erreurs serveur 5xx (Critical)

Compte les requêtes en erreur serveur de l'api et de connect dans les métriques
APM (`metrics-apm.transaction.1m-*`), par **template d'URL**
(`transaction.name`, ex. `GET /jeunes/:idJeune`) : les `url.path` des logs
contiennent des identifiants et dispersent une même route sur des milliers de
valeurs. `COUNT(transaction.duration.summary)` donne le nombre de requêtes
(champ `aggregate_metric_double`) ; il égale le compte des traces brutes, sans
perte à l'échantillonnage. La cause de chaque erreur reste dans les logs : le
Discover « Erreurs serveur 5xx » la retrouve par son `trace.id`.

| Paramètre               | Valeur                                                                                                             |
|-------------------------|--------------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `API - Prod - Erreurs 5xx`                                                                                         |
| **Type**                | Elasticsearch query rule (ES\|QL), `groupBy: all` : une seule alerte tant que l'incident dure                     |
| **Requête ES\|QL**      | voir ci-dessous — l'alerte part dès qu'elle renvoie une ligne (une par template, 10 au plus)                       |
| **Fenêtre**             | 5 min                                                                                                              |
| **Fréquence**           | 1 min                                                                                                              |
| **Sévérité**            | Critical                                                                                                           |
| **Throttle**            | `On custom action intervals` / `Run every 1 hour` / `Run when: Query matched` (onglet Actions → Settings)          |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production**, et Workflow `tchap-alerte-a2` (relance la requête, poste dans le salon monitoring-production) — messages dans le bloc de la règle |
| **Related dashboards**  | dans la règle (onglet Related dashboards), mêmes dashboards que le message |
| **Investigation guide** | dans la règle (mêmes étapes que le message) ; runbook : [runbook d'investigation](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md) |

**Requête ES|QL** :
```
FROM metrics-apm.transaction.1m-*
| WHERE service.name IN ("pass-emploi-api-prod", "pass-emploi-connect-prod") AND transaction.result == "HTTP 5xx"
| STATS erreurs = COUNT(transaction.duration.summary) BY service = service.name, template = transaction.name
| INLINE STATS total = SUM(erreurs)
| WHERE total > 50
| SORT erreurs DESC
| LIMIT 10
```

**Calibrage** (2026-10-20, 26 jours de métriques, par tranche de 5 min) :
p99 = 116, max = 1 061 (le 2026-10-08 à 13 h 20, sessions Milo), 32 tranches
au-dessus de 50.
```
FROM metrics-apm.transaction.1m-*
| WHERE @timestamp >= NOW() - 26 days
    AND service.name IN ("pass-emploi-api-prod", "pass-emploi-connect-prod") AND transaction.result == "HTTP 5xx"
| STATS n = COUNT(transaction.duration.summary) BY tranche = BUCKET(@timestamp, 5 minutes)
| STATS p99 = PERCENTILE(n, 99), max = MAX(n), au_dessus = COUNT(*) WHERE n > 50
```

**Message et étapes « À vérifier »** : dans le bloc de la règle de [`rules/1-rules-applicatives.console`](rules/1-rules-applicatives.console), qui fait foi ; son Investigation guide reprend les mêmes étapes.

### A3 — Pic d'authentifications refusées (Critical)

Le volume normal de `auth_failed` varie selon l'heure (tokens expirés en
journée) : la référence est la moyenne **de la même heure** sur les 7 jours
précédents, ramenée à 10 min (7 j × 6 tranches = 42). Le plancher de 20 refus
évite de déclencher la nuit sur une référence proche de 0.

| Paramètre               | Valeur                                                                                                             |
|-------------------------|--------------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `API - Prod - Pic d'auth refusées`                                                                                 |
| **Type**                | Elasticsearch query rule (ES\|QL)                                                                                  |
| **Requête ES\|QL**      | voir ci-dessous — l'alerte part dès qu'elle renvoie une ligne                                                      |
| **Fenêtre**             | 8 jours (la requête filtre elle-même les 10 dernières minutes et la référence)                                     |
| **Fréquence**           | 5 min                                                                                                              |
| **Sévérité**            | Critical                                                                                                           |
| **Throttle**            | `On custom action intervals` / `Run every 1 hour` / `Run when: Query matched` (onglet Actions → Settings)          |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production** — message dans le bloc de la règle                                      |
| **Related dashboards**  | dans la règle (onglet Related dashboards), mêmes dashboards que le message |
| **Investigation guide** | dans la règle (mêmes étapes que le message) ; runbook : [runbook d'investigation](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md) |

**Requête ES|QL** :
```
FROM logs-prod-default
| WHERE event.action == "auth_failed"
| EVAL recent = @timestamp >= NOW() - 10 minutes,
       meme_heure = @timestamp < NOW() - 1 day
                AND DATE_EXTRACT("HOUR_OF_DAY", @timestamp) == DATE_EXTRACT("HOUR_OF_DAY", NOW())
| STATS refus = COUNT(*) WHERE recent, historique = COUNT(*) WHERE meme_heure
| EVAL reference = ROUND(historique / 42.0, 1)
| WHERE refus >= 20 AND refus > 3 * reference
```

**Calibrage** (7 jours, par tranche de 10 min) :
```
FROM logs-prod-default
| WHERE @timestamp >= NOW() - 7 days AND event.action == "auth_failed"
| STATS n = COUNT(*) BY tranche = BUCKET(@timestamp, 10 minutes)
| EVAL heure = DATE_EXTRACT("HOUR_OF_DAY", tranche)
| STATS moyenne = AVG(n), max = MAX(n) BY heure
| SORT heure
```

**Message et étapes « À vérifier »** : dans le bloc de la règle de [`rules/1-rules-applicatives.console`](rules/1-rules-applicatives.console), qui fait foi ; son Investigation guide reprend les mêmes étapes.

### A6 — Erreurs base de données (Critical)

Compte les erreurs Sequelize (`error.type` `Sequelize*`) de tous les logs de
prod : connexion perdue, pool de connexions saturé
(`SequelizeConnectionAcquireTimeoutError`), contrainte violée. Remplace
« 🏠 API - erreurs DB », cassée : 4 tranches de 5 min au-dessus de son seuil en
30 jours, aucune alerte.

| Paramètre               | Valeur                                                                                                             |
|-------------------------|--------------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `API - Prod - Erreurs base de données`                                                                             |
| **Type**                | Elasticsearch query rule (ES\|QL), `groupBy: all`                                                                 |
| **Requête ES\|QL**      | voir ci-dessous — l'alerte part dès qu'elle renvoie une ligne (une par service)                                    |
| **Fenêtre**             | 5 min                                                                                                              |
| **Fréquence**           | 1 min                                                                                                              |
| **Sévérité**            | Critical                                                                                                           |
| **Throttle**            | `On custom action intervals` / `Run every 1 hour` / `Run when: Query matched` (onglet Actions → Settings)          |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production**, et Workflow `tchap-alerte-a6` — messages dans le bloc de la règle |
| **Related dashboards**  | dans la règle (onglet Related dashboards), mêmes dashboards que le message |
| **Investigation guide** | dans la règle (mêmes étapes que le message) ; runbook : [runbook d'investigation](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md) |

**Requête ES|QL** :
```
FROM logs-prod-default
| WHERE error.type LIKE "Sequelize*"
| EVAL message = SUBSTRING(error.message, 1, 120)
| STATS erreurs = COUNT(*), types = VALUES(error.type), exemples = VALUES(message) BY service = service.name
| WHERE erreurs > 20
| EVAL types = MV_CONCAT(types, ", "), exemples = MV_CONCAT(MV_SLICE(exemples, 0, 1), " / ")
```

**Calibrage** (2026-10-20, 30 jours, par tranche de 5 min) : max = 345, 3
tranches au-dessus de 20 (3 heures distinctes), toutes de vrais incidents de
connexion à la base.
```
FROM logs-prod-default
| WHERE @timestamp >= NOW() - 30 days AND error.type LIKE "Sequelize*"
| STATS n = COUNT(*) BY service.name, tranche = BUCKET(@timestamp, 5 minutes)
| STATS p99 = PERCENTILE(n, 99), max = MAX(n), au_dessus = COUNT(*) WHERE n > 20 BY service.name
```

**Message et étapes « À vérifier »** : dans le bloc de la règle de [`rules/1-rules-applicatives.console`](rules/1-rules-applicatives.console), qui fait foi ; son Investigation guide reprend les mêmes étapes. La règle est **nouvelle** : la créer avec `POST` (cf. l'en-tête de son bloc).

## Événements Scalingo — ce qui arrive aux apps

Des **Elasticsearch query rules (KQL)** sur les événements des notifiers
Scalingo, collectés dans `logs-alertes-scalingo-<env>-default` (cf.
[collecte des événements externes](../collecte/evenements-externes/README.md)).
Elles remplacent le fil d'activité que les notifiers `Mattermost*` publiaient
directement : **une règle par environnement**, qui liste chaque événement sur
une ligne, préfixée de sa gravité :

| Ligne en prod | Ligne en staging / perf | Événements |
|---|---|---|
| 🚨 incident | ⚠️ incident | crash, crash répété, redémarrage (quelle que soit la raison), arrêt |
| ⚠️ incident | ⚠️ incident | seuil de ressource dépassé |
| ℹ️ infra | ℹ️ infra | tout le reste, par défaut : déploiement, scaling, variables, retour sous le seuil… |

Les niveaux reprennent ceux des anciennes règles X1 à X3. Le titre du message
ne porte pas de gravité : un même message peut lister des lignes de niveaux
différents.

Exemple : `🚨 pass-emploi-api-prod : app_crashed (oom) sur web, par scalingo-platform`.

Les apps de la stack d'observabilité (`pass-emploi-logstash`,
`pass-emploi-logstash-process`, `pass-emploi-elastic-agent`,
`pass-emploi-heartbeat`, quel que soit l'environnement) sont exclues : leurs
événements vont aux règles 6a / 6b des
[alertes de la stack](alertes-stack-observabilite.md). Une nouvelle app est
couverte d'office, sans toucher aux règles.

Chaque exécution ne compte que les documents arrivés depuis la précédente
(`excludeHitsFromPreviousRun`) : un événement = une notification, sans
throttle.

**Création** : rejouer [`rules/1-rules-applicatives.console`](rules/1-rules-applicatives.console),
après les sessions Discover de [`discovers/evenements-externes/`](discovers/evenements-externes/).

### A4a — Événements Scalingo des apps applicatives, prod

| Paramètre               | Valeur |
|-------------------------|--------|
| **Rule name**           | `Scalingo - Prod - Événements des apps applicatives` |
| **Type**                | Elasticsearch query rule (KQL), data view `logs-alertes-scalingo-prod-default` |
| **Requête**             | `not service.name : ("pass-emploi-logstash" or "pass-emploi-logstash-process" or "pass-emploi-elastic-agent" or "pass-emploi-heartbeat")` |
| **Fenêtre / fréquence** | 5 min / 1 min |
| **Actions**             | Mattermost-monitoring-production ; Tchap via le Workflow `tchap-monitoring-production` |
| **Related dashboards**  | dans la règle (onglet Related dashboards), mêmes dashboards que le message |

**À vérifier** :
1. Le Discover **[Pass Emploi] Alertes externes de Prod - Événements Scalingo**,
   onglet « Incidents » ou « Infra » : l'événement, sa raison et son auteur.
2. Pour un incident, l'impact sur les utilisateurs : le dashboard
   **[Pass Emploi] Diagnostic d'erreurs - Entrée**, puis le Discover
   **[Pass Emploi] Logs de Prod - Erreurs serveur 5xx**.
3. L'activité de l'app (onglet Activity) dans le **[Scalingo] Dashboard des apps**.

### A4b — Événements Scalingo des apps applicatives, staging / perf

| Paramètre               | Valeur |
|-------------------------|--------|
| **Rule name**           | `Scalingo - Hors-Prod - Événements des apps applicatives` |
| **Type**                | Elasticsearch query rule (KQL), data view `logs-alertes-scalingo-staging-default,logs-alertes-scalingo-perf-default` |
| **Requête**             | celle d'A4a |
| **Fenêtre / fréquence** | 10 min / 5 min |
| **Actions**             | Mattermost-monitoring-staging ; Tchap via le Workflow `tchap-monitoring-staging` |
| **Related dashboards**  | dans la règle (onglet Related dashboards), mêmes dashboards que le message |

**À vérifier** :
1. Le Discover **[Pass Emploi] Alertes externes Hors-Prod - Événements Scalingo**,
   onglet « Incidents » ou « Infra » : l'événement, sa raison et son auteur.
2. L'activité de l'app (onglet Activity) dans le **[Scalingo] Dashboard des apps**.

### Sortir l'infra des salons de monitoring

Si l'équipe veut isoler les lignes ℹ️ (déploiements…) dans des salons
`infra-{env}` : créer les salons Tchap `infra-production` et `infra-staging`,
copier un Workflow de salon en `tchap-infra-{env}.console`, puis, pour A4a, A4b
(et 6a, 6b), ajouter `and labels.categorie : "incident"` à la requête et
dupliquer la règle avec `labels.categorie : "infra"` vers `tchap-infra-{env}`.
Aucun changement de pipeline ni de données ; réversible.

## Jobs — un job de l'api a échoué

Des **Elasticsearch query rules (KQL)** sur les logs de l'api
(`logs-<env>-default`) : `job_crashed` (le handler a levé une exception) et
`job_handler_not_found`, posés par le worker. Elles notifient les canaux
Mattermost des jobs (`jobs-production`, `jobs-staging`), où `SuiviJobService`
poste aujourd'hui le résultat des jobs ; une ligne par échec :
`❌ <job> : job_crashed — <message d'erreur>`. Pas encore de salon Tchap des
jobs : pas d'action Tchap.

**Version dégradée** (décision du 2026-10-19) : uniquement à partir des logs
existants, sans modifier l'api. Ce que les notifications de `SuiviJobService`
donnent et que A5a / A5b ne donnent pas :

| Notification actuelle | A5a / A5b | Perdu |
|---|---|---|
| Échec d'un job qui plante, avec sa stack | une ligne par `job_crashed`, la stack dans la session | le `resultat` détaillé et `nbErreurs` |
| Échec **rapporté** par le job (`succes: false`, sans exception) | — | tout : le worker logue alors `job_completed` en `success` |
| Résultat d'un job réussi | — | tout (pas de log du résultat métier) |
| Rapport quotidien des CRONs | onglet « Exécutions » des sessions : `job_completed` par `labels.job_type`, statut et durée | le nombre d'exécutions attendues (« a-t-il tourné le nombre de fois prévu ? ») |

**Rapport quotidien** : chaque jour à 9 h 30 (heure de Paris), un tableau de
tous les jobs des 24 dernières heures, dans `jobs-production` et
`jobs-staging` (Tchap seulement) : a-t-il tourné le nombre de fois prévu, sans
échec, ses exécutions attendues et réelles, sa durée moyenne, sa description.
Ce n'est pas une règle : une action Tchap ne sait pas viser une heure fixe,
c'est un Workflow planifié
([`rapport-jobs-prod.console`](workflows/tchap/rapport-jobs-prod.console)).
Les exécutions attendues viennent des expressions cron de pass-emploi-api,
lues par [`generer-workflows.py`](workflows/tchap/generer-workflows.py) : à
relancer quand les CRON changent. Les jobs hors CRON qui ont tourné y figurent
aussi, sans exécutions attendues. Seul manque `nbErreurs`, absent des logs.

Les notifications de `SuiviJobService` **restent actives** tant que la parité
n'est pas jugée suffisante.

**Création** : créer les connecteurs de
[`connecteurs/mattermost-jobs.console`](connecteurs/mattermost-jobs.console),
importer les sessions de [`discovers/applicatives/`](discovers/applicatives/)
(`discover-session-*-jobs.ndjson`), puis rejouer les blocs A5a / A5b de
[`rules/1-rules-applicatives.console`](rules/1-rules-applicatives.console)
(`POST` : ce sont de nouvelles règles).

### A5a — Jobs en échec, prod

| Paramètre               | Valeur |
|-------------------------|--------|
| **Rule name**           | `API - Prod - Jobs en échec` |
| **Type**                | Elasticsearch query rule (KQL), data view `logs-prod-default,logs-router-prod-default` |
| **Requête**             | `service.name : "pass-emploi-api" and event.action : ("job_crashed" or "job_handler_not_found")` |
| **Fenêtre / fréquence** | 5 min / 1 min |
| **Actions**             | Mattermost-jobs-production |

**À vérifier** :
1. Le Discover **[Pass Emploi] Logs de Prod - Jobs**, onglet « Jobs en échec » :
   le job, son erreur et sa stack.
2. Son onglet « Exécutions » : le job échoue-t-il à chaque exécution, ou a-t-il
   réussi depuis ?

### A5b — Jobs en échec, staging / perf

Comme A5a, sur `logs-staging-default,logs-perf-default`, toutes les 5 min
(fenêtre de 10 min), vers Mattermost-jobs-staging ; la ligne donne
l'environnement. Session : **[Pass Emploi] Logs Hors-Prod - Jobs**.
