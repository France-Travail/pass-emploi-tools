# Kibana — objets à déployer

Les objets Kibana versionnés (SLO, règles d'alerte, Workflows Tchap, dashboards,
sessions Discover, connecteurs, intégrations Fleet) et leurs générateurs : ce
qui se colle dans Kibana → Dev Tools ou s'importe dans *Saved objects*.

Ce qu'on surveille et pourquoi : [doc d'observabilité](../docs/observabilite/README.md).
Inventaire des objets et import : [objets-kibana.md](objets-kibana.md).
Les objets Elasticsearch (rétentions, templates, ingest pipelines) : [`../elasticsearch/`](../elasticsearch/README.md).

## Les objets Kibana à déployer

| Répertoire | Contenu | Mode d'emploi |
|---|---|---|
| [slo/](slo/) | les SLO : `seuils.json` (objectifs et seuils de burn rate, à régler ici), `_modele.console`, `generated/1-slos.console` | [objets Kibana](objets-kibana.md#slo-et-règles-console) |
| [rules/](rules/) | les règles d'alerte : une règle = un fichier JSON par périmètre, et les fichiers générés à coller dans Dev Tools (`rules/generated/`) | [rules/README.md](rules/README.md) |
| [workflows/tchap/](workflows/tchap/) | l'envoi des alertes dans Tchap : `tchap-client`, et les Workflows générés par salon (`workflows/tchap/generated/`) | [workflows/tchap/README.md](workflows/tchap/README.md) |
| [connecteurs/](connecteurs/) | le connecteur Kibana à créer : Tchap | en-tête de chaque fichier |
| [dashboards/](dashboards/) | les dashboards (`.ndjson`) | [objets Kibana](objets-kibana.md#dashboards) |
| [discovers/](discovers/) | les sessions Discover (`.ndjson`), citées par les alertes | [objets Kibana](objets-kibana.md#sessions-discover) |

Les fichiers des répertoires `generated/` sont produits par un script : ne pas les
modifier, modifier leur source (cf. leur en-tête et le mode d'emploi).

## Où arrivent les alertes

Dans les salons Tchap `monitoring-*`, `o11y-*` et `jobs-*` : cf.
[workflows/tchap/README.md](workflows/tchap/README.md). AutoOps alerte en direct
(disque, indexation), par e-mail et dans Tchap : cf. [alertes de la stack](../docs/observabilite/infra/alertes-stack-observabilite.md).
