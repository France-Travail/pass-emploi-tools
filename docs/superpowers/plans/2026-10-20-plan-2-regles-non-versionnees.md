# Plan 2 — Règles non versionnées : APM, partenaires, base de données, Uptime

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Les 15 règles actives non versionnées (lignes 11 et 12 de l'inventaire §3 de la spec) sont remplacées ou versionnées au format habituel, avec leur action Tchap : A1 et A2 reconstruites sur l'APM, A6 (erreurs base de données), A7 (erreurs du front), A10 à A13 (Uptime) ; les 11 règles mortes ou fusionnées sont désactivées.

**Architecture:** Le générateur de règles entre dans le repo (`rules/generer-regles.py`) et apprend les règles ES|QL. Une règle ES|QL passe en `groupBy: all` : une seule alerte, à l'identité stable, dont Mattermost reçoit les lignes par `context.hits` ; le Workflow de salon ne les recevant pas, chaque règle ES|QL a son propre Workflow Tchap qui relance la requête au moment de l'alerte. Les règles Uptime gardent leur type et leurs paramètres ; leurs messages passent au format habituel, avec un message de rétablissement.

**Tech Stack:** Kibana 9.4.7 (règles `.es-query` ES|QL, `xpack.uptime.*`, Workflows), ES|QL (`INLINE STATS`, `COUNT` sur `aggregate_metric_double`), Python 3 (générateurs), pile locale du harnais.

**Spec:** `docs/superpowers/specs/2026-10-19-migration-mattermost-tchap-design.md` (§3 lignes 11 et 12, §7, §9, §11). Constats et décisions du 2026-10-20 ci-dessous, à reporter dans la spec en Task 8.

## Constats et décisions du 2026-10-20

| Règle(s) en prod | Constat (lecture seule, 2026-10-20) | Décision de l'équipe |
|---|---|---|
| 7 APM : `2fdcb950-839e-11ee-8a21-83fc356e1168`, `7168ce70-29b8-11ef-864f-5fed7da6b3f6`, `eaf59860-6e47-11ec-9757-c9700cd1bb4e`, `7ee22a20-9bc0-11ec-9757-c9700cd1bb4e`, `d82b1c00-6e47-11ec-9757-c9700cd1bb4e`, `f44b6dc0-29b8-11ef-864f-5fed7da6b3f6`, `5b9ee990-9bc0-11ec-9757-c9700cd1bb4e` | **mortes** : services `pa-back-prod`, `pa-auth-prod`, `pass-emploi-connect`, `rum-pa-front-prod` qui n'émettent plus (0 alerte en 30 j) | désactivées ; **une** règle neuve pour le front (A7) |
| 3 « 🔌 Partenaires » (5xx `f87bff78-3f67-42d1-82fa-ad8cdd3afebb`, timeouts `0230add3-41c5-42da-ae90-604f59094332`, 429 `14fbf32e-2c00-4a3d-8c14-144646106d0c`) | vivantes, bruyantes (100, 93, 48 alertes en 30 j), recoupent A1 | **fusionnées dans A1**, désactivées |
| « 🏠 API - erreurs DB » `738fda9e-02b8-403c-b84c-cea6a5d5e679` | **cassée** : 4 tranches de 5 min au-dessus du seuil en 30 j (jusqu'à 345 erreurs), 0 alerte | réécrite en **A6**, désactivée |
| 4 Uptime : `44d7b9b0-6e45-11ec-9757-c9700cd1bb4e` (api), `45585b60-6e45-11ec-9757-c9700cd1bb4e` (web), `4439f310-6e45-11ec-9757-c9700cd1bb4e` (connect), `6dd99b60-9886-11ec-9757-c9700cd1bb4e` (TLS) | vivantes (moniteurs Heartbeat `pa-back-prod-status`, `pa-web-prod-status`, `pass-emploi-connect-status`) | versionnées en **A10 à A13**, mêmes IDs |
| A1 et A2 (sur les logs) | les `url.path` contiennent des identifiants, l'APM donne le template (`transaction.name`) et la destination des appels sortants | **reconstruites sur l'APM**, mêmes IDs |

## Global Constraints

- Messages et documentation en français ; titres d'objets Kibana « Prod » / « Hors-Prod ».
- Format Mattermost : un champ par section, titres au pluriel (« À vérifier », « Dashboards », « Discover sessions »), étapes numérotées (3 au plus) qui disent quoi vérifier et où, sans acronymes d'alertes ; Dashboards et Discover sessions = exactement ce que citent les étapes ; jamais de Discover non enregistré.
- Investigation guide (`artifacts.investigation_guide`) et Related dashboards (`artifacts.dashboards`) au même contenu que le message.
- Tchap : aucun lien HTML (URL brutes), `=` remplacé par `＝` dans le texte affiché, période de la règle dans les liens Kibana ; Workflows générés, jamais modifiés à la main.
- Aucune règle supprimée : les remplacées sont **désactivées** (`_disable`), après mise en service des remplaçantes.
- Seuils (calibrés le 2026-10-20, par tranche de 5 min) : A2 **total > 50** 5xx (api + connect) ; A1 **> 50** échecs par partenaire ; A6 **> 20** erreurs `Sequelize*` ; A7 **> 200** erreurs du front.
- Déploiement en prod sans action Tchap tant que le bot n'existe pas (`prod.py --sans-tchap`), après accord de l'utilisateur.

## Review Focus

- Un incident de 5xx qui dure 30 min donne **un** message Mattermost (puis un rappel par heure) et **un** message Tchap, pas un par exécution → test de Task 3, Step 5.
- Un appel sortant vers nos propres services (`*.pass-emploi.beta.gouv.fr`) ou vers les statistiques (`stats.beta.gouv.fr`) n'est **pas** compté comme une panne de partenaire → test de Task 4, Step 2.
- Un échec d'appel sortant sans code HTTP (timeout, réseau) est compté, et classé « timeout / réseau » → test de Task 4, Step 2.
- Un moniteur Uptime qui revient « up » envoie un message de rétablissement dans Mattermost **et** dans Tchap → test de Task 7, Step 4.
- Une règle ES|QL dont le Workflow relance la requête alors que l'incident vient de se résorber poste quand même un message lisible (lignes vides → « plus d'erreur au moment de l'envoi ») → test de Task 2, Step 4.

---

## Task 1: Générateur de règles dans le repo, règles ES|QL

**Files:**
- Create: `docs/observabilite/supervision/rules/generer-regles.py` (reprend `~/.claude/jobs/10d0628e/tmp/generer_regles.py`)
- Test: `docs/observabilite/supervision/rules/generer-regles.py --verifier` (compare chaque bloc généré au bloc du fichier)

**Interfaces:**
- Produces: `python3 -I generer-regles.py <code>…` écrit les blocs ; `--ecrire` les remplace dans les fichiers `.console` ; `--verifier` sort en erreur si un bloc diffère. Une définition de règle ES|QL porte `esql` (requête sans filtre de temps), `fenetre`, `lignes_mattermost` (gabarit `{{#context.hits}}…{{/context.hits}}`) et `tchap` (`{'colonnes': [...], 'ligne': '<gabarit Liquid sur une ligne v>'}`).

- [ ] **Step 1 : `--verifier` sur les règles déjà générées (A4a, A4b, A5a, A5b, 6a, 6b, 14, V1)**
Run: `python3 -I docs/observabilite/supervision/rules/generer-regles.py --verifier A4a A4b A5a A5b 6a 6b 14 V1`
Expected (avant l'implémentation) : FAIL, fichier absent.
- [ ] **Step 2 : copier le générateur, ajouter `--ecrire` / `--verifier` et le type ES|QL** (`params.searchType: esqlQuery`, `groupBy: all`, `threshold: [0]`, `thresholdComparator: '>'`, `size: 100`, action Mattermost en `onThrottleInterval` / `1h`, action Tchap vers `tchap-alerte-<code>` avec `alertStates` `{new: true, ongoing: false, recovered: false}`).
- [ ] **Step 3 : relancer Step 1** — Expected : PASS (aucun bloc différent).
- [ ] **Step 4 : commit** `feat(rules): générateur de règles dans le repo, règles ES|QL`.

## Task 2: Workflow Tchap propre à une règle ES|QL

**Files:**
- Modify: `docs/observabilite/supervision/workflows/tchap/generer-workflows.py`
- Create (générés) : `docs/observabilite/supervision/workflows/tchap/tchap-alerte-<code>.console` pour A1, A2, A3, A6, A7

**Interfaces:**
- Consumes: Task 1 — définition `esql`, `fenetre`, `tchap`.
- Produces: Workflow `tchap-alerte-<code>` (déclencheur `alert`) : étape `elasticsearch.esql.query` = la requête de la règle précédée de `WHERE @timestamp >= NOW() - <fenetre>`, puis `tchap-client` avec le message de la règle (titre en couleur, « Déclenchée à », une ligne par résultat, explications, liens). Le Workflow de salon ne traite plus ces règles.

- [ ] **Step 1 : test local** — règle ES|QL d'essai (`groupBy: all`) sur l'index `test-appels` (2 partenaires à 60 et 55 échecs, cf. `harnais/test_groupby_all.py`), action vers `tchap-alerte-essai`. Expected : un message Synapse avec 2 lignes `api.i-milo.fr:443 : 60` et `api.francetravail.io:443 : 55`.
- [ ] **Step 2 : lancer** — Expected : FAIL (Workflow absent).
- [ ] **Step 3 : implémenter** la génération (le texte fixe vient du message Mattermost, comme pour les Workflows de salon).
- [ ] **Step 4 : test** Step 1 puis le même avec l'index vidé avant l'exécution du Workflow — Expected : PASS ; sans ligne, le message dit « plus d'erreur au moment de l'envoi ».
- [ ] **Step 5 : A3** (`ad326ad3-aea7-4ef8-be28-31008c4aebce`, pic d'authentifications refusées) passe aussi en `groupBy: all`, avec son Workflow `tchap-alerte-A3` ; sa requête et son seuil ne changent pas.
- [ ] **Step 6 : commit** `feat(tchap): Workflow propre à chaque règle ES|QL`.

## Task 3: A2 sur l'APM (`98e0103a-f809-48f2-8343-d1269213dce4`)

**Files:** `rules/1-rules-applicatives.console` (bloc A2, régénéré), `alertes-applicatives.md` (section A2), harnais : index `metrics-apm.transaction.1m-test` (gabarit local, `transaction.duration.summary` en `aggregate_metric_double`).

Requête :
```
FROM metrics-apm.transaction.1m-*
| WHERE service.name IN ("pass-emploi-api-prod", "pass-emploi-connect-prod") AND transaction.result == "HTTP 5xx"
| STATS erreurs = COUNT(transaction.duration.summary) BY service.name, transaction.name
| INLINE STATS total = SUM(erreurs)
| WHERE total > 50
| SORT erreurs DESC | LIMIT 10
```
Titre : `🚨 **Erreurs 5xx — prod** — plus de 50 requêtes en erreur serveur en 5 min.` ; une ligne par template : `` `pass-emploi-api-prod` POST /jeunes/:idJeune/demarches-ia : 58 `` ; étapes : les templates les plus touchés (dashboard Diagnostic d'erreurs - Apps), un partenaire en cause (Diagnostic d'erreurs - Entrée, Discover Échecs partenaires), le détail d'une requête par son `trace.id` (Discover Erreurs serveur 5xx).

- [ ] **Step 1 : test local** — 51 5xx en 5 min sur 2 templates → une alerte, 2 lignes (Mattermost et Tchap) ; 50 → aucune alerte.
- [ ] **Step 2 : lancer** — Expected : FAIL (ancienne requête sur les logs).
- [ ] **Step 3 : définition A2** dans le générateur, `--ecrire A2`.
- [ ] **Step 4 : test** Step 1 — Expected : PASS. Contrôle en prod, lecture seule : la requête avec `@timestamp` sur une tranche du pic du 2026-10-20 renvoie des lignes.
- [ ] **Step 5 : test d'incident long** — 60 5xx injectés à chaque minute pendant 5 min : 1 message Mattermost, 1 message Tchap.
- [ ] **Step 6 : doc** (section A2 : source APM, seuil, calibrage du 2026-10-20 : p99 = 116, max = 1 061, 32 tranches > 50 en 26 j), commit `feat(alertes-applicatives): A2 sur les templates d'URL de l'APM`.

## Task 4: A1 sur les appels sortants APM (`1b751543-4233-4857-8fe6-8141a7c2d040`), fusion des 🔌

Requête (traces, pour le code HTTP ; rétention 21 j) :
```
FROM traces-apm*
| WHERE service.name == "pass-emploi-api-prod" AND processor.event == "span" AND span.type == "external" AND event.outcome == "failure"
  AND NOT span.destination.service.resource LIKE "*pass-emploi.beta.gouv.fr*" AND span.destination.service.resource != "stats.beta.gouv.fr:443"
| EVAL type = CASE(http.response.status_code == 429, "429", http.response.status_code >= 500, "5xx", http.response.status_code IS NULL, "timeout / réseau", "autre")
| STATS echecs = COUNT(*), types = VALUES(type) BY partenaire = span.destination.service.resource
| WHERE echecs > 50
| SORT echecs DESC
```
Une ligne par partenaire : `api.i-milo.fr:443 : 206 échecs (5xx, timeout / réseau)`. Le champ « Contacts partenaires » (Notion) est gardé.

- [ ] **Step 1 : test local** (index `traces-apm-test`) : 51 échecs Milo dont 10 sans code, 60 échecs vers `id.pass-emploi.beta.gouv.fr:443`, 60 vers `stats.beta.gouv.fr:443` → une ligne Milo avec `5xx, timeout / réseau` ; nos services et les statistiques absents.
- [ ] **Step 2 : lancer** — FAIL, puis définition A1, `--ecrire A1`, relancer — PASS.
- [ ] **Step 3 : doc** (section A1 : la fusion des 3 règles 🔌, calibrage : Milo p99 = 40, France Travail p99 = 22, 15 tranches > 50 en 21 j), commit `feat(alertes-applicatives): A1 sur les appels sortants de l'APM, fusion des alertes partenaires`.

## Task 5: A6, erreurs base de données (`c9164880-1829-4847-acb1-5a70433ecbb8`)

Requête : `FROM logs-prod-default | WHERE error.type LIKE "Sequelize*" | STATS erreurs = COUNT(*), types = VALUES(error.type), exemples = VALUES(error.message) BY service.name | WHERE erreurs > 20 | EVAL exemples = MV_SLICE(exemples, 0, 2)`. Titre `🚨 **Erreurs base de données — prod** — plus de 20 erreurs de base de données en 5 min.` Étapes : le type et le message de l'erreur (Discover d'une session à créer, `[Pass Emploi] Logs de Prod - Erreurs base de données`, onglet `error.type : Sequelize*`), l'état de la base PostgreSQL dans le [Scalingo] Dashboard des apps, l'impact (Diagnostic d'erreurs - Entrée).

- [ ] **Step 1 : test local** : 21 erreurs `SequelizeConnectionError` → une alerte ; 20 → aucune. FAIL, puis session Discover (`discovers/applicatives/discover-session-prod-erreurs-base-de-donnees.ndjson`), définition A6, PASS.
- [ ] **Step 2 : doc**, commit `feat(alertes-applicatives): A6, erreurs base de données`.

## Task 6: A7, erreurs du front (`52c66a2a-2ee1-4de2-bc5c-642a96395405`)

Requête : `FROM logs-apm.error-* | WHERE service.name == "rum-pass-emploi-web-prod" | STATS erreurs = COUNT(*) BY erreur = error.grouping_name | INLINE STATS total = SUM(erreurs) | WHERE total > 200 | SORT erreurs DESC | LIMIT 5`. Titre `⚠️ **Erreurs du front — prod** — plus de 200 erreurs JavaScript en 5 min dans l'app web.` Étapes : les erreurs les plus fréquentes (lignes du message), l'écran et le navigateur touchés (dashboard APM du service `rum-pass-emploi-web-prod`), un déploiement récent du web (activité de `pass-emploi-web-prod` dans le [Scalingo] Dashboard des apps).

- [ ] **Step 1 : test local** (index `logs-apm.error-test`) : 201 erreurs sur 3 `error.grouping_name` → 3 lignes ; 200 → rien. FAIL, définition, PASS.
- [ ] **Step 2 : doc** (calibrage : p99 = 173, max = 1 502, 29 tranches > 200 en 30 j), commit `feat(alertes-applicatives): A7, erreurs du front`.

## Task 7: A10 à A13, règles Uptime versionnées

**Files:** `rules/1-rules-applicatives.console` (4 blocs `PUT` aux IDs actuels, `rule_type_id` et `params` inchangés), `generer-workflows.py` (variables `{{state.X}}` → `foreach.item.kibana.alert.state.X` ; règle à message de rétablissement → `alertStates.recovered: true` et texte de rétablissement si `kibana.alert.status == 'recovered'`).

| Code | Règle | Titre de panne | Rétablissement |
|---|---|---|---|
| A10 | api (`pa-back-prod-status`) | `🚨 **api injoignable — prod**` | `✅ **api de nouveau joignable — prod**` |
| A11 | web (`pa-web-prod-status`) | `🚨 **app web conseiller injoignable — prod**` | `✅ …` |
| A12 | connect (`pass-emploi-connect-status`) | `🚨 **authentification injoignable — prod**` | `✅ …` |
| A13 | TLS | `⚠️ **Certificat TLS bientôt expiré**` — `{{state.commonName}}` : `{{state.summary}}` | — |

Champs : URL du moniteur, motif (`{{state.latestErrorMessage}}`), depuis (`{{state.currentTriggerStarted}}`) ; étapes : l'état du service dans le [Scalingo] Dashboard des apps, les 5xx et l'APM au même moment (Diagnostic d'erreurs - Entrée), un déploiement en cours.

- [ ] **Step 1 : test** des Workflows avec des alertes Uptime d'exemple (champs relevés en prod le 2026-10-20) : panne puis rétablissement → 2 messages ; TLS → 1 message. FAIL, implémentation, PASS.
- [ ] **Step 2 : test** `--verifier` et création locale impossible (type Uptime sans moniteur) : validation par `PUT` en prod en Task 9.
- [ ] **Step 3 : doc**, commit `feat(alertes-applicatives): A10 à A13, disponibilité et certificats (Uptime)`.

## Task 8: Documentation et spec

- [ ] `alertes-applicatives.md` : récapitulatif (A1, A2 sur l'APM ; A6, A7, A10 à A13), section « Données APM » (rétention : métriques 1 min 90 j, traces 21 j, erreurs 85 j ; `COUNT` sur `aggregate_metric_double`) ; `objets-kibana.md` (nouvelle session) ; README Tchap (Workflows `tchap-alerte-*`).
- [ ] Spec : §3 lignes 11 et 12 → ✅ ; §13 écarts (A1 et A2 sur l'APM, `groupBy: all` et Workflows `tchap-alerte-*`).
- [ ] `generer-workflows.py`, `generer-regles.py --verifier` sur tout ; commit `docs: Plan 2, règles APM, base de données, front et Uptime`.

## Task 9: Déploiement en prod (avec l'accord de l'utilisateur)

- [ ] Import de la session « Erreurs base de données » ; `PUT` A1, A2, A3, A10 à A13 ; `POST` A6, A7 (`prod.py --sans-tchap`, `--creer` pour A6, A7).
- [ ] Contrôle : les 8 règles en `ok` ou `active` après 2 exécutions.
- [ ] Désactivation (`POST kbn:/api/alerting/rule/<id>/_disable`) des 11 règles de la table « Constats » (7 APM, 3 🔌, erreurs DB) ; consignation des IDs dans la spec §10.
- [ ] Commit `docs(spec): journal, Plan 2 déployé`.
