# Disponibilité des apps — Heartbeat

**Heartbeat** (Elastic) sonde en HTTP les endpoints des apps Pass Emploi pour
détecter les indisponibilités (uptime), et écrit directement dans Elasticsearch
(`heartbeat-*`) — **hors** Logstash et **hors** Fleet (binaire autonome, config
versionnée dans `heartbeat/heartbeat.template.yml`).

## Ce qui est sondé

| Monitor | Type | Fréquence | Condition de succès |
|---|---|---|---|
| `$API_SERVICE_NAME` | http | `@every 5s` | status `200` |
| `$FRONT_SERVICE_NAME` | http | `@every 5s` | status `200` |
| `$AUTH_SERVICE_NAME` | http | `@every 5s` | status `200` |
| Wordpress (doc, 3 pages) | http | `@every 60s` | status `200` (si `WORDPRESS_ENABLED=true`) |

## Pourquoi c'est une métrique

Elastic classe `heartbeat` en `data_stream.type: logs`, mais c'est une **mesure
périodique** (un ping toutes les 5 s), pas un événement métier discret : on le
range et on le retient avec les métriques (90 j, cf.
[stockage/metriques](../../stockage/metriques/README.md)).

Déploiement, variables d'environnement, buildpacks :
[`heartbeat/README.md`](../../../../heartbeat/README.md).
