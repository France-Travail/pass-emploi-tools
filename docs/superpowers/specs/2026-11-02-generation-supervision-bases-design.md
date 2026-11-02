# Supervision des bases : dashboards enrichis et configuration générée — design

> Suite de `2026-10-30-supervision-bases-de-donnees-design.md` (branche
> `ops/o11y-supervision-bdd`, PR #31). Cadrage du 2026-11-02. À supprimer avec
> l'autre spec et le plan à la fin du chantier (règle de doc n° 1, décision de
> l'utilisateur du 2026-10-30).

## 1. Intention

Deux besoins, dans cet ordre (décision de l'utilisateur) :

1. **Mieux diagnostiquer.** Retour de l'équipe sur la prod : les requêtes les
   plus lentes plaisent ; la mémoire des nœuds Postgres « souvent à 100 % »
   inquiète. L'utilisateur veut aussi que les dashboards reprennent les
   pratiques d'investigation PostgreSQL d'un support d'audit qu'il a réalisé
   pour un client (usage des index). Les pratiques retenues ici sont génériques ;
   **aucune donnée de ce client ne doit apparaître** dans le repo, un commit ou
   un message.
2. **Ne plus configurer Fleet à la main.** Vendredi, la prod a été configurée
   par saisies dans Kibana → Fleet : le README a divergé de la réalité, et le
   programme CEL de prod est resté sur une version antérieure aux corrections
   (constaté le 2026-11-02). Le jour où quelqu'un ajoute une base ou qu'un mot de
   passe change chez Scalingo, il ne doit avoir qu'à **alimenter une liste finie
   de valeurs** (comme `salons.json`) et lancer un script.

## 2. Objectifs, non-objectifs

**Objectifs**

- Les ajouts aux dashboards du §4.
- Un générateur des intégrations Fleet de l'agent dédié, et un générateur des
  dashboards des bases, versionnés avec garde-fous (§5).
- Test sur la perf, puis reprise de la prod par le script (§6).

**Non-objectifs**

- **Aucune nouvelle alerte**, y compris pour l'expiration des certificats
  (décision de l'utilisateur) : information dans les dashboards seulement.
- Pas de provider Terraform : un script Python, sur le modèle existant.
- Pas de déplacement de l'app Scalingo `elastic-agent/` (cf. §5.4).
- Pas d'export de la policy Fleet sans génération : jugé inutile par
  l'utilisateur.

## 3. Constats qui fondent le design (relevés le 2026-11-02)

- **Mémoire des nœuds Postgres** (4 jours) : 100 % surtout entre 1 h et 5 h UTC,
  sur le nœud secondaire bien plus que sur le principal (354 contre 96 minutes),
  CPU du secondaire presque nul, swap stable (57 à 76 Mo). Lecture retenue :
  cache des fichiers lus par les sauvegardes et exports nocturnes, compté dans la
  mémoire du conteneur ; signal d'alarme réel = swap qui monte. (Que Scalingo
  compte le cache dans `memory_usage` n'est pas documenté : supposition.)
- **Swap** : Scalingo le retire des **conteneurs d'application** d'ici fin 2026
  (changelog du 2026-09-02). Rien trouvé pour les bases, qui en ont toujours.
  Conséquence hors de ce chantier : l'alerte `swap` du ticket « Être prévenu
  d'une suspicion d'attaque DDoS… » (apps) est à retirer.
- **Certificats** : l'autorité « Scalingo Databases Certificate Authority »
  (`https://db-api.osc-secnum-fr1.scalingo.com/api/ca_certificate`, la même pour
  `osc-fr1`) expire le **2037-07-29** ; le certificat de chaque serveur, signé par
  elle, a une date inconnue. Les Redis de l'api et de connect n'ont pas Force TLS :
  pas de certificat serveur à lire (ticket TLS des Redis).
- **Toutes les requêtes du support** utilisent des vues lisibles sans
  superutilisateur ni `pg_monitor` (`pg_stat_user_indexes`, `pg_index`,
  `pg_indexes`, `pg_stat_user_tables`, `pg_stat_activity` du rôle courant,
  fonctions de taille). Ne s'appliquent pas : `auto_explain` (droits
  d'administration), tables temporaires ou UNLOGGED, index supprimés avant un
  chargement massif.
- **Ma clé de session est en lecture seule**, et la session n'a pas droit aux
  actions de prod (conteneurs, logs) : l'utilisateur les lance.

## 4. Ajouts aux dashboards (partie 1)

### 4.1 PostgreSQL

1. **Encadré « Investiguer »** en tête (panneau texte Markdown), synthétique,
   chaque point renvoyant à son tableau :
   1. avant de conclure : date de remise à zéro (« Depuis ») et période choisie ;
      un index utilisé par un job mensuel paraît inutile sur une semaine ;
   2. index jamais utilisé : supprimable s'il ne porte aucune contrainte et
      qu'aucune requête du code ne s'en sert ; priorité au-delà de 1 Go ;
   3. index peu sélectif (plus de 1 000 lignes lues par scan, ou moins de 10 %
      des lignes lues récupérées) : colonne mal choisie ;
   4. trop d'index sur une table (au-delà de 5 à 15, ou index plus lourds que la
      table) : coût à l'écriture et au vacuum ;
   5. table lue sans index : `EXPLAIN (ANALYZE)` ; un `Seq Scan` sur une petite
      table est normal ; une écriture se teste entre `BEGIN` et `ROLLBACK` ;
   6. plan qui se dégrade d'un coup : estimations loin du réel ou beaucoup de
      modifications depuis le dernier `ANALYZE` → `ANALYZE` sur la table ;
   7. après une migration : aucun index invalide (`CREATE INDEX CONCURRENTLY`
      interrompu) ;
   8. table lente sans changement de code : son entretien ; lignes mortes
      nombreuses ou `ANALYZE` ancien → `VACUUM (ANALYZE)`.
2. **Sélectivité des index** : `idx_tup_read / idx_scan` et
   `idx_tup_fetch / idx_tup_read` (colonnes ajoutées à `index_stats.sql`), seuils
   du point 3 ; seuil « peu utilisé » (moins de 10 scans sur la période) en plus du
   strict zéro.
3. **Hygiène des index** (nouvelle requête `index_hygiene.sql`, relevée une fois
   par jour) : index invalides (`indisvalid`, `indisready`), en doublon ou inclus
   dans un autre (même table, colonnes en préfixe, même prédicat), nombre d'index
   par table, poids des index face à la table (`pg_indexes_size`, `pg_table_size`).
4. **Entretien des tables** (colonnes ajoutées à `table_stats.sql`) :
   `last_analyze`, `last_autoanalyze`, `n_mod_since_analyze`, `last_vacuum`,
   `last_autovacuum`, `n_dead_tup` face à `n_live_tup` ; tableau trié des tables
   les plus en retard.
5. **Verrous et transactions longues** : deadlocks (déjà collectés par
   l'intégration), plus vieille transaction ouverte et sessions en attente de
   verrou (`xact_start`, `state_change`, `wait_event_type` de `pg_stat_activity`,
   par une nouvelle requête SQL Input ou l'intégration si elle les fournit).
6. **Date de remise à zéro de `pg_stat_statements`** (colonne `stats_reset` déjà
   collectée) affichée à côté des tableaux de requêtes.
7. **Mémoire** : swap affiché à côté, description du 100 % nocturne (§3).
8. **Certificat** : « valide jusqu'au … (dans N jours) » pour l'autorité de
   certification des bases Scalingo seulement (décision de l'utilisateur) ; pas de
   certificat serveur, dont la lecture exigerait un conteneur ponctuel en prod à
   chaque poussée. Un certificat serveur non renouvelé se voit dans « Erreurs de
   collecte ».

### 4.2 Redis

1. Encadré « Investiguer » : mémoire du conteneur seule limite (pas de
   `maxmemory`, `noeviction` : conteneur tué si plein), file Bull qui grossit =
   jobs non consommés, compteurs cumulés à lire à la pente.
2. Swap à côté de la mémoire.
3. Certificat de l'autorité de certification.

### 4.3 Données

Nouvelles colonnes et requêtes validées par `verifier.sh` (lecture seule, en
staging puis en prod par l'utilisateur), briques de rétention à jour
(`stockage/metriques/`). Le test versionné des dashboards
(`supervision/tests/test_dashboards_bases_de_donnees.py`) couvre les ajouts.

## 5. Configuration générée (partie 2)

### 5.1 Ce que l'équipe manipule

Un fichier versionné, liste finie de valeurs (nom à fixer par le constructeur,
par exemple `supervision/agents/bases.json`) : par environnement, les apps et
les types de bases à superviser, et la policy Fleet de l'environnement.

- **Ajouter une base** : une entrée dans ce fichier, régénérer, pousser.
- **Mot de passe changé par Scalingo** : relancer la poussée, sans rien modifier.

### 5.2 Le générateur des intégrations

Sur le modèle de `docs/observabilite/supervision/workflows/tchap/` (consigne de
l'utilisateur) : fichier de configuration, gabarits dans `modeles/` avec repères
`@@NOM@@`, avertissement « fichier généré » en tête de chaque fichier produit,
sortie commitée dans `generated/`.

Trois commandes :

1. **Générer** (sans réseau, sans secret) : les intégrations de chaque
   environnement (Redis, PostgreSQL, SQL Input avec les requêtes versionnées, CEL
   avec son état initial), à partir du fichier, des gabarits, des requêtes SQL et
   du programme CEL. Hôte, port et mot de passe restent des repères.
2. **Pousser** (lancée par l'utilisateur) : lit dans Scalingo l'hôte, le port, le
   mot de passe de chaque base, les identifiants d'addon, les plans (quotas), le
   réglage Force TLS, et la date d'expiration de l'autorité de certification
   (requête HTTP publique) ; remplit les
   repères à la volée ; crée ou met à jour les intégrations par l'API Fleet, les
   mots de passe directement en secrets Fleet. Rien de secret n'est écrit sur
   disque ni affiché.
3. **Vérifier** : compare ce que Fleet exécute à ce qui est généré (requêtes,
   programme, réglages ; pas les secrets).

La date d'expiration de l'autorité passe par l'état initial du CEL, qui l'émet à
chaque relevé (§4.1 point 8) : elle se met à jour à chaque poussée. La poussée ne
lance aucun conteneur.

### 5.3 Le générateur des dashboards

`generer_dashboards.py` et `verif_dashboards.py`, jetables aujourd'hui dans
`.superpowers/sdd/…` (exclu de git), entrent dans le repo sur le même modèle,
avec les ajouts du §4. Le `.ndjson` versionné devient leur sortie.

### 5.4 Emplacement

Les sources Fleet quittent `elastic-agent/` pour
`docs/observabilite/supervision/agents/` (idée de l'utilisateur) : requêtes SQL,
programmes CEL, leurs tests, générateurs, configuration, `generated/`, et la
partie Fleet du README. **L'app Scalingo reste dans `elastic-agent/`**
(`Procfile`, `start.sh`, `tests/test_start.sh`, déploiement) : les apps de prod et
de perf sont déployées avec `PROJECT_DIR=elastic-agent`. Liens à reprendre dans
`docs/observabilite/` ; les deux ADR qui citent `elastic-agent/` sont des traces
datées : leurs liens ne sont pas modifiés (choix par défaut, cf. §8).

### 5.5 Garde-fous

- Une étape du check CI `.github/workflows/elastic-rules-and-workflows-checks.yml`,
  comme « Workflows Tchap et rapports des jobs à jour » : régénère (commande 1 et
  dashboards), échoue sur `git diff --exit-code` ou sur des fichiers générés non
  suivis. Possible parce que la génération ne dépend ni de Scalingo ni d'un
  secret.
- Tests du générateur (fichier de configuration invalide, base inconnue, sortie
  identique aux sources) dans `supervision/tests/`, joués par le même check.

## 6. Déploiement

1. Ajouts du §4 en prod, **à la main, pour la dernière fois** (décision de
   l'utilisateur) : nouvelles colonnes et requêtes saisies dans Fleet, briques de
   rétention, dashboards réimportés. La poussée du §6.4 reprend ensuite ces
   intégrations, et « Vérifier » confirme qu'il ne reste aucun écart.
2. Générateurs (§5).
3. **Perf** : configuration par le script uniquement, agent de perf démarré
   quelques minutes pour vérifier, puis arrêté (arrêté entre deux tirs par
   économie ; les bases de perf tournent en permanence). Bases : PostgreSQL
   `ad-c0724c96-5896-48be-a772-854e5e649818` (starter-512, 10 Go, 30 connexions),
   Redis api `ad-cb98c1a9-b97b-4382-ab13-bc69dafc8235` et Redis connect
   `ad-8209e500-8257-4bc5-bd9c-bf6120606e9f` (starter-256, 5 Go). Agent de perf :
   déployer la branche et poser `POSTGRESQL_CA_CERT_BASE64`.
4. **Prod** reprise par le script, ce qui réaligne le programme CEL ; puis
   « Vérifier » sans écart.

Clé Kibana avec écriture Fleet : créée par l'utilisateur au moment de la
poussée, limitée et de courte durée, gardée de son côté.

## 7. Contraintes

- Aucune donnée du client du support d'audit dans le repo, les commits ou les
  messages.
- Aucun secret dans le repo, `generated/`, les logs ou la sortie du script.
- Les actions de prod (conteneurs, logs, Fleet en écriture) sont lancées par
  l'utilisateur.
- Les règles de commentaires et de documentation de `docs/CONTEXTE-TRANSVERSE.md`.

## 8. Mes choix (non validés par l'utilisateur)

- Un fichier de configuration unique pour tous les environnements.
- Les liens des deux ADR laissés tels quels.
- Seuils de l'encadré repris du support (1 000 lignes par scan, 10 %, 5 à 15
  index, 1 Go) ; seuil « en retard » de l'entretien fixé sur les valeurs réelles
  de prod.

- **Périmètre de la poussée** : seulement les intégrations qu'elle génère,
  reconnues à leur nom. Les intégrations de la stack d'observabilité présentes
  dans la même policy (Redis de Logstash, mémoire des conteneurs Logstash, System)
  restent hors du script : stack et infra applicative sont toujours séparées. La
  poussée ne supprime jamais rien ; « Vérifier » signale ce qu'elle ne gère pas.
- **Génération des dashboards hors ligne** : colonnes et types déclarés dans le
  générateur, régénération jouée par la CI sans Elasticsearch ; une validation à
  part, lancée à la main avec une clé de lecture, exécute chaque requête contre
  les vraies données.
- **Plus de valeurs de prod en dur dans les dashboards** : chaque intégration
  générée ajoute le nom de la base à ses documents (`labels.base`, par un
  processeur) ; les sélecteurs viennent du fichier des bases, les plafonds
  (connexions, disque) des documents CEL. Ajouter une base au fichier suffit à la
  faire apparaître, perf comprise.

## 9. Laissé au constructeur

- Le format exact du fichier de configuration et des gabarits.
- La détection des index en doublon ou inclus.
- La source des verrous (intégration PostgreSQL ou nouvelle requête).
- La façon dont la poussée lit Scalingo et pilote les conteneurs ponctuels.
