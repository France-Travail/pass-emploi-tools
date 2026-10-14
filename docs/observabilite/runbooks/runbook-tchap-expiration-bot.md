# Runbook — expiration du compte bot Tchap

> **Type** : tutoriel (Diataxis). Quoi faire quand la règle
> **« Tchap - Expiration du compte bot »** (🚨, salon `o11y-production`) signale
> que le compte du bot arrive à expiration.
>
> Configuration : [`rules/5-rules-tchap-expiration-bot.console`](../supervision/rules/5-rules-tchap-expiration-bot.console).
> Notifications Tchap : [Workflows Tchap](../supervision/workflows/tchap/README.md).
> Toutes les requêtes se lancent dans Kibana → Dev Tools.

Le bot qui poste toutes nos alertes dans Tchap est un compte Tchap ordinaire :
Tchap n'a pas de compte de service. Comme tout compte, il doit être renouvelé
selon les [CGU Tchap](https://tchap.numerique.gouv.fr/cgu). Durées relevées dans
les CGU le **2026-10-14** : les CGU peuvent changer, les relire à chaque
renouvellement (§ 1, étape 2) et corriger ce tableau, la règle et le pipeline de
[`5-rules-tchap-expiration-bot.console`](../supervision/rules/5-rules-tchap-expiration-bot.console)
si elles ont bougé.

| Moment | Ce qui se passe |
|---|---|
| inscription ou dernier renouvellement + 11 mois | Tchap envoie un **lien de renouvellement** à l'email du bot ; la règle alerte (J-60) |
| 60 jours plus tard | le compte **expire** : Tchap refuse ses envois, **plus aucune alerte n'arrive dans Tchap** |
| 4 mois après l'expiration | le compte est **supprimé** |

La règle tourne une fois par jour et rappelle chaque jour, tant que la date
d'expiration rangée dans Elasticsearch n'a pas été repoussée.

## 1. Renouveler le compte

1. Ouvrir la boîte fonctionnelle du bot (`bot-pass-emploi@francetravail.fr`)
   et cliquer le lien de renouvellement de Tchap. Le compte est prolongé de
   13 mois (CGU du 2026-10-14).
2. Relire la section sur le renouvellement des [CGU Tchap](https://tchap.numerique.gouv.fr/cgu) :
   si la durée de prolongation (13 mois) ou le préavis du lien (60 jours avant
   l'expiration) ont changé, adapter la date ci-dessous, le préavis du pipeline
   `tchap-expiration-bot` (`minusDays(60)`) et le tableau ci-dessus.
3. Ranger la nouvelle date d'expiration (date du jour + 13 mois) :
   ```
   PUT tchap-expiration-bot/_doc/bot?refresh=true
   {
     "compte": "@bot-pass-emploi:agent.tchap.gouv.fr",
     "expire_le": "2027-11-14"
   }
   ```
4. Vérifier : la règle passe en *Recovered* à sa prochaine exécution (ou tout
   de suite avec *Run rule* dans Kibana → Rules). Le jeton du bot ne change pas,
   rien d'autre à faire.

## 2. Le lien est introuvable ou périmé

- Chercher dans les indésirables de la boîte du bot.
- Se connecter au compte du bot dans [Tchap web](https://tchap.gouv.fr) : à
  confirmer au premier renouvellement, Tchap y propose de renvoyer l'email de
  renouvellement.
- Sinon, demander dans le salon [Bots et Intégrations Tchap](https://tchap.gouv.fr/#/room/#BotsetIntgrationsTchapU2tHdMEN80D:agent.dinum.tchap.gouv.fr).

## 3. Le compte a déjà expiré

Symptômes : aucune alerte dans Tchap, et la règle **« Tchap - Envoi en échec »**
en alerte dans Kibana → Alerts, avec des erreurs `403` dans *Workflows →
Executions*.

1. Tant que le compte n'est pas supprimé (4 mois après l'expiration), le
   renouveler comme à l'étape 1 : le lien de l'email reste le moyen de le
   réactiver. Le jeton existant refonctionne.
2. Pendant la coupure, les alertes ne sont pas perdues : elles restent dans
   Kibana → Alerts. Les relire une fois le bot rétabli.

## 4. Le compte a été supprimé : recréer le bot

1. Recréer le compte comme à la [mise en service](../supervision/workflows/tchap/README.md#mise-en-service)
   (compte, jeton), l'inviter dans les 4 salons et l'y faire rejoindre.
2. Mettre le nouveau jeton partout où l'ancien était :
   - le connecteur Tchap de Kibana : `PUT` de
     [`connecteur-tchap.console`](../supervision/workflows/tchap/connecteur-tchap.console) ;
   - les connecteurs Tchap d'AutoOps des [alertes 11 et 12](../supervision/alertes-stack-observabilite.md#alerte-11--disque-des-nœuds-elasticsearch-autoops)
     (en-tête `Authorization`).
3. Ranger la date d'expiration du nouveau compte (inscription + 11 mois +
   60 jours), et son identifiant s'il a changé, comme à l'étape 1.
4. Tester : `POST kbn:/api/workflows/workflow/tchap-client/run` vers chaque
   salon (cf. [mise en service](../supervision/workflows/tchap/README.md#mise-en-service)).
