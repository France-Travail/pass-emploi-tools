# Modèles des Workflows Tchap

Les gabarits que `../generer-workflows.py` assemble pour produire les Workflows de
`../generated/`. Les modifier ici, jamais dans `../generated/`, puis lancer
`python3 -I ../generer-workflows.py` (cf. [README Tchap](../README.md)).

Les repères `@@NOM@@` sont remplacés à la génération. Le Liquid (`{{ … }}`,
`{% … %}`) est laissé tel quel : c'est Kibana qui l'exécute quand le Workflow tourne.

## `commun/` : utilisé par tous les fichiers générés

| Fichier | Quand | Contenu |
|---|---|---|
| `avertissement-fichier-genere.console` | en tête de **chaque** fichier de `../generated/` (salons et rapports) | « ⚠️ FICHIER GÉNÉRÉ… NE PAS LE MODIFIER » : quoi modifier à la place, quelle commande lancer |

## `salon/` : un Workflow par salon, `tchap-<salon>.console`

Le Workflow qui reçoit les alertes des règles d'un salon et poste leur message.

| Fichier | Quand | Repères |
|---|---|---|
| `workflow.console` | pour chacun des salons de `../salons.json` | `@@SALON@@` (nom du salon), `@@ID_SALON@@` (son identifiant Tchap), `@@TEXTE@@` et `@@HTML@@` (le message de chaque règle, construit par le générateur depuis les fichiers JSON des règles), `@@SI_ESQL_…@@` (cf. ci-dessous) |
| `etape-esql.yaml` | à la place de `@@SI_ESQL_ETAPE@@`, **seulement** si une règle du salon est en ES\|QL `groupBy: all` (aujourd'hui : `monitoring-production`) | l'étape qui relance la requête de la règle, lue dans l'alerte, pour obtenir ses lignes de résultat |
| `commentaire-esql.console` | à la place de `@@SI_ESQL_COMMENTAIRE@@`, dans les mêmes conditions | le commentaire qui explique cette étape |

## `rapport-jobs/` : le rapport quotidien des jobs, `tchap-jobs-<env>-rapport.console`

Le Workflow planifié chaque jour à 9 h 30 (heure de Paris), un par entrée de
`../rapports-jobs.json` (prod → `jobs-production`, staging → `jobs-staging`).

| Fichier | Rôle | Repères |
|---|---|---|
| `workflow.console` | le Workflow : déclencheur planifié, liste des jobs suivis, requête, envoi | `@@SALON@@`, `@@ID_SALON@@`, `@@ENV@@`, `@@JOBS@@` (la liste des CRON, lue dans pass-emploi-api), `@@REQUETE@@`, `@@TEXTE@@`, `@@HTML@@` |
| `executions-des-jobs-sur-24h.esql` | la requête ES\|QL : exécutions et échecs de chaque job sur 24 h | `@@INDEX@@` |
| `jour-du-mois-et-de-la-semaine.liquid` | le jour du mois et de la semaine, aujourd'hui et hier, pour savoir si un job mensuel ou hebdomadaire était attendu | — |
| `statut-d-un-job.liquid` | pour un job : exécutions attendues, exécutions réelles, échecs, ✅ / ❌ | `@@RAPPORT_HEURE@@` (9 h 30, en minutes) |
| `texte.liquid` | le message en texte brut (version de repli de Tchap) | `@@ENV@@`, `@@JOUR_DU_MOIS_ET_DE_LA_SEMAINE@@`, `@@STATUT_D_UN_JOB@@` |
| `html.liquid` | le message affiché : tableau des jobs et lien vers la session Discover | `@@ENV@@`, `@@LIBELLE_ENV@@`, `@@SESSION_JOBS@@`, `@@JOUR_DU_MOIS_ET_DE_LA_SEMAINE@@`, `@@STATUT_D_UN_JOB@@` |

Les fichiers `.liquid` sont écrits **une instruction par ligne** pour être lisibles :
le générateur recolle les lignes bout à bout, sans espace (un retour à la ligne dans
le message s'écrit `\n`, ou `<br/>` en HTML).
