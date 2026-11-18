# Logs applicatifs — le standard

Ce que les apps (api, connect, web) émettent, et comment chaque champ se
construit. Principe : **la ligne émet un fait, le dashboard et l'alerte
l'interprètent.**

## Une ligne, un fait

- Format **ECS**, en JSON, émis par le **`rootLogger`** du repo. Jamais de
  `console.log`, jamais de logger de framework qui créerait une seconde
  instance (sans contexte ni redaction).
- **`message` = `event.action`.** Le détail va dans des champs (`http.*`,
  `url.*`, `error.*`, `labels.*`), jamais interpolé dans le message.

## `event.action`

Un fait au passé, en snake_case, à faible cardinalité : c'est une clé de
regroupement, pas une étiquette.

On en crée un seulement si les deux conditions sont réunies :

1. on va le **compter ou alerter dessus** ;
2. le fait **n'est pas déjà capturé** par une action existante et ses
   dimensions.

Une ligne qu'on ne lira qu'en enquête n'est pas une action : message libre,
ou `debug`.

## Les familles de lignes

| Famille | Combien | Porte |
|---|---|---|
| **Requête** (`request_completed`, `request_failed`) | une par requête HTTP | parcours, status, durée |
| **Handler** (`handler_executed`) | une par commande, requête interne ou job | opération, erreur métier |
| **Appel partenaire** (`external_api_call`) | une par appel sortant | domaine, status du partenaire, durée |
| **Connexion** (`login_completed`, `login_failed`) | une par tentative de connexion de bout en bout | mode d'authentification, motif de refus |
| **Événement métier** | à la demande | le fait métier |

Aucun appel partenaire ne sort sans sa ligne, que le client soit axios ou un
SDK.

**Corrélation** : `trace.id` relie les lignes d'une même requête. Un parcours
qui s'étale sur plusieurs requêtes (connexion OIDC, job) porte sa propre clé
dans `labels.<nom>_id`.

## `event.outcome` : le fait

`success` ou `failure`, sur chaque ligne qui porte un `event.action`. Il dit si
**l'opération de cette ligne** a abouti, rien de plus.

| Famille | `success` quand |
|---|---|
| Requête | status < 400 |
| Handler | le résultat est un succès |
| Appel partenaire | status du partenaire < 400, sans panne de transport |
| Connexion | la connexion a abouti |

Une même panne donne donc plusieurs `failure` (appel, handler, requête) : ce
n'est pas un doublon, chaque ligne décrit sa propre opération. On filtre
toujours l'`outcome` avec un `event.action`.

L'`outcome` n'est **pas** le verdict d'un SLO : un SLO lit le status de la
requête (cf. [SLO](slo.md)).

## `log.level` : qui doit lire

Deux niveaux opérationnels, **`info`** et **`error`**. Pas de `warn`.
`debug` existe en plus, en opt-in (cf. [données sensibles](#données-sensibles)).

**`error` = un humain doit lire cette ligne, prise isolément.** Une seule ligne
`error` par incident : **celle qui porte la cause**.

| Famille | `error` quand | `info` sinon, notamment |
|---|---|---|
| Appel partenaire | 5xx, panne de transport, timeout, ou 4xx dû à notre appel (400, 401, 403, 429) | 4xx métier : ressource absente, conflit, refus lié à la demande de l'utilisateur |
| Handler | exception imprévue | échec métier, échec reçu d'un partenaire (sa cause est déjà en `error` sur l'appel) |
| Requête | exception qu'aucune ligne en amont n'a loggée (garde, middleware, sérialisation) | tout le reste, y compris un 5xx traduit d'une panne partenaire |
| Connexion, événement métier | quelque chose a cassé | refus ou résultat attendu |

Un volume anormal de lignes `info` en `failure` (des 4xx qui grimpent) ne se
voit pas ligne à ligne : c'est le rôle des [alertes d'anomalie](alertes.md#anomalies).

## Le code HTTP : ce que l'appelant doit comprendre

| Code | Sens | Exemples |
|---|---|---|
| 2xx, 3xx | servi | |
| **4xx** | **c'est la demande** | refus métier, ressource absente, droits, payload invalide |
| **5xx** | **c'est nous, ou un partenaire** | exception, base de données, partenaire en panne |

Le code décrit la relation entre **l'appelant et nous**, jamais celle entre
nous et un partenaire. Le front réagit au code (un 401 déconnecte le
conseiller), et le SLO le compte : un code qui ment trompe les deux.

**Une erreur partenaire se traduit à la frontière de son client** :

| Réponse du partenaire | Cause | On renvoie |
|---|---|---|
| 401, 403 | nos identifiants | 502 |
| 400 | la requête qu'on a construite | 502 |
| 429 | notre quota | 503 |
| timeout | | 504 |
| 5xx, panne de transport | | 502 |
| 404, 409, 422 qui découlent de la demande de l'utilisateur | la demande | le 4xx, ou une erreur métier dédiée |

Une erreur qu'aucun mapping ne reconnaît sort en **500**.

## Le parcours

Chaque route de l'api appartient à un **parcours** (`labels.user_journey`),
posé sur la ligne de requête : c'est ce que fait l'utilisateur, pas le nom de
la route. Le SLO de disponibilité se calcule par parcours : **renommer un
parcours casse son historique**.

## Champs

- Namespaces ECS standards : `event`, `error`, `http`, `url`, `user`,
  `service`, `trace`.
- **`labels.<clé>`** (keyword) pour une dimension ou un identifiant de
  corrélation. Jamais de champ générique inventé (`data`, `payload`, `meta`) :
  son type serait figé par le premier document, et les suivants rejetés.
- **Namespace dédié et typé** pour une valeur numérique à sommer : un compteur
  dans `labels` serait un keyword. Un nouveau namespace demande son rename dans
  Logstash et son mapping (cf. [stockage des logs](infra/stockage/logs/README.md)).
- `user.*` et `trace.id` sont posés par le mixin du logger, jamais dans le
  payload.

### Les exceptions

Une exception passe **toujours** par `toEcsError` avant d'atteindre un logger.
Une exception brute (une erreur axios notamment) embarque la requête complète :

- **fuite** : le corps d'une authentification partenaire contient des
  identifiants ;
- **perte** : la ligne dépasse 16 Ko, le drain Scalingo la tronque, et elle
  n'arrive jamais dans l'index applicatif.

## Données sensibles

- Une clé dont le nom **contient** `token`, `secret`, `password`,
  `authorization`, `bearer`, `api_key`, `apikey` ou `credential` est masquée
  (`[Redacted]`), à toute profondeur du payload.
- Les **bodies** sont loggés sur échec uniquement, tronqués à 4 Ko. Sur succès,
  seulement en `debug`.
- **`debug`** s'active par environnement, pour instrumenter un parcours
  difficile à reproduire. Il reste soumis à la redaction et aux mappings des
  index.
