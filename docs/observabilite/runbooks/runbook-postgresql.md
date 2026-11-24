# Runbook — PostgreSQL : transaction longue et verrous

> **Type** : tutoriel (Diataxis). Quoi faire quand le panneau « Verrous et
> transactions longues » du dashboard [[Pass Emploi] Bases de données - PostgreSQL](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/66b0c0ac-d034-489b-ab0a-7b07539074ff)
> monte : une transaction reste ouverte, des sessions attendent un verrou.
>
> Collecte et requêtes : [`kibana/agents/`](../../../kibana/agents/README.md).

Une transaction ouverte bloque le vacuum et peut bloquer les écritures des autres
sessions : les requêtes de l'api s'empilent, puis échouent sur leur délai.

## 1. Voir qui bloque qui, dans le dashboard

1. **« Verrous et transactions longues »** : quand, combien de temps, combien de
   sessions en attente.
2. **« Qui bloque qui »** : une flèche va de la session qui bloque vers celle qui
   attend. Survoler une session donne son modèle de requête (sans valeur), son
   état et sa durée ; survoler une flèche, le verrou attendu et sa durée.
3. **« Sessions qui en bloquent d'autres »** : les bloqueurs, triés par nombre de
   sessions bloquées.

Lecture :

| Ce qu'on voit | Ce que ça veut dire |
|---|---|
| bloqueur `idle in transaction` | l'app a ouvert une transaction et ne la termine pas : son dernier modèle de requête et son application désignent le code en cause |
| bloqueur `active`, longue transaction | une requête lourde (job, migration) tient ses verrous jusqu'à sa fin |
| session en pointillés, « non visible » | le bloqueur est la session d'un autre utilisateur de la base (console, outil) : la supervision, qui n'a pas `pg_monitor`, ne voit que les sessions de l'utilisateur de l'app |
| « modèle inconnu (requête en cours) » | `pg_stat_statements` n'enregistre une requête qu'une fois terminée |

## 2. Confirmer en direct (si le blocage dure)

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

## 3. Décider

- **Le bloqueur fait un travail attendu** (job, migration) et va finir : attendre,
  en surveillant les erreurs de l'api.
- **Le bloqueur est bloqué ou oublié** (`idle in transaction` qui dure, console
  restée ouverte) : annuler sa requête, puis, en dernier recours, couper sa session.
  Sa transaction est annulée et son travail en cours perdu.
  ```sql
  SELECT pg_cancel_backend(<pid>);     -- annule la requête en cours
  SELECT pg_terminate_backend(<pid>);  -- coupe la session et annule la transaction
  ```
- **Après coup** : retrouver le code d'où vient le modèle de requête du bloqueur
  (transaction non fermée, appel lent dans une transaction) et l'ouvrir en ticket.

## Limites

- Un blocage de moins d'une minute peut passer entre deux relevés.
- Le graphe montre toutes les bases supervisées de la période : le sélecteur
  « Base » ne s'applique qu'au tableau des bloqueurs.
