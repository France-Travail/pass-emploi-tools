# Post-mortem — Saturation de la base de l'api (24 novembre 2026)

> **Type** : trace datée. Trois épisodes de saturation de la base PostgreSQL de
> `pass-emploi-api-prod` le mardi 24/11/2026, leurs causes, les correctifs
> livrés du 24 au 26/11 et leur effet mesuré le 26/11.
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

Le 26/11, les compteurs de portefeuille MiLo ne pèsent plus presque rien et
l'autovacuum de la TOAST passe environ trois fois moins souvent. Mais **chaque
passage sature encore la base** : le 26/11 de 11h05 à 11h27, il a provoqué des
salves de 5xx. Hors vacuum, la charge de la base est inchangée (§ 4).

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

Mercredi 25/11 (avant #581, #582 et #583) contre jeudi 26/11, de 08h16 à 13h16.
Sources : logs du routeur, et logs de l'addon PostgreSQL (requêtes de plus de
500 ms, disponibles à partir de 10h22 pour le 25/11).

**Trafic** (routeur) : 1,38 M requêtes le 25/11, 1,34 M le 26/11.

| Routeur, 08h16–13h16 | 25/11 | 26/11 |
|---|---|---|
| 5xx | 936 | 881, dont 599 entre 11h et 12h |
| Requêtes > 5 s | 1 549 | 1 259, dont 622 entre 11h et 12h |

**Autovacuum de la TOAST** :

| | Passages en journée | Durée | Pages relues | WAL |
|---|---|---|---|---|
| 24/11, seuil par défaut | toutes les 5h20 | 70 et 39 min | 83 % (15h55) | ~7,8 Go |
| 25/11, après l'ALTER manuel (5 %) | toutes les 1h40 (09h11, 10h53, 12h34) | 9 à 14 min | ~36 % | ~2,2 Go |
| 26/11, après #583 | un seul, 5h50 après le précédent (11h05) | 22 min | 45 % | 2,8 Go |

#583 divise par environ 3,4 le rythme des chunks morts (309 k en 5h50, contre
environ 300 k en 1h40). Mais un passage plus espacé relit plus de pages et dure
plus longtemps.

**Base, 10h22–13h16, pendant et hors vacuum** (temps cumulé des requêtes de plus
de 500 ms, par minute) :

| | 25/11 | 26/11 |
|---|---|---|
| Pendant un vacuum de la TOAST | 468 s/min (26 min) | 532 s/min (23 min) |
| Hors vacuum | 30 s/min | 29 s/min |

Le 26/11, le vacuum de 11h05–11h27 coïncide avec les salves de 5xx de 11h06,
11h17 et 11h23 (60 à 130 par minute) et avec 305 des 350 annulations par
`statement_timeout` de la fenêtre.

Un second épisode, de 14h54 à 15h03 le 26/11, survient **sans vacuum** : jusqu'à
87 requêtes de plus de 5 s par minute, 247 annulations par `statement_timeout`
dans l'heure. Les upserts de `cache_api_partenaire` dominent (881 lentes,
2 742 s en 10 min, jusqu'à 19 s), suivis de 105 `INSERT` lents dans
`notification_jeune`, signe d'un envoi de notifications en masse dont l'origine
n'est pas identifiée. Le cache pèse donc aussi hors vacuum, par ses écritures.

**Par requête, 10h22–13h16** :

| Requêtes lentes (> 500 ms) | 25/11 | 26/11 |
|---|---|---|
| Compteurs de portefeuille MiLo (#582) | 913 (3 115 s) | 311 (638 s) |
| Actions à qualifier du conseiller et leur `count` | 302 + 302 | 484 + 483 |
| Actions d'un jeune par date d'échéance, hors vacuum | 154 (183 s) | 273 (453 s) |
| Upserts `cache_api_partenaire`, hors vacuum | 1 534 (1 559 s) | 1 286 (1 299 s) |

Limites :
- Une mesure faite le matin du 26/11 sur 08h16–09h19 montrait un temps cumulé
  divisé par 2,8. Elle est trompeuse : le 25/11, un vacuum de la TOAST tombait
  dans cette fenêtre, pas le 26/11.
- #580 n'est pas mesurable dans ces logs : aucun archivage n'a tourné depuis.
- La hausse des actions d'un jeune hors vacuum n'est pas due au plan
  d'exécution. Relevé le 26/11 sur un jeune à 253 actions : `idx_action_id_jeune`,
  196 pages lues sur disque en 1,8 s, soit environ 9 ms par lecture. Le plan
  est correct ; c'est la latence du disque qui limite.

Effets de bord de #581 :
- Les annulations portent surtout sur les actions à qualifier du conseiller.
  Côté utilisateur, rien ne change : ces requêtes dépassaient déjà le timeout
  HTTP de 10 s.
- La notification des nouvelles immersions, lancée depuis le web sans être
  attendue, est annulée quand sa recherche dépasse 10 s. Son erreur non
  interceptée a fait planter `web-1` le 26/11 à 15h01 (corrigé par #586 ; la
  notification passe en job worker avec #587).

## 5. Actions réalisées

- [api #580](https://github.com/France-Travail/pass-emploi-api/pull/580) : 9 index, dont les 4 clés étrangères vers `jeune` sans
  index (24/11).
- `ALTER TABLE` manuel sur la TOAST de `cache_api_partenaire`, seuil
  d'autovacuum à 5 % (24/11 au soir).
- [api #583](https://github.com/France-Travail/pass-emploi-api/pull/583) : le cache partenaire ne réécrit plus un résultat
  inchangé ; seuil d'autovacuum de la TOAST passé en migration (25/11).
- [api #582](https://github.com/France-Travail/pass-emploi-api/pull/582) : index `action(id_jeune, date_creation)` pour les
  compteurs de portefeuille MiLo (25/11).
- [api #581](https://github.com/France-Travail/pass-emploi-api/pull/581) : `statement_timeout` de 10 s sur le process web (25/11).
- [api #586](https://github.com/France-Travail/pass-emploi-api/pull/586) : deux erreurs non interceptées n'arrêtent plus le
  process. L'échec de l'enregistrement du suivi d'un job faisait planter le
  worker (24/11, 10h11). La notification des nouvelles immersions, annulée par
  le `statement_timeout` de #581, a fait planter `web-1` le 26/11 à 15h01.

## 6. Suites identifiées

Suivies sur le board :

1. Pause et arrêt par type de job pour les jobs par lots, délai entre les lots,
   priorité à la reprise seulement.
2. Actions à qualifier du conseiller : le filtre `statut` /
   `qualification_heures` n'est porté par aucun index. La requête relit toutes
   les actions des jeunes du conseiller pour n'en garder que quelques-unes :
   pour un conseiller de 21 jeunes, environ 500 actions lues (estimation du
   plan, 3 s à froid) pour une trentaine retenues. Piste : index partiel sur les
   actions à qualifier.
3. `NOTIFIER_RENDEZVOUS_PE` : partir du dernier passage réussi, pas des 2 h
   précédant l'exécution.
4. Convention « toute clé étrangère a son index ».
5. Autoscaler du worker : critère à revoir.
6. Base : `log_lock_waits`, `idle_in_transaction_session_timeout`.
7. Vacuum de la TOAST de `cache_api_partenaire` : il sature encore la base à
   chaque passage. Leviers : moins de réécritures du cache, vacuum ralenti,
   ou revoir ce stockage.
8. Notification des nouvelles immersions : la passer en job worker, pour
   qu'elle ne soit plus annulée au bout de 10 s
   ([api #587](https://github.com/France-Travail/pass-emploi-api/pull/587)).
9. Latence du disque de l'addon (environ 9 ms par page lue hors cache, RAM
   saturée) : ce que garantissent les plans Scalingo supérieurs.
