# Configuration Elasticsearch — logs & observabilité

Templates et politiques de rétention ES custom de pass-emploi : pipeline logs
(applicatif + router) et observabilité (APM + Heartbeat).

> Ce dossier centralise **toute la config ES custom** versionnée, comme un état
> désiré à la Terraform : rejouer ces fichiers **amène le cluster à l'état déclaré**
> (c'est le sens de « idempotent » ici — pas « sans effet »). Deux **bundles**
> indépendants :
> - **Pipeline logs** (fichiers `1`→`3`) : la chaîne applicative/router qui transite
>   par Logstash. Importer dans l'ordre (dépendance de couches).
> - **Observabilité APM & Heartbeat** (`observabilite.console`) : data streams gérés
>   par Elastic, alimentés en direct (agents APM / Heartbeat), **hors** Logstash.
>   Fichier autonome, importé d'un bloc (pas dans la séquence 1→3).
>
> **Non versionné (volontaire)** : `metrics-apm.*` (auto-géré Elastic, ~90 j), les
> component templates/pipelines x-pack & APM (`logs@mappings`, `apm@mappings`,
> `ecs@mappings`, `*-fallback@ilm`, `*@default-pipeline`…, référencés seulement), et
> tout l'écosystème système (Kibana, Fleet, Security…).

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

| Data stream                          | Index template                | Rétention (ILM)          | Cible |
|---------------------------------------|--------------------------------|--------------------------|-------|
| `logs-prod-default`                   | `logs-prod@template-custom`    | `logs-prod-retention`    | 180 j |
| `logs-staging-default`                | `logs-staging@template-custom` | `logs-staging-retention` | 14 j  |
| `logs-router-{prod,staging}-default`  | `logs-router`                  | `logs-router-retention`  | 30 j  |

> **Router découplé** : `logs-router` a désormais sa propre policy
> `logs-router-retention` (30 j, opérationnel) via la brique dédiée
> `logs-router-retention-custom` — il ne suit plus `logs-prod` (dont la cible passe
> à 180 j pour l'audit légal). La rétention router n'est plus dans
> `logs-router@settings` (qui ne porte plus que shards/replicas).
>
> ⚠️ **`logs-prod-retention` = 180 j est l'état désiré, mais** : (1) la phase
> cold/frozen de l'archive 30→180 j reste à ajouter quand le tier froid existera
> (devis) ; (2) l'appliquer fait croître le flux vers ~1,8 To sur plusieurs mois →
> à monitorer côté capacité. Cf. commentaires dans `1-ilm-policies.console`.

Les champs ECS custom (`event.action`, `event.outcome`, `log.logger`,
`error.*`) sont définis **une seule fois**, dans le component template
`logs@custom`, composé par les templates applicatifs ET le template router.
Ajouter un champ ECS custom = le déclarer dans `logs@custom`, et nulle part
ailleurs.

Les component templates `logs@mappings`, `logs@settings`, `ecs@mappings` sont
fournis par Elasticsearch (x-pack) — on s'y réfère seulement.

## Observabilité APM & Heartbeat — `observabilite.console`

Bundle autonome pour les data streams alimentés en direct par les agents APM et
Heartbeat (**hors** Logstash). Fichier **entièrement reproductible** : policies +
briques de rétention + les 3 index templates APM `@template-custom` (`managed:false`,
donc à nous) + rollovers. Il compose des objets Elastic (component templates,
pipelines de l'intégration APM) référencés par nom — **l'intégration APM doit être
installée**.

Décrit l'**état désiré** (rétentions cibles, arbitrage sizing 2026-07) :

| Data stream(s)                                    | Policy ILM                 | Rétention cible |
|---------------------------------------------------|----------------------------|-----------------|
| `traces-apm-default`, `traces-apm.rum-default`    | `traces-apm-retention`     | 30 j            |
| `logs-apm.error-default`                          | `logs-apm.error-retention` | 90 j            |
| `heartbeat-9.1.5`                                 | `heartbeat`                | 90 j            |

Appliquer ces rétentions **réduit** l'existant (60 j / ∞) → suppression au prochain
passage ILM (voulu), matérialisée par les rollovers en fin de fichier.

**Mécanisme de rétention** (miroir de `logs@custom`) : elle était centralisée dans la
brique partagée `apm-retention-custom` (composée en dernier par les 3 templates → elle
gagnait sur tout). On la **vide** et on la porte **par flux** dans les briques
`<flux>@custom`, désormais les dernières à poser un `index.lifecycle.name` :

| Brique                     | Policy pointée             | Flux            |
|----------------------------|----------------------------|-----------------|
| `traces-apm@custom`        | `traces-apm-retention`     | traces (30 j)   |
| `traces-apm.rum@custom`    | `traces-apm-retention`     | rum (30 j)      |
| `logs-apm.error@custom`    | `logs-apm.error-retention` | error (90 j)    |
| `apm-retention-custom`     | *(vidée, no-op)*           | —               |

**Rappel** : la cible `logs-prod` 180 j est figée dans `1-ilm-policies.console`
(bundle logs), avec sa phase cold/frozen encore à ajouter (tier froid = devis).

## Application

Dans **Kibana → Dev Tools → Import requests**, importer puis exécuter.

**Bundle pipeline logs** — dans l'ordre (les index templates référencent les
component templates et les policies) :

1. `1-ilm-policies.console`
2. `2-component-templates.console`
3. `3-index-templates.console`

**Bundle observabilité** — `observabilite.console`, d'un bloc (ordre interne géré
dans le fichier : policies → briques → templates → rollovers). Indépendant du
bundle logs.

L'opération est idempotente au sens « état désiré » : rejouer amène le cluster à
l'état déclaré dans les fichiers.

## Rollover

Un rollover matérialise sur les **nouveaux** backing indices ce qui ne s'applique
pas rétroactivement. Deux cas distincts :

1. **Changement de _nom_ de policy** (repointage) — déjà **inclus en fin de bundle**
   (`3-index-templates.console` pour `router`, `observabilite.console` pour `error`).
   Rien à lancer à la main : importer le bundle suffit.
2. **Changement de _mappings_** (ex. nouveau champ dans `logs@custom`) — à lancer
   après coup sur les flux concernés (non destructif ; l'ILM expire les anciens) :

```
POST logs-prod-default/_rollover
POST logs-staging-default/_rollover
POST logs-router-prod-default/_rollover
POST logs-router-staging-default/_rollover
```

> Un changement de _contenu_ de policy (ex. `60d` → `30d` sur un même nom) s'applique
> **sans** rollover : inutile de rejouer les flux concernés.

## Vérification

Les API de templates n'acceptent pas les listes séparées par virgules — un GET
par ligne :

```
GET _ilm/policy/logs-prod-retention,logs-router-retention,logs-staging-retention

GET _component_template/logs@custom
GET _component_template/logs-router@mappings
GET _component_template/logs-router@settings
GET _component_template/logs-prod-retention-custom
GET _component_template/logs-router-retention-custom
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

### Observabilité (après import de `observabilite.console`)

```
GET _ilm/policy/traces-apm-retention
GET _ilm/policy/logs-apm.error-retention
GET _ilm/policy/heartbeat

GET _component_template/apm-retention-custom
GET _component_template/traces-apm@custom
GET _component_template/traces-apm.rum@custom
GET _component_template/logs-apm.error@custom

GET _data_stream/traces-apm-default,traces-apm.rum-default,logs-apm.error-default,heartbeat-9.1.5
```

- Après les rollovers, le backing index le plus récent de chaque flux doit porter
  la bonne `ilm_policy` (traces/rum → `traces-apm-retention`, error →
  `logs-apm.error-retention`, heartbeat → `heartbeat`).
- `apm-retention-custom` doit être **vide** (`template.settings` sans `lifecycle`).

### Contrôle post-application (est-ce *effectivement* appliqué ?)

Les GET ci-dessus montrent ce qu'on a écrit ; ces contrôles montrent l'état réel.

**1. Rétention effective de chaque policy** (le `delete.min_age` attendu) :
```
GET _ilm/policy/logs-prod-retention,logs-router-retention,logs-staging-retention,traces-apm-retention,logs-apm.error-retention,heartbeat?filter_path=*.policy.phases.delete.min_age
```
Attendu : logs-prod `180d`, router `30d`, staging `14d`, traces `30d`, error `90d`,
heartbeat `90d`.

**2. Policy par flux ET par backing index** (vérifie que les rollovers ont repointé) :
```
GET _data_stream/logs-prod-default,logs-router-prod-default,logs-router-staging-default,logs-staging-default,traces-apm-default,traces-apm.rum-default,logs-apm.error-default,heartbeat-9.1.5?filter_path=data_streams.name,data_streams.ilm_policy,data_streams.indices.index_name,data_streams.indices.ilm_policy
```
Attendu : le backing index **le plus récent** de `router` porte `logs-router-retention`,
celui d'`error` porte `logs-apm.error-retention` (les anciens gardent l'ancienne
policy jusqu'à expiration — normal).

**3. Aucun index bloqué en erreur ILM** (câblage cassé, policy introuvable…) :
```
GET .ds-*/_ilm/explain?only_errors=true&filter_path=indices.*.index,indices.*.step,indices.*.step_info
```
Attendu : réponse **vide** (`{}`). Sinon, l'index listé pointe le problème.

**4. Volumes réels** (pour recaler la projection après purge ILM) :
```
GET _data_stream/_stats?human
```
