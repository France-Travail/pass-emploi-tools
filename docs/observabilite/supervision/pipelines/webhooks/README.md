# Ingest pipelines des webhooks

Les ingest pipelines Elasticsearch qui transforment, **avant indexation**, les
événements reçus par webhook (notifiers Scalingo, CVE Dependabot) en documents
ECS, et l'accès en écriture de leurs émetteurs. Chaque fichier `.console` se
colle dans Kibana → Dev Tools. Ils précèdent les règles : celles de
[`../../rules/`](../../rules/README.md) lisent les documents qu'ils produisent.

La chaîne complète et l'ordre de mise en service : [collecte par webhook](../../../collecte/webhooks/README.md).

| Fichier | Contenu |
|---|---|
| [`correspondance-ecs.md`](correspondance-ecs.md) | **ce que font ces pipelines** : correspondance entre le payload de chaque source et les champs ECS, gabarit de la ligne `message`, rejets |
| [`ingest-alertes-scalingo.console`](ingest-alertes-scalingo.console) | transformation commune des événements Scalingo |
| [`ingest-alertes-scalingo-format-slack.console`](ingest-alertes-scalingo-format-slack.console) | remet au format habituel un événement Scalingo envoyé au format Slack |
| [`ingest-alertes-scalingo-prod-default.console`](ingest-alertes-scalingo-prod-default.console), [`-staging-`](ingest-alertes-scalingo-staging-default.console), [`-perf-default.console`](ingest-alertes-scalingo-perf-default.console) | pipeline par défaut de chaque data stream Scalingo : vérifie l'enveloppe et l'environnement, puis appelle le pipeline commun |
| [`ingest-alertes-github-default.console`](ingest-alertes-github-default.console) | transformation des alertes Dependabot |
| [`acces-webhooks.console`](acces-webhooks.console) | rôle et utilisateur des notifiers Scalingo, clé API de `security-alerts.yml` : écriture seule dans leurs data streams |

Ordre de rejeu : `ingest-alertes-scalingo.console` et
`ingest-alertes-scalingo-format-slack.console` d'abord (les pipelines par
environnement les appellent), puis les autres. Les `_simulate` en fin de
fichier doivent donner les résultats annoncés en commentaire.

Modifier un pipeline : reporter le changement dans
[`correspondance-ecs.md`](correspondance-ecs.md) dans la même PR, puis le
rejouer en `_simulate` avant de l'appliquer.

Les data streams, leurs mappings et leur rétention :
[`stockage/logs/`](../../../stockage/logs/README.md).
