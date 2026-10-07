# Objets Kibana versionnés

Tout ce qui est configuré dans Kibana pour la supervision est versionné ici, et
se rejoue à l'identique sur un cluster vide. Deux formats :

- **`.ndjson`** : export de *Saved objects* (dashboards, sessions Discover, avec
  leurs data views et tags), importé par la page *Saved objects* ;
- **`.console`** : requêtes Dev Tools (SLO, règles d'alerte, ILM et templates).

Les identifiants sont conservés à l'import : les messages Mattermost des alertes
et cette doc pointent vers les objets par leur id.

## Dashboards

| Dashboard | Fichier | Usage |
|---|---|---|
| [[Pass Emploi] SLO de PROD](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14) | [`dashboards/dashboard-slo.ndjson`](dashboards/dashboard-slo.ndjson) | statut des SLO, cf. [routine](../routine-surveillance.md#promesses-utilisateurs-slo) |
| [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d) | [`dashboards/dashboard-supervision-stack-observabilite.ndjson`](dashboards/dashboard-supervision-stack-observabilite.ndjson) | chaîne de logs, cf. [routine](../routine-surveillance.md#santé-de-la-stack-dobservabilité) |

## Sessions Discover

Chaque session est le lien « À vérifier » d'une alerte : elle ouvre directement
les logs à examiner.

| Session | Fichier | Alerte | Contenu |
|---|---|---|---|
| [[Pass Emploi] Logs de PROD - Failure partenaires](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/a28897ac-ecb1-4b4f-b413-0340c7241293) | [`discovers/applicatives/discover-session-prod-erreurs-partenaires.ndjson`](discovers/applicatives/discover-session-prod-erreurs-partenaires.ndjson) | A1 | `external_api_call` en échec, un onglet par famille de clients : Milo, France Travail, `*ApiClient`, OIDC |
| [[Pass Emploi] Logs de Prod - Erreurs serveur 5xx](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/d076df50-1625-443b-978c-1aa9a1288e73) | [`discovers/applicatives/discover-session-prod-erreurs-5xx.ndjson`](discovers/applicatives/discover-session-prod-erreurs-5xx.ndjson) | A2 | `request_failed` de l'api, motif et `trace.id` |
| [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8) | [`discovers/applicatives/discover-session-prod-erreurs-authentification.ndjson`](discovers/applicatives/discover-session-prod-erreurs-authentification.ndjson) | A3 | `auth_failed` ; répartition par IDP dans l'onglet *Field statistics* |
| [[Pass Emploi] Logs de Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/97e2d85f-7bd2-49df-86b3-2ffc290bbe69) | [`discovers/stack-observabilite/discover-session-prod-logstash-process-rejet-dlq.ndjson`](discovers/stack-observabilite/discover-session-prod-logstash-process-rejet-dlq.ndjson) | 1a | logs non indexés pour une cause non détectée par Logstash (DLQ), prod |
| [[Pass Emploi] Logs Hors-Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/e5bec6b4-0ae3-47b1-8bb5-2e9bf77493a4) | [`discovers/stack-observabilite/discover-session-hors-prod-logstash-process-rejet-dlq.ndjson`](discovers/stack-observabilite/discover-session-hors-prod-logstash-process-rejet-dlq.ndjson) | 1b | idem, staging et perf |
| [[Pass Emploi] Logs de PROD - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/f10de9e3-0fdd-4761-9d44-bacc96504e17) | [`discovers/stack-observabilite/discover-session-prod-logstash-process-traitement-failures.ndjson`](discovers/stack-observabilite/discover-session-prod-logstash-process-traitement-failures.ndjson) | 2a | logs non indexés à cause d'une erreur de transformation détectée par Logstash, prod |
| [[Pass Emploi] Logs Hors-Prod - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/716175ed-b2a0-4fe1-8f9d-1892d04dbe92) | [`discovers/stack-observabilite/discover-session-hors-prod-logstash-process-traitement-failures.ndjson`](discovers/stack-observabilite/discover-session-hors-prod-logstash-process-traitement-failures.ndjson) | 2b | idem, staging et perf |
| [[Pass Emploi] Historique ILM - Index hors rétention](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/3f3c69ef-e515-4be4-b679-eff837c92ecb) | [`discovers/stack-observabilite/discover-session-elasticsearch-index-hors-retention-ilm.ndjson`](discovers/stack-observabilite/discover-session-elasticsearch-index-hors-retention-ilm.ndjson) | 10 | index de nos flux en échec ILM ou sur une policy par défaut, d'après l'historique ILM |

## Requêtes Dev Tools

| Fichier | Contenu |
|---|---|
| [`slo/1-slos.console`](slo/1-slos.console) | les SLO, cf. [sli-slo](sli-slo.md) |
| [`rules/1-rules-applicatives.console`](rules/1-rules-applicatives.console) | règles S2, S3 et A1 à A3, cf. [alertes applicatives](alertes-applicatives.md) |
| [`rules/2-rules-stack-observabilite.console`](rules/2-rules-stack-observabilite.console) | règles 1 à 5 et 7 à 9, cf. [alertes de la stack](alertes-stack-observabilite.md) |

Les rétentions (ILM, templates) sont dans [`stockage/`](../stockage/README.md#import--ordre-et-portée).

## Importer

### Dashboards et sessions Discover (`.ndjson`)

1. Ouvrir la page **Saved objects** depuis la barre de recherche (`Ctrl + /`).
2. **Import**, choisir le fichier `.ndjson`.
3. Garder la détection des objets existants et choisir l'**écrasement
   automatique** des conflits. Ne pas choisir la création d'objets avec de
   nouveaux identifiants : les liens des alertes ne pointeraient plus dessus.
4. Importer.

Chaque fichier embarque ses data views et ses tags : l'ordre d'import est libre.
Écraser une data view partagée (par exemple `logs-prod-default,logs-router-prod-default`)
remplace aussi ses réglages d'affichage, sans effet sur les données.

### SLO et règles (`.console`)

Copier le fichier dans Dev Tools et exécuter les requêtes, dans l'ordre :
`slo/1-slos.console`, puis `rules/1-rules-applicatives.console`, puis
`rules/2-rules-stack-observabilite.console`. Sur un cluster vide, l'en-tête de
chaque fichier indique comment transformer les `PUT` en `POST` de création.

## Modifier un objet

Modifier dans Kibana, puis réexporter par-dessus le fichier versionné :

- **dashboard ou session Discover** : page *Saved objects*, sélectionner l'objet,
  **Export** avec *Include related objects* ;
- **règle d'alerte** : modifier d'abord le tableau et le body dans
  `alertes-*.md`, puis le `PUT` du `.console` correspondant, et le rejouer.
