# Traitement des logs — vue d'ensemble

Comment un log brut lu dans Redis devient un document ECS indexé dans le bon
data stream. L'amont (drain → Redis) est dans
[`../../collecte/logs/`](../../collecte/logs/README.md) ; les data streams et
rétentions dans [`../../stockage/logs/`](../../stockage/logs/README.md).

```
Redis logstash:ingest ──► pipeline process ──┬──► logs-<env>-default              (app)
                          (filtres ECS)       ├──► logs-router-<env>-default       (router Scalingo)
                                              ├──► logs-logstash-errors-<env>-default (échec de filtre)
                                              └──► rejet ES ──► DLQ disque ──► pipeline dead_letter_queue
                                                                               └──► logs-logstash-dlq-<env>-default
```

Tourne dans `pass-emploi-logstash-process-<env>` (process `worker`,
`PROCESS_ENABLED=true`). Dimensionnement et garde-fous JVM :
[`../../infrastructure.md`](../../infrastructure.md).

## Pour aller plus loin

| Fichier | Contenu |
|---|---|
| [pipeline.md](pipeline.md) | Pipelines `process` et `dead_letter_queue` : filtres, drops, routage, frontière in-app / Logstash |
| [performances.md](performances.md) | Test de non-régression, trajectoire de scaling, historique complet des campagnes de charge (résultats, next steps) |
