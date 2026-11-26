# Post-mortem — Saturation de la base de l'api (24 novembre 2026)

> **Type** : trace datée. Trois épisodes de saturation de la base PostgreSQL de
> `pass-emploi-api-prod` le mardi 24/11/2026, leurs causes, les quatre correctifs
> livrés les 24 et 25/11 et leur effet mesuré le 26/11.
>
> Heures en heure de Paris. Que faire quand ça recommence :
> [runbook PostgreSQL § 5](../../observabilite/runbooks/runbook-postgresql.md#5-la-base-sature-sans-bloqueur-net).

## TL;DR

Le 24/11, la base a saturé trois fois : le matin, en début d'après-midi et en
fin d'après-midi. Chaque fois, l'api a renvoyé des 5xx en rafale. Ce n'est pas
une cause unique, mais trois mécanismes qui s'additionnent :

| Mécanisme | Effet | Correctif |
|---|---|---|
| Cascades de suppression vers des tables sans index sur la clé étrangère | Chaque jeune supprimé par l'archivage de migration parcourt `notification_jeune`, `suggestion`, `communication_envoi` et `liste-de-diffusion-beneficiaire-association` en entier : 12 s et 3,2 M blocs par lot de 100 | #580 : 9 index |
| Autovacuum de la TOAST de `cache_api_partenaire` (15 Go) | Chaque appel partenaire réécrivait son JSON, même inchangé. Au seuil par défaut, un passage relit la TOAST d'un bloc : 70 min et 7,9 Go de WAL le matin, 39 min l'après-midi | ALTER manuel le 24/11 au soir, puis #583 |
| Requêtes SQL du web jamais annulées | Le timeout HTTP coupe la réponse à 10 s, mais la requête continue en base (jusqu'à 299 s). Elles s'accumulent et épuisent les pools de connexions | #581 : `statement_timeout` ; #582 : index `action(id_jeune, date_creation)` |

Le 26/11 au matin, comparé au 25/11 sur la même fenêtre, le temps cumulé des
requêtes lentes est divisé par 2,8 et les requêtes de plus de 10 s passent de
85 à 2 (§ 4).

## 1. Chronologie

### Matin : archivage de migration et vacuum de la TOAST

| Heure | Fait | Source |
|---|---|---|
| 09h00 | Lancement de l'archivage de la population `CONSEILLERS_FT_PASS_EMPLOI_MIGRATION_3`, environ 11 500 jeunes, par lots de 100 | `archive_jeune` |
| 09h20 | 600 erreurs 5xx sur le routeur par tranche de 10 min (environ 50 k requêtes) | logs routeur |
| 09h25 | Début de l'autovacuum de la TOAST de `cache_api_partenaire`. Premières attentes de verrou (16 sessions) | logs PG, `metrics-sql` |
| 10h00–10h10 | Pic : environ 2 360 erreurs 5xx en 10 min, 25 à 33 sessions en attente de verrou (jusqu'à 66 s) | routeur, `metrics-sql` |
| 10h07 | Alerte Scalingo « High 5xx » sur monitoring-production (337), résolue en 1 min | timeline Scalingo |
| 10h11 | Crash du `worker-2` : `SequelizeConnectionAcquireTimeoutError` non interceptée dans l'enregistrement du suivi d'un job | événement Scalingo |
| 10h13 | Seconde alerte « High 5xx » (386), prise en charge | timeline, conversation |
| 10h24 | Workers coupés (3 → 0) | timeline |
| 10h35 | Fin de l'autovacuum : 4 204 s, 7,88 Go de WAL. Retour au calme | logs PG |
| 11h04 | Merge de #580 ; déploiement à 11h15 | git, timeline |
| 11h20 | Workers relancés (0 → 2) | timeline |
| 11h20 → après 13h14 | Les lots d'archivage restants (environ 1 600 jeunes) passent environ une fois par heure, alors qu'un lot dure 8 à 20 s | `archive_jeune`, Kibana |
| 13h11 | Passage manuel à 4 workers | timeline |

Le retour au calme coïncide à la fois avec la coupure des workers et avec la fin
du vacuum : **on ne peut pas départager les deux**. Le job n'était pas le
premier consommateur de la base : depuis 08h30, les `COUNT` des compteurs de
portefeuille MiLo totalisaient 36 500 s, contre environ 1 200 s pour les
suppressions du job.

### 14h31–14h44 : requêtes orphelines

- Les `COUNT(action.id)` des compteurs de portefeuille MiLo passent de 2 à 8
  requêtes lentes par minute à 30 à 83 (jusqu'à 299 s). Les appels HTTP
  n'augmentent presque pas et échouent à 10 s, mais le SQL continue.
- De 14h36:00 à 14h36:35, les 3 conteneurs web décrochent ensemble : 230
  erreurs 502, 275 `SequelizeConnectionAcquireTimeoutError`, environ 75 upserts
  bloqués (dont 59 sur `cache_api_partenaire`).
- Un `GET /auth/users` de connect vers l'api échoue à 5 s.
- Le déclencheur initial n'est pas identifié.

### 15h55–16h36 : second vacuum de la TOAST

- 1 575 erreurs 5xx sur le routeur (dont 1 535 en 502), à trafic stable.
- Requêtes de plus de 500 ms : 120 à 590 par minute, contre 10 à 50 avant.
- Autovacuum de la TOAST de 15h55:40 à 16h34:25 : 2 326 s, 7,7 Go de WAL,
  1,2 M chunks morts retirés. Second passage en 5h20 au seuil par défaut.

## 2. Ce qui a aggravé

- **Pas de pause par type de job.** Le seul levier était `scale worker:0`, qui
  arrête tous les jobs, crons compris.
- **Ordre de reprise.** Les lots d'archivage sont remis en file sans priorité,
  alors que `TRAITER_EVENEMENT_MILO` est en `priority: 2`. Bull place donc chaque
  événement MiLo devant eux, et l'arriéré MiLo accumulé pendant l'heure de
  coupure les a fait attendre.
- **Jobs décalés.** `NOTIFIER_RENDEZVOUS_PE` prévu à 12h00 est parti à 12h55. Il
  ne retient que les notifications créées dans les 2 h avant son exécution :
  celles créées entre 10h00 et 10h55 n'ont pas été envoyées (déduit du code).
- **Crash du worker.** Un échec de l'enregistrement du suivi de job, qui n'est
  ni attendu ni intercepté, arrête le process Node. Le job en cours tombe avec
  lui.
- **Autoscaler du worker sur le CPU.** Quand c'est la base qui sature, ajouter
  des workers ajoute de la charge à la base et augmente le risque de 429 côté
  MiLo (limiteurs en mémoire, un par process).
- **Alerte brève.** La première alerte 5xx s'est résolue en une minute.

## 3. Pourquoi on ne l'a pas vu avant

- En staging, les tables sont petites : un parcours complet ne coûte rien, et
  les cascades sans index passent inaperçues.
- La TOAST de `cache_api_partenaire` est absente de `pg_stat_user_tables`, et
  donc du dashboard des bases (panneau ajouté depuis, tools #61).
- `pg_stat_statements` cumule depuis le 25/02/2026 : sans deux relevés à
  comparer, impossible de dater une dégradation.

## 4. Effet des correctifs (mesuré le 26/11)

Logs de l'addon PostgreSQL (requêtes de plus de 500 ms), fenêtre 08h16–09h19,
mercredi 25/11 (avant #581, #582 et #583) contre jeudi 26/11 :

| | 25/11 | 26/11 |
|---|---|---|
| Requêtes > 500 ms | 2 655 | 1 484 |
| > 5 s | 222 | 55 |
| > 10 s | 85 | 2 |
| Temps cumulé | 5 982 s | 2 167 s |
| Annulées par `statement_timeout` | — | 38 |
| Compteurs portefeuille MiLo lents | 567 (2 022 s) | 87 (158 s) |
| Upserts `cache_api_partenaire` lents | 1 141 (1 758 s) | 653 (634 s) |

Autovacuum de la TOAST :
- 24/11, seuil par défaut : 70 et 39 min, environ 7,8 Go de WAL, toutes les 5h20 ;
- 25/11 matin, après l'ALTER manuel (seuil à 5 %) : 9 à 14 min, environ 2,2 Go
  de WAL, toutes les 1h40 environ ;
- après #583 (25/11, 14h36) : passages à 21h34 et 05h15, puis aucun jusqu'à
  09h19 le 26/11. Les intervalles de soirée et de nuit ne valent pas une mesure
  de journée.

Limites : pas de normalisation par le trafic (l'autoscaler était à 3 conteneurs
web les deux matins). #580 n'est pas mesurable dans ces logs : aucun archivage
n'a tourné depuis.

Effet de bord de #581 : les 38 annulations du 26/11 sont toutes la liste des
actions à qualifier du conseiller et son `count`. Côté utilisateur, rien ne
change : ces requêtes dépassaient déjà le timeout HTTP de 10 s.

## 5. Suites identifiées

Suivies sur le board :

1. Intercepter l'échec de l'enregistrement du suivi de job (crash du worker).
2. Pause et arrêt par type de job pour les jobs par lots, délai entre les lots,
   priorité à la reprise seulement.
3. Actions à qualifier du conseiller : index partiels `WHERE annule = false`
   inutilisables, requête à revoir.
4. `NOTIFIER_RENDEZVOUS_PE` : partir du dernier passage réussi, pas des 2 h
   précédant l'exécution.
5. Convention « toute clé étrangère a son index ».
6. Autoscaler du worker : critère à revoir.
7. Base : `log_lock_waits`, `idle_in_transaction_session_timeout`.
