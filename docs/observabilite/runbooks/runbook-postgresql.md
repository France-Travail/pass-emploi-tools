# Runbook — PostgreSQL : verrous, transactions longues et saturation

> **Type** : tutoriel (Diataxis). Quoi faire quand le panneau « Verrous et
> transactions longues » du dashboard [[Pass Emploi] Bases de données - PostgreSQL](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/66b0c0ac-d034-489b-ab0a-7b07539074ff)
> monte : une transaction reste ouverte, des sessions attendent un verrou.
>
> Collecte et requêtes : [`kibana/agents/`](../../../kibana/agents/README.md).

## Comprendre en deux minutes

- **Session** : une connexion de l'api (ou d'une console) à la base. Elle a un
  numéro, le `pid`. L'api en ouvre plusieurs, par son pool de connexions Sequelize.
- **Transaction** : un groupe de requêtes qui réussissent ou échouent ensemble
  (`BEGIN` … `COMMIT`). Dans l'api, c'est le bloc `sequelize.transaction(async
  transaction => { … })` : la transaction reste ouverte **tant que le bloc n'est
  pas terminé**, y compris pendant un `await` sur autre chose que la base.
- **Verrou** : une ligne modifiée (`UPDATE`, `DELETE`, `SELECT … FOR UPDATE`) est
  verrouillée jusqu'à la **fin de la transaction**, pas jusqu'à la fin de la
  requête. Une autre session qui veut modifier la même ligne **attend**, sans
  erreur, jusqu'à ce que la première termine.
- **Blocage** : la session A tient un verrou, B attend A. Si C attend B, c'est une
  chaîne : un seul bloqueur peut immobiliser beaucoup de requêtes de l'api, qui
  finissent par échouer sur leur délai.
- **Deadlock** : A attend B et B attend A. PostgreSQL le détecte en environ une
  seconde et annule l'une des deux transactions (erreur `deadlock detected` dans
  l'api). Il se compte dans « Deadlocks (cumul) », pas dans le graphe.
- **Pourquoi une longue transaction gêne même sans bloquer** : tant qu'elle est
  ouverte, le vacuum ne peut pas nettoyer les lignes mortes créées depuis son
  début ; les tables grossissent et ralentissent.

## 1. Lire le dashboard

1. **« Verrous et transactions longues »** répond à *quand* et *combien* : âge de
   la plus vieille transaction ouverte, sessions « idle in transaction »,
   sessions qui attendent un verrou.
2. **« Qui bloque qui »** répond à *qui* : un cercle par session, une flèche de la
   session qui bloque vers celle qui attend.
   - couleur : rouge = bloqueur, orange = bloqué, orange foncé = les deux (milieu
     d'une chaîne) ;
   - taille : plus le cercle est grand, plus la session tient sa transaction (ou
     attend) depuis longtemps ;
   - **survoler une session** : son modèle de requête (la requête sans ses valeurs,
     `$1`, `$2` à leur place), son état, son application, sa durée ;
   - **survoler une flèche** : le verrou attendu et sa durée ;
   - cercle en pointillés : le bloqueur est une session d'un autre utilisateur de
     la base (console, outil). La supervision ne voit pas son détail.
3. **« Sessions qui en bloquent d'autres »** : les mêmes bloqueurs en tableau,
   triés par nombre de sessions bloquées. Commencer par le premier : c'est
   souvent le seul à traiter.

**Exemple de lecture** : un cercle rouge, état `idle in transaction`, transaction
ouverte depuis 220 s, modèle `UPDATE "jeune" SET … WHERE "id" = $1`, et dix
flèches vers des sessions orange qui attendent un verrou `transactionid`. Une
transaction de l'api a modifié un jeune, puis s'est mise à attendre autre chose
sans valider : tant qu'elle n'est ni validée ni annulée, personne d'autre ne peut
modifier ce jeune.

## 2. Reconnaître la cause

| Ce que montre le bloqueur | Cause habituelle | Où chercher |
|---|---|---|
| `idle in transaction`, la durée monte | dans un bloc `sequelize.transaction`, un `await` sur autre chose que la base (appel HTTP à un partenaire, file de jobs, boucle de traitement) : la transaction reste ouverte pendant ce temps | le code qui exécute le modèle de requête du bloqueur ; ses appels sortants dans le même bloc |
| `active`, longue transaction | une requête lourde (job, export, migration) qui tient ses verrous jusqu'à sa fin | le Discover « Logs de Prod - Jobs » sur la même période |
| `idle in transaction (aborted)` | une requête de la transaction a échoué et la transaction n'a pas été annulée | l'erreur dans les logs de l'api au moment du début |
| cercle en pointillés | une console ou un outil connecté avec un autre compte | qui a ouvert une console (timeline Scalingo de l'app) |

Le type de verrou, au survol d'une flèche :

| `type_verrou` | Ce qu'on attend |
|---|---|
| `transactionid` | la fin de la transaction qui a modifié la même ligne (le cas le plus courant) |
| `tuple` | une ligne précise, que plusieurs sessions veulent modifier en même temps |
| `relation` | une table entière, souvent une migration (`ALTER TABLE`) ou un `LOCK TABLE` |
| `advisory` | un verrou applicatif posé volontairement par le code |

## 3. Confirmer en direct (si le blocage dure)

La supervision relève une fois par minute. En direct, depuis une console sur la
base (`scalingo --region osc-secnum-fr1 --app <app> pgsql-console`) :

```sql
SELECT pid, pg_blocking_pids(pid) AS bloque_par, state, now() - xact_start AS transaction,
       wait_event_type, wait_event, application_name, left(query, 120) AS requete
FROM pg_stat_activity
WHERE datname = current_database() AND (cardinality(pg_blocking_pids(pid)) > 0 OR xact_start < now() - interval '1 minute')
ORDER BY xact_start;
```

⚠️ La colonne `requete` contient les valeurs réelles : ne pas la copier dans un
ticket ni un salon.

## 4. Décider

- **Le bloqueur fait un travail attendu** (job, migration) et va finir : attendre,
  en surveillant les erreurs de l'api.
- **Le bloqueur est bloqué ou oublié** (`idle in transaction` qui dure, console
  restée ouverte) : annuler sa requête, puis, en dernier recours, couper sa session.
  Sa transaction est annulée et son travail en cours perdu.
  ```sql
  SELECT pg_cancel_backend(<pid>);     -- annule la requête en cours
  SELECT pg_terminate_backend(<pid>);  -- coupe la session et annule la transaction
  ```
  `pg_cancel_backend` n'a pas d'effet sur une session `idle in transaction` (elle
  n'exécute rien) : seul `pg_terminate_backend` la libère.
- **Après coup** : retrouver dans le code le bloc qui exécute le modèle de requête
  du bloqueur, sortir de la transaction ce qui n'est pas une requête à la base, et
  l'ouvrir en ticket.

## 5. La base sature sans bloqueur net

Déclencheurs : alerte Scalingo « High 5xx » ou temps de réponse sur le salon
monitoring-production, des `SequelizeConnectionAcquireTimeoutError` dans les
logs de l'api (pool de connexions épuisé), un worker qui crashe. Le panneau des
verrous monte sans bloqueur qui ressort : la base est lente pour tout le monde.

1. **Ce qui a changé** : déploiements, scale, crashes et alertes de l'app. Les
   heures de la timeline sont en **UTC**.
   ```bash
   scalingo --region osc-secnum-fr1 --app pass-emploi-api-prod timeline
   ```
2. **Ce que fait la base** : les logs de l'addon PostgreSQL portent les requêtes
   de plus de 500 ms (`LOG:  duration:`), la fin de chaque autovacuum
   (`automatic vacuum of table`, avec `elapsed` et le volume de WAL) et les
   requêtes du web annulées par leur timeout
   (`canceling statement due to statement timeout`).
   ```bash
   scalingo --region osc-secnum-fr1 --app pass-emploi-api-prod addons   # id de l'addon PostgreSQL
   scalingo --region osc-secnum-fr1 --app pass-emploi-api-prod --addon <id> logs-archives
   ```
   Chaque tranche donne une URL à télécharger avec `curl`, qui expire en
   quelques minutes : télécharger aussitôt après avoir listé. Seules les 10
   dernières tranches sont proposées (`-p` est sans effet) : pour analyser une
   journée après coup, télécharger le jour même. Les archives arrivent avec
   jusqu'à plus d'une heure de retard ; pour la dernière heure,
   `… --addon <id> logs --lines 50000`. Télécharger dans un répertoire
   temporaire, à supprimer après analyse : les requêtes contiennent des valeurs
   réelles. Chaque ligne commence par l'heure de Paris, le champ `time=` est en
   UTC. Une requête s'étale sur plusieurs lignes, pas forcément dans l'ordre :
   les regrouper par horodatage à la seconde.

   Un autovacuum de plusieurs dizaines de minutes sur une grosse TOAST sature
   les IO disque ; le retour au calme coïncide avec sa fin.
3. **Qui consomme** : `pg_stat_statements` et `pg_stat_user_tables` cumulent
   depuis leur dernière remise à zéro. Une lecture seule ne dit rien : comparer
   deux relevés, ou le delta des datasets `metrics-sql.postgresql_*` dans Kibana
   ([`kibana/agents/`](../../../kibana/agents/README.md)). Les TOAST n'apparaissent
   pas dans `pg_stat_user_tables` : passer par `pg_stat_all_tables` et
   `pg_class.reltoastrelid`. `pgsql-console` est interactive et n'accepte pas de
   requêtes en entrée standard ; pour un script, `db-tunnel` puis un client SQL.
4. **Soulager** : couper les workers arrête **tous** les jobs, crons compris.
   ```bash
   scalingo --region osc-secnum-fr1 --app pass-emploi-api-prod scale worker:0
   ```
   À la reprise, les jobs prévus pendant la coupure partent en retard, et un job
   qui ne traite que les dernières heures avant son exécution en perd une
   partie. Relancer : `scale worker:<n>`.

## Limites

- Un blocage de moins d'une minute peut passer entre deux relevés.
- Les requêtes de moins de 500 ms n'apparaissent pas dans les logs de l'addon.
- Le modèle d'une requête encore en cours est inconnu : `pg_stat_statements` ne
  l'enregistre qu'une fois terminée.
- Le graphe montre toutes les bases supervisées de la période : le sélecteur
  « Base » ne s'applique qu'au tableau des bloqueurs.
