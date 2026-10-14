# Notifications d'alertes vers Tchap par les Workflows Kibana

* Statut: accepté
* Décideurs: équipe pass-emploi
* Date: 2026-10-13

## Contexte et Définition du Problème

Mattermost est décommissionné le 1er novembre 2026. Les règles Kibana y
notifient des canaux par des connecteurs Webhook, un par canal. Elles doivent
notifier Tchap, la messagerie de l'État, qui est un serveur Matrix.

Envoyer un message Matrix, c'est `PUT /rooms/{salon}/send/m.room.message/{txnId}`,
avec un `txnId` unique par message : un `txnId` déjà vu est pris pour une
nouvelle tentative et rien n'est posté. Le connecteur Webhook de Kibana a une
URL fixe : il ne peut pas produire ce `txnId`.

## Facteurs de Décision

* Pas de brique intermédiaire à héberger et à maintenir chez nous.
* La règle choisit son salon, comme elle choisissait son canal Mattermost.
* Migrer les autres règles avant le 1er novembre sans écrire de code par règle.

## Solutions Étudiées

* Passerelle slack2tchap (beta.gouv), hébergée chez nous
* Service n8n mutualisé de l'incubateur beta.gouv
* Connecteur Webhook Kibana en `POST` sur l'ancienne route sans `txnId`
* Watcher Elasticsearch (`PUT` avec `{{ctx.id}}`)
* Workflows Kibana, avec un Workflow par règle
* Workflows Kibana, avec un Workflow par salon
* Workflows Kibana, avec un Workflow générique et le salon porté par un tag de la règle

## Résultat de la Décision

Solution retenue : « Workflows Kibana, avec un Workflow par salon », **parce que
nous sommes en licence Elastic Cloud Enterprise**, que les Workflows exigent.
Le connecteur `.http` des Workflows accepte des variables dans son chemin :
`txnId = {{ execution.id }}`, conforme à la norme Matrix. La règle déclenche le
Workflow de son salon ; un Workflow commun, `tchap-client`, est le seul à
appeler Tchap. Détail : [`supervision/workflows/tchap/`](../observabilite/supervision/workflows/tchap/README.md).

### Impacts Positifs

* Aucune brique à héberger ; tout est versionné en `.console`.
* Migrer une règle : un tag et une action.
* Échappement HTML des données (`| escape`), impossible avec Mustache.

### Impacts Négatifs

* Dépendance à la licence Enterprise. **Sans elle**, repli sur le connecteur
  Webhook en `POST` sans `txnId` (route tolérée par Synapse, hors norme
  Matrix ; pas d'échappement HTML).
* Message générique : le texte « À vérifier » propre à chaque règle reste dans
  la doc des alertes.
* Les champs des documents n'arrivent pas appariés au Workflow : chaque
  pipeline doit écrire une ligne `message` toute faite.
* Un envoi en échec ne fait pas échouer la règle : il faut une règle dédiée.

### Alertes émises hors Kibana (AutoOps)

Les alertes 11 (disque des nœuds) et 12 (saturation de l'indexation) viennent
d'**AutoOps**, l'outil de supervision officiel d'Elastic Cloud, qui tourne en
dehors de notre cluster. Elles postent directement dans Tchap, par un connecteur
Webhook AutoOps en `POST` sur la route sans `txnId` : AutoOps n'a ni variable
unique par événement, ni variable dans l'URL, ni moyen d'appeler un Workflow.

* Elles ne passent **pas** par Elasticsearch et les Workflows : elles doivent
  alerter justement quand le cluster va mal (un disque plein bloque l'écriture,
  le document d'alerte ne serait jamais indexé).
* Concession acceptée : un envoi rejoué après une coupure réseau peut doubler
  le message ; AutoOps envoie peu d'événements (ouverture et clôture).
* Risque : la route `POST` sans `txnId` est hors norme Matrix. Si Tchap la
  supprimait, ces notifications cesseraient ; une notification AutoOps par
  email reste en secours.
* L'alerte 6 (webhook Scalingo des apps Logstash) n'est pas migrée : les règles
  X1 et X3 des alertes externes couvrent les mêmes événements et notifient Tchap.

Configuration : [alertes de la stack, alertes 11 et 12](../observabilite/supervision/alertes-stack-observabilite.md#alerte-11--disque-des-nœuds-elasticsearch-autoops).

## Avantages et Inconvénients des Solutions

### Passerelle slack2tchap

[`betagouv/slack2tchap`](https://github.com/betagouv/slack2tchap) : passerelle
Python qui reçoit des webhooks au format Slack/Mattermost et les poste dans un
salon Tchap, avec les identifiants du bot chiffrés dans l'URL du webhook.

* Bien, car elle accepte le format Slack actuel des messages.
* Mauvais, car c'est une application à héberger, mettre à jour et superviser.
* Mauvais, car elle ne protège pas mieux des doublons : un nouveau `txnId` à
  chaque requête reçue.

### Service n8n mutualisé beta.gouv

Instance n8n hébergée par l'incubateur (`n8n.incubateur.net`), avec une seule
URL de webhook pour toutes les équipes. Chaque équipe déclare son salon et ses
sources par une PR sur
[`betagouv/n8n-configs/tchap-webhooks.yaml`](https://github.com/betagouv/n8n-configs/blob/main/tchap-webhooks.yaml)
(dépôt non public : accès réservé aux membres de l'organisation `betagouv`),
puis invite le bot `tchap-bot@beta.gouv.fr` dans le salon.

* Bien, car rien à héberger.
* Mauvais, car un service tiers, sans engagement, et un routage par PR sur un
  fichier commun.

### Connecteur Webhook en `POST` sans `txnId`

* Bien, car aucun changement d'architecture.
* Mauvais, car hors norme Matrix (route ancienne tolérée par Synapse), pas
  d'échappement HTML.

### Watcher Elasticsearch

* Bien, car `PUT` conforme, licence Gold.
* Mauvais, car un second système d'alerte : requêtes à réécrire, retards
  d'indexation et liens Discover à gérer soi-même.

### Workflow par règle

* Bien, car message sur mesure par règle.
* Mauvais, car un Workflow à écrire par règle, et le salon se change dans le
  Workflow, pas dans la règle.

### Salon porté par un tag de la règle

* Bien, car un seul Workflow pour toutes les règles.
* Mauvais, car la liste des salons possibles n'est visible nulle part, et une
  faute de frappe dans le tag perd l'alerte sans erreur ; avec un Workflow par
  salon, le salon se choisit dans une liste déroulante de l'action.

## Liens

* Spécification : [`docs/superpowers/specs/2026-10-13-alertes-tchap-workflows-design.md`](../superpowers/specs/2026-10-13-alertes-tchap-workflows-design.md)
* [Alertes externes](../observabilite/supervision/alertes-externes.md)
* [slack2tchap](https://github.com/betagouv/slack2tchap)
* [Configuration n8n des webhooks Tchap de beta.gouv](https://github.com/betagouv/n8n-configs/blob/main/tchap-webhooks.yaml) (dépôt non public)
