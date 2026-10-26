# Supervision — index

Ce qui surveille pass-emploi dans Kibana : les promesses de service (SLO), les
alertes, et les objets Kibana qui les portent. Pour ce qu'on regarde sans attendre
une alerte : [routine de surveillance](../routine-surveillance.md) ; pour enquêter
sur un incident : [runbooks](../runbooks/).

Deux sortes de contenus, rangés séparément :

- **les pages à lire**, ici : ce qui est surveillé, pourquoi, avec quels seuils ;
- **les objets Kibana à déployer**, dans les sous-répertoires : ce qui se colle
  dans Kibana → Dev Tools ou s'importe dans *Saved objects*.

## Les pages à lire

| Page | Question à laquelle elle répond |
|---|---|
| [sli-slo.md](sli-slo.md) | Quelles promesses de service tient-on (SLI, SLO, seuils) ? |
| [alertes-applicatives.md](alertes-applicatives.md) | Quelles alertes sur les pannes visibles des utilisateurs (SLO, partenaires, 5xx, base de données, front, disponibilité, événements Scalingo, jobs), et que vérifier quand elles sonnent ? |
| [alertes-stack-observabilite.md](alertes-stack-observabilite.md) | Quelles alertes sur notre infra de télémétrie (Logstash, Redis, Elastic Agent, ILM, événements Scalingo de la stack) ? |
| [alertes-securite.md](alertes-securite.md) | Quelles alertes sur les vulnérabilités des dépendances (CVE Dependabot) ? |
| [objets-kibana.md](objets-kibana.md) | Quels dashboards, sessions Discover, SLO et règles sont versionnés, et comment les importer ou les modifier ? |

## Les objets Kibana à déployer

| Répertoire | Contenu | Mode d'emploi |
|---|---|---|
| [slo/](slo/) | les SLO (`1-slos.console`) | [sli-slo.md](sli-slo.md), [objets Kibana](objets-kibana.md#slo-et-règles-console) |
| [rules/](rules/) | les règles d'alerte : une règle = un fichier JSON par périmètre, et les fichiers générés à coller dans Dev Tools (`rules/generated/`) | [rules/README.md](rules/README.md) |
| [workflows/tchap/](workflows/tchap/) | l'envoi des alertes dans Tchap : `tchap-client`, et les Workflows générés par salon (`workflows/tchap/generated/`) | [workflows/tchap/README.md](workflows/tchap/README.md) |
| [pipelines/webhooks/](pipelines/webhooks/) | les ingest pipelines qui transforment les événements reçus par webhook (Scalingo, Dependabot) en champs ECS, et l'accès de leurs émetteurs | [pipelines/webhooks/README.md](pipelines/webhooks/README.md) |
| [connecteurs/](connecteurs/) | les connecteurs Kibana à créer : Tchap, Mattermost des jobs | en-tête de chaque fichier |
| [dashboards/](dashboards/) | les dashboards (`.ndjson`) | [objets Kibana](objets-kibana.md#dashboards) |
| [discovers/](discovers/) | les sessions Discover (`.ndjson`), citées par les alertes | [objets Kibana](objets-kibana.md#sessions-discover) |

Les fichiers des répertoires `generated/` sont produits par un script : ne pas les
modifier, modifier leur source (cf. leur en-tête et le mode d'emploi).

## Où arrivent les alertes

Dans les canaux Mattermost de monitoring jusqu'au 1er novembre 2026, puis dans
les salons Tchap (`monitoring-*`, `o11y-*`, `jobs-*`) : cf.
[workflows/tchap/README.md](workflows/tchap/README.md). AutoOps alerte en direct
(disque, indexation) : cf. [alertes de la stack](alertes-stack-observabilite.md).
