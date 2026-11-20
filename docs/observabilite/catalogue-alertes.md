<!-- ⚠️ FICHIER GÉNÉRÉ par kibana/rules/scripts/generer-regles-alerting.py : NE PAS LE MODIFIER. -->
# Catalogue des alertes

Toutes les règles d'alerte Kibana. Généré depuis leurs fichiers JSON
([`kibana/rules/`](../../kibana/rules/README.md)) : la question d'une alerte est la clé
`_question` de son fichier. Le pourquoi, les seuils et le calibrage : la page de
chaque périmètre. Les gravités : [alertes applicatives](alertes.md#gravités). Ce qui
remplit les index lus : [sources des données](#sources-des-données).

## Sécurité

Détail : [alertes de sécurité](alertes-securite.md).

| Code | À quoi elle sert | Gravité | Basée sur | Salon | Règle |
|---|---|---|---|---|---|
| S1 | Une CVE high ou critical reste-t-elle ouverte sur un de nos repos ? | 🚨 | KQL sur `logs-alertes-github-default` | monitoring-securite | GitHub - CVE high ou critical ouverte |
| S2a | Une app subit-elle une attaque par déni de service (pic de trafic et de 5xx à la fois) ? | 🚨 | ES\|QL sur `logs-alertes-scalingo-prod-default` | monitoring-securite | Scalingo - Prod - Suspicion d'attaque DDoS |
| S2b | Une app subit-elle une attaque par déni de service (pic de trafic et de 5xx à la fois) ? | 🚨 | ES\|QL sur `logs-alertes-scalingo-staging-default`, `logs-alertes-scalingo-perf-default` | monitoring-staging | Scalingo - Hors-Prod - Suspicion d'attaque DDoS |
| S3a | Notre limite de débit bloque-t-elle des requêtes ? | ⚠️ | ES\|QL sur `logs-prod-default` | monitoring-securite | Pass Emploi - Prod - Limite de débit déclenchée |
| S3b | Notre limite de débit bloque-t-elle des requêtes ? | ⚠️ | ES\|QL sur `logs-staging-default` | monitoring-staging | Pass Emploi - Hors-Prod - Limite de débit déclenchée |

## Applicatives

Détail : [alertes applicatives](alertes.md), [SLO](slo.md).

| Code | À quoi elle sert | Gravité | Basée sur | Salon | Règle |
|---|---|---|---|---|---|
| A1 | Un partenaire est-il en panne (part de ses appels en erreur) ? | ⚠️ | ES\|QL sur `logs-prod-default` | monitoring-production | API - Prod - Partenaire en panne |
| A4a | Une app applicative a-t-elle un incident Scalingo (crash, arrêt, seuil de métrique) ? | selon l'événement | KQL sur `logs-alertes-scalingo-prod-default` | monitoring-production | Scalingo - Prod - Incidents des apps applicatives |
| A4b | Une app applicative a-t-elle un incident Scalingo (crash, arrêt, seuil de métrique) ? | selon l'événement | KQL sur `logs-alertes-scalingo-staging-default`, `logs-alertes-scalingo-perf-default` | monitoring-staging | Scalingo - Hors-Prod - Incidents des apps applicatives |
| A4c | Quelle opération d'infra a touché une app applicative (déploiement, scaling, variable) ? | ℹ️ | KQL sur `logs-alertes-scalingo-prod-default` | infra-production | Scalingo - Prod - Opérations d'infra des apps applicatives |
| A4d | Quelle opération d'infra a touché une app applicative (déploiement, scaling, variable) ? | ℹ️ | KQL sur `logs-alertes-scalingo-staging-default`, `logs-alertes-scalingo-perf-default` | infra-staging | Scalingo - Hors-Prod - Opérations d'infra des apps applicatives |
| A5a | Un job a-t-il planté, ou son handler est-il introuvable ? | ⚠️ | KQL sur `logs-prod-default`, `logs-router-prod-default` | jobs-production | API - Prod - Jobs en échec |
| A5b | Un job a-t-il planté, ou son handler est-il introuvable ? | ⚠️ | KQL sur `logs-staging-default`, `logs-perf-default` | jobs-staging | API - Hors-Prod - Jobs en échec |
| A6 | Des erreurs s'accumulent-elles dans les apps, hors appels partenaires ? | ⚠️ | ES\|QL sur `logs-prod-default` | monitoring-production | API - Prod - Erreurs applicatives |
| A7 | Le web conseiller lève-t-il des erreurs JavaScript ? | ⚠️ | ES\|QL sur `logs-apm.error-*` | monitoring-production | Web - Prod - Erreurs du front |
| A8 | L'API est-elle injoignable de l'extérieur ? | 🚨 | sonde Heartbeat `pa-back-prod-status` | monitoring-production | API - Prod - Disponibilité |
| A9 | Le web conseiller est-il injoignable de l'extérieur ? | 🚨 | sonde Heartbeat `pa-web-prod-status` | monitoring-production | Web - Prod - Disponibilité |
| A10 | Le service d'authentification est-il injoignable de l'extérieur ? | 🚨 | sonde Heartbeat `pass-emploi-connect-status` | monitoring-production | Connect - Prod - Disponibilité |
| A11 | Un certificat TLS expire-t-il bientôt ? | ⚠️ | certificats vus par les sondes Heartbeat | monitoring-production | TLS - Certificat bientôt expiré |
| A12 | Un parcours refuse-t-il plus de demandes que d'habitude ? | ⚠️ | ES\|QL sur `logs-prod-default` | monitoring-production | API - Prod - Refus anormaux d'un parcours |
| A13 | Un partenaire refuse-t-il plus de nos appels que d'habitude ? | ⚠️ | ES\|QL sur `logs-prod-default` | monitoring-production | API - Prod - Refus partenaire anormaux |
| SLO1 | Des utilisateurs sont-ils empêchés d'utiliser un parcours de l'API ? | 🚨 sur 1 h · ⚠️ sur 6 h | burn rate du SLO « API — disponibilité par parcours » | monitoring-production | SLO - Prod - API — disponibilité par parcours |
| SLO3-conseiller-departemental | Les conseillers départementaux arrivent-ils à se connecter ? | ⚠️ sur 168 h | burn rate du SLO « Login — réussite conseiller départemental » | monitoring-production | SLO - Prod - Login — réussite conseiller départemental |
| SLO3-conseiller-france-travail | Les conseillers France Travail arrivent-ils à se connecter ? | 🚨 sur 1 h · ⚠️ sur 6 h | burn rate du SLO « Login — réussite conseiller France Travail » | monitoring-production | SLO - Prod - Login — réussite conseiller France Travail |
| SLO3-invite | Les invités arrivent-ils à se connecter ? | ⚠️ sur 72 h | burn rate du SLO « Login — réussite invité » | monitoring-production | SLO - Prod - Login — réussite invité |
| SLO3-jeune-france-travail | Les jeunes France Travail arrivent-ils à se connecter ? | 🚨 sur 1 h · ⚠️ sur 6 h | burn rate du SLO « Login — réussite jeune France Travail » | monitoring-production | SLO - Prod - Login — réussite jeune France Travail |
| SLO3-milo-conseiller | Les conseillers Milo arrivent-ils à se connecter ? | 🚨 sur 1 h · ⚠️ sur 6 h | burn rate du SLO « Login — réussite conseiller Milo » | monitoring-production | SLO - Prod - Login — réussite conseiller Milo |
| SLO3-milo-jeune | Les jeunes Milo arrivent-ils à se connecter ? | 🚨 sur 1 h · ⚠️ sur 6 h | burn rate du SLO « Login — réussite jeune Milo » | monitoring-production | SLO - Prod - Login — réussite jeune Milo |

## Stack d'observabilité

Détail : [alertes de la stack](infra/alertes-stack-observabilite.md).

| Code | À quoi elle sert | Gravité | Basée sur | Salon | Règle |
|---|---|---|---|---|---|
| M1a | Des logs ont-ils été écartés en Dead Letter Queue faute d'être indexables ? | 🚨 | KQL sur `logs-logstash-dlq-prod-default` | o11y-production | Logstash - Prod - Détection présence event dans DLQ |
| M1b | Des logs ont-ils été écartés en Dead Letter Queue faute d'être indexables ? | ⚠️ | KQL sur `logs-logstash-dlq-staging-default`, `logs-logstash-dlq-perf-default` | o11y-staging | Logstash - Hors-Prod - Détection présence event dans DLQ |
| M2a | Le pipeline Logstash de traitement rencontre-t-il des erreurs ? | ⚠️ | KQL sur `logs-logstash-errors-prod-default` | o11y-production | Logstash - Prod - Détection erreurs pipeline process |
| M2b | Le pipeline Logstash de traitement rencontre-t-il des erreurs ? | ⚠️ | KQL sur `logs-logstash-errors-staging-default`, `logs-logstash-errors-perf-default` | o11y-staging | Logstash - Hors-Prod - Détection erreurs pipeline process |
| M3a | Les logs applicatifs arrivent-ils encore ? | 🚨 | KQL sur `logs-prod-default` | o11y-production | Logstash - Prod - Détection absence ingestion logs applicatifs |
| M3b | Les logs du routeur Scalingo arrivent-ils encore ? | 🚨 | KQL sur `logs-router-prod-default` | o11y-production | Logstash - Prod - Détection absence ingestion logs router |
| M3c | Les logs applicatifs arrivent-ils encore ? | ⚠️ | KQL sur `logs-staging-default`, `logs-perf-default` | o11y-staging | Logstash - Hors-Prod - Détection absence ingestion logs applicatifs |
| M3d | Les logs du routeur Scalingo arrivent-ils encore ? | ⚠️ | KQL sur `logs-router-staging-default`, `logs-router-perf-default` | o11y-staging | Logstash - Hors-Prod - Détection absence ingestion logs router |
| M4a | L'ingestion Logstash est-elle bloquée (backpressure) ? | 🚨 | KQL sur `metrics-logstash.pipeline-default` | o11y-production | Logstash - Prod - Détection backpressure ingest (inputs bloqués) |
| M4b | L'ingestion Logstash est-elle bloquée (backpressure) ? | ⚠️ | KQL sur `metrics-logstash.pipeline-default` | o11y-staging | Logstash - Hors-Prod - Détection backpressure ingest (inputs bloqués) |
| M5a | La heap JVM de Logstash est-elle saturée ? | 🚨 | KQL sur `metrics-logstash.node-default` | o11y-production | Logstash - Prod - Détection heap JVM élevé |
| M5b | La heap JVM de Logstash est-elle saturée ? | ⚠️ | KQL sur `metrics-logstash.node-default` | o11y-staging | Logstash - Hors-Prod - Détection heap JVM élevé |
| M6a | Une app de la stack d'observabilité a-t-elle un événement Scalingo ? | selon l'événement | KQL sur `logs-alertes-scalingo-prod-default` | o11y-production | Scalingo - Prod - Événements des apps de la stack |
| M6b | Une app de la stack d'observabilité a-t-elle un événement Scalingo ? | selon l'événement | KQL sur `logs-alertes-scalingo-staging-default`, `logs-alertes-scalingo-perf-default` | o11y-staging | Scalingo - Hors-Prod - Événements des apps de la stack |
| M7a | Des logs s'accumulent-ils dans Redis sans être lus par Logstash ? | 🚨 | KQL sur `metrics-redis.key-default` | o11y-production | Redis - Prod - Backlog logstash:ingest anormal |
| M7b | Des logs s'accumulent-ils dans Redis sans être lus par Logstash ? | ⚠️ | KQL sur `metrics-redis.key-default` | o11y-staging | Redis - Hors-Prod - Backlog logstash:ingest anormal |
| M8a | Un Elastic Agent est-il hors service, ou échoue-t-il à envoyer ? | 🚨 | ES\|QL sur `logs-elastic_agent.status_change-default`, `metrics-elastic_agent.*beat-*` | o11y-production | Elastic Agent - Prod - Agent en défaut |
| M8b | Un Elastic Agent est-il hors service, ou échoue-t-il à envoyer ? | ⚠️ | ES\|QL sur `logs-elastic_agent.status_change-default`, `metrics-elastic_agent.*beat-*` | o11y-staging | Elastic Agent - Staging - Agent en défaut |
| M9a | Un conteneur Logstash approche-t-il de sa limite mémoire Scalingo ? | 🚨 | KQL sur `logs-scalingo.container_stats-default` | o11y-production | Logstash - Prod - Mémoire conteneur proche de la limite Scalingo |
| M9b | Un conteneur Logstash approche-t-il de sa limite mémoire Scalingo ? | ⚠️ | KQL sur `logs-scalingo.container_stats-default` | o11y-staging | Logstash - Hors-Prod - Mémoire conteneur proche de la limite Scalingo |
| M10 | L'ILM échoue-t-il, ou un index vit-il sous une policy qui ne supprime rien ? | ⚠️ | ES\|QL sur `.ds-ilm-history-7-*` | o11y-production | Elasticsearch - ILM en échec ou policy sans suppression |
| M13 | Un événement externe (webhook) a-t-il été rejeté à l'indexation ? | ⚠️ | KQL sur `logs-alertes-scalingo-prod-default::failures`, `logs-alertes-scalingo-staging-default::failures`, `logs-alertes-scalingo-perf-default::failures`, `logs-alertes-github-default::failures` | o11y-production | Événements externes - Payload rejeté (failure store) |

## Tchap

Détail : [chemin jusqu'à Tchap](fonctionnement.md).

| Code | À quoi elle sert | Gravité | Basée sur | Salon | Règle |
|---|---|---|---|---|---|
| tchap-envoi-echec | Les notifications Tchap partent-elles encore ? | aucune notification | requête Elasticsearch sur `.workflows-executions` | — | Tchap - Envoi en échec |

## Tchap : compte du bot

Détail : [runbook d'expiration](runbooks/runbook-tchap-expiration-bot.md).

| Code | À quoi elle sert | Gravité | Basée sur | Salon | Règle |
|---|---|---|---|---|---|
| expiration-bot | Le compte du bot Tchap expire-t-il bientôt ? | 🚨 | requête Elasticsearch sur `tchap-expiration-bot` | o11y-production | Tchap - Expiration du compte bot |

## Sources des données

Ce qui écrit chaque index lu par une règle, et où lire comment un document y arrive.

| Source | Écrite par | Comment elle est remplie | Lue par |
|---|---|---|---|
| `logs-<env>-default` | Logstash `process`, sortie par défaut : les lignes des apps, reçues par le drain Scalingo | [routage en sortie](infra/process/logs/pipeline.md#routage-en-sortie) | A1, A5a, A5b, A6, A12, A13, M3a, M3c, S3a, S3b, SLO1, SLO3-conseiller-departemental, SLO3-conseiller-france-travail, SLO3-invite, SLO3-jeune-france-travail, SLO3-milo-conseiller, SLO3-milo-jeune |
| `logs-router-<env>-default` | Logstash `process` : les lignes du routeur Scalingo | [routage en sortie](infra/process/logs/pipeline.md#routage-en-sortie) | A5a, M3b, M3d |
| `logs-logstash-errors-<env>-default` | Logstash `process` : les lignes dont un filtre a échoué | [routage en sortie](infra/process/logs/pipeline.md#routage-en-sortie) | M2a, M2b |
| `logs-logstash-dlq-<env>-default` | Logstash `dead_letter_queue` : les documents refusés par Elasticsearch | [Dead Letter Queue](infra/process/logs/pipeline.md#dead-letter-queue) | M1a, M1b |
| `logs-alertes-scalingo-<env>-default` | notifiers Scalingo, par webhook, sans Logstash | [collecte par webhook](infra/collecte/webhooks/README.md#la-chaîne) | A4a, A4b, A4c, A4d, M6a, M6b, M13, S2a, S2b |
| `logs-alertes-github-default` | workflow GitHub des CVE Dependabot, sans Logstash | [collecte par webhook](infra/collecte/webhooks/README.md#la-chaîne) | M13, S1 |
| `logs-apm.error-*` | agent APM du web conseiller | [traces APM](infra/collecte/traces/README.md) | A7 |
| `metrics-logstash.*`, `metrics-redis.*` | Elastic Agent, intégrations Fleet | [métriques de la stack](infra/collecte/metriques/stack-observabilite.md#data-streams) | M4a, M4b, M5a, M5b, M7a, M7b |
| `metrics-elastic_agent.*`, `logs-elastic_agent.*` | Elastic Agent, sur lui-même | [savoir qu'un agent a décroché](infra/pilotage.md#savoir-quun-agent-a-décroché) | M8a, M8b |
| `logs-scalingo.container_stats-default` | Elastic Agent, intégration Custom API sur l'API Scalingo | [mémoire des conteneurs](../../kibana/agents/README.md#mémoire-des-conteneurs-scalingo-intégration-custom-api) | M9a, M9b |
| sondes Heartbeat | Heartbeat | [disponibilité](infra/collecte/metriques/disponibilite.md) | A8, A9, A10, A11 |
| `tchap-expiration-bot` | date posée à la main au renouvellement du compte | [runbook](runbooks/runbook-tchap-expiration-bot.md) | expiration-bot |
| index internes | Elasticsearch et Kibana eux-mêmes | — | M10, tchap-envoi-echec |

## Hors règles Kibana

- Disque et indexation Elasticsearch (M11, M12) : notifications AutoOps d'Elastic Cloud, cf.
  [alertes de la stack](infra/alertes-stack-observabilite.md#notifications-autoops-m11-et-m12).
- Alertes de métriques Scalingo (5xx au routeur, trafic, RAM) : relayées par A4a, A4b, M6a, M6b.
