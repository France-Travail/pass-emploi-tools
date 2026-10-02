# Stockage des métriques

Rétention des métriques Fleet et Heartbeat. Collecte : [collecte/metriques](../../collecte/metriques/README.md). Import des 3 `.console` de ce dossier : [stockage/README](../README.md#import--ordre-et-portée).


| Data stream                                                              | Rétention (ILM)              | Cible |
|-----------------------------------------------------------------------------|--------------------------------|-------|
| `metrics-logstash.{node,pipeline,plugins,health_report}-default`            | `metrics-fleet-retention`     | 90 j  |
| `metrics-redis.{info,key,keyspace}-default`                                 | `metrics-fleet-retention`     | 90 j  |
| `metrics-system.*-default` (11 datasets — hosts Scalingo)                   | `metrics-fleet-retention`     | 90 j  |
| `metrics-elastic_agent.*-default` (4 datasets — santé de l'agent lui-même)   | `metrics-fleet-retention`     | 90 j  |
| `metrics-fleet_server.{agent_status,agent_versions}-default`                | `metrics-fleet-retention`     | 90 j  |
| `logs-scalingo.container_stats-default` (Custom API — mémoire des conteneurs) | `metrics-fleet-retention`     | 90 j  |
| `logs-elastic_agent{,.filebeat,.metricbeat,.status_change}-default`         | `logs-elastic-agent-retention`| 90 j  |
| `heartbeat-<version>` (seul `heartbeat-9.1.5` existe au 2026-09-30)         | `heartbeat`                   | 90 j  |

> **Gap comblé le 2026-09-23** : ces datasets Fleet tombaient par défaut sur les
> policies système `metrics@lifecycle` / `logs@lifecycle` (fournies par Elastic,
> `_meta.managed: true`) — **rollover uniquement, aucune phase `delete`** →
> rétention infinie non voulue. Confirmé en direct sur le cluster :
> ```
> GET _ilm/policy/metrics@lifecycle
> GET _ilm/policy/logs@lifecycle
> ```
> Les deux ne renvoient qu'une phase `hot`/`rollover` (30j/50gb), sans `delete`.
>
> Règle Elastic : *"You should never edit managed policies directly"* — on les
> **clone** (`metrics-fleet-retention`, `logs-elastic-agent-retention`) plutôt que
> de les modifier en place. Réf. :
> [Customize built-in ILM policies](https://www.elastic.co/docs/manage-data/lifecycle/index-lifecycle-management/tutorial-customize-built-in-policies).
>
> **90 j retenu par alignement avec `heartbeat`** (même famille : mesure
> périodique de supervision infra), plutôt que 30 j (traces) — décision du
> 2026-09-23.
>
> **Non couvert par ce correctif** (statut inconnu ou hors périmètre observabilité
> applicative, à date du 2026-09-23) : `metricbeat-9.1.5` (policy `metricbeat`,
> même défaut confirmé — mais **aucune trace de ce composant dans ce repo**,
> origine à clarifier avant d'y toucher). Relevé du 2026-09-30 : ~1,07 M docs,
> tous écrits entre le 2026-07-30 ~18h55 et le 2026-07-31 ~11h05, rien depuis.
> Hôtes = identifiants de conteneurs Docker (`f773affe0aa9`…), modules
> `elasticsearch` (3 hôtes, `ingest_pipeline` à 99 %), `kibana`, `http`
> (`fleet-server-es-containerhost`, `elastic-agent`), `beat` : la stack
> Elastic Cloud qui se supervise elle-même, pas une app Scalingo. Très
> probablement un monitoring de déploiement activé ~16 h dans la console Elastic
> Cloud puis coupé. Sans valeur aujourd'hui : supprimable par
> `DELETE _data_stream/metricbeat-9.1.5` ; les data streams système internes
> Kibana/Fleet/Cloud (`.fleet-*`, `.monitoring-*`, `elastic-cloud-logs-*`,
> `.entities.*`, `.items-default`, `.lists-default`, `.workflows-events`).
>
> **Pas d'index template custom pour les flux Fleet** (`metriques/3-index-templates.console`
> ne contient que des rollovers) : le template managé du package Fleet référence
> déjà nos briques `@custom` par convention de nommage (`<type>-<dataset>@custom`)
> — rien à recréer, juste à composer.


> Procédure de contrôle à rejouer après toute nouvelle intégration Fleet :
> [stockage/README](../README.md#procédure-de-contrôle-à-rejouer-après-toute-nouvelle-intégration-fleet).

## Montée de version Heartbeat

Chaque version crée un **nouveau data stream** `heartbeat-<version>`. Rien à
rejouer côté ES : au démarrage, Heartbeat charge son index template qui
référence la policy par son **nom** `heartbeat` (défaut `setup.ilm.policy_name`)
et ne l'écrase pas si elle existe (défaut `setup.ilm.overwrite: false`) — la
rétention 90 j s'applique d'elle-même.

Après le redéploiement :

1. Vérifier le rattachement : `GET _data_stream/heartbeat-*` → le nouveau data
   stream porte `ilm_policy: heartbeat`, et `GET _ilm/policy/heartbeat` a
   toujours sa phase `delete` à 90 j.
2. L'ancien data stream n'est plus alimenté : ILM supprime ses backing indices
   au fil de l'eau, **sauf la dernière** (index d'écriture, jamais supprimé par
   ILM). 90 j après la bascule, le supprimer à la main :
   `DELETE _data_stream/heartbeat-<ancienne version>`.

## Commandes de contrôle (Dev Tools)


```
GET _ilm/policy/metrics-fleet-retention,logs-elastic-agent-retention,heartbeat

GET _component_template/metrics-logstash.node@custom
GET _component_template/metrics-redis.key@custom
GET _component_template/logs-elastic_agent@custom
GET _component_template/logs-scalingo.container_stats@custom

GET _data_stream/metrics-logstash*,metrics-redis*,metrics-system*,metrics-elastic_agent*,metrics-fleet_server*,logs-elastic_agent*,logs-scalingo*,heartbeat-*?filter_path=data_streams.name,data_streams.ilm_policy
```
