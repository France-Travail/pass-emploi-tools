# Routine de surveillance

Ce qu'on regarde **sans attendre une alerte**, en best effort : quelques minutes
par jour, un quart d'heure par semaine. Les alertes arrivent d'elles-mêmes dans
les salons Tchap de monitoring (cf. [alertes applicatives](alertes.md),
[de la stack](infra/alertes-stack-observabilite.md),
[de sécurité](alertes-securite.md)) ; cette routine couvre ce
qu'aucune alerte ne signale. Pour enquêter sur un incident :
[runbook d'investigation](runbooks/investigation-incident.md).

## Chaque jour (5 min)

1. **Kibana → Alerts** : les alertes en cours. Surtout **« Tchap - Envoi en
   échec »** : elle n'envoie aucune notification (Tchap ne peut pas signaler sa
   propre panne), on ne la voit qu'ici. Une alerte = des messages Tchap perdus ;
   l'erreur est dans *Workflows → Executions* (cf. [Workflows Tchap](../../kibana/workflows/tchap/README.md#pièges)).
2. **[[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)** :
   le budget d'erreur restant de chaque promesse (cf. [ci-dessous](#promesses-utilisateurs-slo)).
3. **Le rapport des jobs de 9 h 30**, dans le canal `jobs-production` : un job
   en échec, ou qui n'a pas tourné.
4. **Le salon `monitoring-securite`**, suivi par ses membres : une 🚨 suspicion
   d'attaque DDoS (S2a) se traite dès réception, avec le
   [runbook](runbooks/investigation-incident.md#suspicion-de-ddos-ou-surcharge-de-linfra) ;
   les CVE high ou critical (S1), répétées à chaque passage de
   `security-alerts.yml` tant qu'elles restent ouvertes, dans la journée.

Le salon `infra-production` (déploiements, scaling, variables, consoles
ouvertes : A4c) n'est pas à suivre en continu. Il sert à retrouver une action :
qui a déployé, scalé ou ouvert une console, et quand.

## Chaque semaine (15 min)

Sur les **7 derniers jours** :

1. **[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)** :
   la tendance de la mémoire des conteneurs, du heap, du backlog Redis et des
   logs non indexés. Une courbe qui monte lentement n'atteint aucun seuil
   d'alerte avant le jour où elle les dépasse tous. Signification des
   métriques : [collecte/metriques/stack-observabilite](infra/collecte/metriques/stack-observabilite.md).
2. **[[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)** :
   les erreurs qui augmentent sans franchir de seuil (un parcours, une app, un
   partenaire).

## Promesses utilisateurs (SLO)

| Dashboard | Ce qu'on y lit |
|---|---|
| **[Pass Emploi] SLO de Prod**, versionné dans [`kibana/dashboards/dashboard-slo.ndjson`](../../kibana/dashboards/dashboard-slo.ndjson) | statut et budget restant de chaque SLO, par parcours api et par mode de login ; alertes burn rate en cours ; budget et burn rate du login jeune France Travail |

Leurs définitions : [`kibana/slo/generated/1-slos.console`](../../kibana/slo/generated/1-slos.console).

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
Conventions des champs : [standard des logs](logs.md).
