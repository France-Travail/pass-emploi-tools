# Runbook — rétention ILM

> **Type** : tutoriel (Diataxis). Quoi faire quand l'[alerte 10](../supervision/alertes-stack-observabilite.md#alerte-10--ilm-en-échec-ou-policy-sans-suppression)
> sonne : un index n'applique pas la rétention prévue.
>
> Rétentions attendues et scripts : [`stockage/`](../stockage/README.md).
> Toutes les requêtes se lancent dans Kibana → Dev Tools.

Un index qui n'applique pas sa rétention ne casse rien tout de suite : il grossit
sans être supprimé (policy par défaut, sans phase `delete`), ou reste bloqué sur
une étape. On a des jours pour corriger, pas des minutes.

## Vue d'ensemble

| Ce que dit l'alerte | Scénario |
|---|---|
| `index_policy_par_defaut` > 0 | [1 — Index sur une policy par défaut](#scénario-1--index-sur-une-policy-par-défaut) |
| `index_en_echec` > 0 | [2 — Étape ILM en échec](#scénario-2--étape-ilm-en-échec) |

Hors alerte, à connaître : [3 — Policy inexistante](#scénario-3--policy-inexistante-non-alerté)
et [Index frozen introuvable](#index-frozen-introuvable).

---

## Scénario 1 — Index sur une policy par défaut

**Signature** : un index de nos flux est sur `logs`, `metrics`, `logs@lifecycle`,
`metrics@lifecycle`, `metricbeat` ou une policy `*-default_policy` de package.
Les policies Elastic `@lifecycle` n'ont pas de phase `delete` : rétention infinie.

**Cause habituelle** : la brique `<type>-<dataset>@custom` qui porte notre policy
manque (scripts `stockage/*/2-component-templates.console` jamais rejoués, ou
nouvelle intégration Fleet). Les index créés depuis retombent sur la policy du
package.

1. **Voir si c'est le data stream ou seulement d'anciens index** :
   ```
   GET _data_stream/<data stream>?filter_path=data_streams.name,data_streams.ilm_policy
   ```
   - le data stream affiche une policy par défaut → étape 2 puis 3 ;
   - il affiche la bonne policy → les anciens index seuls sont en cause : étape 3.
2. **Rejouer les briques** du bundle concerné, dans l'ordre :
   `stockage/<logs|traces|metriques>/1-ilm-policies.console` puis
   `2-component-templates.console`. Pour une nouvelle intégration, ajouter
   d'abord sa brique `@custom` dans `2-component-templates.console`.
3. **Rattacher les index existants** à la policy de leur data stream (appliqué à
   tous ses index, y compris celui en cours d'écriture) :
   ```
   PUT <data stream>/_settings
   { "index.lifecycle.name": "<policy attendue>" }
   ```
   ⚠️ Les index plus vieux que la rétention sont supprimés aussitôt.
4. **Vérifier** : `GET _data_stream/<data stream>?filter_path=data_streams.ilm_policy`
   affiche la bonne policy.

---

## Scénario 2 — Étape ILM en échec

**Signature** : `success: false` dans l'historique ILM. L'index est bloqué sur
une étape (`step: ERROR`) et n'avance plus vers les phases suivantes.

1. **Lire la cause** :
   ```
   GET .ds-*,partial-*/_ilm/explain?expand_wildcards=all&only_errors=true&filter_path=indices.*.index,indices.*.phase,indices.*.failed_step,indices.*.step_info
   ```
2. **Corriger selon `step_info`** :

   | Cause | Correction |
   |---|---|
   | échec de snapshot (`searchable_snapshot`) | vérifier le dépôt : `GET _snapshot/found-snapshots` ; disque du nœud frozen : `GET _cat/allocation?v` |
   | `rollover` refusé (alias, index déjà basculé) | vérifier que l'index n'est plus l'index d'écriture : `GET _data_stream/<data stream>` |
   | autre | chercher le message exact dans la doc Elastic avant toute action |

3. **Relancer l'étape** une fois la cause corrigée :
   ```
   POST <index>/_ilm/retry
   ```
4. **Vérifier** : la requête de l'étape 1 ne renvoie plus l'index.

---

## Scénario 3 — Policy inexistante (non alerté)

**Signature** : `step_info` contient `unable to parse steps for policy [...] as
it doesn't exist`. ILM ne compte pas ce cas comme un échec d'étape :
**l'alerte 10 ne le voit pas**.

**Cause** : des index ont été rattachés à une policy avant sa création (cas du
2026-10-05). Rejouer `stockage/<bundle>/1-ilm-policies.console`. Le message
disparaît au prochain changement d'étape de l'index ; rien d'autre à faire si la
policy existe : `GET _ilm/policy/<policy>?filter_path=*.modified_date`.

---

## Index frozen introuvable

En phase frozen, ILM remplace l'index par un searchable snapshot renommé
`partial-.ds-…`, **caché** : sans `expand_wildcards=all`, il semble avoir disparu.

```
GET _cat/indices/partial-*?v&expand_wildcards=all&h=index,health,docs.count,store.size&s=index
```

Attendu : tous `green`. `store.size` à `0b` est normal (les données restent dans
le snapshot), comme un disque du nœud frozen occupé à ~90 % (cache réservé
d'office).

---

## Index d'alertes de Kibana jamais supprimés (à nettoyer tous les 3 mois)

**Constat** : les index où Kibana enregistre les alertes (`.internal.alerts-*`)
basculent sur un nouvel index chaque mois, mais leur policy `.alerts-ilm-policy`
n'a pas de phase `delete`. Elle est gérée et réécrite par Kibana : une phase
`delete` ajoutée à la main serait perdue. Sans nettoyage, ~10 shards de plus
chaque mois (index de quelques Mo, mais 2 shards chacun).

**Règle** : garder les 3 derniers mois de chaque série, et toujours l'index le
plus récent (celui qui reçoit les nouvelles alertes).

1. **Lister les index** :
   ```
   GET _cat/indices/.internal.alerts-*?v&expand_wildcards=all&h=index,docs.count,store.size,creation.date.string&s=index
   ```
2. **Vérifier qu'aucun index à supprimer ne contient d'alerte active** : Kibana
   met à jour une alerte en cours dans l'index où elle a été créée, la supprimer
   lui fait perdre son suivi.
   ```
   GET .internal.alerts-*/_search?expand_wildcards=all
   { "size": 0, "query": { "term": { "kibana.alert.status": "active" } },
     "aggs": { "par_index": { "terms": { "field": "_index", "size": 100 } } } }
   ```
3. **Supprimer** les index de plus de 3 mois absents de la réponse de l'étape 2
   (définitif, l'historique de ces alertes est perdu) :
   ```
   DELETE <index 1>,<index 2>,…
   ```
