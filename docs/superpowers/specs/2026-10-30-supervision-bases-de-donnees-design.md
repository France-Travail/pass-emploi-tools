# Visualiser dans Kibana l'état des bases de données (PostgreSQL, Redis) — design

> Ticket Notion : « ETQ supports L2/3, je visualise dans Kibana les lenteurs
> applicatives causées par les BDD (Redis, Postgres) ».
> Cadrage du 2026-10-30. Les relevés cités ont été faits ce jour-là.

## 1. Intention

Quand une alerte sonne (5xx, disponibilité, métriques infra), l'équipe support
L2/L3 doit pouvoir répondre vite à une question : **la lenteur vient-elle d'une
base de données, et de laquelle ?**

Elle n'a aujourd'hui qu'une vue partielle :

- côté PostgreSQL, les erreurs Sequelize dans les logs, qui signalent surtout des
  bugs d'implémentation, pas l'état de santé de la base ;
- côté Redis, rien dans Kibana : l'état des Redis applicatifs n'est visible que
  dans le tableau de bord Scalingo, ce qui contredit la règle de centraliser
  l'information dans Kibana.

## 2. Objectifs

Rendre visibles dans Kibana, pour chaque base :

**PostgreSQL** (base de pass-emploi-api)

- mémoire, espace disque, CPU de l'instance ;
- requêtes lentes : moyenne, P95 et P99 (cf. 7.2 pour la forme) ;
- requêtes les plus appelées ;
- requêtes à optimiser : index à ajouter, à modifier ou à supprimer ;
- santé générale : connexions, cache, verrous.

**Redis** (Redis de pass-emploi-api et Redis de pass-emploi-connect)

- état de santé, mémoire ;
- activité inhabituelle (commandes par seconde, clients) ;
- listes qui grossissent anormalement vite ;
- erreurs.

## 3. Non-objectifs et anti-objectifs

- **Aucune nouvelle alerte.** L'équipe réduit le bruit des alertes (point du
  2026-10-28 avec Marie, TL) ; les alertes sur les SLO vont être désactivées, seules
  restent les alertes sur des métriques d'infra. Une alerte de plus serait du
  bruit. Ce projet sert au diagnostic, à partir des alertes existantes.
- **Pas de correction de l'APM de connect.** L'APM de connect ne voit aucun appel
  Redis (relevé du 2026-10-30 : transactions et appels sortants seulement). Pour le
  Redis de connect, on se contente de la version « light », comme pour le Redis de
  Logstash : les métriques de la base, sans la vue côté application.
- **Pas staging** (autre région Scalingo, `osc-fr1` : il faudrait un agent de plus).
- **Pas de passage par Logstash** : la collecte ne doit pas dépendre du log drain ni
  de Logstash, qui ont décroché pendant 25 h lors de l'incident du 23/10/2026.

## 4. Environnements et ordre

1. **Prod** : PostgreSQL et Redis de `pass-emploi-api-prod`, Redis de
   `pass-emploi-connect-prod`.
2. **Perf** ensuite : mêmes bases sur `pass-emploi-api-perf` et
   `pass-emploi-connect-perf` (plans `starter`), utiles pendant les tirs de charge.
   L'agent et les apps de perf sont arrêtés entre deux tirs : les vues n'ont de
   données que pendant un tir.

## 5. Décisions prises avec l'utilisateur

| Sujet | Décision |
|---|---|
| Collecteur | L'Elastic Agent dédié existant, `pass-emploi-elastic-agent-<env>` (Fleet), qui écrit directement dans Elasticsearch. Pas les alertes Scalingo : elles ne portent que sur les conteneurs d'app, pas sur les bases (doc Scalingo). |
| Métriques des instances (CPU, mémoire, disque) | API des bases de Scalingo, `GET https://db-api.osc-secnum-fr1.scalingo.com/api/databases/<id>/metrics` (réponse du support Scalingo du 2026-10-30), lue par une intégration CEL, sur le modèle de `elastic-agent/integrations/scalingo-container-stats.cel`. |
| Token Scalingo | Le token existant du compte personnel de l'utilisateur, déjà utilisé par l'intégration CEL de la mémoire des conteneurs (prod et perf), rangé dans Bitwarden sous « API Token Scalingo pour Elastic ». Il migrera vers un compte technique `@francetravail.fr`, hors de ce projet : ticket Notion [« Email Scalingo - Echéance 17/12/2026 - Créer un compte technique @francetravail.fr avec double authent pour les tokens de supervision »](https://app.notion.com/p/Email-Scalingo-Ech-ance-17-12-2026-Cr-er-un-compte-technique-francetravail-fr-avec-double-authe-4097bd17c27a80f095cfdb6640116864). |
| Utilisateur PostgreSQL | **L'utilisateur de l'app**, sans attendre le support : la réponse de Scalingo sur `pg_monitor` (demandée le 2026-10-30) peut prendre du temps. Si Scalingo l'accorde plus tard, passer à un utilisateur de supervision dédié avec `pg_monitor`. |
| Redis de connect | Version « light » : métriques de la base seulement. |
| Environnements | Prod, puis perf. Pas staging. |
| Requêtes lentes | Deux tableaux côte à côte : moyenne (`pg_stat_statements`) et P95/P99 par table (APM). |
| Utilisateurs | L'équipe de développement, qui assure le support L2/L3 ; tous ont les mêmes droits Kibana que l'utilisateur. Pas de rôle ni d'espace à créer ; le texte des requêtes SQL peut être affiché. |
| Exposition du token | Acceptée par l'utilisateur : son compte personnel est collaborateur complet sur api et connect (prod et perf), son token peut lire leurs variables et déployer, jusqu'à l'arrivée du compte technique. |

## 6. Contraintes constatées

- **Réseau** : l'agent de prod et les bases sont dans la même région
  (`osc-secnum-fr1`) ; l'accès depuis Internet, désactivé sur les bases, n'est pas
  nécessaire (support Scalingo, 2026-10-30). L'agent lit déjà le Redis de
  `pass-emploi-logstash-process-prod` à son adresse interne.
- **Droits Scalingo** : un collaborateur *limited* ne peut pas lire les métriques
  des bases ; le compte du token doit être **collaborateur** sur
  `pass-emploi-api-prod` et `pass-emploi-connect-prod` (et sur leurs équivalents
  de perf). Le token initial doit être celui d'un collaborateur de l'app qui porte
  la base (support Scalingo). Auth de l'API des bases :
  [developers.scalingo.com/databases](https://developers.scalingo.com/databases/index#authentication).
- **Réponse de l'API des métriques** : `cpu_usage`, `memory` (usage, limite, swap,
  maximum atteint), `database_stats.data_size`, `real_disk_size`, et le détail par
  instance (`instances_metrics`). **Pas de limite de disque** dans la réponse.
- **Disque et connexions inclus dans les plans** (description publique des plans,
  `GET https://api.osc-secnum-fr1.scalingo.com/v1/addon_providers/<postgresql|redis>/plans`,
  relevée le 2026-10-30). C'est un **quota facturé au-delà, pas une limite
  dure** : le dépassement est facturé au Go-heure.

  | Base | Plan | RAM | Disque inclus | Connexions max |
  |---|---|---|---|---|
  | PostgreSQL api prod | `postgresql-business-8192` | 8 Go par nœud (2 nœuds) | 160 Go par nœud | 480 |
  | Redis api prod | `redis-business-8192` | 8 Go par nœud | 160 Go par nœud | — |
  | Redis connect prod | `redis-business-1024` | 1 Go par nœud | 20 Go par nœud | — |
  | PostgreSQL api perf | `postgresql-starter-512` | 512 Mo | 10 Go | 30 |
  | Redis api perf | `redis-starter-256` | 256 Mo | 5 Go | — |

  Les dashboards montrent l'usage face à ces valeurs, posées en constantes (à
  mettre à jour si un plan change).
- **Extensions actives en prod** (console Scalingo, 2026-10-30) : `postgis`,
  `pg_trgm`, `postgis_topology`, `fuzzystrmatch`, `pg_stat_statements`,
  `postgis_tiger_geocoder`, `plpgsql`. Les extensions ne se gèrent que par la
  console interactive distante
  ([doc Scalingo](https://doc.scalingo.com/databases/postgresql/managing#managing-extensions)).
- **`pg_stat_statements`** : installée (1.10) et active en prod comme en staging.
  En prod : 4 934 requêtes suivies, compteurs cumulés depuis le **2026-02-20**
  (pas de remise à zéro depuis). Elle ne calcule **pas de centiles** (moyenne,
  écart-type, min, max, total seulement).
- **Utilisateur de l'app** (`pa_back_pro_817`) : ni superutilisateur ni
  `pg_read_all_stats`. Sans ce droit, un autre utilisateur voit les statistiques
  des requêtes de l'app mais pas leur texte (`<insufficient privilege>`, constaté
  sur staging pour les requêtes d'un autre rôle).
- **Index** : `pg_stat_user_indexes` est lisible ; 92 index n'ont jamais servi en
  prod depuis la remise à zéro des statistiques. Certains garantissent une
  contrainte (clé primaire, unicité) et ne sont pas supprimables.
- **APM de l'api** : instrumente Postgres (`pg` sous Sequelize, environ 10 M
  requêtes par jour, P95 à 89 ms) et Redis (`redis` v5, environ 27 000 appels par
  jour). Le texte SQL est dans `span.db.statement` pour 61 % des spans (le reste
  sans texte) ; `span.name` est grossier (`SELECT FROM "jeune"`). Échantillonnage
  des transactions à 50 %.
- **Intégration Redis** : déjà installée (package 1.21.2), avec les dashboards
  `[Metrics Redis] Overview` et `[Metrics Redis] Keys`. L'input des slowlogs n'a
  pas d'option TLS (désactivé pour le Redis de Logstash, cf.
  `elastic-agent/README.md`) ; TLS n'est pas forcé sur les Redis de l'api et de
  connect.
- **Intégration PostgreSQL** et package **SQL** : non installés.
- **Clés Redis** (recensement en lecture seule sur staging, `SCAN`, le
  2026-10-30 ; la structure des clés est celle du code, les volumes de prod
  diffèrent) :
  - **Redis de l'api** : la file de jobs Bull, `bull:JobQueue:*` (3 361 clés, dont
    3 356 hashes `bull:JobQueue:repeat:…` des jobs récurrents, et les ensembles
    triés `bull:JobQueue:completed` et `bull:JobQueue:failed`). Aucune liste au
    moment du relevé : celles de Bull (`wait`, `active`) n'existent que
    lorsqu'elles contiennent des jobs.
  - **Redis de connect** : les objets d'oidc-provider, `oidc:*` (2 386 clés :
    jetons, sessions, grants). Les listes sont des `oidc:grant:<id>`, une par
    grant (306, 22 éléments au plus) : beaucoup de petites listes, pas une liste
    qui grossit.
  - Les deux en `maxmemory-policy noeviction` sur staging : mémoire pleine = les
    écritures échouent. En prod, `CONFIG GET` est refusé par Scalingo (`unknown
    command 'CONFIG'`) : la politique se lit dans `INFO memory`
    (`maxmemory_policy`), que l'intégration Redis collecte.
  - En prod, `bull:JobQueue:wait` existe bien : 27 jobs en attente au relevé du
    2026-10-30 (`LLEN`, par l'utilisateur).
  - **`INFO memory` du Redis de l'api en prod** (2026-10-30, par l'utilisateur) :
    `maxmemory:0` et `maxmemory_policy:noeviction`, donc **aucune limite côté
    Redis** : la seule limite est celle du conteneur (8 Go du plan). Mémoire
    pleine = conteneur tué par Scalingo, pas une erreur d'écriture propre.
    Utilisée : 369 Mo (RSS 488 Mo) ; **pic à 5,52 Go** depuis le dernier
    démarrage (69 % du plan), date inconnue. `total_system_memory` (39 Go) est
    la mémoire de l'hôte, pas une limite : ne jamais l'afficher comme plafond.
    Le dashboard compare l'usage (RSS) à la limite du conteneur donnée par l'API
    des métriques Scalingo (`memory_limit`).
- **Rétention** : les datasets Fleet doivent recevoir une politique ILM explicite
  (sinon rétention infinie) : procédure de `docs/observabilite/stockage/README.md`,
  « Procédure de contrôle à rejouer après toute nouvelle intégration Fleet » ;
  cible 90 j comme les autres métriques Fleet (`stockage/metriques/README.md`).

## 7. Ce qui est à construire

### 7.1 Collecte (policy Fleet `pass-emploi-elastic-agent-<env>`)

1. **Intégration Redis** : deux nouvelles instances, Redis de l'api et Redis de
   connect.
   - **Api** : dataset `redis.key` sur les clés de la file Bull,
     `bull:JobQueue:wait`, `bull:JobQueue:active`, `bull:JobQueue:delayed`,
     `bull:JobQueue:failed`, `bull:JobQueue:completed` : ce sont elles qui
     « grossissent anormalement » quand les jobs ne sont plus consommés.
   - **Connect** : pas de `redis.key` par grant (une clé par grant, cardinalité
     non bornée en prod). La croissance se suit par le nombre total de clés
     (`redis.keyspace`) et la mémoire.
2. **Intégration PostgreSQL** : métriques de la base, de l'activité et des
   requêtes (`pg_stat_statements`).
3. **Package SQL** : requêtes sur mesure pour les statistiques des tables et des
   index, que l'intégration PostgreSQL ne lit pas.
4. **Intégration CEL** sur l'API des bases de Scalingo : un document par instance
   et par relevé, pour les trois bases.

Les URL des bases sont posées en variables de l'app de l'agent, comme le prévoit
`elastic-agent/README.md` (« Ajout d'un nouveau Redis à monitorer »).

### 7.2 Restitution

- Les dashboards livrés par les intégrations, tels quels.
- **`[Pass Emploi] Bases de données - PostgreSQL`** : santé de l'instance (mémoire,
  disque, CPU, connexions, cache), requêtes lentes en **deux tableaux côte à
  côte** (décision de l'utilisateur, 2026-10-30) : la moyenne par requête
  normalisée d'après `pg_stat_statements`, et les P95/P99 par `span.name` (par
  table) d'après l'APM, sur 21 j au plus (rétention des traces). Pas de
  normalisation du SQL des spans APM. Requêtes les plus appelées,
  requêtes à optimiser (index jamais utilisés hors contraintes, tables surtout lues
  sans index).
- **`[Pass Emploi] Bases de données - Redis`** : les deux Redis applicatifs, avec
  un sélecteur : santé, mémoire, activité, listes, erreurs, CPU et disque de
  l'instance.
- Versionnés en `.ndjson` dans `docs/observabilite/supervision/dashboards/`, comme
  les autres dashboards.

Requêtes « lentes » et « les plus appelées » : les compteurs de
`pg_stat_statements` sont cumulés depuis février ; les vues montrent les **écarts
sur la période choisie** dans Kibana, jamais les valeurs cumulées.

### 7.3 Lien avec les alertes existantes

Aucune règle nouvelle. Les étapes « À vérifier » des règles dont la cause peut être
une base citent les nouveaux dashboards (cf. principes de `alertes-applicatives.md`,
« étapes d'investigation ») : au minimum A2 (`API - Prod - Erreurs 5xx`) et A6
(`API - Prod - Erreurs base de données`), modifiées dans leurs fichiers de `rules/2-applicatives/` puis
régénérées.

### 7.4 Documentation

- `elastic-agent/README.md` : les nouvelles intégrations et variables, dans le
  schéma d'architecture et la policy recommandée ; le programme CEL versionné dans
  `elastic-agent/integrations/`.
- `docs/observabilite/stockage/metriques/README.md` : les nouveaux datasets et leur
  rétention.
- `docs/observabilite/supervision/objets-kibana.md` : les nouveaux dashboards.

## 8. Mes choix (non validés par l'utilisateur)

- Un dashboard Pass Emploi par type de base, plutôt qu'un seul pour toutes.
- Le dashboard Redis couvre les deux Redis avec un sélecteur.
- Rétention de 90 j, alignée sur les métriques Fleet existantes.
- Les règles A2 et A6 comme points d'entrée vers les dashboards.
- Dataset de l'intégration CEL : `scalingo.database_stats`, sur le modèle de
  `scalingo.container_stats`.
- **Volume des statistiques de requêtes** : la prod suit 4 934 requêtes ; une ligne
  par requête et par relevé ferait environ 7 M documents par jour à 1 min. On ne
  collecte donc que les **200 premières requêtes par temps total et les 200
  premières par nombre d'appels**, toutes les **10 min** (requête sur mesure du
  package SQL si le dataset de l'intégration PostgreSQL ne sait pas se limiter),
  soit quelques dizaines de milliers de documents par jour. Rétention 90 j comme le
  reste, à réduire si le volume réel le justifie.
- **Ordre de livraison** : d'abord les intégrations Redis, PostgreSQL et SQL, qui
  ne dépendent pas du token Scalingo ; l'intégration CEL des métriques d'instance en
  dernier. Le compte personnel qui porte le token doit être collaborateur (pas
  *limited*) sur `pass-emploi-api-prod`, `pass-emploi-connect-prod` et leurs
  équivalents de perf : à vérifier avant cette dernière étape. Ce token peut aussi
  lire les variables de ces apps et déployer (cf. 5).

## 9. Laissé au constructeur

- La fréquence des autres relevés que les statistiques de requêtes (celle de la mémoire des conteneurs est de 1 min).
- Ce que l'intégration Redis donne vraiment des « erreurs » (connexions refusées,
  évictions, statistiques d'erreurs du `INFO`), et le complément si besoin.

## 10. Suite, après la livraison

- **`pg_monitor`** : reprendre la demande au support Scalingo (ouverte le
  2026-10-30) et, s'il l'accorde, remplacer l'utilisateur de l'app par un
  utilisateur de supervision dédié.
