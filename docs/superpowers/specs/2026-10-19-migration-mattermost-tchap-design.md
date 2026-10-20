# Réorganisation des alertes par périmètre et migration Mattermost → Tchap — design

> **Statut : validé le 2026-10-19 ; Plan 1 (réorganisation) implémenté le
> 2026-10-19** ([plan](../plans/2026-10-19-plan-1-reorganisation-par-perimetre.md), écarts en §13). Fait suite à
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
| D7 | **Jobs : version dégradée** à partir des logs existants (règle sur les échecs, dashboard des exécutions) ; la parité complète est une suite (§10) | Décision de l'utilisateur : pas de code applicatif dans ce chantier |
| D8 | **Ordre : réorganisation d'abord**, puis migration vers Tchap | Choix de l'utilisateur |
| D9 | **Les étapes d'investigation de toutes les règles sont revues** (« À vérifier », « Dashboards », « Discover sessions », Investigation guide) selon les principes du §7 | Les étapes actuelles font divaguer l'analyse : branches hors périmètre, sessions Discover qui ne montrent pas l'erreur d'origine |

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
| 9  | `SuiviJobService` (pass-emploi-api) : résultat de chaque job notifiable (succès compris), stack d'erreur, rapport quotidien des CRONs | `MATTERMOST_JOBS_WEBHOOK_URL` | version dégradée : règle A5 + dashboard (§5) ; envoi Mattermost conservé | 🔲 §5 |
| 11 | Kibana Rules **non versionnées**, actives, vers `Mattermost-monitoring-production` : APM (7 : error count front/auth/back, Connect threshold, Connect transactions failed, failed transaction rate auth/back), Uptime (4 : Check TLS, statut connect/back/web prod) | `#monitoring-production` | versionnées puis migrées comme les autres (format, Investigation guide, action Tchap) | 🔲 §7 |
| 12 | Kibana Rules **non versionnées** « 🏠 / 🔌 » (créées le 2026-08-24), vivantes : 🏠 API - erreurs DB, 🔌 Partenaires - 429 rate-limit, - 5xx, - Timeouts | `#monitoring-production` | versionnées dans les alertes applicatives (A6 à A9), migrées | 🔲 §7 |
| 10 | *(nouveau)* failure store des événements externes | — | **14** (stack) | 🔲 §4 |
| —  | Notifier « Dashboard Pass Emploi » sur `api-prod` → `pass-emploi-dashboard.osc-secnum-fr1.scalingo.io` (app absente du compte, HTTP 503, citée par aucun repo) | **pas Mattermost** | hors périmètre : à supprimer après confirmation de l'équipe | ❓ |

Points à confirmer avant implémentation :
- **Nombre d'événements des notifiers de prod** (ligne 3) : la CLI Scalingo en
  liste 41 à 45, l'utilisateur en voit au plus 5 dans le dashboard. Les
  notifiers Elasticsearch reprennent **exactement** la sélection de chaque
  notifier Mattermost, après vérification dans le dashboard.
- **Connecteur Kibana du canal Mattermost de staging** (action Mattermost de
  A4b pendant la transition) : ✅ `Mattermost-monitoring-staging`
  (`4cb10f00-22d9-4cf0-bda1-e288c4abb339`), vérifié en prod le 2026-10-19 (nom,
  type `.webhook`, URL du webhook du canal staging).

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

Pour chaque app qui a aujourd'hui un notifier `Mattermost*` (§3, lignes 3 à 6) :
un notifier webhook vers `logs-alertes-scalingo-<env>-default` (utilisateur
`alertes-scalingo`), avec **la même sélection d'événements** que le notifier
Mattermost, et **le même nom au préfixe près** (`Mattermost monitoring
production` → `Elastic monitoring production`, `Mattermost monitoring o11y
staging` → `Elastic monitoring o11y staging`…). Une app qui a deux notifiers
`Mattermost*` (logstash-prod, heartbeat-prod) n'a qu'**un** notifier Elastic,
`Elastic monitoring o11y production`, avec l'union de leurs événements : deux
notifiers écriraient deux fois les événements communs. Les alertes de métriques Scalingo de Logstash sont rattachées à ce
notifier. Le notifier de test de `pass-emploi-logstash-perf` (« Elastic
monitoring o11y staging », actuellement en *Send all events*) est ramené à la
sélection de son notifier Mattermost.

### 4.4 Sessions Discover

Les 4 sessions existantes sont reprises. Les sessions « Événements Scalingo »
(prod, hors prod) passent de deux onglets par type (« Crashs, redémarrages et
arrêts », « Seuils de ressource ») à deux onglets par catégorie
(« Incidents », « Infra ») et sont citées par A4a/A4b comme par 6a/6b. Les
sessions d'impact déjà versionnées (5xx, DLQ, erreurs de traitement) ne sont
citées que si elles passent la revue du §7.

## 5. Jobs (`SuiviJobService`, pass-emploi-api) : version dégradée

**Décision du 2026-10-19 : version dégradée**, à partir des seuls logs existants,
sans modifier le code de l'api.

Aujourd'hui, `SuiviJobService` poste dans Mattermost : le résultat de chaque job
notifiable (`estNotifiable` : tout échec, et les succès hors liste
d'exclusion), sa stack d'erreur, et un rapport quotidien (exécutions attendues
et réelles, erreurs, échecs par CRON, job `MONITORER_JOBS`).

| Notification actuelle | Version dégradée (logs existants) | Perdu |
|---|---|---|
| Résultat d'un job en échec, avec sa stack | **A5a / A5b** : règle sur `job_crashed` et `job_handler_not_found` (l'erreur y est ; `job_completed` en `failure` le double) | le `resultat` détaillé et `nbErreurs` |
| Échec **rapporté** par le job (`succes: false`, sans exception) | — | tout : le worker logue `job_completed` en `success` dans ce cas (constaté dans `worker.service.db.ts` le 2026-10-19) |
| Résultat d'un job réussi | — | tout (pas de log du résultat métier) |
| Rapport quotidien des CRONs | onglet « Exécutions » des sessions **[Pass Emploi] Logs de Prod / Hors-Prod - Jobs** (`job_completed` par `labels.job_type` : statut, durée), au lieu d'un dashboard | le nombre d'exécutions attendues, donc « a-t-il tourné le nombre de fois prévu » |

Les notifications Mattermost des jobs **restent actives** tant que la version
dégradée n'est pas validée ; leur retrait du code est une suite (§10).

## 6. Sortir l'infra des salons de monitoring (évolution prévue)

Si l'équipe demande d'isoler les événements `infra` (déploiements…) dans des
salons `infra-{env}` :
1. créer les salons Tchap `infra-production` et `infra-staging` ;
2. copier un Workflow de salon en `tchap-infra-{env}.console` ;
3. pour A4a, A4b, 6a, 6b (et A5) : ajouter `and labels.categorie : "incident"`
   à la requête, puis dupliquer la règle avec `labels.categorie : "infra"` vers
   `tchap-infra-{env}`.

Aucun changement de pipeline ni de données ; réversible.

## 7. Étapes d'investigation : principes et revue

Constat de l'équipe : les sessions Discover citées par les alertes sur les
erreurs 5xx ou par partenaire ne permettent pas de remonter, en un coup d'œil,
à l'erreur d'origine. Elle a créé un **dashboard d'investigation des
incidents** pour ça : `eb348ed9-3bc2-4204-a5c2-c31465731c74`, **non versionné
à ce jour**.

**Principes**, appliqués à chaque règle :
1. **Une étape répond à une question de diagnostic**, dans l'ordre où on la
   pose : qu'est-ce qui s'est passé (le fait) → pourquoi (l'erreur d'origine)
   → qu'est-ce que ça touche (l'impact). Trois étapes au plus.
2. **Une étape ne parle que du périmètre de la règle.** Pas de branche « pour
   une app d'une autre famille », pas de vérification « au cas où ».
3. **Le dashboard d'investigation d'abord** pour remonter à l'erreur d'origine
   d'un incident applicatif (5xx, partenaires, authentification) ; une session
   Discover seulement pour la liste exhaustive des documents, en dernier.
4. **Chaque lien cité est versionné** (dashboards et sessions dans
   `supervision/`), titré par son origine (`[Pass Emploi]`, `[Scalingo]`…), et
   repris à l'identique dans « Dashboards », « Discover sessions »,
   l'Investigation guide et Related dashboards.
5. **Les sessions Discover existantes restent citées**, après le dashboard :
   elles donnent la liste exhaustive des documents (décision du 2026-10-19).

**Revue** : toutes les règles (S1 à S3, A1 à A5, V1, 1 à 14, Tchap) passent
par ces principes. Pour chacune : la question de chaque étape, les objets
cités, ce qui est retiré. Les dashboards de diagnostic de l'équipe sont **versionnés**
(`supervision/dashboards/dashboard-diagnostic-erreurs.ndjson`, mis aux
conventions le 2026-10-19) et cités **en plus** des sessions existantes :

| Alerte | Dashboard cité en premier |
|---|---|
| A2 Erreurs serveur 5xx | [Pass Emploi] Diagnostic d'erreurs - Entrée, puis - Apps |
| A1 Pic d'échecs partenaire | [Pass Emploi] Diagnostic d'erreurs - Apps |
| A3 Pic d'authentifications refusées | [Pass Emploi] Diagnostic d'erreurs - Robots / scan |
| S1 à S3 (SLO) | [Pass Emploi] Diagnostic d'erreurs - Entrée |
| A4a Événements Scalingo prod | [Pass Emploi] Diagnostic d'erreurs - Entrée |

## 8. Étapes jusqu'au 1er novembre

| # | Étape | Dépend de |
|---|-------|-----------|
| 0 | ✅ Dashboards de diagnostic versionnés et mis aux conventions ; **réimport en prod** (écrasement des conflits) | — |
| 1 | ✅ (Plan 1, 2026-10-19, sauf la revue §7 des autres règles : Plan 2) **Réorganisation** : revue des étapes d'investigation (§7) de toutes les règles ; collecte dans `collecte/evenements-externes/`, `alertes-securite.md`, A4a/A4b, 6a/6b, V1, 14 avec IDs conservés, pipeline (catégorie, émoji), sessions par catégorie ; suppression de `alertes-externes.md` (contenu réparti) et de `3-rules-alertes-externes.console` | — |
| 2 | ✅ (2026-10-19, sans Tchap, cf. §10) Mise à jour en prod : `PUT` des 5 règles, création de 6b, pipeline, sessions ; `PUT` des Workflows de salon là où ils existent (filtre du bagotement, §13) | 1 |
| 3 | ✅ (2026-10-19, cf. §10 ; parité à vérifier en réel) Notifiers Elasticsearch sur toutes les apps de §3 (même sélection que Mattermost) ; vérification en réel par catégorie | 2 |
| 4 | ✅ (2026-10-19, testé sur api ; fusion des 3 branches en attente, cf. §10) `security-alerts.yml` : envoi vers Elasticsearch en plus de Mattermost ; secret dans les 4 repos | 2 |
| 5 | ✅ (2026-10-19, A5a / A5b en prod, cf. §10) Jobs, version dégradée : règle A5 et dashboard des exécutions | — (parallèle) |
| 6 | Bot Tchap (boîte `bot-pass-emploi@francetravail.fr`, compte, jeton), test du `POST` sans `txnId` | boîte mail |
| 7 | Branchement Tchap : connecteur, `tchap-client`, Workflows de salon, actions `.workflows` sur **toutes** les règles (lignes 1, 2 de §3 et §4), connecteurs AutoOps | 6 |
| 8 | **Bascule, app par app et règle par règle** : une fois la parité constatée (même contenu dans Kibana/Tchap que dans Mattermost), **désactiver** (jamais supprimer) le notifier Scalingo `Mattermost*` correspondant, puis retirer l'action Mattermost de la règle | 7 |
| 9 | **1er novembre** : les actions et connecteurs Mattermost restants de Kibana, l'envoi Mattermost de `security-alerts.yml` et les connecteurs Mattermost d'AutoOps sont retirés ; les notifiers Scalingo `Mattermost*` restent désactivés | 8 |

## 9. Règles de la période de migration (jusqu'au 1er novembre)

- **Aucune alerte n'est supprimée** tant que la parité n'est pas constatée :
  les anciennes sources (notifiers Scalingo `Mattermost*`, actions Mattermost)
  continuent pendant que les nouvelles règles sont validées, quitte à doubler
  les messages pendant quelques jours.
- **Les notifiers Scalingo `Mattermost*` sont désactivés, jamais supprimés**
  (retour arrière possible).
- **Seuls les connecteurs Tchap sont à créer** (connecteur `.http` « Tchap »
  dans Kibana, connecteurs Webhook Tchap dans AutoOps) ; les connecteurs
  Mattermost existent déjà.

## 10. Journal des actions en prod

**2026-10-19 : 11 règles désactivées** (aucune supprimée). Pour revenir en
arrière : `POST kbn:/api/alerting/rule/<id>/_enable`.

| Motif | Règle | ID |
|---|---|---|
| Wordpress : canal Mattermost sans abonné | Wordpress Status(Simple status alert) | `dbb84a10-987b-11ec-9757-c9700cd1bb4e` |
| Wordpress : canal Mattermost sans abonné | Wordpress Status(Simple status alert) | `d852ff00-987b-11ec-9757-c9700cd1bb4e` |
| SLO non versionnée, sans action | Réussite par user journey (perf) Burn Rate rule | `9a77c7bb-1b78-4804-b640-afd3482f2589` |
| morte : 0 document en 30 j, champ absent du mapping | 🏠 API - exceptions non gérées | `9413c659-479b-4dab-bc63-a65ea82f1773` |
| SLO non versionnée, sans action | Poc SLO avec user_journey (latence) Burn Rate rule | `3b5aebe6-9f51-4e65-a3ba-c538385a73b8` |
| Wordpress : canal Mattermost sans abonné | Wordpress Status(Simple status alert) | `d442f500-987b-11ec-9757-c9700cd1bb4e` |
| SLO non versionnée, sans action | Rapidité par user journey (prod) Burn Rate rule | `af2c642b-0571-4836-93b5-234892deae30` |
| SLO non versionnée, sans action | Réussite par user journey (prod) Burn Rate rule | `7e6e6779-9f39-4dbc-862c-f49153e9f7de` |
| morte : 0 document en 30 j, champ absent du mapping | 🏠 API - 5xx servis | `f0a7a4c0-6b0b-49bb-8d94-51475e8028f5` |
| SLO non versionnée, sans action | [Copy] Réussite par user journey (staging) Burn Rate rule | `4984db21-d13b-4dc8-9465-6d50292dd724` |
| SLO non versionnée, sans action | Rapidité par user journey (perf) Burn Rate rule | `233e7d24-4d8d-4679-808a-140facd94fcc` |

Hors migration, sans changement : les 10 règles « [Elastic Agent] … » de
l'intégration Elastic (déjà désactivées ; on n'y touche pas), et le connecteur
`Mattermost-monitoring-wordpress`, sans règle active.

**2026-10-19 : réorganisation déployée** (étape 2 de §8, sans Tchap : ni
Workflows ni connecteur Tchap n'existent encore en prod, l'action `.workflows`
est retirée des corps au rejeu ; elle viendra avec l'étape 7).

| Objet | Action | Résultat |
|---|---|---|
| Pipeline `ingest-alertes-scalingo` | `PUT` (catégorie, émoji) | 9 `_simulate` conformes |
| Sessions `bb62451a…` (prod), `33bed466…` (hors prod) | import avec écrasement | onglets « Incidents » / « Infra » |
| A4a `1b97f0e0…` (ex-X1), A4b `07c9c5d7…` (ex-X3), 6a `c16f2ab5…` (ex-X2), 14 `ae398f47…` (ex-X5), V1 `67846c2c…` (ex-X4) | `PUT` | actives, `ok` |
| 6b `5d1f7c2a…` | `POST` (création) | active, `ok` |

Retour arrière : rejouer en `PUT` les blocs de `rules/3-rules-alertes-externes.console`
au commit `f1757ec` (mêmes IDs) et supprimer 6b ; réimporter les sessions de ce
même commit. Le notifier « Elastic monitoring o11y staging » de
`pass-emploi-logstash-perf` envoie encore tous les événements : 6b les poste
tous dans `#o11y-staging` jusqu'à sa remise à la sélection du notifier
`Mattermost*` (étape 3).

**2026-10-19 : format Slack des événements de variables.** Un test sur
`pass-emploi-logstash-perf` (variable ajoutée puis retirée, conteneurs à 0) a
montré que le notifier webhook envoie ces événements au format Slack : ils
partaient au failure store (2 rejets signalés par la règle 14). Pipeline
`ingest-alertes-scalingo-format-slack` ajouté et déployé avec les 4 autres
pipelines de la collecte. Contre-test réel : variable ajoutée / retirée et
scaling web 0 → 1 → 0 → 4 événements indexés (2 au format Slack, 2 au format
brut), aucun rejet, 6b notifiée.

**2026-10-19 : notifiers Scalingo vers Elasticsearch** (étape 3 de §8). Un
notifier `webhook` par app qui a un notifier `Mattermost*` actif, même nom au
préfixe près, même sélection ; les `Mattermost*` restent actifs (doublon accepté,
à désactiver ensemble si l'équipe RUN est gênée). Aucune alerte de métriques
rattachée : rien de plus que l'existant.

| App | Notifier | Événements |
|---|---|---|
| api-prod, connect-prod, metabase-prod | Elastic monitoring production | ceux du `Mattermost*` (type `slack`) sauf 5 indisponibles en `webhook` : `app_alert_triggered`, `app_region_migration_started`, `project_created`, `project_deleted`, `project_edited` |
| web-prod | Elastic monitoring production | tous |
| logstash-prod, logstash-process-prod, heartbeat-prod | Elastic monitoring o11y production | `app_crashed_repeated`, `app_restarted`, `app_stopped` (heartbeat aligné sur Logstash, à la demande de l'équipe) |
| logstash-perf (mis à jour, n'envoie plus tout), logstash-process-perf | Elastic monitoring o11y staging | `app_crashed_repeated`, `app_restarted` |
| api-staging | Elastic monitoring staging | `app_crashed`, `app_crashed_repeated`, `app_deployed`, `app_restarted`, `app_stopped` |
| web-staging, keycloak-staging | Elastic monitoring staging | `app_deployed` |
| connect-staging | Elastic | tous |

`app_alert_triggered` (alertes de métriques Scalingo) n'existe pas en
`webhook` : sans conséquence, api-prod, connect-prod et metabase-prod n'ont
aucune alerte de métriques configurée (`scalingo alerts` vide, vérifié le
2026-10-19). Si l'on en crée une, la rattacher au notifier Elastic de l'app.

**2026-10-19 : gravité alignée sur X1 à X3 déployée** (§13) : `PUT` du pipeline
`ingest-alertes-scalingo` (10 `_simulate` conformes) et de A4a, A4b, 6a, 6b,
sans Tchap.

**2026-10-19 : `security-alerts.yml` vers Elasticsearch** (étape 4 de §8).
Workflow réutilisable : étape `_bulk` vers `logs-alertes-github-default` après
l'envoi Mattermost, active si l'appelant passe `elastic-url` (variable
`ELASTIC_URL`) et le secret `ELASTIC_ALERTES_GITHUB_API_KEY` (posés dans les 3
repos appelants : api, web, connect ; l'app mobile n'appelle pas ce workflow).
Appelants : branches `ci/security-alerts-elasticsearch`, épinglées sur le
commit `2fe40247` de la branche pass-emploi-tools (pas encore fusionnée, en
attente de relecture), avec `workflow_dispatch`. Test réel sur
pass-emploi-api : 4 CVE indexées, aucun rejet, V1 notifiée (1 action, 0
erreur). Reste : relecture et fusion des 3 branches dans `develop`, puis
réépinglage sur `master` après fusion de pass-emploi-tools.

**2026-10-19 : V1, lien vers les alertes Dependabot du repo** : `PUT` du
pipeline `ingest-alertes-github-default` (`labels.dependabot_url`) et de V1
(sans Tchap) ; guide à 3 liens fixes, message à un lien par CVE.

**2026-10-19 : jobs, prod** (étape 5) : connecteur `Mattermost-jobs-production`
(`cd0b8285…`, URL lue dans `MATTERMOST_JOBS_WEBHOOK_URL` de
pass-emploi-api-prod, jamais affichée), session **[Pass Emploi] Logs de Prod -
Jobs**, A5a (`POST`) : active, `ok`. **Staging non créé** : la variable
`MATTERMOST_JOBS_WEBHOOK_URL` de pass-emploi-api-staging vise
`pass-emploi-dashboard.osc-secnum-fr1.scalingo.io` (app absente, 503) ; ses 109
envois des 7 derniers jours ont échoué, le canal `jobs-staging` ne reçoit donc
rien de l'api de staging.

**2026-10-19, 20:19 UTC : jobs, staging corrigé.** `MATTERMOST_JOBS_WEBHOOK_URL`
de pass-emploi-api-staging remplacée par le webhook du canal `jobs-staging`
(fourni par l'équipe), redémarrage du seul conteneur `worker` (le `web` n'a pas
été touché). Connecteur `Mattermost-jobs-staging` (`3f71e705…`), session
**[Pass Emploi] Logs Hors-Prod - Jobs** et A5b (`POST`) créés : active, `ok`.
À vérifier : les envois de `SuiviJobService` en staging passent de 503 à 200
(`external_api_call`, `log.logger` SuiviJobService), au plus tard au crash
nocturne de `CHARGER_EVENEMENTS_ANALYTICS`. Même jour : celle de
pass-emploi-api-perf (mauvais copier-coller à la création de la perf, il n'y a
pas de canal `jobs-perf`) pointe aussi vers `jobs-staging` ; conteneurs à 0,
prise en compte au prochain démarrage de la perf.

## 11. Suites à reporter en tickets (Notion)

- [ ] Règles SLO « Burn Rate » non versionnées désactivées le 2026-10-19
      (§10) : décider si elles sont à reprendre (versionnées, avec action) ou
      à supprimer.
- [ ] Jobs : parité complète des notifications (`resultat` détaillé,
      `nbErreurs`, échecs rapportés `succes: false`, exécutions attendues par
      CRON), puis retrait de `envoyerMessageMattermost` et de
      `MATTERMOST_JOBS_WEBHOOK_URL`. Deux voies : des logs ECS dans l'api, ou,
      sans toucher l'api, un filtre Logstash `process` qui décode le corps des
      `external_api_call` de `SuiviJobService` : il contient déjà le message
      Mattermost complet (`http.request.body.content`, constaté le 2026-10-19).
- [ ] Notifier « Dashboard Pass Emploi » d'api-prod : vise l'app absente
      `pass-emploi-dashboard` (la variable jobs de staging, qui la visait
      aussi, est corrigée le 2026-10-19) ; à retirer.
- [ ] Jobs dans Tchap : salons `jobs-production` / `jobs-staging`, Workflows de
      salon, action `.workflows` sur A5a / A5b. Les logs `job_crashed` n'ont pas
      de `message` de notification (leur `message` est le log brut) : le
      Workflow doit construire la ligne depuis `labels.job_type` et
      `error.message`, ou un champ dédié posé en amont.

## 12. Risques et points ouverts

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

## 13. Écarts du Plan 1

- **Workflows de salon : alertes qui bagotent** (trouvé en test le
  2026-10-19). Une règle dont l'alerte change souvent d'état (*flapping*) la
  garde « active », à 0 document, pendant plusieurs exécutions après son
  rétablissement (`pending_recovered_count` > 0). L'action `.workflows` la
  transmet quand même (le connecteur Mattermost, non) : chaque exécution
  postait un message Tchap vide « (0) ». Les 4 Workflows de salon filtrent
  désormais ces alertes dans leur `foreach`. `ongoing: false` a été écarté : il
  perdrait les vrais événements arrivés pendant le bagotement (vérifié : un
  événement remet `pending_recovered_count` à 0 et passe). Concerne toutes les
  règles branchées sur Tchap, pas seulement celles du Plan 1.
- **Collecte** : les en-têtes des `.console` déplacés, `2-component-templates`,
  `objets-kibana.md` et ADR-004 ont aussi été mis à jour (le plan ne listait
  qu'une partie des références).
- **Gravité des événements Scalingo** (décision de l'équipe, 2026-10-19) :
  ℹ️ par défaut ; seuls gardent leur niveau les événements que notifiaient les
  anciennes X1 à X3 : en prod, 🚨 crash, crash répété, redémarrage (même
  volontaire) et arrêt, ⚠️ seuil dépassé ; en staging / perf, ⚠️ pour tous
  ceux-là. Remplace la règle « redémarrage volontaire = ℹ️ » de D5. Le titre des
  messages A4a, A4b, 6a, 6b ne porte plus de gravité (ni émoji, ni tag
  `warning`) : elle est sur chaque ligne.
- **Tchap sur toutes les règles versionnées** (2026-10-19, repo seulement,
  déploiement avec le bot) : action `.workflows` ajoutée aux 27 règles qui n'en
  avaient pas, salon déduit du canal Mattermost de la règle. L'action
  `.workflows` ignore toute fréquence (throttle 6 h, bilan de 9 h 30) :
  décision de l'équipe, `ongoing: false` pour les règles à seuil (un message à
  l'apparition de l'alerte), `ongoing: true` gardé pour les règles d'événements
  (Scalingo, CVE, jobs). AutoOps (11, 12) : connecteur Webhook `POST` direct,
  avec ses propres fréquences. Les Workflows de salon choisissent les lignes
  par tag de la règle : `tchap-lignes` (champ `message` posé par un pipeline),
  `jobs` (`labels.job_type` et `error.message`), sinon la raison de l'alerte.
  Salons `jobs-production` et `jobs-staging` créés, Workflows associés.
