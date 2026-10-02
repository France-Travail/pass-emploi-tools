# Drain Scalingo — le maillon qu'on ne maîtrise pas

Le **Log Drain** Scalingo pousse le `stdout` de chaque app en HTTP (POST) vers
`pass-emploi-logstash-<env>`. On ne le configure qu'à peine et on ne l'observe
qu'indirectement (logs router) : ses règles sont à connaître par cœur, car elles
transforment un hoquet de Logstash en perte de logs.

> Récit de l'incident qui a produit ces règles :
> [postmortem-2026-07-blackout-logs.md](../../post-mortems/postmortem-2026-07-blackout-logs.md).

## Garde-fous durables

1. **Quarantaine** = **10 lignes consécutives** refusées → drain quarantiné
   **5 min** (aucun log envoyé), escalade **10/15/20 min**. Frappe la **plus
   grosse** app en premier (api ≈ 59 % du volume, ~5-6× web/connect) : elle
   atteint 10 refus consécutifs le plus vite. Un hoquet Logstash d'1 s = blackout
   de 5 min pour api. *(Amplification énorme — c'est le mode B.)*
2. **Troncature à 16384 octets** (2^14) par ligne, quelle que soit l'app. Une
   ligne plus longue arrive **coupée en plein milieu** : si c'est du JSON, le
   filtre `json` échoue (`_jsonparsefailure`) et l'event part dans
   `logs-logstash-errors-<env>-default` au lieu de son index applicatif. Ce n'est
   pas réparable côté Logstash — un JSON tronqué n'est pas récupérable. **La
   correction est toujours côté app** : ne pas émettre de ligne > 16 Ko (cf.
   [format/logs/conventions](../../format/logs/conventions.md) § « Ne jamais
   logger une exception brute »). Signature : `Unexpected end-of-input … column: 16385`.
3. **Codes vus dans les logs router** : **429** = input Logstash plein
   (backpressure) ; **499** = le drain a coupé (Logstash trop lent à répondre) ;
   **0 requête** d'une app = son drain en quarantaine.
4. **Le nom de l'app INGEST est figé** (`pass-emploi-logstash-<env>`) : tous les
   drains pointent vers son URL. La renommer = reconfigurer chaque drain.

## Maintien du drain — décision du 2026-09-23

Exploration d'un mécanisme de collecte alternatif, cf.
[ADR-003 — Pertinence de l'usage des Log Drains Scalingo](../../../decisions/ADR-003-usage-log-drain-scalingo.md) :

- **Décision** : statu quo — pas de changement de transport (syslog écarté, aucune
  exception documentée à la quarantaine par type de drain), pas de nouvelle
  infrastructure (shipper applicatif direct ou broker en amont écartés : coût élevé,
  risques déjà documentés déplacés plutôt que traités).
- **Deux socles d'archivage distincts identifiés** : Logs Archives Scalingo (brut,
  non indexé, 1 an, lié au `stdout`, indépendant du drain) vs rétention ES — cf.
  [stockage/logs](../../stockage/logs/README.md#archivage-hors-es--logs-archives-scalingo).
- **Suites ouvertes** : confirmation à obtenir du support Scalingo sur le comportement
  quarantaine en syslog ; vérification du plafond d'ingestion Scalingo (16 384
  lignes/min et 64 MiB/min par conteneur) face au débit réel de `pass-emploi-api`.
