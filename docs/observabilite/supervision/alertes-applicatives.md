# Alertes applicatives

Les alertes sur des pannes **visibles des utilisateurs et impactantes pour le
métier**, en deux couches :

- **alertes SLO** (S1 à S3) — la promesse de [sli-slo](sli-slo.md) est-elle
  menacée ? Déduites des SLO Kibana ;
- **alertes de diagnostic** (A1 à A3) — pourquoi : un partenaire qui tombe, des
  5xx qui s'accumulent, une vague de refus d'authentification.

Elles s'appuient sur les logs ECS (`event.action` / `event.outcome`, cf.
[format/logs/conventions](../format/logs/conventions.md)). Les pannes de la
chaîne de télémétrie elle-même sont dans
[alertes-stack-observabilite](alertes-stack-observabilite.md) : si elle est
aveugle (alerte 3 « silence »), ces alertes-ci ne peuvent pas se déclencher.

Toutes notifient via Mattermost (`#monitoring-production`).

## Récapitulatif

| #  | Signal                     | Index / source      | Condition                                             | Fréquence | Throttle | Sévérité    |
|----|----------------------------|---------------------|-------------------------------------------------------|-----------|----------|-------------|
| S1 | SLO disponibilité api      | SLO Kibana          | burn rate ≥ 6 par parcours critique                   | 1 min     | —        | 🚨 Critical |
| S2 | SLO latence api            | SLO Kibana          | burn rate ≥ 6 par parcours critique                   | 1 min     | —        | 🚨 Critical |
| S3 | SLO réussite login         | SLO Kibana          | burn rate ≥ 6 par mode d'authentification             | 1 min     | —        | 🚨 Critical |
| A1 | Pic d'échecs partenaire    | `logs-prod-default` | `external_api_call` `failure` > 25 / 5 min par client | 1 min     | 1h       | ⚠️Warning  |
| A2 | Erreurs serveur 5xx        | `logs-prod-default` | requêtes api en 5xx > 5 / 5 min                       | 1 min     | 1h       | 🚨 Critical |
| A3 | Pic d'auth refusées        | `logs-prod-default` | `auth_failed` > 3 × même heure sur 7 j, ≥ 20 / 10 min | 5 min     | 1h       | 🚨 Critical |

> **Prod uniquement** : en staging, ces signaux reflètent les tests en cours, pas
> une panne.
>
> **Seuils à calibrer** (A1 à A3) : ceux ci-dessous reprennent les intentions de départ
> (5 échecs/min, 1 erreur 5xx/min, 3 × la normale), pas une mesure. Avant
> d'activer une règle, lancer sa requête de calibrage dans Discover (mode
> ES|QL) et placer le seuil au-dessus du `max` observé sur 7 jours.
>
> **Aucun dashboard applicatif n'existe dans Kibana** : les messages renvoient
> vers la page du SLO, Discover et le [runbook d'investigation](../runbooks/investigation-incident.md).

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
- **S3** — SLO « Login — réussite jeune France Travail » et « Login — réussite des autres modes ».

**Création** : à l'enregistrement d'un SLO, Kibana propose de créer sa règle
(sinon **Observability → Alerts → Manage Rules → Create rule → SLO burn rate**).

| Paramètre               | Valeur                                                                                               |
|-------------------------|------------------------------------------------------------------------------------------------------|
| **Rule name**           | `SLO - Prod - <nom du SLO>`                                                                          |
| **Type**                | SLO burn rate                                                                                        |
| **SLO**                 | le SLO visé                                                                                          |
| **Fenêtres**            | valeurs par défaut de Kibana, cf. tableau ci-dessous                                                 |
| **Fréquence**           | 1 min                                                                                                |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production**, groupes `Critical` et `High` uniquement — voir body ci-dessous |
| **Related dashboards**  | —                                                                                                    |
| **Investigation guide** | Voir [runbook d'investigation](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md) |

| Groupe   | Fenêtre longue / courte | Burn rate | Sens : budget des 30 j épuisé en… | Notifié ? |
|----------|-------------------------|-----------|-----------------------------------|-----------|
| Critical | 1 h / 5 min             | 14,4      | ~2 jours                          | oui       |
| High     | 6 h / 30 min            | 6         | 5 jours                           | oui       |
| Medium   | 24 h / 2 h              | 3         | 10 jours                          | non — visible sur la page SLO |
| Low      | 72 h / 6 h              | 1         | 30 jours                          | non — visible sur la page SLO |

> **Faible trafic** : sur un parcours peu sollicité (la nuit, ou `authentification`
> hors heures de connexion), 1 échec sur 10 requêtes suffit à dépasser un burn
> rate de 14,4 sur 1 h. La règle n'a pas de volume minimum : surveiller la
> première semaine, et sortir du SLO un parcours trop bruyant plutôt que de
> relâcher l'objectif de tous.

**Body du webhook** :
```json
{
  "text": "🚨 **SLO menacé — prod** — {{context.reason}}",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "SLO", "value": "{{context.sloName}}", "short": true },
        { "title": "Parcours / mode", "value": "`{{context.sloInstanceId}}`", "short": true },
        { "title": "Burn rate (longue / courte)", "value": "{{context.longWindow.burnRate}} / {{context.shortWindow.burnRate}} (seuil {{context.burnRateThreshold}})", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "SLO", "value": "[Budget d'erreur et historique]({{context.viewInAppUrl}})" },
        { "title": "À vérifier", "value": "Alertes de diagnostic A1 à A3 en cours : partenaire en panne, 5xx, IDP" },
        { "title": "Runbook", "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)" }
      ]
    }
  ]
}
```

Les variables `context.*` sont celles de la règle SLO burn rate ; vérifier les
noms dans la liste proposée par le bouton d'ajout de variable de l'action.

## Alertes de diagnostic — pourquoi ça casse

Des **Elasticsearch query rules (ES|QL)**. Elles pointent une cause (partenaire,
5xx, IDP), pas le respect d'une promesse : couche diagnostic de
[sli-slo](sli-slo.md#principe--trois-usages-une-pyramide).

### A1 — Pic d'échecs partenaire (Warning)

`external_api_call` en `failure` compte les 4xx (échecs gérés, `log.level: info`)
comme les 5xx et pannes de transport (`error`) : un 401 isolé n'est pas un
problème, un volume soutenu l'est (cf. [conventions](../format/logs/conventions.md#doctrine--choisir-le-level-test-dactionabilité)).
La colonne `dont_crash` sépare les deux dans le message.

| Paramètre               | Valeur                                                                                                             |
|-------------------------|--------------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `API - Prod - Pic d'échecs partenaire`                                                                             |
| **Type**                | Elasticsearch query rule (ES\|QL)                                                                                  |
| **Requête ES\|QL**      | voir ci-dessous — l'alerte part dès qu'elle renvoie au moins une ligne (une par client partenaire)                 |
| **Fenêtre**             | 5 min                                                                                                              |
| **Fréquence**           | 1 min                                                                                                              |
| **Sévérité**            | Warning                                                                                                            |
| **Throttle**            | `On custom action intervals` / `Run every 1 hour` / `Run when: Query matched` (onglet Actions → Settings)          |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production** — voir body ci-dessous                                      |
| **Related dashboards**  | —                                                                                                                  |
| **Investigation guide** | Voir [runbook d'investigation](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md) |

**Requête ES|QL** :
```
FROM logs-prod-default
| WHERE event.action == "external_api_call" AND event.outcome == "failure"
| STATS echecs = COUNT(*), dont_crash = COUNT(*) WHERE log.level == "error",
        statuts = VALUES(http.response.status_code)
  BY log.logger
| WHERE echecs > 25
```

**Calibrage** (7 jours, par tranche de 5 min) :
```
FROM logs-prod-default
| WHERE @timestamp >= NOW() - 7 days
    AND event.action == "external_api_call" AND event.outcome == "failure"
| STATS n = COUNT(*) BY log.logger, tranche = BUCKET(@timestamp, 5 minutes)
| STATS p99 = PERCENTILE(n, 99), max = MAX(n) BY log.logger
| SORT max DESC
```

**Body du webhook** :
```json
{
  "text": "⚠️ **Pic d'échecs partenaire — prod** — un client partenaire dépasse 25 échecs en 5 min.",
  "attachments": [
    {
      "color": "#f2c744",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Détail", "value": "{{context.message}}" },
        { "title": "À vérifier", "value": "Dans Discover : `event.action: external_api_call AND event.outcome: failure AND log.logger: \"<Client>\"` — `http.response.status_code`, `http.response.www_authenticate`, `error.message`" },
        { "title": "Runbook", "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)" }
      ]
    }
  ]
}
```

### A2 — Erreurs serveur 5xx (Critical)

| Paramètre               | Valeur                                                                                                             |
|-------------------------|--------------------------------------------------------------------------------------------------------------------|
| **Rule name**           | `API - Prod - Erreurs 5xx`                                                                                         |
| **Type**                | Elasticsearch query rule (ES\|QL)                                                                                  |
| **Requête ES\|QL**      | voir ci-dessous — l'alerte part dès qu'elle renvoie une ligne                                                      |
| **Fenêtre**             | 5 min                                                                                                              |
| **Fréquence**           | 1 min                                                                                                              |
| **Sévérité**            | Critical                                                                                                           |
| **Throttle**            | `On custom action intervals` / `Run every 1 hour` / `Run when: Query matched` (onglet Actions → Settings)          |
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production** — voir body ci-dessous                                      |
| **Related dashboards**  | —                                                                                                                  |
| **Investigation guide** | Voir [runbook d'investigation](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md) |

**Requête ES|QL** :
```
FROM logs-prod-default
| WHERE service.name == "pass-emploi-api" AND event.action == "request_failed"
| STATS erreurs_5xx = COUNT(*), statuts = VALUES(http.response.status_code),
        parcours = VALUES(labels.user_journey)
| WHERE erreurs_5xx > 5
```

**Calibrage** (7 jours, par tranche de 5 min) :
```
FROM logs-prod-default
| WHERE @timestamp >= NOW() - 7 days
    AND service.name == "pass-emploi-api" AND event.action == "request_failed"
| STATS n = COUNT(*) BY tranche = BUCKET(@timestamp, 5 minutes)
| STATS p99 = PERCENTILE(n, 99), max = MAX(n)
```

**Body du webhook** :
```json
{
  "text": "🚨 **Erreurs 5xx — prod** — plus de 5 requêtes en erreur serveur en 5 min.",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Détail", "value": "{{context.message}}" },
        { "title": "À vérifier", "value": "Dans Discover : `service.name: pass-emploi-api and event.action: request_failed` — `labels.user_journey`, `url.path`, `error.type`, puis `trace.id` pour remonter la requête" },
        { "title": "Runbook", "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)" }
      ]
    }
  ]
}
```

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
| **Action**              | Connecteur Kibana **Mattermost-monitoring-production** — voir body ci-dessous                                      |
| **Related dashboards**  | —                                                                                                                  |
| **Investigation guide** | Voir [runbook d'investigation](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md) |

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

**Body du webhook** :
```json
{
  "text": "🚨 **Pic d'authentifications refusées — prod** — plus de 3 × la normale sur 10 min : IDP ou Keycloak probablement en cause.",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        { "title": "Règle", "value": "`{{rule.name}}`", "short": true },
        { "title": "Déclenchée à", "value": "`{{date}}`", "short": true },
        { "title": "Détail", "value": "{{context.message}}" },
        { "title": "À vérifier", "value": "Dans Discover : `event.action: auth_failed` — répartition par `user.structure` et `error.message` (un seul IDP touché ou tous ?)" },
        { "title": "Runbook", "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)" }
      ]
    }
  ]
}
```
