# Configuration Elasticsearch des logs

Templates et politiques de rétention des logs pass-emploi.

## Vue d'ensemble

Deux familles de logs (applicatifs et router Scalingo), deux environnements,
un seul jeu de briques partagées :

```
                        logs@custom  (event.action/outcome, log.logger, error.*)
                       /     |      \
        logs-prod@tpl-custom |       logs-router
        logs-staging@tpl-cust|            |
                             |       logs-router@mappings + logs-router@settings
                  ecs@mappings (x-pack)
```

| Data stream                          | Index template                | Rétention (ILM)          |
|---------------------------------------|--------------------------------|--------------------------|
| `logs-prod-default`                   | `logs-prod@template-custom`    | `logs-prod-retention`    |
| `logs-staging-default`                | `logs-staging@template-custom` | `logs-staging-retention` |
| `logs-router-{prod,staging}-default`  | `logs-router`                  | `logs-prod-retention`    |

Les champs ECS custom (`event.action`, `event.outcome`, `log.logger`,
`error.*`) sont définis **une seule fois**, dans le component template
`logs@custom`, composé par les templates applicatifs ET le template router.
Ajouter un champ ECS custom = le déclarer dans `logs@custom`, et nulle part
ailleurs.

Les component templates `logs@mappings`, `logs@settings`, `ecs@mappings` sont
fournis par Elasticsearch (x-pack) — on s'y réfère seulement.

## Application

Dans **Kibana → Dev Tools → Import requests**, importer puis exécuter les
fichiers **dans l'ordre** :

1. `1-ilm-policies.console`
2. `2-component-templates.console`
3. `3-index-templates.console`

L'ordre est imposé : les index templates référencent les component templates et
les politiques ILM. L'opération est idempotente — rejouable sans risque après
toute modification.

## Rollover

Les nouveaux mappings ne s'appliquent qu'aux **nouveaux** backing indices. Pour
les appliquer, faire un rollover (non destructif : les indices existants
restent, l'ILM les expire) :

```
POST logs-prod-default/_rollover
POST logs-staging-default/_rollover
POST logs-router-prod-default/_rollover
POST logs-router-staging-default/_rollover
```

## Vérification

Les API de templates n'acceptent pas les listes séparées par virgules — un GET
par ligne :

```
GET _ilm/policy/logs-prod-retention,logs-staging-retention

GET _component_template/logs@custom
GET _component_template/logs-router@mappings
GET _component_template/logs-router@settings
GET _component_template/logs-prod-retention-custom
GET _component_template/logs-staging-retention-custom

GET _index_template/logs-prod@template-custom
GET _index_template/logs-staging@template-custom
GET _index_template/logs-router

GET _data_stream/logs-*-default
```

Contrôler que le router résout bien les champs ECS :

```
GET _index_template/logs-router
POST _index_template/_simulate_index/logs-router-prod-default
GET .ds-logs-router-prod-default-*/_mapping/field/event.action,event.outcome
```

- `GET _index_template/logs-router` → `composed_of` doit lister `logs@custom`.
- `_simulate_index` renvoie le mapping **fusionné** (pas `composed_of`) : ses
  `mappings.properties` doivent contenir `event.action` / `event.outcome` en
  `keyword`.
- `_mapping/field/...` sur le backing index courant confirme l'indexation
  effective.

Le `_simulate_index` doit lister `logs@custom` dans `composed_of`, et le mapping
doit contenir `event.action` / `event.outcome` (type `keyword`). Côté Discover,
filtrer `event.action: request_routed` doit alors retourner des résultats.
