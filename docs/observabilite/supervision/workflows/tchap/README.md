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
| [`../../rules/5-rules-tchap-expiration-bot.console`](../../rules/5-rules-tchap-expiration-bot.console) | règle « Tchap - Expiration du compte bot », date d'expiration rangée dans Elasticsearch |

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

Référence : la [documentation technique Tchap sur les bots et intégrations](https://aide.tchap.beta.gouv.fr/fr/article/documentation-technique-bot-et-integrations-tchap-1z3dfx/),
et le salon d'entraide [Bots et Intégrations Tchap](https://tchap.gouv.fr/#/room/#BotsetIntgrationsTchapU2tHdMEN80D:agent.dinum.tchap.gouv.fr).

1. **Compte bot** : Tchap n'a pas de compte de service, le bot est un compte
   utilisateur ordinaire, créé à la main dans Tchap web. Email recommandé par
   Tchap : préfixé par `bot-`, ici une **boîte fonctionnelle lue par l'équipe**
   (`bot-pass-emploi@francetravail.fr`, par exemple), parce que le compte doit
   être **renouvelé chaque année** : 11 mois après l'inscription, Tchap envoie
   un lien de renouvellement à cette adresse ; sans clic, le compte expire
   60 jours plus tard et **toutes** les notifications Tchap s'arrêtent.
   Noter la date de renouvellement dans l'agenda de l'équipe.
2. **Serveur du bot** : Tchap répartit les comptes sur plusieurs serveurs selon
   le domaine de l'email. Le vérifier avant tout :
   ```bash
   curl -s "https://matrix.agent.tchap.gouv.fr/_matrix/identity/api/v1/info?medium=email&address=bot-pass-emploi@francetravail.fr"
   # {"hs": "agent.tchap.gouv.fr"} → https://matrix.agent.tchap.gouv.fr
   ```
   `francetravail.fr` donne `agent.tchap.gouv.fr`, l'URL utilisée dans cette
   doc. Pour un autre domaine (`beta.gouv.fr` → `agent.dinum.tchap.gouv.fr`),
   remplacer l'URL partout : connecteur, `curl` ci-dessous, connecteurs AutoOps
   des [alertes 11 et 12](../../alertes-stack-observabilite.md#alerte-11--disque-des-nœuds-elasticsearch-autoops).
3. **Salons** : `monitoring-production`, `monitoring-staging`, `o11y-production`
   et `o11y-staging`, **non chiffrés** (Tchap n'impose pas le chiffrement d'un
   salon de bot, réponse de l'équipe Tchap du 2026-10-13 ; les messages
   respectent les [CGU](https://tchap.numerique.gouv.fr/cgu) : pas de donnée
   sensible ni classifiée). Y inviter le bot.
4. **Jeton** : se connecter **une seule fois** et réutiliser le jeton.
   Tchap le recommande : se reconnecter à chaque appel crée des dizaines de
   sessions. Puis faire rejoindre chaque salon au bot :
   ```bash
   curl -s -X POST https://matrix.agent.tchap.gouv.fr/_matrix/client/v3/login -H 'Content-Type: application/json' \
     -d '{"type":"m.login.password","identifier":{"type":"m.id.user","user":"<identifiant du bot>"},"password":"<mot de passe>"}'
   curl -s -X POST "https://matrix.agent.tchap.gouv.fr/_matrix/client/v3/rooms/<id du salon encodé>/join" -H "Authorization: Bearer <jeton>"
   ```
   Ranger le jeton dans le coffre de l'équipe.
5. **Kibana**, dans Dev Tools : rejouer `connecteur-tchap.console` en
   remplaçant `<jeton-du-bot>`, puis `tchap-client.console`, puis les 4
   `tchap-<salon>.console` en remplaçant `<id-salon-…>`.
6. **Test** : poster dans chaque salon depuis Dev Tools.
   ```
   POST kbn:/api/workflows/workflow/tchap-client/run
   { "inputs": { "salon": "<id du salon>", "texte": "test", "html": "<b>test</b>" } }
   ```
7. **Règles** : brancher les règles (ci-dessous), puis rejouer
   [`4-rules-tchap.console`](../../rules/4-rules-tchap.console) et
   [`5-rules-tchap-expiration-bot.console`](../../rules/5-rules-tchap-expiration-bot.console),
   en remplaçant `<date-expiration>` par la date d'inscription du bot + 11 mois
   + 60 jours.

**Questions ouvertes**, à poser dans le salon Bots et Intégrations :
- la durée de vie du jeton et des sessions inactives. Tchap délègue son
  authentification au Matrix Authentication Service (`auth.agent.tchap.gouv.fr`),
  où elles se règlent côté serveur ; la connexion par mot de passe reste
  acceptée. Un bot qui alerte rarement pourrait voir sa session expirer ;
- l'acceptation durable du `POST …/send/m.room.message` sans `txnId`, dont
  dépendent les alertes AutoOps.

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
- Le compte du bot **expire s'il n'est pas renouvelé** chaque année (lien reçu
  par email 11 mois après l'inscription) : toutes les notifications s'arrêtent.
  La règle « Tchap - Expiration du compte bot » prévient 60 jours avant ;
  procédure : [runbook](../../../runbooks/runbook-tchap-expiration-bot.md).
- Un envoi en échec laisse la règle d'origine à « ok » : seule la règle
  « Tchap - Envoi en échec » le montre. L'erreur Matrix se lit dans l'exécution
  du Workflow (*Workflows → Executions*).
