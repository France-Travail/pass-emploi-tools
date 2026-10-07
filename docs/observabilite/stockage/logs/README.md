# Stockage des logs

Data streams, rétentions et mapping des logs dans Elasticsearch. Production des
documents : [process/logs](../../process/logs/README.md). Import des 3 `.console`
de ce dossier : [stockage/README](../README.md#import--ordre-et-portée).

## Data streams

| Data stream | Contenu |
|---|---|
| `logs-{prod,staging,perf}-default` | logs applicatifs |
| `logs-router-*-default` | logs du router Scalingo (`request_routed`) |
| `logs-logstash-errors-*-default` | events en erreur de **traitement** Logstash (`_jsonparsefailure`, `_mutate_error`, `_rubyexception`…) |
| `logs-logstash-dlq-*-default` | events **rejetés par ES** (conflit de mapping), relus depuis la Dead Letter Queue |
| `logs-apm.error-default` | errors non catchées remontées par l'APM (cf. [collecte/traces](../../collecte/traces/README.md)) |

Les index `logs-logstash-*` sont les index de diagnostic de la chaîne elle-même :
leur exploitation (alertes, KQL, actions correctives) est dans le
[runbook Logstash](../../runbooks/runbook-logstash.md).

## Rétention et composition des templates

Deux familles de logs (applicatifs et router Scalingo), trois environnements,
un seul jeu de briques partagées :

```
              pass-emploi-logs@mappings  (event.action/outcome, log.logger, error.*)
                       /     |      \
        logs-prod@tpl-custom |       logs-router
        logs-staging@tpl-cust|            |
                             |       logs-router@mappings + logs-router@settings
                  ecs@mappings (x-pack)
```

| Data stream                          | Index template                | Rétention (ILM)            | Cible |
|---------------------------------------|--------------------------------|------------------------------|-------|
| `logs-prod-default`                   | `logs-prod@template-custom`    | `logs-prod-retention`      | 90 j (14 hot + 7 warm + 69 frozen) |
| `logs-staging-default`                | `logs-staging@template-custom` | `logs-staging-retention`   | 14 j  |
| `logs-perf-default`                   | `logs-perf@template-custom`    | `logs-perf-retention`      | 2 j   |
| `logs-router-{prod,staging,perf}-default` | `logs-router`              | `logs-router-retention`    | 21 j (14 hot + 7 warm) |
| `logs-logstash-errors-*-default`      | `logs-logstash-errors@template-custom` | `logs-logstash-errors-retention` | 30 j |
| `logs-logstash-dlq-*-default`         | `logs-logstash-dlq@template-custom`    | `logs-logstash-dlq-retention`    | 30 j |
| `logs-apm.error-default`              | `logs-apm.error@template-custom`       | `logs-apm.error-retention`       | 90 j (14 hot + 7 warm + 69 frozen) |

> **Plan de rétention x3.1** (conseiller Elastic, 2026-10-05) : 14 j hot et 7 j
> warm avec 1 réplica, puis frozen sans réplica (searchable snapshot sur
> `found-snapshots`) jusqu'à la suppression. Prod et erreurs APM : 90 j au total.
> Router (et traces APM) : 21 j, sans frozen. Il remplace la cible de 180 j de
> `logs-prod`.
>
> **Router découplé** : `logs-router` a sa propre policy `logs-router-retention`,
> partagée par prod, staging et perf.

Les champs ECS custom (`event.action`, `event.outcome`, `log.logger`,
`error.*`) sont définis **une seule fois**, dans le component template
`pass-emploi-logs@mappings`, composé par les templates applicatifs ET le template
router. Ajouter un champ ECS custom = le déclarer dans `pass-emploi-logs@mappings`,
et nulle part ailleurs.

> **Pas dans `logs@custom`** : ce nom est le point d'ancrage que **tous** les
> templates `logs-*` d'Elastic composent, y compris `logs-otel@template`, qui
> déclare `error.stack_trace` en alias. Depuis l'arrivée de ce template,
> Elasticsearch refuse tout `logs@custom` qui déclare ce champ en concret (constaté
> le 2026-10-07). `logs@custom` est laissé vide ; nos templates composent
> `pass-emploi-logs@mappings`.

Les component templates `logs@mappings`, `logs@settings`, `ecs@mappings` sont
fournis par Elasticsearch (x-pack) — on s'y réfère seulement.

## Settings critiques

- `index.mode: logsdb`
- `index.mapping.total_fields.ignore_dynamic_beyond_limit: true` → nouveaux
  champs dynamiques silencieusement `_ignored` au-delà de `total_fields.limit`.
- `logs-router@mappings` en `dynamic: false`.

## Archivage hors ES — Logs Archives Scalingo

Deux socles d'archivage distincts (identifiés le 2026-09-23, cf.
[ADR-003](../../../decisions/ADR-003-usage-log-drain-scalingo.md)) :

| | Logs Archives Scalingo | Rétention ES |
|---|---|---|
| Forme | brut, non indexé | indexé, cherchable |
| Durée | 1 an | 90 j prod |
| Source | le `stdout` de l'app, **indépendant du drain** | le drain → Logstash |
| Activation | filet déjà actif, sans configuration | ILM ci-dessus |

Les archives Scalingo restent disponibles même quand le drain est en quarantaine.

## Pièges connus

**App prod — `_ignored` (2026-05-19)** : après la refonte ECS, champs `event.*`
en `_ignored` malgré présence dans `_source`. Cause : datastream en génération
45, mapping pollué par des années de logs freeform → saturation
`total_fields.limit`. Fix : `POST logs-prod-default/_rollover`.

**Router — `event.action` non cherchables (mai 2026)** : cause **différente**
(pas de saturation) — le template `logs-router` ne composait pas `logs@custom`,
et son `logs-router@mappings` hand-rollé en `dynamic: false` ne déclarait pas
`event.action` / `outcome`. Fix : `logs-router` compose désormais `logs@custom`
(devenu `pass-emploi-logs@mappings` le 2026-10-07), puis rollover.

À retenir : après tout changement de schéma d'ingestion, surveiller `_ignored`
et prévoir un `_rollover` (non destructif).

## Commandes de contrôle (Dev Tools)

```
GET _data_stream/logs-*-default
GET _component_template/<nom>     # pas de liste séparée par virgules sur les templates
GET _index_template/<nom>
GET _ilm/policy/logs-prod-retention
POST <datastream>/_rollover       # non destructif
```

```
GET _component_template/pass-emploi-logs@mappings
GET _component_template/logs-router@mappings
GET _component_template/logs-router@settings
GET _component_template/logs-prod-retention-custom
GET _component_template/logs-router-retention-custom
GET _component_template/logs-staging-retention-custom
GET _component_template/logs-apm.error@custom

GET _index_template/logs-prod@template-custom
GET _index_template/logs-staging@template-custom
GET _index_template/logs-router
GET _index_template/logs-apm.error@template-custom

GET _data_stream/logs-*-default,logs-apm.error-default
```

Contrôler que le router résout bien les champs ECS :

```
GET _index_template/logs-router
POST _index_template/_simulate_index/logs-router-prod-default
GET .ds-logs-router-prod-default-*/_mapping/field/event.action,event.outcome
```

- `GET _index_template/logs-router` → `composed_of` doit lister `pass-emploi-logs@mappings`.
- `_simulate_index` renvoie le mapping **fusionné** (pas `composed_of`) : ses
  `mappings.properties` doivent contenir `event.action` / `event.outcome` en
  `keyword`.
- `_mapping/field/...` sur le backing index courant confirme l'indexation
  effective.

Le `_simulate_index` doit lister `pass-emploi-logs@mappings` dans `composed_of`, et le mapping
doit contenir `event.action` / `event.outcome` (type `keyword`). Côté Discover,
filtrer `event.action: request_routed` doit alors retourner des résultats.
