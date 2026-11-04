# inventaire

Matrice des versions de toutes les briques Pass Emploi (Scalingo + repos + Elastic Cloud), par environnement.

## Prérequis

- `scalingo` connectée (`scalingo login`), `jq`, `git`, `curl`.
- Repos frères clonés à côté de `pass-emploi-tools` ; un repo absent est ignoré.
- Optionnel, pour la version du cluster Elastic :
  - `ELASTIC_URL` : endpoint **Elasticsearch** (`….es.…`), pas Kibana ;
  - `ELASTIC_INVENTAIRE_API_KEY` : valeur **`encoded`** d'une clé API limitée au privilège cluster `monitor`.

  Ne jamais passer la clé en clair sur la ligne de commande :
  `read -s ELASTIC_INVENTAIRE_API_KEY && export ELASTIC_INVENTAIRE_API_KEY`.

## Lancer

    inventaire/inventaire-versions.sh                          # ~6 min
    inventaire/inventaire-versions.sh --sans-fetch --sortie /tmp/inv

## Sortie (`inventaire/sortie/`, ignorée par git)

- `inventaire.md` : stack Elastic comparée au cluster, écarts, matrice complète, addons, apps.
- `inventaire.json` : même contenu, pour le passage hebdo.

Écart = deux valeurs dont aucune n'est préfixe de l'autre, ou `latest`.
Stack Elastic : `violation` = brique au-dessus du cluster, `en retard` = en dessous.
« Collecte incomplète » en tête : des cellules sont vides à tort, relancer.

## Garanties et limites

- Lecture seule : sous-commandes Scalingo en liste blanche ; seules les variables `*_VERSION` sont lues.
- L'auth Scalingo limite à ~30 appels CLI par minute : exécution séquentielle avec reprise, d'où la durée.
- Version « déployée » = log du dernier déploiement réussi.
- Repos lus sur `origin/HEAD`, jamais le working tree.
- L'app Scalingo d'un addon n'est pas forcément son usage : la base analytics est attachée à `pass-emploi-logstash-prod`.
