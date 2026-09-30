# Runbook — disque des nœuds Elasticsearch

> **Type** : tutoriel (Diataxis). Quoi faire quand l'[alerte 11](../supervision/alertes-stack-observabilite.md#alerte-11--disque-des-nœuds-elasticsearch-autoops)
> (AutoOps) signale un nœud Elasticsearch qui se remplit.
>
> Rétentions et volumétrie attendues : [`stockage/`](../stockage/README.md).
> Toutes les requêtes se lancent dans Kibana → Dev Tools.

Elasticsearch réagit au remplissage d'un nœud en trois paliers (*watermarks*).
Chacun durcit le précédent ; le dernier arrête l'ingestion des logs.

| Palier | Seuil | Effet côté Elasticsearch | Délai pour agir |
|---|---|---|---|
| préavis (AutoOps) | 75 % | aucun : 10 points avant le palier low | semaines |
| low | 85 % | plus aucun nouveau shard sur ce nœud | jours |
| high | 90 % | des shards quittent ce nœud | heures |
| flood stage | 95 % | **écriture bloquée** sur les index de ce nœud : l'ingestion s'arrête | immédiat |

> **Nœud frozen** (`f`) : son disque est occupé à ~90 % en permanence par le
> cache des searchable snapshots, réservé d'office. C'est normal, et Elasticsearch
> lui applique des seuils à part. Une alerte sur ce nœud seul n'est pas un
> remplissage de données.

## 1. Situer le remplissage

```
GET _cat/allocation?v&s=disk.percent:desc
GET _cat/shards?v&expand_wildcards=all&s=store:desc&h=index,shard,prirep,store,node&size=20
```

- un seul nœud plein, les autres non → déséquilibre de shards : Elasticsearch le
  corrige lui-même à partir du palier high ; rien à faire au palier low ;
- tous les nœuds d'un même tier (hot ou warm) montent ensemble → le volume
  dépasse la capacité : étape 2.

## 2. Trouver le flux qui grossit

```
GET _cat/indices/.ds-*?v&expand_wildcards=all&s=store.size:desc&h=index,store.size,docs.count&size=20
```

Comparer au volume attendu du [plan de rétention](../stockage/logs/README.md)
(`logs-prod` ~31 Go/j, traces APM et router ~55 Go/j). Un flux nettement
au-dessus signale une hausse de volume côté application (logs de debug restés
actifs, boucle d'erreurs) : la traiter à la source.

## 3. Libérer de la place

Par ordre de préférence :

1. **Laisser ILM faire** au palier low : vérifier qu'aucun index n'est bloqué
   (cf. [runbook ILM](runbook-ilm.md)) ; les suppressions planifiées libèrent
   l'espace.
2. **Avancer la rétention** du flux en cause, en accord avec l'équipe : modifier
   sa policy dans `stockage/<bundle>/1-ilm-policies.console` et la rejouer.
3. **Supprimer les plus vieux index** du flux en cause, en dernier recours
   (définitif) :
   ```
   DELETE .ds-<data stream>-<date>-<numéro>
   ```
   Jamais l'index d'écriture (le plus récent) : `GET _data_stream/<data stream>`
   le désigne.
4. **Augmenter la capacité** du tier dans la console Elastic Cloud, si la hausse
   de volume est durable.

## 4. Au palier flood stage

L'écriture est bloquée (`index.blocks.read_only_allow_delete`) : Logstash ne
peut plus indexer, les alertes de backpressure et de backlog Redis suivent.
Libérer de la place tout de suite (étape 3, points 3 ou 4). Elasticsearch lève
le blocage de lui-même dès que le nœud repasse sous le palier high ; vérifier :

```
GET _all/_settings/index.blocks.read_only_allow_delete?expand_wildcards=all
```

Puis contrôler que Logstash rattrape son retard : backlog Redis et DLQ, cf.
[runbook Logstash](runbook-logstash.md).

## Cluster en statut red

Au moins un shard principal est indisponible : une partie des données n'est plus
consultable, et l'écriture échoue si c'est un index d'écriture.

```
GET _cat/shards?v&expand_wildcards=all&h=index,shard,prirep,state,unassigned.reason&s=state
GET _cluster/allocation/explain
```

`allocation/explain` donne la raison (disque plein, nœud perdu…). Disque plein :
étapes 1 à 3. Nœud perdu : vérifier l'état du déploiement dans la console Elastic
Cloud.
