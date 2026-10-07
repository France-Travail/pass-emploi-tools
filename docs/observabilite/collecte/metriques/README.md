# Collecte des métriques — vue d'ensemble

Mesures numériques périodiques : santé de la stack de log management, des hosts,
des agents eux-mêmes, et disponibilité des apps. Aucune ne passe par Logstash :
chaque collecteur écrit **directement** dans Elastic Cloud, sans étape de
traitement de notre côté.

| Collecteur | Piloté par | Ce qu'il mesure | Data streams | Détail |
|---|---|---|---|---|
| Elastic Agent co-localisé (×2 par env) | Fleet | Logstash INGEST / PROCESS, host | `metrics-logstash.*`, `metrics-system.*` | [stack-observabilite.md](stack-observabilite.md) |
| Elastic Agent dédié (×1 par env) | Fleet | Redis `logstash:ingest` | `metrics-redis.*` | [stack-observabilite.md](stack-observabilite.md) |
| Tous les agents | Fleet | santé de l'agent lui-même | `metrics-elastic_agent.*`, `logs-elastic_agent*`, `metrics-fleet_server.*` | [pilotage.md](../../pilotage.md) |
| Heartbeat | autonome | uptime des apps (sondes HTTP) | `heartbeat-*` | [disponibilite.md](disponibilite.md) |
| APM Server | Elastic Cloud | métriques APM (`metrics-apm.*`) | auto-géré | [collecte/traces](../traces/README.md) |

Rétentions : [stockage/metriques](../../stockage/metriques/README.md).
Alertes qui les exploitent (4, 5, 7, 8) : [supervision/alertes](../../supervision/alertes-stack-observabilite.md).
