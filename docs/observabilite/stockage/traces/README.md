# Stockage des traces

Rétention des traces APM. Collecte : [collecte/traces](../../collecte/traces/README.md). Import des 3 `.console` de ce dossier : [stockage/README](../README.md#import--ordre-et-portée).


| Data stream                | Index template                     | Rétention (ILM)      | Cible |
|------------------------------|-------------------------------------|------------------------|-------|
| `traces-apm-default`         | `traces-apm@template-custom`        | `traces-apm-retention` | 21 j  |
| `traces-apm.rum-default`     | `traces-apm.rum@template-custom`    | `traces-apm-retention` | 21 j  |

Alimentés en direct par le SDK APM (agents api/web/connect) — **hors** Logstash.
⚠️ Dépendance : l'intégration APM d'Elastic doit être installée (fournit
`apm@mappings`, `traces@mappings`, `*-fallback@ilm`… — référencés seulement,
jamais versionnés ici).


## Commandes de contrôle (Dev Tools)


```
GET _ilm/policy/traces-apm-retention

GET _component_template/apm-retention-custom
GET _component_template/traces-apm@custom
GET _component_template/traces-apm.rum@custom

GET _data_stream/traces-apm-default,traces-apm.rum-default
```

- Après les rollovers (aucun requis, cf. `traces/3-index-templates.console`), le
  backing index le plus récent de chaque flux doit porter `traces-apm-retention`.
- `apm-retention-custom` doit être **vide** (`template.settings` sans `lifecycle`).
