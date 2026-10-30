# Supervision des bases de données dans Kibana — plan de réalisation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** rendre visibles dans Kibana l'état et les requêtes du PostgreSQL de l'api et des Redis de l'api et de connect, en prod puis en perf, sans nouvelle alerte.

**Architecture:** l'Elastic Agent dédié existant (`pass-emploi-elastic-agent-<env>`, piloté par Fleet) collecte sans passer par Logstash : intégration Redis (2 instances), intégration PostgreSQL, package SQL (requêtes versionnées dans le repo), intégration CEL sur l'API des bases de Scalingo. Deux dashboards `[Pass Emploi]` versionnés en `.ndjson` ; les règles A2 et A6 y renvoient.

**Tech Stack:** Fleet / Elastic Agent 9.x, packages `redis`, `postgresql`, `sql`, `cel` ; ES|QL et Lens ; CEL (`mito` pour les tests) ; Python 3 (`unittest`) pour les tests du repo ; CLI Scalingo.

**Spec:** [`docs/superpowers/specs/2026-10-30-supervision-bases-de-donnees-design.md`](../specs/2026-10-30-supervision-bases-de-donnees-design.md)

## Global Constraints

- Aucune règle d'alerte nouvelle (spec §3).
- Aucune collecte par le log drain ni par Logstash (spec §3).
- Environnements : prod d'abord, perf ensuite ; jamais staging (spec §4). Staging sert seulement à valider des requêtes en lecture seule.
- Région des bases de prod et de perf : `osc-secnum-fr1` ; API des bases : `https://db-api.osc-secnum-fr1.scalingo.com`.
- Utilisateur PostgreSQL : l'utilisateur de l'app (`SCALINGO_POSTGRESQL_URL` de `pass-emploi-api-<env>`) (spec §5).
- Token Scalingo : Bitwarden « API Token Scalingo pour Elastic », posé seulement dans le *Secret CEL evaluation state* ; jamais dans le repo, un log ou une variable en clair (spec §5).
- Statistiques de requêtes : 200 premières par temps total ∪ 200 premières par appels, relevées toutes les **10 min** ; dataset `statement` de l'intégration PostgreSQL **désactivé** (spec §8).
- Rétention : `metrics-fleet-retention` (90 j) pour tout nouveau data stream (spec §6, §8).
- Les compteurs de `pg_stat_statements` sont cumulés depuis le 2026-02-20 : un panneau ne montre jamais une valeur cumulée, toujours l'écart `MAX − MIN` sur la période choisie (spec §7.2).
- Mémoire des Redis : comparer le RSS à `memory_limit` de l'API Scalingo ; ne jamais afficher `total_system_memory` (spec §6).
- Quotas de disque et connexions par plan (spec §6) : PG api prod 160 Go/nœud, 480 connexions ; Redis api prod 160 Go/nœud ; Redis connect prod 20 Go/nœud ; PG api perf 10 Go, 30 connexions ; Redis api perf 5 Go.
- Titres des dashboards : `[Pass Emploi] Bases de données - PostgreSQL` (id `66b0c0ac-d034-489b-ab0a-7b07539074ff`) et `[Pass Emploi] Bases de données - Redis` (id `86b702ee-b9c7-4344-91ef-a10a50405ed5`).
- Toute commande sur une app de **prod** (`scalingo run`, `logs`, consoles) est lancée par l'utilisateur : la session de l'agent n'y a pas droit. Préparer la commande, la lui donner, lire la sortie qu'il colle.
- Commentaires et docs : règles de `docs/CONTEXTE-TRANSVERSE.md` (pas de commentaire qui paraphrase ; un fait, un endroit).
- Chaque commit se termine par la ligne `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Remise à zéro de `pg_stat_statements`** (redémarrage, maintenance Scalingo) : `MAX − MIN` devient négatif ou faux sur la période ; on attend des valeurs ≥ 0, la requête concernée ignorée sur la période → test dans la tâche 6.
2. **Identifiants d'une base changés par Scalingo** (rotation de mot de passe, URL modifiée) : la collecte doit échouer visiblement (document d'erreur, agent *Unhealthy*), pas se taire → test dans la tâche 3 (Redis) et la tâche 4 (PG).
3. **API Scalingo en erreur** (token révoqué, 401, 404 sur une base) : l'intégration CEL émet un document `error.message` par base en erreur et continue les autres → test dans la tâche 5.
4. **Texte SQL avec des valeurs en clair** (requête non paramétrée) : le texte affiché est celui normalisé par `pg_stat_statements` (`$1`, `$2`), jamais celui des spans APM → vérification dans la tâche 2.
5. **Perf arrêtée entre deux tirs** : les dashboards de perf vides ne doivent pas lever d'erreur ; l'agent de perf démarre et s'arrête avec les apps de perf → vérification dans la tâche 8.

---

### Task 1: Rétention des nouveaux data streams

**Files:**
- Modify: `docs/observabilite/stockage/metriques/2-component-templates.console`
- Modify: `docs/observabilite/stockage/metriques/3-index-templates.console`
- Modify: `docs/observabilite/stockage/metriques/README.md` (tableau des data streams)

**Interfaces:**
- Produces : les data streams `metrics-postgresql.database-default`, `metrics-postgresql.activity-default`, `metrics-postgresql.bgwriter-default`, `metrics-sql.postgresql_statements-default`, `metrics-sql.postgresql_index_stats-default`, `metrics-sql.postgresql_table_stats-default`, `logs-scalingo.database_stats-default`, tous en `metrics-fleet-retention`.

- [ ] **Step 1 : Ajouter une brique `<type>-<dataset>@custom` par data stream** dans `2-component-templates.console`, au format exact des briques Redis existantes, `"name": "metrics-fleet-retention"`, `_meta.managed_by: "pass-emploi-tools"`.
- [ ] **Step 2 : Ajouter un `POST <data stream>/_rollover`** par data stream dans `3-index-templates.console`, comme pour `logs-scalingo.container_stats-default`.
- [ ] **Step 3 : Compléter le tableau** de `stockage/metriques/README.md` (une ligne par famille, cible 90 j).
- [ ] **Step 4 : Importer** les briques dans Dev Tools (prod), avant toute intégration.
Expected : `"acknowledged": true` pour chaque `PUT`. Les `_rollover` échouent tant que les data streams n'existent pas : les rejouer à la fin des tâches 3 à 5.
- [ ] **Step 5 : Commit**

```bash
git add docs/observabilite/stockage/metriques/
git commit -m "feat(stockage): rétention des métriques des bases de données"
```

### Task 2: Requêtes SQL sur mesure

**Files:**
- Create: `elastic-agent/integrations/postgresql/statements.sql`
- Create: `elastic-agent/integrations/postgresql/index_stats.sql`
- Create: `elastic-agent/integrations/postgresql/table_stats.sql`
- Create: `elastic-agent/integrations/postgresql/verifier.sh` (lance les 3 requêtes, imprime colonnes, nombre de lignes et durée)

**Interfaces:**
- Produces (colonnes exactes, consommées par la tâche 6) :
  - `statements.sql` : `queryid` (texte), `requete` (texte normalisé, 2 000 caractères au plus), `calls`, `total_exec_time_ms`, `mean_exec_time_ms`, `stddev_exec_time_ms`, `rows`, `shared_blks_hit`, `shared_blks_read`, `classement` (`temps`, `appels` ou `temps,appels`). 400 lignes au plus.
  - `index_stats.sql` : `schema`, `table`, `index`, `idx_scan`, `taille_octets`, `contrainte` (booléen : clé primaire, unicité ou index d'une contrainte).
  - `table_stats.sql` : `schema`, `table`, `seq_scan`, `seq_tup_read`, `idx_scan`, `n_live_tup`, `taille_octets`.

- [ ] **Step 1 : Écrire `verifier.sh`** : pour chaque fichier, `psql "$SCALINGO_POSTGRESQL_URL" -X -A -F '|'`, affiche l'en-tête, le nombre de lignes et la durée ; sort en erreur si une requête échoue ou si `statements.sql` dépasse 400 lignes.
- [ ] **Step 2 : Lancer `verifier.sh` sur staging avant d'écrire les requêtes** (base64 + `scalingo --region osc-fr1 --app pass-emploi-api-staging run --detached`, sortie par `logs --filter one-off-…`, cf. spec §6) : il doit échouer (fichiers absents).
- [ ] **Step 3 : Écrire les 3 requêtes.** `statements.sql` : union des deux top 200 de `pg_stat_statements`, dédoublonnée par `queryid`, filtrée sur `userid = (select oid from pg_roles where rolname = current_user)` (les requêtes des autres rôles n'ont pas de texte lisible). `index_stats.sql` : `pg_stat_user_indexes` joint à `pg_index` (`indisprimary or indisunique` ou présent dans `pg_constraint.conindid`).
- [ ] **Step 4 : Relancer `verifier.sh` sur staging.**
Expected : 3 requêtes OK, `statements` ≤ 400 lignes, chacune en moins de 2 s, aucune `requete` contenant `<insufficient privilege>`, les valeurs littérales remplacées par `$n` (Review Focus 4).
- [ ] **Step 5 : Donner à l'utilisateur la commande équivalente pour la prod** (`--app pass-emploi-api-prod`, sans `--region`) et lire la sortie qu'il colle.
Expected : mêmes critères ; 92 lignes d'`index_stats` à `idx_scan = 0` environ (spec §6).
- [ ] **Step 6 : Commit**

```bash
git add elastic-agent/integrations/postgresql/
git commit -m "feat(elastic-agent): requêtes SQL des statistiques PostgreSQL"
```

### Task 3: Redis de l'api et de connect (prod)

**Files:**
- Modify: `elastic-agent/README.md` (schéma « Architecture », « Policy Fleet recommandée », variables)

**Interfaces:**
- Produces : variables `REDIS_API_URL` et `REDIS_CONNECT_URL` sur `pass-emploi-elastic-agent-prod` ; documents `metrics-redis.{info,keyspace}` avec `service.address` de ces deux Redis, et `metrics-redis.key` pour les 5 clés Bull.

- [ ] **Step 1 : Écrire la requête de contrôle** (ES|QL, échoue tant que rien n'arrive) :

```
FROM metrics-redis.info-default
| WHERE @timestamp > NOW() - 15 minutes
| STATS n = COUNT(*), politique = VALUES(redis.info.memory.max.policy) BY service.address
```
Expected avant : seule l'adresse du Redis de `pass-emploi-logstash-process-prod`.
- [ ] **Step 2 : L'utilisateur pose les variables** sur l'app de l'agent, depuis `SCALINGO_REDIS_URL` de `pass-emploi-api-prod` et de `pass-emploi-connect-prod` (commande à lui donner : `scalingo --app pass-emploi-elastic-agent-prod env-set REDIS_API_URL=… REDIS_CONNECT_URL=…`, valeurs lues par lui, jamais par l'agent de session).
- [ ] **Step 3 : Ajouter dans la policy `pass-emploi-elastic-agent-prod` deux instances de l'intégration Redis** : `hosts: ["${REDIS_API_URL}"]` et `["${REDIS_CONNECT_URL}"]`, slowlogs désactivés (cf. README), période 1 min. Sur l'instance api seulement, `redis.key` avec les motifs `bull:JobQueue:wait`, `bull:JobQueue:active`, `bull:JobQueue:delayed`, `bull:JobQueue:failed`, `bull:JobQueue:completed`. Pas de `redis.key` sur connect (spec §7.1).
- [ ] **Step 4 : Relancer la requête du step 1.**
Expected : 3 adresses, `politique = noeviction` pour l'api ; puis `FROM metrics-redis.key-default | WHERE redis.key.name LIKE "bull:JobQueue:*"` renvoie la longueur de `wait` (27 au relevé du 2026-10-30, l'ordre de grandeur suffit).
- [ ] **Step 5 : Tester l'échec visible** (Review Focus 2) : sur une instance de test temporaire avec un mot de passe faux, vérifier qu'un `error.message` apparaît dans `logs-elastic_agent.metricbeat-default` et que l'agent passe *Unhealthy* ; supprimer l'instance de test.
- [ ] **Step 6 : Documenter** dans `elastic-agent/README.md` les deux instances, les variables et le choix « pas de `redis.key` sur connect ».
- [ ] **Step 7 : Commit**

```bash
git add elastic-agent/README.md
git commit -m "feat(elastic-agent): métriques des Redis de l'api et de connect"
```

### Task 4: PostgreSQL de l'api (prod)

**Files:**
- Modify: `elastic-agent/README.md`

**Interfaces:**
- Consumes : les requêtes de la tâche 2.
- Produces : variable `PG_API_URL` sur `pass-emploi-elastic-agent-prod` ; data streams `metrics-postgresql.{database,activity,bgwriter}-default` et `metrics-sql.postgresql_{statements,index_stats,table_stats}-default`.

- [ ] **Step 1 : Requête de contrôle** (échoue avant) :

```
FROM metrics-postgresql.database-default, metrics-sql.postgresql_statements-default
| WHERE @timestamp > NOW() - 30 minutes
| STATS n = COUNT(*) BY data_stream.dataset
```
- [ ] **Step 2 : L'utilisateur pose `PG_API_URL`** (valeur de `SCALINGO_POSTGRESQL_URL` de `pass-emploi-api-prod`) sur l'app de l'agent.
- [ ] **Step 3 : Installer l'intégration PostgreSQL** dans la policy prod, `hosts: ["${PG_API_URL}"]`, datasets `database`, `activity`, `bgwriter` à 1 min, **`statement` désactivé**, logs désactivés.
- [ ] **Step 4 : Installer le package SQL** (`sql`, driver `postgres`, même hôte) : 3 inputs, un par fichier de la tâche 2, datasets `sql.postgresql_statements`, `sql.postgresql_index_stats`, `sql.postgresql_table_stats`, période **10 min**, la requête collée depuis le fichier versionné.
- [ ] **Step 5 : Relancer la requête du step 1.**
Expected : 2 datasets non vides ; au relevé suivant, `metrics-sql.postgresql_statements-default` contient ≤ 400 documents par relevé.
- [ ] **Step 6 : Vérifier l'échec visible** (Review Focus 2), comme à la tâche 3, step 5.
- [ ] **Step 7 : Rejouer les `_rollover` de la tâche 1** pour les datasets PostgreSQL et SQL, puis la procédure de contrôle de `docs/observabilite/stockage/README.md`.
Expected : chaque backing index porte `metrics-fleet-retention`.
- [ ] **Step 8 : Documenter** dans `elastic-agent/README.md` (intégration, package SQL, fichiers de requêtes, `statement` désactivé et pourquoi).
- [ ] **Step 9 : Commit**

```bash
git add elastic-agent/README.md
git commit -m "feat(elastic-agent): métriques et statistiques du PostgreSQL de l'api"
```

### Task 5: Métriques des instances par l'API Scalingo (CEL)

**Files:**
- Create: `elastic-agent/integrations/scalingo-database-stats.cel`
- Create: `elastic-agent/integrations/tests/test_scalingo_database_stats.py`
- Create: `elastic-agent/integrations/tests/faux_scalingo.py` (serveur HTTP local qui imite les 3 endpoints)
- Modify: `elastic-agent/README.md` (section sur le modèle de « Mémoire des conteneurs Scalingo »)

**Interfaces:**
- State attendu (Initial CEL evaluation state) : `url` (API Scalingo, `https://api.osc-secnum-fr1.scalingo.com`), `auth_url` (`https://auth.scalingo.com/v1/tokens/exchange`), `db_api_url` (`https://db-api.osc-secnum-fr1.scalingo.com`), `bases` : liste de `{app, addon_id, nom, disque_inclus_octets, connexions_max}` (connexions_max absent pour Redis) ; secret `api_token`.
- Enchaînement : échange du token → pour chaque base `POST {url}/v1/apps/{app}/addons/{addon_id}/token` (réponse : l'addon avec un champ `token`) → `GET {db_api_url}/api/databases/{addon_id}/metrics` avec ce token. Que l'identifiant de la base soit celui de l'addon est à confirmer au step 6 ; sinon prendre l'identifiant renvoyé avec le token.
- Produces : un document par instance, dataset `scalingo.database_stats`, champs `scalingo.database.{nom,app,addon_id,instance}`, `scalingo.cpu.usage`, `scalingo.memory.{usage,limit,highest}.bytes`, `scalingo.memory.pct`, `scalingo.swap.usage.bytes`, `scalingo.disk.{usage,inclus}.bytes`, `scalingo.disk.pct` (usage / inclus), `scalingo.database.data_size.bytes`, `scalingo.database.connexions_max`. Une base en erreur : un document `error.message` avec `scalingo.database.nom`, les autres continuent.

- [ ] **Step 1 : Écrire `faux_scalingo.py`** : répond à l'échange, au token d'addon et aux métriques avec l'exemple de réponse de la doc Scalingo (spec §6), et en 401 pour un `addon_id` nommé `addon-en-erreur`.
- [ ] **Step 2 : Écrire les tests** (`unittest`, lancent `mito -data <state.json> scalingo-database-stats.cel` contre le faux serveur ; ignorés avec un message si `mito` est absent) :
  - `test_un_document_par_instance` : 1 base, 1 instance → 1 événement, `scalingo.memory.limit.bytes == 536870912`, `scalingo.disk.usage.bytes == 37825858`.
  - `test_pourcentage_de_disque_sur_le_quota_du_plan` : `disque_inclus_octets = 160 * 1024**3` → `scalingo.disk.pct` = `37825858 / (160 * 1024**3)`.
  - `test_base_en_erreur_n_arrete_pas_les_autres` (Review Focus 3) : 2 bases dont `addon-en-erreur` → 1 document de métriques et 1 document `error.message` contenant le nom de la base et `401`.
  - `test_echange_du_token_refuse` : échange en 401 → un seul document `error.message`, aucun appel aux bases.
- [ ] **Step 3 : Installer `mito`** (binaire de release GitHub `elastic/mito`, hors du repo) et lancer les tests.
Run : `python3 -I -m unittest discover -s elastic-agent/integrations/tests -v`
Expected : FAIL (programme absent).
- [ ] **Step 4 : Écrire `scalingo-database-stats.cel`** sur le modèle de `scalingo-container-stats.cel` (lecture du secret, échange, `map` sur `state.bases`, `flatten`, `want_more: false`).
- [ ] **Step 5 : Relancer les tests.** Expected : 4 PASS.
- [ ] **Step 6 : Faire lancer par l'utilisateur `mito` contre la vraie API** (state de prod sans le token dans le fichier, token passé par lui) pour les 3 bases de prod : PG api `ad-a402741f-8751-409c-b602-a645998335ef`, Redis api `ad-a1a0483d-c0b0-4e75-afb8-d53afb90bc9c`, Redis connect `ad-82bc06a9-c3b8-431e-acd7-c62382fcda2c`.
Expected : 3 bases sans `error.message` ; sinon corriger l'identifiant de base (cf. Interfaces) et ajouter un test.
- [ ] **Step 7 : Installer l'intégration** « Custom API using Common Expression Language » dans la policy prod : nom `scalingo-database-stats-prod`, dataset `scalingo.database_stats`, intervalle 1 min, programme collé depuis le fichier, token dans le *Secret CEL evaluation state*. Rejouer le `_rollover` de la tâche 1.
Expected : `FROM logs-scalingo.database_stats-default | STATS COUNT(*) BY scalingo.database.nom` → 3 noms.
- [ ] **Step 8 : Documenter** dans `elastic-agent/README.md` (tableau des champs, state, test avec `mito`).
- [ ] **Step 9 : Commit**

```bash
git add elastic-agent/integrations/ elastic-agent/README.md
git commit -m "feat(elastic-agent): métriques des instances de bases via l'API Scalingo"
```

### Task 6: Dashboard `[Pass Emploi] Bases de données - PostgreSQL`

**Files:**
- Create: `docs/observabilite/supervision/dashboards/dashboard-bases-de-donnees.ndjson` (les deux dashboards, comme `dashboard-diagnostic-erreurs.ndjson`)
- Modify: `docs/observabilite/supervision/objets-kibana.md` (tableau « Dashboards »)

**Interfaces:**
- Consumes : datasets des tâches 4 et 5 ; spans APM `traces-apm*` (`service.name == "pass-emploi-api-prod"`, `span.subtype == "postgresql"`).
- Produces : dashboard d'id `66b0c0ac-d034-489b-ab0a-7b07539074ff`, consommé par la tâche 7.

- [ ] **Step 1 : Écrire les requêtes ES|QL des panneaux de requêtes** et les valider dans Discover sur 24 h :
  - **Requêtes lentes (moyenne)** : par `queryid`, `Δappels = MAX(calls) − MIN(calls)`, `Δtemps = MAX(total_exec_time_ms) − MIN(total_exec_time_ms)`, `moyenne = Δtemps / Δappels`, en ne gardant que `Δappels > 0` et `Δtemps ≥ 0` (Review Focus 1), tri par moyenne, 20 lignes, avec `requete`.
  - **Requêtes les plus appelées** : même calcul, tri par `Δappels`.
  - **Requêtes lentes (P95/P99, APM)** : `PERCENTILE(span.duration.us, 95)` et `99` par `span.name`, 20 lignes, avec le nombre d'appels.
- [ ] **Step 2 : Tester la remise à zéro** (Review Focus 1) : dans Discover, rejouer la requête « moyenne » sur un jeu où `calls` décroît pour un `queryid` (index de test `test-remise-a-zero`, 2 documents écrits à la main puis supprimés).
Expected : la requête est absente du résultat, aucune valeur négative.
- [ ] **Step 3 : Construire le dashboard** dans Kibana avec l'id fixé, 4 sections (spec §7.2) :
  - **Santé de l'instance** : `scalingo.memory.pct`, `scalingo.disk.pct` (quota 160 Go/nœud), `scalingo.cpu.usage` par instance ; connexions (`metrics-postgresql.activity`) face à 480 ; taux de cache et verrous (`metrics-postgresql.database`).
  - **Requêtes lentes** : deux tableaux côte à côte, moyenne (step 1) et P95/P99 APM (step 1), avec la mention « APM : 21 j au plus ».
  - **Requêtes les plus appelées** (step 1).
  - **Requêtes à optimiser** : index `idx_scan = 0` et `contrainte = false` (dernier relevé), tables triées par `seq_tup_read` avec `idx_scan`.
  - Contrôle d'environnement (prod / perf) sur `service.address` ou `scalingo.database.nom`.
- [ ] **Step 4 : Vérifier** : chaque panneau affiche des données sur les dernières 24 h ; aucun panneau ne montre de compteur cumulé brut.
- [ ] **Step 5 : Exporter** (*Saved objects* → Export avec *Include related objects*) vers `dashboard-bases-de-donnees.ndjson` ; ajouter la ligne dans `objets-kibana.md`.
- [ ] **Step 6 : Commit**

```bash
git add docs/observabilite/supervision/dashboards/dashboard-bases-de-donnees.ndjson docs/observabilite/supervision/objets-kibana.md
git commit -m "feat(supervision): dashboard des bases de données - PostgreSQL"
```

### Task 7: Dashboard Redis, et renvoi depuis les alertes

**Files:**
- Modify: `docs/observabilite/supervision/dashboards/dashboard-bases-de-donnees.ndjson`
- Modify: `docs/observabilite/supervision/objets-kibana.md`
- Modify: `docs/observabilite/supervision/rules/2-applicatives/A2.json`, `A6.json`
- Modify (générés) : `docs/observabilite/supervision/rules/generated/2-rules-applicatives.console`, Workflows Tchap concernés
- Test: `docs/observabilite/supervision/tests/test_generateurs.py`

**Interfaces:**
- Consumes : dashboard PG `66b0c0ac-d034-489b-ab0a-7b07539074ff` (tâche 6).
- Produces : dashboard Redis `86b702ee-b9c7-4344-91ef-a10a50405ed5`.

- [ ] **Step 1 : Construire le dashboard Redis** avec l'id fixé et un contrôle « base » (Redis api / Redis connect) : mémoire RSS face à `memory_limit` (CPU, disque face au quota du plan) depuis `logs-scalingo.database_stats` ; politique mémoire (`noeviction` signalé comme « mémoire pleine = conteneur tué ») ; commandes par seconde et clients ; nombre de clés (`redis.keyspace`) ; longueur des 5 files Bull (api) ; connexions refusées et évictions. Aucun panneau sur `total_system_memory`.
- [ ] **Step 2 : Exporter** dans le même `.ndjson`, ajouter la ligne dans `objets-kibana.md`.
- [ ] **Step 3 : Modifier A6** : l'étape 1 cite `[Pass Emploi] Bases de données - PostgreSQL` à la place du dashboard Scalingo, dans le message, l'Investigation guide et `artifacts.dashboards` (même texte aux trois endroits, cf. `rules/README.md`).
- [ ] **Step 4 : Modifier A2** sans dépasser 3 étapes : l'étape 2 devient « Si un partenaire ou une base de données est en cause » et cite aussi les deux dashboards des bases.
- [ ] **Step 5 : Régénérer et lancer les tests.**
Run (depuis `docs/observabilite/supervision/`) : `FEATURE_NOTIFIER_ALERTES_MATTERMOST=true python3 -I rules/generer-regles.py && python3 -I workflows/tchap/generer-workflows.py`, puis depuis la racine `python3 -I -m unittest discover -s docs/observabilite/supervision/tests -v`.
Expected : tous PASS, dont `test_regles_generees_identiques_a_leurs_sources`.
- [ ] **Step 6 : Faire déployer par l'utilisateur** A2 et A6 (`PUT` dans Dev Tools depuis le `.console` généré), puis « Update API keys » (mémoire de session : une règle poussée par API tourne avec la clé de l'appelant).
- [ ] **Step 7 : Commit**

```bash
git add docs/observabilite/supervision/
git commit -m "feat(supervision): dashboard Redis et renvoi des alertes A2 et A6 vers les bases"
```

### Task 8: Perf

**Files:**
- Modify: `elastic-agent/README.md`

**Interfaces:**
- Consumes : tout ce qui précède ; addons de perf : PG `ad-c0724c96-5896-48be-a772-854e5e649818`, Redis api `ad-cb98c1a9-b97b-4382-ab13-bc69dafc8235`, Redis connect à relever (`scalingo --app pass-emploi-connect-perf addons`).

- [ ] **Step 1 : Pendant un tir** (apps de perf démarrées), reproduire les tâches 3 à 5 sur `pass-emploi-elastic-agent-perf` et sa policy : mêmes intégrations, state CEL avec les quotas de perf (PG 10 Go / 30 connexions, Redis api 5 Go).
- [ ] **Step 2 : Vérifier** les 2 dashboards avec le contrôle d'environnement sur perf.
Expected : données pendant le tir.
- [ ] **Step 3 : Vérifier l'arrêt** (Review Focus 5) : apps et agent de perf arrêtés, les dashboards sur perf s'affichent sans erreur (panneaux vides), et l'alerte 8 de la stack ne sonne pas pour un agent de perf volontairement arrêté (cf. `pilotage.md`).
- [ ] **Step 4 : Documenter et commit**

```bash
git add elastic-agent/README.md
git commit -m "feat(elastic-agent): supervision des bases de perf"
```
