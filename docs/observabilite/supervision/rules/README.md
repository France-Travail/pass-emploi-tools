# Règles d'alerte Kibana

Les règles d'alerte Kibana sont **générées** : chaque règle est décrite par un
fichier JSON, et un script assemble les fichiers `.console` qui se collent dans
Kibana → Dev Tools. Un second script produit, depuis les mêmes JSON, les Workflows
qui envoient les alertes dans Tchap.

Ce qu'elles signalent et pourquoi : [alertes applicatives](../alertes-applicatives.md),
[de la stack](../alertes-stack-observabilite.md), [de sécurité](../alertes-securite.md).

## Où modifier quoi

```
rules/
├── 1-securite/                 ← un répertoire par périmètre
│   ├── _modele.console         ←   le texte du fichier généré autour des règles
│   └── V1.json                 ←   une règle = un fichier JSON
├── 2-applicatives/             ←   S2, S3…, A1 à A13…
├── 3-stack-observabilite/      ←   1a à 10, 6a, 6b, 14
├── 4-tchap/                    ←   Tchap - Envoi en échec
├── 5-tchap-expiration-bot/     ←   expiration du compte bot (et son pipeline, son index)
├── generer-regles.py           ← le générateur (aucune règle dedans)
└── generated/                  ← GÉNÉRÉ : à coller dans Dev Tools, ne pas modifier
    └── <n>-rules-<périmètre>.console
```

| Je veux changer… | Je modifie… |
|---|---|
| une règle : seuil, requête, fréquence, message, étapes « À vérifier » | son fichier `<périmètre>/<code>.json` |
| un commentaire d'en-tête, une note entre deux règles, une requête qui n'est pas une règle (pipeline, index…) | `<périmètre>/_modele.console` |
| la page qui explique une alerte (seuil, calibrage) | `../alertes-*.md` |

**Ne jamais modifier `generated/`** : ces fichiers sont écrasés à chaque
génération, et le check de la PR échoue s'ils ne correspondent plus à leurs sources.

## Le fichier JSON d'une règle

C'est le JSON de la règle tel que Kibana le reçoit, avec deux commodités :

- le message de chaque action Mattermost (`actions[].params.body`) est un **objet
  JSON**, lisible ; le générateur le transforme en texte pour Kibana ;
- les clés qui commencent par `_` ne sont pas envoyées à Kibana :

| Clé | Rôle |
|---|---|
| `_id` | identifiant de la règle dans Kibana (`PUT kbn:/api/alerting/rule/<_id>`) |
| `_methode` | `POST` pour une règle à créer (avec `rule_type_id` et `consumer`) ; `PUT` par défaut |
| `_commentaire` | lignes de commentaire écrites au-dessus de la règle dans le fichier généré |
| `_message` | le message d'une règle **sans** action Mattermost (même format qu'un `body`) : c'est lui que Tchap affiche |
| `_tchap` | règle ES\|QL en `groupBy: all` : `ligne`, le gabarit d'une ligne de résultat dans Tchap (`{0}`, `{1}`… = colonnes), et `vide`, le texte quand la relecture ne trouve plus rien |

Le message Tchap de chaque règle est lu **ici**, dans ce fichier, jamais dans
l'action Mattermost générée : retirer Mattermost ne change pas les messages Tchap.

Les étapes « À vérifier » suivent les
[principes des étapes à vérifier](../alertes-applicatives.md#principes-des-étapes-à-vérifier),
et l'Investigation guide (`artifacts.investigation_guide`) reprend les mêmes étapes.

## Générer

Depuis `docs/observabilite/supervision/` :

```bash
FEATURE_NOTIFIER_ALERTES_MATTERMOST=true python3 -I rules/generer-regles.py
python3 -I workflows/tchap/generer-workflows.py
```

1. `generer-regles.py` écrit `generated/<n>-rules-<périmètre>.console` : le
   `_modele.console` du périmètre, où chaque repère `@@REGLE <code>@@` est
   remplacé par la règle `<code>.json`.
2. `generer-workflows.py` écrit les Workflows Tchap
   (`../workflows/tchap/generated/`), depuis les mêmes JSON.

Commiter les sources **et** les fichiers générés dans la même PR.
`python3 -I rules/generer-regles.py --verifier` compare `generated/` à ses
sources sans rien écrire.

## `FEATURE_NOTIFIER_ALERTES_MATTERMOST`

Feature flipping, selon la convention des apps : **active seulement si elle vaut
`true`**.

- `true` : les règles générées gardent leurs actions Mattermost (jusqu'au
  décommissionnement de Mattermost, le 1er novembre 2026) ;
- absente : elles n'ont plus que leur action Tchap. Les messages Tchap ne changent pas.

Le CI la fixe à `true`. Le jour de la bascule : régénérer sans elle, passer celle
du CI (`.github/workflows/verifier-alertes.yml`) à `false` dans le même commit,
redéployer.

## Le check de la PR

« Alertes Kibana et Workflows Tchap à jour avec leurs générateurs »
([`verifier-alertes.yml`](../../../../.github/workflows/verifier-alertes.yml))
échoue si :

- un fichier de `generated/` ne correspond plus à ses sources (générateur oublié,
  ou fichier généré modifié à la main) ;
- un générateur refuse une règle : JSON invalide, règle placée dans aucun
  `_modele.console` ou deux fois, code défini deux fois, message absent,
  Workflow de salon inconnu, règle ES|QL dont le champ de temps n'est pas
  `@timestamp` ou sans `_tchap.ligne`.

## Déployer

Manuel, jamais par le CI :

1. Dans Kibana → Dev Tools, coller le bloc de la règle depuis `generated/`
   (`PUT` pour une règle existante, `POST` pour une règle à créer).
2. Si le déploiement passe par l'API avec une clé API (script, `curl`) plutôt
   que par Dev Tools : faire ensuite **« Update API keys »** sur les règles, sinon
   elles tournent avec cette clé et tombent en panne à son expiration (cf.
   [objets Kibana](../objets-kibana.md#slo-et-règles-console)).
3. Workflows Tchap : cf. [Workflows Tchap, mise en service](../workflows/tchap/README.md#mise-en-service).

## Ajouter une règle

1. Copier le JSON d'une règle du même type (KQL, ES|QL, Uptime, SLO) dans le
   répertoire du périmètre, sous le nom `<code>.json`, et l'adapter. Pour une règle
   à créer : `_methode: "POST"`, avec `rule_type_id` et `consumer`.
2. Placer le repère `@@REGLE <code>@@` dans le `_modele.console` du périmètre.
3. Générer, commiter, déployer.
