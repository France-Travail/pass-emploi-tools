# Notifications Tchap — Workflows Kibana

Les règles Kibana notifient Tchap par des **Workflows** : une règle choisit son
salon en choisissant le Workflow de ce salon dans son action `.workflows`,
comme elle choisissait un connecteur Mattermost par canal. Décision :
[ADR-004](../../../../decisions/ADR-004-notifications-tchap-kibana-workflows.md).

```
Rule ──action .workflows──► tchap-<salon> ──workflow.execute──► tchap-client ──connecteur .http──► Tchap
                            (met en forme)                     (PUT …/send/m.room.message/{execution.id})
```

| Fichier | Contenu |
|---|---|
| [`connecteur-tchap.console`](connecteur-tchap.console) | connecteur `.http` : URL de Tchap et jeton du bot |
| [`tchap-client.console`](tchap-client.console) | le seul Workflow qui parle à Matrix |
| [`tchap-monitoring-production.console`](tchap-monitoring-production.console), [`tchap-monitoring-staging.console`](tchap-monitoring-staging.console), [`tchap-o11y-production.console`](tchap-o11y-production.console), [`tchap-o11y-staging.console`](tchap-o11y-staging.console) | un Workflow par salon |
| [`../../rules/4-rules-tchap.console`](../../rules/4-rules-tchap.console) | règle « Tchap - Envoi en échec » |

## Le message

Générique, construit à partir de ce que la règle transmet (son id, son nom, ses
tags, ses alertes) :

```
🚨 Scalingo - Prod - Crash, redémarrage ou arrêt d'une app (2)
• pass-emploi-api-prod : app_crashed (oom) sur web, par scalingo-platform
• pass-emploi-web-prod : app_restarted, par alice
Ouvrir dans Discover · Voir la règle
```

- **Sévérité** : tag `critical` (🚨) ou `warning` (⚠️) de la règle.
- **Lignes** : le champ `message` des documents trouvés, écrit par l'ingest
  pipeline ; à défaut, la raison de l'alerte (`kibana.alert.reason`).
- **Liens** : Discover (`kibana.alert.url`) et la page de la règle.

Le Workflow ne reçoit pas les documents trouvés par la règle (`context.hits`) :
ils sont fusionnés champ par champ dans le document d'alerte, sans lien entre
une app et son action, et `event.action` y est écrasé. D'où une ligne toute
faite par document, dans un seul champ.

## Contrat de `tchap-client`

| Entrée | Contenu |
|---|---|
| `salon` | ID du salon, `!…:agent.tchap.gouv.fr` (Tchap → paramètres du salon → Avancé) |
| `texte` | message en texte brut |
| `html` | message en HTML, **déjà échappé** (`\| escape` sur toute donnée) |

Un appel = un message. Le `txnId` de Matrix est l'`execution.id` de l'appel :
il doit changer à chaque message, sinon Matrix croit à une nouvelle tentative
et ne poste rien.

## Mise en service

1. **Tchap** : créer le compte bot sur une boîte fonctionnelle de l'équipe, puis
   les salons `monitoring-production`, `monitoring-staging`, `o11y-production`
   et `o11y-staging`, sans chiffrement si Tchap le permet. Y inviter le bot,
   puis récupérer son jeton et le faire rejoindre chaque salon :
   ```bash
   curl -s -X POST https://matrix.agent.tchap.gouv.fr/_matrix/client/v3/login -H 'Content-Type: application/json' \
     -d '{"type":"m.login.password","identifier":{"type":"m.id.user","user":"<identifiant du bot>"},"password":"<mot de passe>"}'
   curl -s -X POST "https://matrix.agent.tchap.gouv.fr/_matrix/client/v3/rooms/<id du salon encodé>/join" -H "Authorization: Bearer <jeton>"
   ```
   Ranger le jeton dans le coffre de l'équipe.
2. **Kibana**, dans Dev Tools : rejouer `connecteur-tchap.console` en
   remplaçant `<jeton-du-bot>`, puis `tchap-client.console`, puis les 4
   `tchap-<salon>.console` en remplaçant `<id-salon-…>`.
3. **Test** : poster dans chaque salon depuis Dev Tools.
   ```
   POST kbn:/api/workflows/workflow/tchap-client/run
   { "inputs": { "salon": "<id du salon>", "texte": "test", "html": "<b>test</b>" } }
   ```
4. **Règles** : brancher les règles (ci-dessous), puis rejouer
   [`4-rules-tchap.console`](../../rules/4-rules-tchap.console).

## Brancher une règle

1. Ajouter à la règle le tag `critical` ou `warning`.
2. Ajouter l'action `.workflows` vers le Workflow du salon :
   ```json
   { "id": "system-connector-.workflows",
     "params": { "subAction": "run", "subActionParams": {
       "workflowId": "tchap-o11y-production", "summaryMode": true,
       "alertStates": { "new": true, "ongoing": true, "recovered": false } } } }
   ```
   `ongoing: true` : une alerte reste active tant que des événements arrivent,
   chacun doit être notifié. `recovered: false` : pas de message à la fin de
   l'alerte.
3. Si les documents de la règle ont un champ `message`, ce sont eux qui font
   les lignes ; sinon, la raison de l'alerte. **Attention** : dans les logs
   applicatifs (`logs-<env>-default`), `message` est la ligne de log brute, pas
   une ligne de notification. Brancher tel quel une règle sur ces logs
   listerait jusqu'à 20 lignes de log brutes (illisibles, peut-être
   personnelles, et au-delà de 65 Ko l'envoi échoue). Pour ces règles, il faut
   d'abord décider entre un Workflow de salon qui n'utilise que la raison de
   l'alerte et un champ de notification dédié, distinct de `message`.

## Ajouter un salon

1. Créer le salon dans Tchap, y inviter le bot, le faire rejoindre (`curl …/join`
   de la mise en service).
2. Copier un `tchap-<salon>.console` en remplaçant le nom du salon partout,
   l'importer en substituant `<id-salon-…>`.

## Pièges

- La boucle sur les alertes est une **étape** `type: foreach` ; une propriété
  `foreach:` posée sur `workflow.execute` est ignorée sans erreur.
- `kibana.alert.url` est déjà absolue (Kibana a un `server.publicBaseUrl`) : ne
  pas la préfixer.
- Les Workflows exigent la licence **Enterprise**.
- Un envoi en échec laisse la règle d'origine à « ok » : seule la règle
  « Tchap - Envoi en échec » le montre. L'erreur Matrix se lit dans l'exécution
  du Workflow (*Workflows → Executions*).
