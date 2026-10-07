# Stockage — rétention et mapping dans Elasticsearch

Templates et politiques de rétention ES custom de pass-emploi, organisés **par
télémétrie** (au sens ECS — logs / traces / métriques), pas par mode d'ingestion :

| Sous-dossier                | Télémétrie                                                        | Nature                                             |
|------------------------------|--------------------------------------------------------------------|-----------------------------------------------------|
| [`logs/`](./logs/README.md)         | logs applicatifs, router, DLQ/erreurs Logstash, erreurs APM         | événements discrets (une ligne = un fait daté)      |
| [`traces/`](./traces/README.md)     | traces APM (`traces-apm`, `traces-apm.rum`)                        | durée/latence d'une requête (spans, transactions)   |
| [`metriques/`](./metriques/README.md) | Fleet (Logstash, Redis, hosts, agents, Fleet Server) + Heartbeat    | mesures numériques/périodiques de supervision infra |

> **`logs-apm.error` est dans `logs/`, pas `traces/`**, malgré son origine APM :
> une erreur est un événement discret (une ligne = un fait), pas une mesure de
> durée. **`heartbeat` est dans `metriques/`**, bien que classé `logs` par
> Elastic (`data_stream.type: logs`) : c'est une mesure périodique (ping toutes
> les 5s), pas un événement métier discret. Le classement suit la **nature de
> la donnée**, pas l'étiquette technique du fournisseur.

> Ce dossier centralise **toute la config ES custom** versionnée, comme un état
> désiré à la Terraform : rejouer ces fichiers **amène le cluster à l'état déclaré**
> (c'est le sens de « idempotent » ici — pas « sans effet »). Chaque sous-dossier
> reprend la même structure à 3 fichiers, importés **dans l'ordre** (dépendance de
> couches) :
> - **`1-ilm-policies.console`** — politiques de rétention (rollover, delete).
> - **`2-component-templates.console`** — briques de mapping/rétention composées
>   par les index templates.
> - **`3-index-templates.console`** — assemblage final ; peut être quasi-vide si
>   les templates sont déjà fournis par un package Fleet (cf. `metriques/`).
>
> **Alertes** : hors de ce dossier, dans
> [`supervision/`](../supervision/alertes-stack-observabilite.md) — une alerte mélange
> souvent plusieurs télémétries (ex. l'alerte 4 lit `metrics-logstash.pipeline`
> pour détecter un problème qui impacte `logs-prod`).
>
> **Non versionné (volontaire)** : les
> component templates/pipelines x-pack & APM (`logs@mappings`, `apm@mappings`,
> `ecs@mappings`, `*-fallback@ilm`, `*@default-pipeline`…, référencés seulement),
> et tout l'écosystème système (Kibana, Fleet, Security…).

## Procédure de contrôle (à rejouer après toute nouvelle intégration Fleet)

1. **Lister tous les data streams + leur policy** :
   ```
   GET _data_stream?filter_path=data_streams.name,data_streams.ilm_policy
   ```
2. **Repérer les policies génériques suspectes** — Elastic fournit 4 policies
   système `{type}@lifecycle` (`logs`, `metrics`, `synthetics`, `traces`). Sur ce
   cluster, `logs@lifecycle` et `metrics@lifecycle` sont **sans phase `delete`**
   (vérifié 2026-09-23). `traces@lifecycle`/`synthetics@lifecycle` ne sont pas
   utilisées ici (nos traces APM ont déjà `traces-apm-retention`, dédiée) — si
   l'une apparaît un jour, **vérifier son contenu avant de supposer le même défaut**.
3. **En cas de doute sur une policy au nom moins évident**, vérifier son contenu :
   ```
   GET _ilm/policy/<nom-policy>?filter_path=*.policy.phases.delete.min_age
   ```
   Absence de résultat pour cette entrée = pas de phase `delete` = rétention infinie.
4. **Contrôler aussi chaque backing index** : la policy d'un data stream ne vaut
   que pour ses index à venir. Un index créé avant le template custom garde la
   policy par défaut (cas des index DLQ du 2026-08-28, restés sur `logs`) :
   ```
   GET .ds-*/_ilm/explain?only_managed=true&filter_path=indices.*.index,indices.*.policy
   ```
   Correction : [runbook ILM, scénario 1](../runbooks/runbook-ilm.md#scénario-1--index-sur-une-policy-par-défaut).
   En continu, l'[alerte 10](../supervision/alertes-stack-observabilite.md#alerte-10--ilm-en-échec-ou-policy-sans-suppression)
   signale les nouveaux index dans ce cas. Les index frozen sont cachés :
   cf. [runbook ILM](../runbooks/runbook-ilm.md#index-frozen-introuvable).

> **Règle d'or** : à chaque nouvelle intégration Fleet installée (nouvel agent,
> nouvelle policy), rejouer les étapes 1, 2 et 4 avant de considérer l'intégration
> « terminée » — le défaut silencieux (policy générique sans `delete`) est la
> norme chez Elastic pour les intégrations sur étagère, pas l'exception.

## Import — ordre et portée

Chaque sous-dossier (`logs/`, `traces/`, `metriques/`) est un **bundle
indépendant** : importer ses 3 fichiers dans l'ordre (`1` → `2` → `3`), les
bundles entre eux n'ont pas d'ordre imposé. Deux briques sont **partagées entre
deux bundles** (jamais redéfinies deux fois) :
- `apm-retention-custom` — définie dans `traces/2-component-templates.console`,
  référencée (vidée, no-op) par `traces/3-index-templates.console` **et**
  `logs/3-index-templates.console` (flux `logs-apm.error`).
- `pass-emploi-logs@mappings` — définie dans `logs/2-component-templates.console`,
  composée par les templates applicatifs, erreurs Logstash, router et `logs-apm.error`.


## Contrôles transverses (Dev Tools)

### Contrôle post-application (est-ce *effectivement* appliqué ?)

Les GET ci-dessus montrent ce qu'on a écrit ; ces contrôles montrent l'état réel.

**1. Rétention effective de chaque policy** (le `delete.min_age` attendu) :
```
GET _ilm/policy/logs-prod-retention,logs-router-retention,logs-staging-retention,logs-perf-retention,logs-logstash-errors-retention,logs-logstash-dlq-retention,logs-apm.error-retention,traces-apm-retention,metrics-fleet-retention,logs-elastic-agent-retention,heartbeat,metrics-apm-retention,metrics-apm-1m-retention?filter_path=*.policy.phases.delete.min_age
```
Attendu : logs-prod `90d`, router `21d`, staging `14d`, perf `2d`, logstash-errors
`30d`, logstash-dlq `30d`, apm.error `90d`, traces `21d`, metrics-fleet `90d`,
elastic-agent `90d`, heartbeat `90d`, metrics-apm `90d`, metrics-apm-1m `21d`.

**2. Policy par flux ET par backing index** (vérifie que les rollovers ont repointé) :
```
GET _data_stream/logs-prod-default,logs-router-prod-default,logs-router-staging-default,logs-staging-default,logs-perf-default,traces-apm-default,traces-apm.rum-default,logs-apm.error-default,heartbeat-*,metrics-logstash.node-default,metrics-redis.key-default?filter_path=data_streams.name,data_streams.ilm_policy,data_streams.indices.index_name,data_streams.indices.ilm_policy
```
Attendu : le backing index **le plus récent** de chaque flux porte la policy
ci-dessus (les anciens gardent l'ancienne policy jusqu'à expiration — normal).

**3. Aucun index bloqué en erreur ILM** (câblage cassé, policy introuvable…) :
```
GET .ds-*/_ilm/explain?only_errors=true&filter_path=indices.*.index,indices.*.step,indices.*.step_info
```
Attendu : réponse **vide** (`{}`). Sinon, l'index listé pointe le problème.

**4. Volumes réels** (pour recaler la projection après purge ILM) :
```
GET _data_stream/_stats?human
```



Commandes de contrôle propres à chaque télémétrie : dans le README de son sous-répertoire.
