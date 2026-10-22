# Règles de generated/1-rules-applicatives.console définies au format de Kibana : les SLO des alertes applicatives.
# Le corps JSON de chaque règle (regle), et son message à part (messages, un par groupe
# d'action) : il reste disponible pour Tchap quand l'action Mattermost disparaît.
# Les autres règles du fichier sont définies champ par champ dans generer-regles.py.
# Modifier ici, puis : FEATURE_NOTIFIER_ALERTES_MATTERMOST=true python3 -I generer-regles.py
#                     python3 -I ../workflows/tchap/generer-workflows.py
# (cf. README.md)
import json

REGLES_FORMAT_KIBANA = {
    'S2': dict(
        id='e41ef1d8-efd8-449b-b2a5-6fff758c8939', fichier='1-rules-applicatives.console', methode='PUT',
        commentaire="",
        regle=json.loads(r'''
{
  "name": "SLO - Prod - API — latence des parcours critiques",
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nSLO menacé — latence des parcours critiques (prod) : la marge d'erreur du SLO se consomme trop vite.\n\n**Promesse** : 99 % des requêtes des parcours critiques répondent en moins de 500 ms (authentification) ou 2,5 s (parcours avec un partenaire), sur 30 jours glissants.\n\n## À vérifier\n\n1. Quel parcours ralentit, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Si un partenaire répond lentement ou échoue (France Travail, Milo…) : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74), puis le Discover [[Pass Emploi] Logs de Prod - Échecs partenaires](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/a28897ac-ecb1-4b4f-b413-0340c7241293)\n3. Si l'api répond en erreur : le Discover [[Pass Emploi] Logs de Prod - Erreurs serveur 5xx](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/d076df50-1625-443b-978c-1aa9a1288e73)\n\n## Dashboards\n\n- [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n- [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)\n\n## Discover sessions\n\n- [[Pass Emploi] Logs de Prod - Échecs partenaires](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/a28897ac-ecb1-4b4f-b413-0340c7241293)\n- [[Pass Emploi] Logs de Prod - Erreurs serveur 5xx](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/d076df50-1625-443b-978c-1aa9a1288e73)\n\n## Documentation\n\n- [Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)\n"
    },
    "dashboards": [
      {
        "id": "b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14"
      },
      {
        "id": "eb348ed9-3bc2-4204-a5c2-c31465731c74"
      }
    ]
  },
  "schedule": {
    "interval": "1m"
  },
  "tags": [
    "prod",
    "slo"
  ],
  "params": {
    "sloId": "6c55ac3b-8b07-400c-89f8-0e46865166b2",
    "windows": [
      {
        "id": "alert",
        "actionGroup": "slo.burnRate.alert",
        "burnRateThreshold": 14.4,
        "maxBurnRateThreshold": 100.0,
        "longWindow": {
          "value": 1,
          "unit": "h"
        },
        "shortWindow": {
          "value": 5,
          "unit": "m"
        }
      },
      {
        "id": "high",
        "actionGroup": "slo.burnRate.high",
        "burnRateThreshold": 6,
        "maxBurnRateThreshold": 100.0,
        "longWindow": {
          "value": 6,
          "unit": "h"
        },
        "shortWindow": {
          "value": 30,
          "unit": "m"
        }
      },
      {
        "id": "medium",
        "actionGroup": "slo.burnRate.medium",
        "burnRateThreshold": 3,
        "maxBurnRateThreshold": 100.0,
        "longWindow": {
          "value": 24,
          "unit": "h"
        },
        "shortWindow": {
          "value": 2,
          "unit": "h"
        }
      },
      {
        "id": "low",
        "actionGroup": "slo.burnRate.low",
        "burnRateThreshold": 1,
        "maxBurnRateThreshold": 100.0,
        "longWindow": {
          "value": 72,
          "unit": "h"
        },
        "shortWindow": {
          "value": 6,
          "unit": "h"
        }
      }
    ]
  },
  "actions": [
    {
      "group": "slo.burnRate.alert",
      "id": "12e46700-6e45-11ec-9757-c9700cd1bb4e",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onActionGroupChange",
        "throttle": null
      }
    },
    {
      "group": "slo.burnRate.high",
      "id": "12e46700-6e45-11ec-9757-c9700cd1bb4e",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onActionGroupChange",
        "throttle": null
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-monitoring-production",
          "summaryMode": true,
          "alertStates": {
            "new": true,
            "ongoing": false,
            "recovered": false
          }
        }
      }
    }
  ]
}
'''),
        messages={
            "slo.burnRate.alert": r'''{
  "text": "🚨 **SLO menacé — latence des parcours critiques (prod)**",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "Déclenchée à",
          "value": "`{{date}}`",
          "short": true
        },
        {
          "title": "Promesse",
          "value": "99 % des requêtes des parcours critiques répondent en moins de 500 ms (authentification) ou 2,5 s (parcours avec un partenaire), sur 30 jours glissants."
        },
        {
          "title": "Parcours / mode",
          "value": "`{{context.sloInstanceId}}`",
          "short": true
        },
        {
          "title": "Ce qui se passe",
          "value": "Sur {{context.longWindow.duration}}, les requêtes trop lentes consomment la marge d'erreur du mois {{context.longWindow.burnRate}} fois plus vite que prévu ({{context.shortWindow.burnRate}} fois sur les {{context.shortWindow.duration}} les plus récentes). À ce rythme, elle est épuisée en {{#EvalMath}} round(30 / {{context.longWindow.burnRate}}, 1) {{/EvalMath}} jours."
        },
        {
          "title": "À vérifier",
          "value": "1. Quel parcours ralentit, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Si un partenaire répond lentement ou échoue (France Travail, Milo…) : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74), puis le Discover [[Pass Emploi] Logs de Prod - Échecs partenaires](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/a28897ac-ecb1-4b4f-b413-0340c7241293)\n3. Si l'api répond en erreur : le Discover [[Pass Emploi] Logs de Prod - Erreurs serveur 5xx](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/d076df50-1625-443b-978c-1aa9a1288e73)"
        },
        {
          "title": "Dashboards",
          "value": "[[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n[[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs de Prod - Échecs partenaires](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/a28897ac-ecb1-4b4f-b413-0340c7241293)\n[[Pass Emploi] Logs de Prod - Erreurs serveur 5xx](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/d076df50-1625-443b-978c-1aa9a1288e73)"
        },
        {
          "title": "Marge d'erreur",
          "value": "[Budget d'erreur et historique du SLO]({{context.viewInAppUrl}})"
        },
        {
          "title": "Runbook",
          "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)"
        }
      ]
    }
  ]
}''',
            "slo.burnRate.high": r'''{
  "text": "🚨 **SLO menacé — latence des parcours critiques (prod)**",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "Déclenchée à",
          "value": "`{{date}}`",
          "short": true
        },
        {
          "title": "Promesse",
          "value": "99 % des requêtes des parcours critiques répondent en moins de 500 ms (authentification) ou 2,5 s (parcours avec un partenaire), sur 30 jours glissants."
        },
        {
          "title": "Parcours / mode",
          "value": "`{{context.sloInstanceId}}`",
          "short": true
        },
        {
          "title": "Ce qui se passe",
          "value": "Sur {{context.longWindow.duration}}, les requêtes trop lentes consomment la marge d'erreur du mois {{context.longWindow.burnRate}} fois plus vite que prévu ({{context.shortWindow.burnRate}} fois sur les {{context.shortWindow.duration}} les plus récentes). À ce rythme, elle est épuisée en {{#EvalMath}} round(30 / {{context.longWindow.burnRate}}, 1) {{/EvalMath}} jours."
        },
        {
          "title": "À vérifier",
          "value": "1. Quel parcours ralentit, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Si un partenaire répond lentement ou échoue (France Travail, Milo…) : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74), puis le Discover [[Pass Emploi] Logs de Prod - Échecs partenaires](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/a28897ac-ecb1-4b4f-b413-0340c7241293)\n3. Si l'api répond en erreur : le Discover [[Pass Emploi] Logs de Prod - Erreurs serveur 5xx](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/d076df50-1625-443b-978c-1aa9a1288e73)"
        },
        {
          "title": "Dashboards",
          "value": "[[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n[[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs de Prod - Échecs partenaires](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/a28897ac-ecb1-4b4f-b413-0340c7241293)\n[[Pass Emploi] Logs de Prod - Erreurs serveur 5xx](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/d076df50-1625-443b-978c-1aa9a1288e73)"
        },
        {
          "title": "Marge d'erreur",
          "value": "[Budget d'erreur et historique du SLO]({{context.viewInAppUrl}})"
        },
        {
          "title": "Runbook",
          "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)"
        }
      ]
    }
  ]
}''',
        }),
    'S3-jeune-ft': dict(
        id='72914c41-01ed-4ce7-ae68-a1b5eb445773', fichier='1-rules-applicatives.console', methode='PUT',
        commentaire="",
        regle=json.loads(r'''
{
  "name": "SLO - Prod - Login — réussite jeune France Travail",
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nSLO menacé — connexion des jeunes France Travail (prod) : la marge d'erreur du SLO se consomme trop vite.\n\n**Promesse** : 85 % des connexions des jeunes France Travail aboutissent, hors refus métier, sur 30 jours glissants.\n\n## À vérifier\n\n1. Quel mode de connexion échoue, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Le motif des connexions refusées (fournisseur d'identité, Keycloak) : le Discover [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n3. Si un fournisseur d'identité ou un partenaire est en panne : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)\n\n## Dashboards\n\n- [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n- [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)\n\n## Discover sessions\n\n- [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n\n## Documentation\n\n- [Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)\n"
    },
    "dashboards": [
      {
        "id": "b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14"
      },
      {
        "id": "eb348ed9-3bc2-4204-a5c2-c31465731c74"
      }
    ]
  },
  "schedule": {
    "interval": "1m"
  },
  "tags": [
    "prod",
    "slo"
  ],
  "params": {
    "sloId": "ec53b7e4-604e-4e33-a4df-ace9e4aea01b",
    "windows": [
      {
        "id": "alert",
        "actionGroup": "slo.burnRate.alert",
        "burnRateThreshold": 3,
        "maxBurnRateThreshold": 6.67,
        "longWindow": {
          "value": 1,
          "unit": "h"
        },
        "shortWindow": {
          "value": 5,
          "unit": "m"
        }
      },
      {
        "id": "high",
        "actionGroup": "slo.burnRate.high",
        "burnRateThreshold": 2,
        "maxBurnRateThreshold": 6.67,
        "longWindow": {
          "value": 6,
          "unit": "h"
        },
        "shortWindow": {
          "value": 30,
          "unit": "m"
        }
      },
      {
        "id": "medium",
        "actionGroup": "slo.burnRate.medium",
        "burnRateThreshold": 1.5,
        "maxBurnRateThreshold": 6.67,
        "longWindow": {
          "value": 24,
          "unit": "h"
        },
        "shortWindow": {
          "value": 2,
          "unit": "h"
        }
      },
      {
        "id": "low",
        "actionGroup": "slo.burnRate.low",
        "burnRateThreshold": 1,
        "maxBurnRateThreshold": 6.67,
        "longWindow": {
          "value": 72,
          "unit": "h"
        },
        "shortWindow": {
          "value": 6,
          "unit": "h"
        }
      }
    ]
  },
  "actions": [
    {
      "group": "slo.burnRate.alert",
      "id": "12e46700-6e45-11ec-9757-c9700cd1bb4e",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onActionGroupChange",
        "throttle": null
      }
    },
    {
      "group": "slo.burnRate.high",
      "id": "12e46700-6e45-11ec-9757-c9700cd1bb4e",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onActionGroupChange",
        "throttle": null
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-monitoring-production",
          "summaryMode": true,
          "alertStates": {
            "new": true,
            "ongoing": false,
            "recovered": false
          }
        }
      }
    }
  ]
}
'''),
        messages={
            "slo.burnRate.alert": r'''{
  "text": "🚨 **SLO menacé — connexion des jeunes France Travail (prod)**",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "Déclenchée à",
          "value": "`{{date}}`",
          "short": true
        },
        {
          "title": "Promesse",
          "value": "85 % des connexions des jeunes France Travail aboutissent, hors refus métier, sur 30 jours glissants."
        },
        {
          "title": "Ce qui se passe",
          "value": "Sur {{context.longWindow.duration}}, les connexions en échec consomment la marge d'erreur du mois {{context.longWindow.burnRate}} fois plus vite que prévu ({{context.shortWindow.burnRate}} fois sur les {{context.shortWindow.duration}} les plus récentes). À ce rythme, elle est épuisée en {{#EvalMath}} round(30 / {{context.longWindow.burnRate}}, 1) {{/EvalMath}} jours."
        },
        {
          "title": "À vérifier",
          "value": "1. Quel mode de connexion échoue, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Le motif des connexions refusées (fournisseur d'identité, Keycloak) : le Discover [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n3. Si un fournisseur d'identité ou un partenaire est en panne : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Dashboards",
          "value": "[[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n[[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)"
        },
        {
          "title": "Marge d'erreur",
          "value": "[Budget d'erreur et historique du SLO]({{context.viewInAppUrl}})"
        },
        {
          "title": "Runbook",
          "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)"
        }
      ]
    }
  ]
}''',
            "slo.burnRate.high": r'''{
  "text": "🚨 **SLO menacé — connexion des jeunes France Travail (prod)**",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "Déclenchée à",
          "value": "`{{date}}`",
          "short": true
        },
        {
          "title": "Promesse",
          "value": "85 % des connexions des jeunes France Travail aboutissent, hors refus métier, sur 30 jours glissants."
        },
        {
          "title": "Ce qui se passe",
          "value": "Sur {{context.longWindow.duration}}, les connexions en échec consomment la marge d'erreur du mois {{context.longWindow.burnRate}} fois plus vite que prévu ({{context.shortWindow.burnRate}} fois sur les {{context.shortWindow.duration}} les plus récentes). À ce rythme, elle est épuisée en {{#EvalMath}} round(30 / {{context.longWindow.burnRate}}, 1) {{/EvalMath}} jours."
        },
        {
          "title": "À vérifier",
          "value": "1. Quel mode de connexion échoue, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Le motif des connexions refusées (fournisseur d'identité, Keycloak) : le Discover [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n3. Si un fournisseur d'identité ou un partenaire est en panne : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Dashboards",
          "value": "[[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n[[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)"
        },
        {
          "title": "Marge d'erreur",
          "value": "[Budget d'erreur et historique du SLO]({{context.viewInAppUrl}})"
        },
        {
          "title": "Runbook",
          "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)"
        }
      ]
    }
  ]
}''',
        }),
    'S3': dict(
        id='ca02fee2-9d18-46bd-b2b9-dd96d8a6d593', fichier='1-rules-applicatives.console', methode='PUT',
        commentaire="",
        regle=json.loads(r'''
{
  "name": "SLO - Prod - Login — réussite par mode d'authentification",
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nSLO menacé — connexion par mode d'authentification (prod) : la marge d'erreur du SLO se consomme trop vite.\n\n**Promesse** : 99 % des connexions aboutissent, pour chaque mode d'authentification, hors refus métier, sur 30 jours glissants.\n\n## À vérifier\n\n1. Quel mode de connexion échoue, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Le motif des connexions refusées (fournisseur d'identité, Keycloak) : le Discover [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n3. Si un fournisseur d'identité ou un partenaire est en panne : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)\n\n## Dashboards\n\n- [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n- [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)\n\n## Discover sessions\n\n- [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n\n## Documentation\n\n- [Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)\n"
    },
    "dashboards": [
      {
        "id": "b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14"
      },
      {
        "id": "eb348ed9-3bc2-4204-a5c2-c31465731c74"
      }
    ]
  },
  "schedule": {
    "interval": "1m"
  },
  "tags": [
    "prod",
    "slo"
  ],
  "params": {
    "sloId": "9afea251-1cf9-423f-a374-ca43c3e751ac",
    "windows": [
      {
        "id": "alert",
        "actionGroup": "slo.burnRate.alert",
        "burnRateThreshold": 14.4,
        "maxBurnRateThreshold": 100.0,
        "longWindow": {
          "value": 1,
          "unit": "h"
        },
        "shortWindow": {
          "value": 5,
          "unit": "m"
        }
      },
      {
        "id": "high",
        "actionGroup": "slo.burnRate.high",
        "burnRateThreshold": 6,
        "maxBurnRateThreshold": 100.0,
        "longWindow": {
          "value": 6,
          "unit": "h"
        },
        "shortWindow": {
          "value": 30,
          "unit": "m"
        }
      },
      {
        "id": "medium",
        "actionGroup": "slo.burnRate.medium",
        "burnRateThreshold": 3,
        "maxBurnRateThreshold": 100.0,
        "longWindow": {
          "value": 24,
          "unit": "h"
        },
        "shortWindow": {
          "value": 2,
          "unit": "h"
        }
      },
      {
        "id": "low",
        "actionGroup": "slo.burnRate.low",
        "burnRateThreshold": 1,
        "maxBurnRateThreshold": 100.0,
        "longWindow": {
          "value": 72,
          "unit": "h"
        },
        "shortWindow": {
          "value": 6,
          "unit": "h"
        }
      }
    ]
  },
  "actions": [
    {
      "group": "slo.burnRate.alert",
      "id": "12e46700-6e45-11ec-9757-c9700cd1bb4e",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onActionGroupChange",
        "throttle": null
      }
    },
    {
      "group": "slo.burnRate.high",
      "id": "12e46700-6e45-11ec-9757-c9700cd1bb4e",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onActionGroupChange",
        "throttle": null
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-monitoring-production",
          "summaryMode": true,
          "alertStates": {
            "new": true,
            "ongoing": false,
            "recovered": false
          }
        }
      }
    }
  ]
}
'''),
        messages={
            "slo.burnRate.alert": r'''{
  "text": "🚨 **SLO menacé — connexion par mode d'authentification (prod)**",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "Déclenchée à",
          "value": "`{{date}}`",
          "short": true
        },
        {
          "title": "Promesse",
          "value": "99 % des connexions aboutissent, pour chaque mode d'authentification, hors refus métier, sur 30 jours glissants."
        },
        {
          "title": "Parcours / mode",
          "value": "`{{context.sloInstanceId}}`",
          "short": true
        },
        {
          "title": "Ce qui se passe",
          "value": "Sur {{context.longWindow.duration}}, les connexions en échec consomment la marge d'erreur du mois {{context.longWindow.burnRate}} fois plus vite que prévu ({{context.shortWindow.burnRate}} fois sur les {{context.shortWindow.duration}} les plus récentes). À ce rythme, elle est épuisée en {{#EvalMath}} round(30 / {{context.longWindow.burnRate}}, 1) {{/EvalMath}} jours."
        },
        {
          "title": "À vérifier",
          "value": "1. Quel mode de connexion échoue, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Le motif des connexions refusées (fournisseur d'identité, Keycloak) : le Discover [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n3. Si un fournisseur d'identité ou un partenaire est en panne : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Dashboards",
          "value": "[[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n[[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)"
        },
        {
          "title": "Marge d'erreur",
          "value": "[Budget d'erreur et historique du SLO]({{context.viewInAppUrl}})"
        },
        {
          "title": "Runbook",
          "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)"
        }
      ]
    }
  ]
}''',
            "slo.burnRate.high": r'''{
  "text": "🚨 **SLO menacé — connexion par mode d'authentification (prod)**",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "Déclenchée à",
          "value": "`{{date}}`",
          "short": true
        },
        {
          "title": "Promesse",
          "value": "99 % des connexions aboutissent, pour chaque mode d'authentification, hors refus métier, sur 30 jours glissants."
        },
        {
          "title": "Parcours / mode",
          "value": "`{{context.sloInstanceId}}`",
          "short": true
        },
        {
          "title": "Ce qui se passe",
          "value": "Sur {{context.longWindow.duration}}, les connexions en échec consomment la marge d'erreur du mois {{context.longWindow.burnRate}} fois plus vite que prévu ({{context.shortWindow.burnRate}} fois sur les {{context.shortWindow.duration}} les plus récentes). À ce rythme, elle est épuisée en {{#EvalMath}} round(30 / {{context.longWindow.burnRate}}, 1) {{/EvalMath}} jours."
        },
        {
          "title": "À vérifier",
          "value": "1. Quel mode de connexion échoue, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Le motif des connexions refusées (fournisseur d'identité, Keycloak) : le Discover [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n3. Si un fournisseur d'identité ou un partenaire est en panne : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Dashboards",
          "value": "[[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n[[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)"
        },
        {
          "title": "Marge d'erreur",
          "value": "[Budget d'erreur et historique du SLO]({{context.viewInAppUrl}})"
        },
        {
          "title": "Runbook",
          "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)"
        }
      ]
    }
  ]
}''',
        }),
    'S3-invite': dict(
        id='8c760b1b-5859-410e-9a0d-829fb0499412', fichier='1-rules-applicatives.console', methode='PUT',
        commentaire="",
        regle=json.loads(r'''
{
  "name": "SLO - Prod - Login — réussite invité",
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nSLO menacé — connexion en mode invité (prod) : la marge d'erreur du SLO se consomme trop vite.\n\n**Promesse** : 90 % des connexions en mode invité aboutissent, hors refus métier, sur 30 jours glissants.\n\n## À vérifier\n\n1. Quel mode de connexion échoue, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Le motif des connexions refusées (fournisseur d'identité, Keycloak) : le Discover [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n3. Si un fournisseur d'identité ou un partenaire est en panne : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)\n\n## Dashboards\n\n- [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n- [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)\n\n## Discover sessions\n\n- [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n\n## Documentation\n\n- [Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)\n"
    },
    "dashboards": [
      {
        "id": "b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14"
      },
      {
        "id": "eb348ed9-3bc2-4204-a5c2-c31465731c74"
      }
    ]
  },
  "schedule": {
    "interval": "1m"
  },
  "tags": [
    "prod",
    "slo"
  ],
  "params": {
    "sloId": "3d00217c-87b8-45f5-882c-3338bb60750c",
    "windows": [
      {
        "id": "high",
        "actionGroup": "slo.burnRate.high",
        "burnRateThreshold": 2,
        "maxBurnRateThreshold": 10.0,
        "longWindow": {
          "value": 72,
          "unit": "h"
        },
        "shortWindow": {
          "value": 6,
          "unit": "h"
        }
      }
    ]
  },
  "actions": [
    {
      "group": "slo.burnRate.high",
      "id": "12e46700-6e45-11ec-9757-c9700cd1bb4e",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onActionGroupChange",
        "throttle": null
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-monitoring-production",
          "summaryMode": true,
          "alertStates": {
            "new": true,
            "ongoing": false,
            "recovered": false
          }
        }
      }
    }
  ]
}
'''),
        messages={
            "slo.burnRate.high": r'''{
  "text": "🚨 **SLO menacé — connexion en mode invité (prod)**",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "Déclenchée à",
          "value": "`{{date}}`",
          "short": true
        },
        {
          "title": "Promesse",
          "value": "90 % des connexions en mode invité aboutissent, hors refus métier, sur 30 jours glissants."
        },
        {
          "title": "Ce qui se passe",
          "value": "Sur {{context.longWindow.duration}}, les connexions en échec consomment la marge d'erreur du mois {{context.longWindow.burnRate}} fois plus vite que prévu ({{context.shortWindow.burnRate}} fois sur les {{context.shortWindow.duration}} les plus récentes). À ce rythme, elle est épuisée en {{#EvalMath}} round(30 / {{context.longWindow.burnRate}}, 1) {{/EvalMath}} jours."
        },
        {
          "title": "À vérifier",
          "value": "1. Quel mode de connexion échoue, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Le motif des connexions refusées (fournisseur d'identité, Keycloak) : le Discover [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n3. Si un fournisseur d'identité ou un partenaire est en panne : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Dashboards",
          "value": "[[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n[[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)"
        },
        {
          "title": "Marge d'erreur",
          "value": "[Budget d'erreur et historique du SLO]({{context.viewInAppUrl}})"
        },
        {
          "title": "Runbook",
          "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)"
        }
      ]
    }
  ]
}''',
        }),
    'S3-cd': dict(
        id='00f15660-40ba-4fb1-a59d-6345ce07c360', fichier='1-rules-applicatives.console', methode='PUT',
        commentaire="",
        regle=json.loads(r'''
{
  "name": "SLO - Prod - Login — réussite conseiller départemental",
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nSLO menacé — connexion des conseillers départementaux (prod) : la marge d'erreur du SLO se consomme trop vite.\n\n**Promesse** : 95 % des connexions des conseillers départementaux aboutissent, hors refus métier, sur 30 jours glissants.\n\n## À vérifier\n\n1. Quel mode de connexion échoue, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Le motif des connexions refusées (fournisseur d'identité, Keycloak) : le Discover [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n3. Si un fournisseur d'identité ou un partenaire est en panne : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)\n\n## Dashboards\n\n- [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n- [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)\n\n## Discover sessions\n\n- [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n\n## Documentation\n\n- [Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)\n"
    },
    "dashboards": [
      {
        "id": "b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14"
      },
      {
        "id": "eb348ed9-3bc2-4204-a5c2-c31465731c74"
      }
    ]
  },
  "schedule": {
    "interval": "1m"
  },
  "tags": [
    "prod",
    "slo"
  ],
  "params": {
    "sloId": "61f38008-cb75-41de-aadc-0a65d2cb7a0d",
    "windows": [
      {
        "id": "high",
        "actionGroup": "slo.burnRate.high",
        "burnRateThreshold": 4,
        "maxBurnRateThreshold": 20.0,
        "longWindow": {
          "value": 168,
          "unit": "h"
        },
        "shortWindow": {
          "value": 12,
          "unit": "h"
        }
      }
    ]
  },
  "actions": [
    {
      "group": "slo.burnRate.high",
      "id": "12e46700-6e45-11ec-9757-c9700cd1bb4e",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onActionGroupChange",
        "throttle": null
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-monitoring-production",
          "summaryMode": true,
          "alertStates": {
            "new": true,
            "ongoing": false,
            "recovered": false
          }
        }
      }
    }
  ]
}
'''),
        messages={
            "slo.burnRate.high": r'''{
  "text": "🚨 **SLO menacé — connexion des conseillers départementaux (prod)**",
  "attachments": [
    {
      "color": "#d00000",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "Déclenchée à",
          "value": "`{{date}}`",
          "short": true
        },
        {
          "title": "Promesse",
          "value": "95 % des connexions des conseillers départementaux aboutissent, hors refus métier, sur 30 jours glissants."
        },
        {
          "title": "Ce qui se passe",
          "value": "Sur {{context.longWindow.duration}}, les connexions en échec consomment la marge d'erreur du mois {{context.longWindow.burnRate}} fois plus vite que prévu ({{context.shortWindow.burnRate}} fois sur les {{context.shortWindow.duration}} les plus récentes). À ce rythme, elle est épuisée en {{#EvalMath}} round(30 / {{context.longWindow.burnRate}}, 1) {{/EvalMath}} jours."
        },
        {
          "title": "À vérifier",
          "value": "1. Quel mode de connexion échoue, et depuis quand : le dashboard [[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n2. Le motif des connexions refusées (fournisseur d'identité, Keycloak) : le Discover [[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)\n3. Si un fournisseur d'identité ou un partenaire est en panne : le dashboard [[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Dashboards",
          "value": "[[Pass Emploi] SLO de Prod](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/b7c1e0d2-5f43-4a8e-9c61-2d8f3a9e7b14)\n[[Pass Emploi] Diagnostic d'erreurs - Entrée](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/eb348ed9-3bc2-4204-a5c2-c31465731c74)"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs de Prod - Erreurs d'authentification](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/1c0dfc0f-0534-4031-81c6-cee0d1c55de8)"
        },
        {
          "title": "Marge d'erreur",
          "value": "[Budget d'erreur et historique du SLO]({{context.viewInAppUrl}})"
        },
        {
          "title": "Runbook",
          "value": "[Investiguer un incident applicatif](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/investigation-incident.md)"
        }
      ]
    }
  ]
}''',
        }),
}
