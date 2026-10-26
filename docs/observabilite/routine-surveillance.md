# Routine de surveillance

Ce qu'on regarde **sans attendre une alerte**, en best effort : quelques minutes
par jour, un quart d'heure par semaine. Les alertes arrivent d'elles-mêmes dans
les canaux de monitoring (cf. [alertes applicatives](supervision/alertes-applicatives.md),
[de la stack](supervision/alertes-stack-observabilite.md),
[de sécurité](supervision/alertes-securite.md)) ; cette routine couvre ce
qu'aucune alerte ne signale. Pour enquêter sur un incident :
[runbook d'investigation](runbooks/investigation-incident.md).

> **⚠️ Du 1er novembre 2026 à la mise en service du bot Tchap**
>
> Mattermost s'arrête le 1er novembre, et le compte du bot Tchap attend son
> adresse e-mail, demandée mais pas encore créée. Entre les deux, **aucune
> alerte n'arrive dans une messagerie**. Les règles continuent de tourner et
> leurs alertes se déclenchent, mais on ne les voit que dans Kibana.
>
> Pendant cette période, on remplace la lecture des canaux par :
>
> 1. **Les règles en alerte, matin, midi et soir, chaque jour ouvré** :
>    [Kibana → Rules](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/management/insightsAndAlerting/triggersActions/rules),
>    filtre *Last response* = *Active*. Ouvrir une règle pour lire ses alertes
>    et sa raison, puis suivre les étapes « À vérifier » de son Investigation
>    guide, qui reprend le message qu'elle aurait posté.
> 2. **Les jobs, chaque matin**, à la place du rapport de 9 h 30 : le Discover
>    [[Pass Emploi] Logs de Prod - Jobs](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/c0d38bba-66ef-4b68-8a10-4d786f6a9f4a),
>    onglets « Jobs en échec » et « Exécutions », sur les dernières 24 h.
> 3. **AutoOps, chaque matin** (alertes 11 et 12, disque et indexation) : la
>    page AutoOps du déploiement dans Elastic Cloud, qui ne prévient plus
>    Mattermost.
>
> Le point 1 de la routine quotidienne ci-dessous, « Tchap - Envoi en échec »,
> ne s'applique pas encore : rien n'est envoyé.
>
> **Fin de la période** : à la mise en service du bot (cf.
> [Workflows Tchap, mise en service](supervision/workflows/tchap/README.md#mise-en-service)),
> vérifier qu'une alerte de chaque salon arrive dans Tchap, puis retirer cet encadré.

## Chaque jour (5 min)

1. **Kibana → Alerts** : les alertes en cours. Surtout **« Tchap - Envoi en
   échec »** : elle n'envoie aucune notification (Tchap ne peut pas signaler sa
   propre panne), on ne la voit qu'ici. Une alerte = des messages Tchap perdus ;
   l'erreur est dans *Workflows → Executions* (cf. [Workflows Tchap](supervision/workflows/tchap/README.md#pièges)).
2. **[[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)** :
   le budget d'erreur restant de chaque promesse (cf. [ci-dessous](#promesses-utilisateurs-slo)).
3. **Le rapport des jobs de 9 h 30**, dans le canal `jobs-production` : un job
   en échec, ou qui n'a pas tourné.

## Chaque semaine (15 min)

Sur les **7 derniers jours** :

1. **[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)** :
   la tendance de la mémoire des conteneurs, du heap, du backlog Redis et des
   logs non indexés. Une courbe qui monte lentement n'atteint aucun seuil
   d'alerte avant le jour où elle les dépasse tous. Signification des
   métriques : [collecte/metriques/stack-observabilite](collecte/metriques/stack-observabilite.md).
2. **[[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)** :
   les erreurs qui augmentent sans franchir de seuil (un parcours, une app, un
   partenaire).

## Promesses utilisateurs (SLO)

| Dashboard | Ce qu'on y lit |
|---|---|
| **[Pass Emploi] SLO de Prod**, versionné dans [`supervision/dashboards/dashboard-slo.ndjson`](supervision/dashboards/dashboard-slo.ndjson) | statut et budget restant de chaque SLO, par parcours api et par mode de login ; alertes burn rate en cours ; budget et burn rate du login jeune France Travail |

Les promesses elles-mêmes : [supervision/sli-slo](supervision/sli-slo.md).

## Reporting métier

« Combien d'actions métier cette semaine, par structure ? », dans Discover :

| Métrique | KQL |
|---|---|
| Actions métier réussies | `event.action: handler_executed AND event.outcome: success` |
| Échecs par handler | `… AND event.outcome: failure`, réparti par `log.logger` |
| Activité par structure | filtre ou répartition par `user.structure` |

## Pré-requis

Les logs de prod sont dans deux data streams : `logs-prod-default` (logs
applicatifs : code et pino-http) et `logs-router-prod-default` (routeur
Scalingo, `event.action: request_routed`). Pour corréler les deux par
`http.request.id`, la data view doit couvrir les deux : `logs-*-default-*`.
Conventions des champs : [format/logs/conventions](format/logs/conventions.md) ;
propres à l'api : [format/logs/couverture-api](format/logs/couverture-api.md).
