# Règles d'alerte Kibana

Les règles d'alerte Kibana sont **générées** : on modifie leurs sources, puis un
script produit les fichiers `.console` qui se collent dans Kibana → Dev Tools.
Le même passage produit les Workflows qui envoient les alertes dans Tchap.

Ce qu'elles signalent et pourquoi : [alertes applicatives](../alertes-applicatives.md),
[de la stack](../alertes-stack-observabilite.md), [de sécurité](../alertes-securite.md).

## Où modifier quoi

```
rules/
├── generer-regles.py                                  ← source : règles définies champ par champ
├── 1-rules-applicatives-definitions-kibana.py         ← source : règles définies au format de Kibana
├── 2-rules-stack-observabilite-definitions-kibana.py  ←   (un fichier par fichier généré)
├── 5-rules-tchap-expiration-bot-definitions-kibana.py ←
├── modeles/<fichier>.console                          ← source : le texte autour des règles
├── 4-rules-tchap.console                              ← écrit à la main, non généré
└── generated/<fichier>.console                        ← GÉNÉRÉ : à coller dans Dev Tools, ne pas modifier
```

| Je veux changer… | Je modifie… |
|---|---|
| le seuil, la requête ou le message d'une règle A1 à A13, A4a/b, A5a/b, 6a/b, 14, V1 | sa définition dans `generer-regles.py` (dictionnaire `REGLES`, une entrée par code) |
| une règle SLO (S2, S3…), de la stack (1a à 10) ou l'expiration du bot | sa définition dans `<n>-rules-<périmètre>-definitions-kibana.py` : `regle` (le corps JSON de la règle) et `messages` (son message, un par groupe d'action) |
| un commentaire d'en-tête, une note entre deux règles, une requête qui n'est pas une règle (pipeline, index…) | `modeles/<fichier>.console` |
| la page qui explique une alerte (seuil, calibrage) | `../alertes-*.md` |

**Ne jamais modifier `generated/`** : ces fichiers sont écrasés à chaque génération,
et le check de la PR échoue s'ils ne correspondent plus à leurs sources.

Deux formes de définition, pour une seule raison historique : les règles A1 à
V1 ont été écrites pour le générateur, champ par champ (titre, étapes « À
vérifier », dashboards, sessions Discover). Les autres existaient avant lui :
elles sont reprises au format de Kibana, sans changement. Les deux produisent
le même résultat.

## Générer

Depuis `docs/observabilite/supervision/` :

```bash
FEATURE_NOTIFIER_ALERTES_MATTERMOST=true python3 -I rules/generer-regles.py
python3 -I workflows/tchap/generer-workflows.py
```

1. `generer-regles.py` assemble chaque fichier de `generated/` : le modèle
   `modeles/<fichier>.console`, où chaque repère `@@REGLE <code>@@` est remplacé
   par la règle générée depuis sa définition.
2. `generer-workflows.py` produit les Workflows Tchap
   (`../workflows/tchap/generated/`) : le message Tchap de chaque règle est lu
   dans sa définition, jamais dans son action Mattermost.

Commiter les sources **et** les fichiers générés dans la même PR.
`python3 -I rules/generer-regles.py --verifier` compare `generated/` à ses
sources sans rien écrire.

## `FEATURE_NOTIFIER_ALERTES_MATTERMOST`

Feature flipping, selon la convention des apps : **active seulement si elle vaut
`true`**.

- `true` : les règles générées gardent leurs actions Mattermost (jusqu'au
  décommissionnement de Mattermost, le 1er novembre 2026) ;
- absente : elles n'ont plus que leur action Tchap. Le message Tchap ne change pas.

Le CI la fixe à `true`. Le jour de la bascule : régénérer sans elle, passer celle
du CI (`.github/workflows/verifier-alertes.yml`) à `false` dans le même commit,
redéployer.

## Le check de la PR

« Alertes Kibana et Workflows Tchap à jour avec leurs générateurs »
([`verifier-alertes.yml`](../../../../.github/workflows/verifier-alertes.yml))
échoue si :

- un fichier de `generated/` ne correspond plus à ses sources (générateur oublié,
  ou fichier généré modifié à la main) ;
- un générateur refuse une règle : message absent ou qui n'est pas du JSON valide
  tel quel (l'éditeur de Kibana ne pourrait pas l'afficher), Workflow de salon
  inconnu, règle ES|QL dont le champ de temps n'est pas `@timestamp`, règle placée
  dans aucun modèle ou deux fois.

## Déployer

Manuel, jamais par le CI :

1. Dans Kibana → Dev Tools, coller le bloc de la règle depuis `generated/`
   (`PUT` pour une règle existante ; une nouvelle règle se crée par `POST`, cf.
   l'en-tête de son bloc).
2. Si le déploiement passe par l'API avec une clé API (script, `curl`) plutôt
   que par Dev Tools : faire ensuite **« Update API keys »** sur les règles, sinon
   elles tournent avec cette clé et tombent en panne à son expiration (cf.
   [objets Kibana](../objets-kibana.md#slo-et-règles-console)).
3. Workflows Tchap : cf. [Workflows Tchap, mise en service](../workflows/tchap/README.md#mise-en-service).

## Ajouter une règle

1. Lui choisir un code et l'écrire champ par champ dans `REGLES` de
   `generer-regles.py`, sur le modèle d'une règle du même type (KQL, ES|QL,
   Uptime). Une nouvelle règle n'a pas besoin de la forme « format de Kibana ».
2. Placer le repère `@@REGLE <code>@@` dans le modèle du fichier voulu
   (`modeles/<fichier>.console`).
3. Générer, commiter, déployer avec `POST` (création).

Les étapes « À vérifier » suivent les
[principes des étapes à vérifier](../alertes-applicatives.md#principes-des-étapes-à-vérifier).
