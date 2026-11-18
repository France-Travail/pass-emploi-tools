# SLO — objectifs et seuils

Les SLO de prod (`generated/1-slos.console`) et leurs règles burn rate
(`../rules/2-applicatives/SLO*.json`) sont **générés** : leurs réglages se changent dans
[`seuils.json`](seuils.json), puis `python3 -I rules/scripts/generer-regles-alerting.py`
depuis `kibana/`, et se déploient depuis Kibana → Dev Tools, **avec sa propre
session** (un SLO ou une règle créé par une clé API tourne avec elle).

```json
"SLO3-invite": { "objectif": 0.9, "burn_rate": { "high": 2 } }
```

La clé est le code de la règle burn rate du SLO (nom de son fichier JSON).

## `objectif`

La part des événements qui doivent réussir sur **30 jours glissants**, entre 0 et 1 :
`0.99` = 99 %. Le reste est la **marge d'erreur** du mois (le « budget ») : 1 % des
connexions peuvent échouer sans rompre la promesse.

Il donne la cible du SLO, le texte de la « Promesse » des messages et des guides
d'investigation (`{objectif}`), et le seuil maximal des règles (1 / (1 − objectif)).

## `burn_rate`

La **vitesse** à laquelle la marge se consomme : 1 = elle serait épuisée en
exactement 30 jours ; 14,4 = en un peu plus de 2 jours.

Une valeur par **fenêtre** de la règle. Les fenêtres, leur nom et leur durée sont dans
le fichier JSON de la règle (`params.windows`) ; une fenêtre se déclenche quand la
vitesse dépasse son seuil **sur sa fenêtre longue et sur sa fenêtre courte** (la longue
évite de sonner sur un pic isolé, la courte fait retomber l'alerte dès que le problème
cesse).

| Fenêtre | Sévérité Kibana | Fenêtres longue / courte (règle standard) | Seuil standard | Marge consommée quand elle sonne |
|---|---|---|---|---|
| `alert` | Critical | 1 h / 5 min | 14,4 | 2 % de la marge du mois en 1 h |
| `high` | High | 6 h / 30 min | 6 | 5 % en 6 h |
| `medium` | Medium | 24 h / 2 h | 3 | 10 % en 24 h |
| `low` | Low | 72 h / 6 h | 1 | 10 % en 72 h |

Marge consommée = seuil × fenêtre longue / 30 jours. Baisser un seuil rend la fenêtre
plus sensible ; une règle à faible trafic (invité, conseiller départemental) n'a
qu'une fenêtre longue (`high`), parce qu'un échec isolé sur 1 h y vaudrait 100 %.

Les fenêtres notifiées dans Tchap, et leur gravité, sont dans le message de la règle
(`_message.fenetres`, cf. [le message d'une règle](../rules/README.md#le-message-dune-règle)) :
`alert` en 🚨 critique, `high` en ⚠️ avertissement, `medium` en message allégé gris ; `low`
reste dans Kibana (dashboard « SLO de Prod »). Une alerte est notifiée quand elle apparaît
et chaque fois qu'elle passe à une fenêtre plus grave.

`seuils.json` doit donner un seuil pour **chaque** fenêtre de la règle, ni plus ni moins ;
la génération échoue sinon, comme sur un objectif hors de 0 à 1.
