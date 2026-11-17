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
│   └── S1.json                 ←   une règle = un fichier JSON
├── 2-applicatives/             ←   SLO2, SLO3…, A1 à A11…
├── 3-stack-observabilite/      ←   M1a à M10, M6a, M6b, M13
├── 4-tchap/                    ←   Tchap - Envoi en échec
├── 5-tchap-expiration-bot/     ←   expiration du compte bot (et son pipeline, son index)
├── scripts/                    ← les générateurs : règles, puis notifications (aucune règle dedans)
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

C'est le JSON de la règle tel que Kibana le reçoit, plus des clés qui commencent
par `_`, qui ne lui sont pas envoyées :

| Clé | Rôle |
|---|---|
| `_id` | identifiant de la règle dans Kibana (`PUT kbn:/api/alerting/rule/<_id>`) |
| `_methode` | `POST` pour une règle à créer (avec `rule_type_id` et `consumer`) ; `PUT` par défaut |
| `_commentaire` | lignes de commentaire écrites au-dessus de la règle dans le fichier généré |
| `_message` | le message de la règle au format pivot, indépendant du canal (cf. [ci-dessous](#le-message-dune-règle)) |

Les étapes « À vérifier » suivent les
[principes des étapes à vérifier](../alertes-applicatives.md#principes-des-étapes-à-vérifier),
et l'Investigation guide (`artifacts.investigation_guide`) reprend les mêmes étapes.

## Le message d'une règle

Le message d'une règle est écrit **une fois**, dans la clé `_message` de son fichier
JSON, sans rien qui dépende d'un canal. Chaque canal en fait son rendu :

1. **extraire** les règles qui notifient et leur message, et le valider :
   [`scripts/notifications/1-extraire.py`](scripts/notifications/1-extraire.py), commun à tous les canaux ;
2. **transformer** le message pour le canal : `scripts/notifications/<canal>/2-transformer.py` ;
3. **charger** le résultat dans le format de sortie du canal : `scripts/notifications/<canal>/3-charger.py`.

Seul canal aujourd'hui : Tchap, lancé par
[`scripts/generer-notifications-tchap.py`](scripts/generer-notifications-tchap.py)
(étapes 2 et 3 : variables en Liquid, relance ES|QL, burn rate en français, `=`
remplacé, échappement HTML, un seul lien cliquable). Un autre canal (Mattermost,
Slack, Teams, e-mail…) ajoute ses propres étapes 2 et 3 dans
`scripts/notifications/<canal>/`, et son script de lancement dans `scripts/`, sans
toucher au pivot.

### Le format

```json
"_message": {
  "titre": "**API injoignable — prod (pass-emploi-api)**",
  "gravite": "critique",
  "sections": [
    { "titre": "Détail", "lignes": [ "URL : {etat.monitorUrl}", "Motif : {etat.latestErrorMessage}" ] },
    { "titre": "À vérifier", "lignes": [ "1. L'état de l'app dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)" ] }
  ],
  "liens": {
    "Dashboards": [ { "nom": "[Scalingo] Dashboard des apps", "url": "https://dashboard.scalingo.com/apps" } ],
    "Runbook": [ { "nom": "Investiguer un incident applicatif", "url": "https://github.com/…" } ]
  },
  "retablissement": { "titre": "**API de nouveau joignable — prod (pass-emploi-api)**", "sections": [ … ] },
  "resultat": { "ligne": "`{1}` : {0} échecs ({2})", "vide": "…" }
}
```

| Clé | Contenu |
|---|---|
| `titre` | sans émoji : le canal le déduit de la gravité |
| `gravite` | `critique`, `avertissement` ou `information` ; le rétablissement a la sienne |
| `fenetres` | règle burn rate, à la place de `gravite` : la gravité de chaque fenêtre notifiée (`"medium": { "gravite": "information", "essentiel": true }`) ; une fenêtre absente n'est pas notifiée. Le canal n'envoie qu'une alerte nouvelle ou qui s'aggrave |
| `essentiel` | sections et liens de la version allégée, pour une fenêtre `"essentiel": true` |
| `sections` | titre et lignes : explications, étapes « À vérifier »… |
| `liens` | par section (Dashboards, Discover sessions, Runbook…), des liens nommés |
| `liens_dependabot` | `true` pour une alerte CVE : la page Dependabot de chaque repo concerné, lue dans les documents (`labels.dependabot_url`) |
| `retablissement` | facultatif : le message quand l'alerte se rétablit (règles Uptime) |
| `resultat` | règles ES\|QL en `groupBy: all` : gabarit d'une ligne de résultat (`{0}`, `{1}`… = colonnes) et texte quand il n'y en a plus |

Dans les textes, seulement `**gras**`, `` `code` `` et `[nom](url)`. Les
variables, entre accolades, sont celles de `VARIABLES` dans `1-extraire.py` (`{valeur}`,
`{groupe}`, `{debut}`, `{raison}`, `{burn_rate_long}`…), plus `{etat.<champ>}`
pour l'état d'une règle Uptime. Une variable inconnue, une gravité inconnue ou
une section de liens vide font échouer la génération des règles.

## Générer

Depuis `docs/observabilite/supervision/` :

```bash
python3 -I rules/scripts/generer-regles-alerting.py
python3 -I rules/scripts/generer-notifications-tchap.py
```

1. `generer-regles-alerting.py` écrit `generated/<n>-rules-<périmètre>.console` : le
   `_modele.console` du périmètre, où chaque repère `@@REGLE <code>@@` est
   remplacé par la règle `<code>.json`.
2. `generer-notifications-tchap.py` écrit les Workflows Tchap
   (`../workflows/tchap/generated/`), depuis les mêmes JSON.

Commiter les sources **et** les fichiers générés dans la même PR.
`python3 -I rules/scripts/generer-regles-alerting.py --verifier` compare `generated/` à ses
sources sans rien écrire.

## Le check de la PR

« Règles d'alerte Kibana et Workflows Tchap à jour avec leurs générateurs »
([`elastic-rules-and-workflows-checks.yml`](../../../../.github/workflows/elastic-rules-and-workflows-checks.yml))
échoue si :

- un fichier de `generated/` ne correspond plus à ses sources (générateur oublié,
  ou fichier généré modifié à la main) ;
- un générateur refuse une règle : JSON invalide, règle placée dans aucun
  `_modele.console` ou deux fois, code défini deux fois, `_message` absent ou
  invalide, Workflow de salon inconnu, règle ES|QL dont le champ de temps n'est
  pas `@timestamp` ou sans `_message.resultat.ligne`.

Les générateurs ont leurs tests, sans dépendance (bibliothèque standard Python),
lancés aussi par le CI : `python3 -I -m unittest discover -s docs/observabilite/supervision/tests -v`
depuis la racine du repo. Les lancer après toute modification d'un générateur ou
d'un gabarit.

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
