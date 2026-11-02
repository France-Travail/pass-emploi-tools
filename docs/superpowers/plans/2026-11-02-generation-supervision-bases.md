# Dashboards des bases enrichis et configuration Fleet générée — plan de réalisation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** enrichir les dashboards des bases (pratiques d'investigation, index, entretien, verrous, swap, certificat), puis générer depuis le repo la configuration Fleet de l'agent dédié et les dashboards, avec garde-fous, testés sur la perf puis repris en prod.

**Architecture:** un fichier `bases.json` (liste finie de valeurs) et des gabarits produisent, sans réseau ni secret, les intégrations Fleet de chaque environnement dans `generated/` ; une commande `pousser` lit Scalingo et écrit dans Fleet ; une commande `verifier` compare Fleet au généré. Le générateur des dashboards suit le même modèle. Garde-fous : régénération dans le check CI existant, et un nouveau workflow de vérification contre la prod.

**Tech Stack:** Python 3 (bibliothèque standard, `unittest`), API Fleet de Kibana, API Scalingo et API des bases Scalingo, ES|QL, Lens, CEL (`mito`), GitHub Actions.

**Spec:** [`docs/superpowers/specs/2026-11-02-generation-supervision-bases-design.md`](../specs/2026-11-02-generation-supervision-bases-design.md) (suite de `2026-10-30-supervision-bases-de-donnees-design.md`).

## Global Constraints

- Aucune donnée du client du support d'audit (noms, tables, chiffres) dans le repo, un commit ou un message.
- Aucun secret dans le repo, `generated/`, une sortie de script ou un log ; les mots de passe vont directement dans les secrets Fleet.
- Aucune nouvelle alerte.
- Les actions de prod (Fleet en écriture, Dev Tools, conteneurs, logs) sont lancées par l'utilisateur ; la session prépare et vérifie.
- Modèle des générateurs : `docs/observabilite/supervision/workflows/tchap/` (configuration JSON, gabarits dans `modeles/` avec repères `@@NOM@@`, avertissement en tête de chaque fichier généré, sortie commitée dans `generated/`).
- La génération ne dépend ni du réseau ni d'un secret (jouée par la CI).
- La poussée ne touche que les intégrations qu'elle génère (par nom), ne supprime jamais rien ; les intégrations de la stack (`redis-logstash-<env>`, `scalingo-container-stats-<env>`, `elastic-agent-system-<env>`) restent hors du script.
- Policies Fleet : prod `9d009fa8-7a42-418c-ad47-ef1ceb196552`, perf `6eee0d15-68d9-4135-96fe-e20d467f0042`. Paquets installés : `redis` 1.21.2, `postgresql` 1.32.1, `sql` 1.2.0, `cel` 1.21.0.
- Noms des intégrations générées : `redis-<base>-<env>` (`redis-api-prod`, `redis-connect-prod`), `postgresql-<base>-<env>`, `postgresql-<requete>-<env>` (`statements`, `index-stats`, `table-stats`, `index-hygiene`, `activite`), `scalingo-database-stats-<env>` — ceux de prod existent déjà et sont repris tels quels.
- Chaque document collecté porte `labels.base` = nom de la base (`postgresql-api-prod`, `redis-api-prod`, `redis-connect-prod`, `…-perf`).
- Critères relatifs dans l'encadré et les tableaux ; les repères du support (1 000 lignes par scan, 10 %, 5 à 15 index, 1 Go) seulement comme indicatifs.
- Bases de perf : PostgreSQL `ad-c0724c96-5896-48be-a772-854e5e649818` (10 Go, 30 connexions), Redis api `ad-cb98c1a9-b97b-4382-ab13-bc69dafc8235` (5 Go), Redis connect `ad-8209e500-8257-4bc5-bd9c-bf6120606e9f` (5 Go).
- Autorité de certification : `https://db-api.osc-secnum-fr1.scalingo.com/api/ca_certificate`.
- Règles de commentaires et de doc de `docs/CONTEXTE-TRANSVERSE.md`. Chaque commit se termine par `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Intégration saisie à la main en prod sous le même nom** : la poussée la met à jour, ne crée pas de doublon, ne perd pas son secret si le mot de passe est inchangé → test dans la tâche 7.
2. **Variable Scalingo absente ou URL inattendue** (`rediss://`, sans mot de passe) : erreur explicite pour cette base, rien poussé pour elle, les autres continuent → test dans la tâche 7.
3. **Mot de passe dans un message d'erreur** (exception qui affiche une URL) : jamais affiché → test dans la tâche 7.
4. **Génération non déterministe** (ordre des clés, horodatage) : deux générations successives identiques → test dans la tâche 6.
5. **Dashboards avant la poussée** : un dashboard qui filtre sur `labels.base` est vide tant que la poussée n'a pas eu lieu → ordre de déploiement fixé dans les tâches 10 et 11, et vérification dans la tâche 8.

---

## Partie 1 — Ajouts aux dashboards

### Task 1: Requêtes SQL enrichies

**Files:**
- Modify: `elastic-agent/integrations/postgresql/index_stats.sql`, `table_stats.sql`, `verifier.sh`
- Create: `elastic-agent/integrations/postgresql/index_hygiene.sql`, `activite.sql`
- Modify: `docs/observabilite/stockage/metriques/2-component-templates.console`, `3-index-templates.console`, `README.md`

**Interfaces:**
- Produces (colonnes ajoutées, consommées par la tâche 3) :
  - `index_stats.sql` : `idx_tup_read`, `idx_tup_fetch`, `taille_table_octets`.
  - `table_stats.sql` : `n_dead_tup`, `n_mod_since_analyze`, `last_analyze`, `last_autoanalyze`, `last_vacuum`, `last_autovacuum` (dates en texte ISO, `jamais` si nulles), `n_tup_ins`, `n_tup_upd`, `n_tup_del`.
  - `index_hygiene.sql` (une ligne par index) : `schema`, `table`, `index`, `valide` (`indisvalid and indisready`), `doublon_de` (nom de l'index identique ou qui le contient, sinon vide), `index_de_la_table` (nombre), `taille_index_octets`, `taille_table_octets`, `taille_index_table_octets`.
  - `activite.sql` (une ligne par relevé) : `plus_vieille_transaction_s`, `sessions_idle_in_transaction`, `sessions_en_attente_verrou`, `plus_longue_attente_verrou_s`.
  - Data streams `metrics-sql.postgresql_index_hygiene-default` et `metrics-sql.postgresql_activite-default`, en `metrics-fleet-retention`, types explicites.
- Schémas PostGIS exclus partout (`tiger`, `tiger_data`, `topology`), comme aujourd'hui.

- [ ] **Step 1 : Étendre `verifier.sh`** : vérifier la présence des colonnes ci-dessus dans l'en-tête de chaque fichier et l'existence des deux nouveaux fichiers.
- [ ] **Step 2 : Lancer sur staging** (`.superpowers/sdd/2026-10-30-supervision-bases-de-donnees/lancer-staging.sh`, à recréer si absent : archive du dossier, `scalingo --region osc-fr1 run --detached`, sortie par `logs --filter`). Expected : `VERIFICATION_KO`, colonnes et fichiers absents.
- [ ] **Step 3 : Écrire les requêtes.** `activite.sql` filtre `pg_stat_activity` sur `datname = current_database()` et `usename = current_user` (seules lignes lisibles sans `pg_monitor`).
- [ ] **Step 4 : Relancer sur staging.** Expected : `VERIFICATION_OK`, chaque requête en moins de 2 s.
- [ ] **Step 5 : Donner à l'utilisateur la commande prod**, interactive (`scalingo --app pass-emploi-api-prod run "…"`, sans `--detached`), et lire la sortie qu'il colle. Expected : `VERIFICATION_OK`.
- [ ] **Step 6 : Briques de rétention** des deux nouveaux data streams (types explicites, comme `metrics-sql.postgresql_statements@custom`), colonnes ajoutées aux briques existantes, `_rollover`, tableau du README de `stockage/metriques/`.
- [ ] **Step 7 : Commit**

```bash
git add elastic-agent/integrations/postgresql/ docs/observabilite/stockage/metriques/
git commit -m "feat(elastic-agent): sélectivité, hygiène des index, entretien des tables, verrous"
```

### Task 2: Date d'expiration de l'autorité dans le CEL

**Files:**
- Modify: `elastic-agent/integrations/scalingo-database-stats.cel`, `elastic-agent/integrations/tests/test_scalingo_database_stats.py`, `docs/observabilite/stockage/metriques/2-component-templates.console`, `elastic-agent/README.md`

**Interfaces:**
- Consumes : clé d'état `ca_expire_le` (date ISO 8601, optionnelle).
- Produces : champ `scalingo.database.ca_expire_le` (type `date`) sur chaque document de métriques.

- [ ] **Step 1 : Test `test_date_d_expiration_de_l_autorite`** : avec `ca_expire_le: "2037-07-29T09:57:55Z"` dans l'état, chaque document porte `scalingo.database.ca_expire_le == "2037-07-29T09:57:55Z"` ; sans la clé, le champ est absent.
- [ ] **Step 2 : Lancer.** Run : `MITO=<mito> python3 -I -m unittest discover -s elastic-agent/integrations/tests -v`. Expected : FAIL (`KeyError`). `mito` se compile comme vendredi (`docker run … golang:1.24 … GOTOOLCHAIN=auto go install github.com/elastic/mito/cmd/mito@v1.28.1`), hors du repo.
- [ ] **Step 3 : Ajouter le champ** avec `.with(has(state.ca_expire_le) ? … : {})`.
- [ ] **Step 4 : Relancer.** Expected : tous PASS.
- [ ] **Step 5 : Mapping `date`** dans `logs-scalingo.database_stats@custom`, doc du README, commit.

### Task 3: Dashboards enrichis

**Files:**
- Modify: `.superpowers/sdd/2026-10-30-supervision-bases-de-donnees/generer_dashboards.py` (encore jetable, versionné à la tâche 8)
- Modify: `docs/observabilite/supervision/dashboards/dashboard-bases-de-donnees.ndjson`, `docs/observabilite/supervision/tests/test_dashboards_bases_de_donnees.py`

**Interfaces:**
- Consumes : colonnes des tâches 1 et 2.
- Produces : panneaux nommés exactement « Investiguer » (Markdown, en tête des deux dashboards), « Sélectivité des index », « Hygiène des index », « Entretien des tables », « Verrous et transactions longues », « Swap des nœuds de données », « Certificat de l'autorité ». Panneau texte : `type: markdown`, `embeddableConfig: {content, settings}` (format du dashboard « Diagnostic d'erreurs - Entrée »).

- [ ] **Step 1 : Tests** dans `test_dashboards_bases_de_donnees.py` :
  - `test_encadre_investiguer_en_tete` : premier panneau de chaque dashboard (plus petit `gridData.y`, puis `x`) de type `markdown`, titre « Investiguer », 10 lignes de liste au plus.
  - `test_panneaux_d_investigation_presents` : les titres ci-dessus présents dans le dashboard PostgreSQL ; « Swap des nœuds de données » et « Certificat de l'autorité » aussi dans Redis.
  - `test_aucune_donnee_du_support` : aucun mot du support propre au client (liste fournie par l'utilisateur au step 2, hors repo, passée par variable d'environnement `MOTS_INTERDITS` ; test ignoré si elle est absente).
- [ ] **Step 2 : Lancer.** Expected : FAIL.
- [ ] **Step 3 : Écrire les panneaux.** Encadré PostgreSQL : les 8 points du §4.1 de la spec, en critères relatifs, chacun nommant son tableau. Sélectivité : lignes lues par scan face à `n_live_tup` de la table, part récupérée, seuil « peu utilisé » sur l'écart de `idx_scan` de la période. Entretien : tri par part de lignes mortes puis par ancienneté du dernier `ANALYZE`. Verrous : courbes de `activite.sql` et deadlocks (`postgresql.database.deadlocks`, cumul). `stats_reset` de `pg_stat_statements` dans la description des tableaux de requêtes. Mémoire : description du 100 % nocturne.
- [ ] **Step 4 : Générer** (clé de lecture), puis relancer les tests. Expected : PASS ; le générateur ne signale aucune requête invalide.
- [ ] **Step 5 : Commit** du `.ndjson` et du test.

### Task 4: Déploiement des ajouts en prod (à la main, pour la dernière fois)

**Files:**
- Modify: `elastic-agent/README.md` (nouvelles intégrations SQL Input)

- [ ] **Step 1 : Fiche pour l'utilisateur** (hors repo, en texte brut) : briques et `_rollover` à exécuter, requêtes à remplacer (`postgresql-index-stats-prod`, `postgresql-table-stats-prod`), deux SQL Input à créer (`postgresql-index-hygiene-prod`, période `1d` ; `postgresql-activite-prod`, période `1m`), programme et état du CEL (avec `ca_expire_le`), dashboards à réimporter.
- [ ] **Step 2 : Vérifier** après ses saisies : les 7 flux arrivent, types conformes, aucune erreur de collecte, CEL de Fleet identique au repo.
Expected : `verif` (requête ES|QL et comparaison Fleet en lecture) sans écart.
- [ ] **Step 3 : Commit** du README.

## Partie 2 — Configuration générée

### Task 5: Sources Fleet dans `supervision/agents/`

**Files:**
- Move: `elastic-agent/integrations/` → `docs/observabilite/supervision/agents/integrations/`
- Create: `docs/observabilite/supervision/agents/README.md` (partie Fleet de `elastic-agent/README.md`)
- Modify: `elastic-agent/README.md` (garde l'app : déploiement, variables, `start.sh` ; un titre « Mémoire des conteneurs Scalingo (intégration Custom API) » qui renvoie au nouvel emplacement), liens dans `docs/observabilite/collecte/metriques/stack-observabilite.md`, `infrastructure.md`, `pilotage.md`, `process/logs/performances.md`, `stockage/metriques/2-component-templates.console`, **`docs/decisions/ADR-003-usage-log-drain-scalingo.md`** (lien vers la nouvelle section)

- [ ] **Step 1 : Test** `test_liens_vers_elastic_agent` (dans `supervision/tests/`) : tout lien Markdown relatif du repo qui vise `elastic-agent/` ou `supervision/agents/` pointe vers un fichier existant, et son ancre vers un titre existant.
- [ ] **Step 2 : Lancer.** Expected : PASS avant le déplacement (le test est un garde-fou ; le voir échouer après un `git mv` partiel au step 3).
- [ ] **Step 3 : `git mv`**, mise à jour des liens, du chemin dans le docstring des tests CEL.
- [ ] **Step 4 : Relancer** les tests du lien, des générateurs et du CEL. Expected : tous PASS.
- [ ] **Step 5 : Commit.**

### Task 6: Générateur hors ligne des intégrations

**Files:**
- Create: `docs/observabilite/supervision/agents/bases.json`, `agents/policies.json`, `agents/modeles/` (`commun/avertissement-fichier-genere.json`, `redis.json`, `postgresql.json`, `sql.json`, `cel-database-stats.json`), `agents/generer-integrations.py`, `agents/generated/<env>/<nom>.json`
- Test: `docs/observabilite/supervision/tests/test_generateur_integrations.py`

**Interfaces:**
- `bases.json` : `{"<env>": {"<app>": ["postgresql" | "redis", …]}}`, avec `prod` et `perf`.
- `policies.json` : `{"<env>": "<id de policy>"}`.
- `generer(dossier_sortie: str) -> list[str]` (chemins écrits) ; ligne de commande `python3 -I generer-integrations.py`.
- Chaque fichier généré : le corps de `POST /api/fleet/package_policies` (nom, `policy_ids`, `package` nom et version, `inputs` complets) avec les repères `@@HOTE@@`, `@@PORT@@`, `@@UTILISATEUR@@`, `@@MOT_DE_PASSE@@`, `@@SSL@@`, `@@ADDON_ID@@`, `@@QUOTA_DISQUE_OCTETS@@`, `@@CONNEXIONS_MAX@@`, `@@CA_EXPIRE_LE@@`, `@@API_TOKEN@@` laissés tels quels, et un processeur `add_fields` posant `labels.base`.
- Nom de base : `<type>-<app sans pass-emploi- ni -<env>>-<env>` (`redis-api-prod`, `postgresql-api-perf`).

- [ ] **Step 1 : Tests** :
  - `test_genere_les_integrations_de_prod_attendues` : pour la config actuelle, prod donne exactement `redis-api-prod`, `redis-connect-prod`, `postgresql-api-prod`, `postgresql-statements-prod`, `postgresql-index-stats-prod`, `postgresql-table-stats-prod`, `postgresql-index-hygiene-prod`, `postgresql-activite-prod`, `scalingo-database-stats-prod`.
  - `test_requetes_sql_reprises_des_fichiers` : la requête de chaque SQL Input est le contenu exact de son `.sql`.
  - `test_aucun_secret_ni_hote` : aucun fichier généré ne contient `://`, `scalingo-dbs.com`, `dbs.scalingo.com` ni de valeur à la place d'un repère.
  - `test_generation_deterministe` (Review Focus 4) : deux générations dans deux dossiers temporaires donnent des fichiers identiques octet pour octet.
  - `test_type_de_base_inconnu` : `"mysql"` dans `bases.json` → sortie en erreur, message qui nomme l'app et le type, aucun fichier écrit.
  - `test_fichiers_generes_a_jour` : régénérer dans une copie donne exactement `generated/`.
- [ ] **Step 2 : Lancer.** Expected : FAIL (générateur absent).
- [ ] **Step 3 : Écrire le générateur et les gabarits**, en reprenant les réglages actuels de prod (lus dans Fleet en lecture : périodes, datasets, `statement` désactivé, logs désactivés, slowlogs désactivés, `key` seulement pour le Redis de l'api avec les 5 files Bull).
- [ ] **Step 4 : Relancer.** Expected : PASS.
- [ ] **Step 5 : Commit** (générateur, gabarits, configuration, `generated/`, tests).

### Task 7: Poussée et vérification

**Files:**
- Create: `docs/observabilite/supervision/agents/fleet.py` (client Fleet), `agents/scalingo.py` (client Scalingo)
- Modify: `agents/generer-integrations.py` (sous-commandes `pousser --env <env>`, `verifier --env <env>`)
- Test: `docs/observabilite/supervision/tests/test_pousser_integrations.py`, faux serveurs dans `supervision/tests/faux_fleet.py` (et le faux Scalingo existant, étendu)

**Interfaces:**
- `pousser(env: str) -> int` (code de sortie) : variables `SCALINGO_API_TOKEN`, `KIBANA_URL`, `ES_API_KEY` ; lit addons, variables (`SCALINGO_POSTGRESQL_URL`, `SCALINGO_REDIS_URL`), plans, Force TLS, date de l'autorité ; remplit les repères en mémoire ; met à jour par nom (`PUT /api/fleet/package_policies/<id>`) ou crée (`POST`) ; n'appelle jamais `DELETE`.
- `verifier(env: str) -> int` : variables `KIBANA_URL`, `ES_API_KEY` (lecture) ; compare chaque intégration générée à Fleet (hors secrets et valeurs remplies à la poussée) ; liste les intégrations de la policy non gérées, sans échec.

- [ ] **Step 1 : Tests** :
  - `test_met_a_jour_l_integration_existante_par_son_nom` (Review Focus 1) : Fleet a déjà `redis-api-prod` → un `PUT` sur son id, aucun `POST`.
  - `test_cree_l_integration_absente` : `POST` avec `policy_ids` de l'environnement.
  - `test_ne_supprime_jamais` : aucun appel `DELETE`, même si Fleet a une intégration absente du généré.
  - `test_variable_absente_isole_la_base` (Review Focus 2) : `SCALINGO_REDIS_URL` absente pour connect → code de sortie 1, message nommant la base, les autres bases poussées.
  - `test_mot_de_passe_jamais_affiche` (Review Focus 3) : avec un mot de passe `s3cr3t-test`, ni la sortie standard ni l'erreur ne le contiennent, y compris quand Fleet répond 400.
  - `test_verifier_signale_un_ecart` : programme CEL différent dans Fleet → code 1, nom de l'intégration ; identique → code 0 ; intégration non gérée → listée, code 0.
- [ ] **Step 2 : Lancer.** Expected : FAIL.
- [ ] **Step 3 : Écrire les clients et les sous-commandes** (bibliothèque standard, `urllib`) ; le mot de passe passe en valeur des variables `password` de Fleet, que Fleet stocke en secret.
- [ ] **Step 4 : Relancer.** Expected : PASS.
- [ ] **Step 5 : `verifier --env prod`** (clé de lecture). Expected : écarts limités à ceux attendus (`labels.base`, intégrations encore saisies à la main) ; les noter.
- [ ] **Step 6 : Doc** (`agents/README.md` : ajouter une base, relancer après un mot de passe changé, clés nécessaires), commit.

### Task 8: Générateur des dashboards versionné

**Files:**
- Create: `docs/observabilite/supervision/dashboards/generer-dashboards-bases.py`, `dashboards/modeles/bases/` (encadrés Markdown en fichiers `.md`, gabarit de dashboard)
- Modify: `dashboards/dashboard-bases-de-donnees.ndjson` (généré), `supervision/tests/test_dashboards_bases_de_donnees.py`

**Interfaces:**
- Consumes : `agents/bases.json` (sélecteurs de base et d'environnement), `labels.base`.
- Ligne de commande : `generer-dashboards-bases.py` (hors ligne, colonnes déclarées dans le script) ; `generer-dashboards-bases.py --valider` (exécute chaque requête contre Elasticsearch, `ES_URL`, `ES_API_KEY`).

- [ ] **Step 1 : Tests** : `test_dashboards_generes_a_jour` (régénérer donne le `.ndjson` versionné), `test_aucune_adresse_de_base_en_dur` (aucun `scalingo-dbs.com`, `dbs.scalingo.com`, `pa-back-prod`, `pass-emploi-connect-3919`), `test_selecteurs_issus_de_bases_json`.
- [ ] **Step 2 : Lancer.** Expected : FAIL.
- [ ] **Step 3 : Reprendre le générateur jetable**, remplacer la découverte des colonnes par des déclarations, remplacer la correspondance adresse → base par `labels.base`, l'encadré par les fichiers `.md`.
- [ ] **Step 4 : Relancer**, puis `--valider`. Expected : PASS ; aucune requête invalide (les panneaux sur `labels.base` sont vides avant la poussée : attendu, cf. tâches 10 et 11).
- [ ] **Step 5 : Supprimer le générateur jetable** de `.superpowers/`, commit.

### Task 9: Garde-fous CI

**Files:**
- Modify: `.github/workflows/elastic-rules-and-workflows-checks.yml`
- Create: `.github/workflows/verification-supervision-bases.yml`

- [ ] **Step 1 : Check existant** : une étape « Intégrations Fleet et dashboards des bases à jour » qui lance les deux générateurs hors ligne puis échoue sur `git diff --exit-code` ou des fichiers non suivis dans `agents/generated/` et sur le `.ndjson`, comme l'étape des Workflows Tchap.
- [ ] **Step 2 : Nouveau workflow** : `on: pull_request` (chemins `docs/observabilite/supervision/agents/**`, `docs/observabilite/supervision/dashboards/**`) et `schedule` quotidien ; lance `generer-dashboards-bases.py --valider` et `generer-integrations.py verifier --env prod` ; secrets `ELASTICSEARCH_API_KEY_RESTRICTED_READ_ONLY`, variables `ES_URL`, `KIBANA_URL`.
- [ ] **Step 3 : Vérifier** : une PR de test qui modifie un `.sql` sans régénérer fait échouer le check ; le workflow de vérification passe avec la clé de l'utilisateur (il la crée en lecture seule, données et Fleet, et la pose dans les secrets GitHub).
- [ ] **Step 4 : Commit.**

### Task 10: Perf par le script

- [ ] **Step 1 : L'utilisateur** déploie la branche sur `pass-emploi-elastic-agent-perf`, pose `POSTGRESQL_CA_CERT_BASE64`, crée la clé Fleet en écriture, lance `pousser --env perf`.
Expected : 9 intégrations créées, code 0.
- [ ] **Step 2 : Démarrer l'agent de perf** quelques minutes ; vérifier les flux de perf, `labels.base` présent, aucune erreur de collecte, dashboards en environnement perf.
- [ ] **Step 3 : Arrêter l'agent de perf** ; `verifier --env perf`. Expected : code 0.

### Task 11: Prod reprise par le script

- [ ] **Step 1 : L'utilisateur** lance `pousser --env prod`. Expected : mises à jour par nom, aucune création en double, code 0.
- [ ] **Step 2 : Vérifier** : `verifier --env prod` à 0 ; CEL de Fleet identique au repo ; `labels.base` présent sur les flux de prod.
- [ ] **Step 3 : Réimporter les dashboards générés** (après la poussée : ils filtrent sur `labels.base`), contrôle visuel par l'utilisateur.
- [ ] **Step 4 : Doc** : `elastic-agent/README.md` et `agents/README.md` à jour, procédure manuelle retirée ; commit.
