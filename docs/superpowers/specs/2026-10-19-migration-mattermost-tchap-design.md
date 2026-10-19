# Réorganisation des alertes par périmètre et migration Mattermost → Tchap — design

> **Statut : proposé le 2026-10-19, en relecture.** Fait suite à
> [`2026-10-13-alertes-tchap-workflows-design.md`](2026-10-13-alertes-tchap-workflows-design.md)
> (Workflows Tchap, livrés) et le complète : tout ce qui poste dans Mattermost
> doit arriver dans Tchap avant le **décommissionnement de Mattermost, le
> 1er novembre 2026**.
>
> Artefact de travail : il sert de liste de contrôle jusqu'au 1er novembre. La
> doc de référence reste celle des périmètres (`alertes-*.md`) et de la collecte.

## 1. Problème

1. **Deux logiques de rangement se mélangent.** Les alertes X1 à X5 sont
   rangées par **source** (événements venus de l'extérieur d'Elastic : notifiers
   Scalingo, CVE GitHub), le reste de la supervision par **périmètre**
   (applicatif, stack d'observabilité). Conséquences constatées : X1 parle à la
   fois de l'api et de Logstash (étape « impact pour une app Logstash » hors
   sujet sur un redémarrage de l'api), l'alerte 6 fait doublon, X2 ne concerne
   en fait que Logstash.
2. **Mattermost disparaît le 1er novembre** et plusieurs sources y postent
   encore directement (inventaire §3), dont certaines hors Kibana.

## 2. Décisions

| #  | Décision | Raison |
|----|----------|--------|
| D1 | **Séparer la collecte des alertes.** La chaîne technique (data streams `logs-alertes-*`, pipelines, accès des émetteurs, failure store, notifiers Scalingo, envoi de `security-alerts.yml`) est documentée dans `collecte/evenements-externes/`. Les règles rejoignent leur périmètre | Une règle se range selon ce qu'elle surveille, pas selon le chemin de ses données |
| D2 | **Les numéros X disparaissent.** Trois familles : applicative (`alertes-applicatives.md`), sécurité (`alertes-securite.md`, nouveau), stack d'observabilité (`alertes-stack-observabilite.md`) | Choix de l'utilisateur ; une famille = un fichier de doc et un fichier de règles |
| D3 | **Convention `{n}a` = prod, `{n}b` = staging/perf** | Convention déjà en place (3a/3b, 9a/9b…) |
| D4 | **Une règle Scalingo par périmètre et par environnement**, qui liste tous les événements de ses apps (crash, arrêt, seuil, déploiement, variable…) | Un notifier Mattermost actuel est déjà un flux unique par app ; une règle par type d'événement serait inmaintenable |
| D5 | **Le pipeline classe chaque événement** : `labels.categorie` (`incident` ou `infra`) et un émoji en tête de `message`, à partir d'**une seule table** | La gravité se lit par ligne dans une règle unique ; sortir l'infra des salons de monitoring plus tard ne touche que des requêtes (§6) |
| D6 | **Aucune régression** : tout ce que l'équipe reçoit aujourd'hui dans Mattermost arrive dans Tchap | Demande de l'utilisateur |
| D7 | **Jobs : les logs ECS remplacent les envois Mattermost du code**, puis des règles les publient | Plus d'appel Mattermost dans l'api ; même contenu qu'aujourd'hui |
| D8 | **Ordre : réorganisation d'abord**, puis migration vers Tchap | Choix de l'utilisateur |

## 3. Inventaire de ce qui poste dans Mattermost (relevé le 2026-10-19)

| #  | Source | Où elle poste | Cible | État |
|----|--------|---------------|-------|------|
| 1  | Kibana Rules applicatives : S1 à S3, A1 à A3 (`1-rules-applicatives`) | `#monitoring-production` | mêmes règles + action Tchap `monitoring-production` | 🔲 §7 |
| 2  | Kibana Rules de la stack : 1 à 5, 7 à 10 (`2-rules-stack-observabilite`) | `#o11y-production`, `#o11y-staging` | mêmes règles + actions Tchap `o11y-*` | 🔲 §7 |
| 3  | Notifiers Scalingo « Mattermost monitoring production » : api, connect, metabase (41 à 45 événements sélectionnés d'après la CLI), web et heartbeat (tous) | `#monitoring-production` | **A4a** (apps applicatives), **6a** (heartbeat, logstash) | 🔲 §4 |
| 4  | Notifiers Scalingo « Mattermost monitoring staging » / « Mattermost » : api (déploiement, redémarrage, crash, arrêt), web et keycloak (déploiement), connect (tous) | canal(aux) staging | **A4b** | 🔲 §4 |
| 5  | Notifiers Scalingo « Mattermost monitoring o11y production / staging » = **alerte 6** : logstash, logstash-process, heartbeat (prod), logstash, logstash-process (perf) | `#o11y-production`, `#o11y-staging` | **6a**, **6b** | 🔲 §4 |
| 6  | Alertes de métriques Scalingo (seuils RAM/CPU) : logstash-prod (2), logstash-perf (1) | via les notifiers des lignes 3 et 5 | **6a**, **6b** (catégorie `incident`) | 🔲 §4 |
| 7  | `security-alerts.yml` (GitHub Actions, workflow réutilisable des repos api, web, connect, app) | `#monitoring-production` | **V1** | 🔲 §4 |
| 8  | AutoOps : alertes 11 (disque) et 12 (indexation) | `#o11y-production` | connecteur AutoOps en `POST` direct vers le salon Tchap `o11y-production` (ADR-004) | 🔲 attend le bot |
| 9  | `SuiviJobService` (pass-emploi-api) : résultat de chaque job notifiable (succès compris), stack d'erreur, rapport quotidien des CRONs | `MATTERMOST_JOBS_WEBHOOK_URL` | logs ECS + règles applicatives (§5) | 🔲 §5 |
| 10 | *(nouveau)* failure store des événements externes | — | **14** (stack) | 🔲 §4 |
| —  | Notifier « Dashboard Pass Emploi » sur `api-prod` → `pass-emploi-dashboard.osc-secnum-fr1.scalingo.io` (app absente du compte, HTTP 503, citée par aucun repo) | **pas Mattermost** | hors périmètre : à supprimer après confirmation de l'équipe | ❓ |

Points à confirmer avant implémentation :
- **Nombre d'événements des notifiers de prod** (ligne 3) : la CLI Scalingo en
  liste 41 à 45, l'utilisateur en voit au plus 5 dans le dashboard. Les
  notifiers Elasticsearch reprennent **exactement** la sélection de chaque
  notifier Mattermost, après vérification dans le dashboard.
- **Connecteur Kibana vers le canal Mattermost staging** de A4b : seuls
  `Mattermost-monitoring-production`, `-o11y-production` et `-o11y-staging`
  existent dans Kibana. À créer pour la période de transition, ou A4b poste
  dans `#o11y-staging` jusqu'au 1er novembre.

## 4. Règles issues des événements Scalingo et GitHub

### 4.1 Les règles

| Règle | Ex | Famille / fichier | Données | Apps | Mattermost (transition) | Tchap |
|-------|----|-------------------|---------|------|-------------------------|-------|
| **A4a** Événements Scalingo — prod | X1 (id `1b97f0e0…`) | applicative / `1-rules-applicatives` | `logs-alertes-scalingo-prod-default` | api, web, connect, metabase | `#monitoring-production` | `monitoring-production` |
| **A4b** Événements Scalingo — hors prod | X3 (id `07c9c5d7…`) | applicative / `1-rules-applicatives` | `logs-alertes-scalingo-{staging,perf}-default` | api, web, connect, keycloak | canal staging (cf. §3) | `monitoring-staging` |
| **6a** Événements Scalingo de la stack — prod | X2 (id `c16f2ab5…`) | stack / `2-rules-stack-observabilite` | `logs-alertes-scalingo-prod-default` | logstash, logstash-process, elastic-agent, heartbeat | `#o11y-production` | `o11y-production` |
| **6b** Événements Scalingo de la stack — hors prod | nouvelle | stack / `2-rules-stack-observabilite` | `logs-alertes-scalingo-{staging,perf}-default` | idem | `#o11y-staging` | `o11y-staging` |
| **V1** CVE high ou critical ouverte | X4 (id `67846c2c…`) | sécurité / `3-rules-securite` (nouveau) | `logs-alertes-github-default` | — | `#monitoring-production` | `monitoring-production` |
| **14** Événement externe rejeté | X5 (id `ae398f47…`) | stack / `2-rules-stack-observabilite` | les 4 `::failures` | — | `#o11y-production` | `o11y-production` |

- **Périmètre par app** : la requête filtre `service.name`. Stack =
  `pass-emploi-logstash`, `pass-emploi-logstash-process`,
  `pass-emploi-elastic-agent`, `pass-emploi-heartbeat` ; applicative = tout le
  reste (`not service.name : (…stack…)`), pour qu'une nouvelle app soit
  couverte par défaut.
- **IDs conservés** : en prod, A4a, A4b, 6a, V1 et 14 se mettent à jour par
  `PUT` ; seule 6b est créée.
- `rules/3-rules-alertes-externes.console` disparaît ; `rules/3-rules-securite.console`
  contient V1.
- **Sévérité de la règle** : `warning` pour A4a/A4b/6a/6b (le flux mêle
  incidents et infra, la gravité se lit par ligne, D5), `critical` pour V1,
  `warning` pour 14.
- **Format des messages et des onglets** : celui validé le 2026-10-15
  (« À vérifier » numérotés, sections « Dashboards » / « Discover sessions »
  cohérentes avec les étapes, un champ par section, un élément par ligne via
  `\n{{!` / `}}`, jamais de Discover non enregistré, Investigation guide et
  Related dashboards). Les étapes ne parlent que du périmètre de la règle.

### 4.2 Catégorie et émoji (pipeline `ingest-alertes-scalingo`)

Une table unique, dans le pipeline, donne pour chaque `event.action` :

| `labels.categorie` | Événements | Émoji en tête de `message` |
|--------------------|------------|----------------------------|
| `incident` | `app_crashed`, `app_crashed_repeatedly`, `app_stopped`, `resource_threshold_exceeded` | 🚨 crash, arrêt ; ⚠️ seuil |
| `incident` | `app_restarted` dont `event.reason` n'est pas `user_restart` | ⚠️ |
| `infra` | `app_restarted` avec `user_restart`, `app_deployed`, `app_scaled`, `resource_threshold_recovered`, et tout autre type (`scalingo_<type>`) | ℹ️ |

Les types sans traitement dédié gardent la ligne générique
`<app> : <event.action>[, par <auteur>]`. Les lignes des types `infra`
fréquents (déploiement, variable, addon, collaborateur) sont enrichies **à la
première capture réelle** de leur payload, comme pour les types de crash.

### 4.3 Notifiers Scalingo vers Elasticsearch

Pour chaque app qui a aujourd'hui un notifier Mattermost (§3, lignes 3 à 6) :
un notifier webhook vers `logs-alertes-scalingo-<env>-default` (utilisateur
`alertes-scalingo`), avec **la même sélection d'événements** que le notifier
Mattermost. Les alertes de métriques Scalingo de Logstash sont rattachées à ce
notifier. Le notifier de test de `pass-emploi-logstash-perf` (« Elastic
monitoring o11y staging », actuellement en *Send all events*) est ramené à la
sélection de son notifier Mattermost.

### 4.4 Sessions Discover

Les 4 sessions existantes sont reprises. Les sessions « Événements Scalingo »
(prod, hors prod) passent de deux onglets par type (« Crashs, redémarrages et
arrêts », « Seuils de ressource ») à deux onglets par catégorie
(« Incidents », « Infra ») et sont citées par A4a/A4b comme par 6a/6b. Les
sessions d'impact déjà versionnées (5xx, DLQ, erreurs de traitement) sont
citées par la seule famille qu'elles concernent.

## 5. Jobs (`SuiviJobService`, pass-emploi-api)

> **À valider** : l'utilisateur a demandé de s'appuyer sur les logs existants ;
> ils ne suffisent pas pour atteindre la parité (ci-dessous). La proposition
> ajoute deux logs ECS dans l'api.

Aujourd'hui, `SuiviJobService` poste dans Mattermost : le résultat de chaque job
notifiable (`estNotifiable` : tout échec, et les succès hors liste
d'exclusion), sa stack d'erreur, et un rapport quotidien (exécutions attendues
et réelles, erreurs, échecs par CRON, job `MONITORER_JOBS`). Les logs ECS
actuels (`job_completed`, `job_crashed`) n'ont **ni le `resultat` détaillé, ni
`nbErreurs`, ni les exécutions attendues**.

- Dans l'api, chaque `envoyerMessageMattermost` est remplacé par un log ECS au
  niveau info, selon les [conventions](../../observabilite/format/logs/conventions.md) :
  `event.action: job_result_recorded` (type, succès, `nbErreurs`, durée,
  `resultat` aplati sous `labels.*`, erreur via `toEcsError`) et
  `event.action: jobs_report_computed` (une entrée par CRON : attendues,
  réelles, erreurs, échecs).
- Deux règles applicatives lisent `logs-prod-default` et publient ces logs dans
  `monitoring-production` : **A5** (résultat d'un job, avec `incident` si échec
  et `infra` sinon, même table que D5) et **A6** (rapport quotidien).
- `MATTERMOST_JOBS_WEBHOOK_URL` et l'appel HTTP disparaissent du code et de la
  configuration Scalingo de l'api.

## 6. Sortir l'infra des salons de monitoring (évolution prévue)

Si l'équipe demande d'isoler les événements `infra` (déploiements…) dans des
salons `infra-{env}` :
1. créer les salons Tchap `infra-production` et `infra-staging` ;
2. copier un Workflow de salon en `tchap-infra-{env}.console` ;
3. pour A4a, A4b, 6a, 6b (et A5) : ajouter `and labels.categorie : "incident"`
   à la requête, puis dupliquer la règle avec `labels.categorie : "infra"` vers
   `tchap-infra-{env}`.

Aucun changement de pipeline ni de données ; réversible.

## 7. Étapes jusqu'au 1er novembre

| # | Étape | Dépend de |
|---|-------|-----------|
| 1 | **Réorganisation** : collecte dans `collecte/evenements-externes/`, `alertes-securite.md`, A4a/A4b, 6a/6b, V1, 14 avec IDs conservés, pipeline (catégorie, émoji), sessions par catégorie ; suppression de `alertes-externes.md` (contenu réparti) et de `3-rules-alertes-externes.console` | — |
| 2 | Mise à jour en prod : `PUT` des 5 règles, création de 6b, pipeline, sessions | 1 |
| 3 | Notifiers Elasticsearch sur toutes les apps de §3 (même sélection que Mattermost) ; vérification en réel par catégorie | 2 |
| 4 | `security-alerts.yml` : envoi vers Elasticsearch en plus de Mattermost ; secret dans les 4 repos | 2 |
| 5 | Jobs : logs ECS dans l'api, règles A5 et A6 | — (parallèle) |
| 6 | Bot Tchap (boîte `bot-pass-emploi@francetravail.fr`, compte, jeton), test du `POST` sans `txnId` | boîte mail |
| 7 | Branchement Tchap : connecteur, `tchap-client`, Workflows de salon, actions `.workflows` sur **toutes** les règles (lignes 1, 2 de §3 et §4), connecteurs AutoOps | 6 |
| 8 | **1er novembre** : retrait des actions Mattermost des règles, des connecteurs `Mattermost-*` de Kibana, des notifiers Scalingo vers Mattermost, de l'envoi Mattermost de `security-alerts.yml`, des connecteurs Mattermost d'AutoOps | 7 |

## 8. Risques et points ouverts

- **Bot Tchap non disponible à temps** (étape 6) : les étapes 1 à 5 restent
  utiles (tout est dans Kibana) ; sans Tchap au 1er novembre, les alertes ne
  sont plus visibles que dans Kibana → Alerts.
- **Webhook Mattermost exposé** : l'URL du webhook entrant de
  `#monitoring-production` a été affichée en clair pendant l'inventaire du
  2026-10-19 ; la régénérer si l'on ne veut pas attendre le 1er novembre.
- **Événements Scalingo non capturés** (types de crash, déploiement, variable…) :
  leur nom et leur payload exacts sont à confirmer à la première occurrence ;
  `labels.scalingo_type` garde la valeur brute.
- **Heartbeat** : rangé dans la stack (6a) ; aucune autre règle de la stack ne
  le couvre aujourd'hui.
