# inventaire

Matrice des versions de toutes les briques Pass Emploi (Scalingo + repos + Elastic Cloud), par environnement,
avec leurs fins de vie (endoflife.date), et envoi des lignes à signaler vers Tchap via Elasticsearch.

## Prérequis

- `scalingo` connectée (`scalingo login`, inutile avec `--depuis`), `jq`, `git`, `curl`.
- Repos frères clonés à côté de `pass-emploi-tools` ; un repo absent est ignoré.
- Optionnel, pour la version du cluster Elastic :
  - `ELASTIC_URL` : endpoint **Elasticsearch** (`….es.…`), pas Kibana ;
  - `ELASTIC_INVENTAIRE_API_KEY` : valeur **`encoded`** d'une clé API limitée au privilège cluster `monitor`.

  Ne jamais passer la clé en clair sur la ligne de commande :
  `read -s ELASTIC_INVENTAIRE_API_KEY && export ELASTIC_INVENTAIRE_API_KEY`.
- Pour `--envoyer` : `ELASTIC_URL` et `ELASTIC_ALERTES_VERSIONS_API_KEY`, valeur `encoded` de la clé
  `alertes-versions-inventaire` (écriture seule dans `logs-alertes-versions-default`, cf.
  [`acces-webhooks.console`](../docs/observabilite/supervision/pipelines/webhooks/acces-webhooks.console)),
  même règle : `read -s ELASTIC_ALERTES_VERSIONS_API_KEY && export ELASTIC_ALERTES_VERSIONS_API_KEY`.

## Lancer

    inventaire/inventaire-versions.sh                          # ~6 min
    inventaire/inventaire-versions.sh --sans-fetch --sortie /tmp/inv
    inventaire/inventaire-versions.sh --depuis inventaire/sortie/inventaire.json --simuler   # sans Scalingo
    inventaire/inventaire-versions.sh --envoyer                # collecte, puis envoi

- `--depuis FICHIER` : repart d'un `inventaire.json`, sans Scalingo ni repos ; recalcule fins de vie,
  markdown et documents.
- `--simuler` : écrit le corps `_bulk` dans `sortie/alertes-versions.ndjson`, sans rien envoyer.
- `--envoyer` : idem, puis l'envoie ; code de sortie 1 si un document est refusé ou part au failure store.

## Sortie (`inventaire/sortie/`, ignorée par git)

- `inventaire.md` : fins de vie, stack Elastic comparée au cluster, écarts, matrice complète, addons, apps.
- `inventaire.json` : même contenu, pour le passage hebdo (`finsDeVie[]`, `finsDeVieNonSuivies[]`).
- `alertes-versions.ndjson` : avec `--simuler` ou `--envoyer`, un document par écart, violation ou retard
  de la stack Elastic, fin de vie dépassée ou à moins de 6 mois, plus un récapitulatif.
  Format, gabarits et gravité : [conventions des webhooks](../docs/observabilite/format/webhooks/conventions.md#rapport-de-versions-logs-alertes-versions-default).

Écart = deux valeurs dont aucune n'est préfixe de l'autre, ou `latest`.
Stack Elastic : `violation` = brique au-dessus du cluster, `en retard` = en dessous.
Fin de vie : `eolFrom` du cycle endoflife.date de chaque version ; `dépassée`, `< 30 j` et `< 6 mois`
sont signalées. Une brique sans produit endoflife.date (Flutter, Dart, Xcode, Elastic Agent…) est listée
« non suivi ». Produit Java : `azul-zulu` sur Scalingo, `eclipse-temurin` ailleurs.
« Collecte incomplète » en tête : des cellules sont vides à tort, ou endoflife.date n'a pas répondu, relancer.

## Garanties et limites

- Lecture seule : sous-commandes Scalingo en liste blanche ; seules les variables `*_VERSION` sont lues.
- L'auth Scalingo limite à ~30 appels CLI par minute : exécution séquentielle avec reprise, d'où la durée.
- Version « déployée » = log du dernier déploiement réussi.
- Repos lus sur `origin/HEAD`, jamais le working tree.
- L'app Scalingo d'un addon n'est pas forcément son usage : la base analytics est attachée à `pass-emploi-logstash-prod`.
