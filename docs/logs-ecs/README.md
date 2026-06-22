# Logs ECS — documentation

Référence du logging structuré ECS, transverse aux apps Pass Emploi (api,
connect, web) et à l'infra mutualisée (`pass-emploi-tools/logs/`).

| Fichier | Contenu |
|---|---|
| [conventions.md](./conventions.md) | Socle transverse : taxonomie `event.action`, `outcome`/`level`, redaction, archi `rootLogger`, patterns d'instrumentation, décisions durables |
| [infra-elasticsearch.md](./infra-elasticsearch.md) | Cluster ES, data streams, templates versionnés, ILM, Logstash, historique incidents |
| [kibana.md](./kibana.md) | Use cases Kibana : investigation incident, reporting métier, monitoring tech, alertes |
| [couverture-api.md](./couverture-api.md) | Spécifique pass-emploi-api : taxonomie, couverture, validation E2E RDV Milo, limites connues |

**Invariant à respecter** : tout nouveau log passe par le `rootLogger` au format
ECS (`event.action` au passé + `event.outcome`, `level` info|error). Jamais de
`console.log`. Lire [conventions.md](./conventions.md) avant d'ajouter ou modifier
un log.
