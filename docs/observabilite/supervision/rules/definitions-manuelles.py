# Règles écrites à la main avant generer-regles.py, reprises telles quelles le 2026-10-22.
# Leur message est rangé ici (messages, un par groupe d'action), à part de l'action
# Mattermost qui l'envoie : il reste disponible pour Tchap quand cette action disparaît.
# regle : le corps de la règle, sans les messages. Modifier ici, puis
# python3 -I generer-regles.py --ecrire <code> et ../workflows/tchap/generer-workflows.py.
import json

REGLES_MANUELLES = {
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
    '1a': dict(
        id='fe53ada2-2c8b-42eb-930c-bae4286b7893', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 1a — DLQ prod (Critical)",
        regle=json.loads(r'''
{
  "name": "Logstash - Prod - Détection présence event dans DLQ",
  "tags": [
    "prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nLogs de prod non indexés : échec de process Logstash indéterminé — des logs de prod ne sont pas consultables dans Kibana, sans erreur détectée par Logstash.\n\n## À vérifier\n\n1. Pourquoi Elasticsearch a refusé ces logs : le Discover [[Pass Emploi] Logs de Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/97e2d85f-7bd2-49df-86b3-2ffc290bbe69) donne le motif de chaque rejet (mapping, document trop gros…) et l'app d'origine\n2. Si des rejets arrivent encore : le débit et les erreurs de l'output Elasticsearch dans le dashboard [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)\n3. Corriger le mapping ou le pipeline selon le motif (runbook, scénario 3)\n\n## Dashboards\n\n- [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)\n\n## Discover sessions\n\n- [[Pass Emploi] Logs de Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/97e2d85f-7bd2-49df-86b3-2ffc290bbe69)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)\n"
    },
    "dashboards": [
      {
        "id": "logstash-4bbf4a50-6ece-11ee-910d-eb0006359086"
      }
    ]
  },
  "schedule": {
    "interval": "1m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "",
        "language": "kuery"
      },
      "index": {
        "id": "b5459fcf-9a0c-45d9-8ab0-f812cf7ddbb3",
        "title": "logs-logstash-dlq-prod-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "Logs Logstash Prod - Dead Letter Queue",
        "allowHidden": true,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 5,
    "timeWindowUnit": "m",
    "threshold": [
      0
    ],
    "thresholdComparator": ">",
    "size": 100,
    "aggType": "count",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": []
  },
  "actions": [
    {
      "group": "query matched",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-production",
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
            "query matched": r'''{
  "text": "🚨 **Logs de prod non indexés : échec de process Logstash indéterminé** — des logs de prod ne sont pas consultables dans Kibana, sans erreur détectée par Logstash.",
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
          "title": "À vérifier",
          "value": "1. Pourquoi Elasticsearch a refusé ces logs : le Discover [[Pass Emploi] Logs de Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/97e2d85f-7bd2-49df-86b3-2ffc290bbe69) donne le motif de chaque rejet (mapping, document trop gros…) et l'app d'origine\n2. Si des rejets arrivent encore : le débit et les erreurs de l'output Elasticsearch dans le dashboard [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)\n3. Corriger le mapping ou le pipeline selon le motif (runbook, scénario 3)"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs de Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/97e2d85f-7bd2-49df-86b3-2ffc290bbe69)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)"
        }
      ]
    }
  ]
}''',
        }),
    '1b': dict(
        id='b100ff40-7409-4859-ac44-755ad2401f03', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 1b — DLQ staging / perf (Warning)",
        regle=json.loads(r'''
{
  "name": "Logstash - Hors-Prod - Détection présence event dans DLQ",
  "tags": [
    "hors-prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nLogs hors prod non indexés : échec de process Logstash indéterminé — des logs de staging/perf ne sont pas consultables dans Kibana, sans erreur détectée par Logstash.\n\n## À vérifier\n\n1. Pourquoi Elasticsearch a refusé ces logs : le Discover [[Pass Emploi] Logs Hors-Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/e5bec6b4-0ae3-47b1-8bb5-2e9bf77493a4) donne le motif de chaque rejet (mapping, document trop gros…) et l'app d'origine\n2. Si des rejets arrivent encore : le débit et les erreurs de l'output Elasticsearch dans le dashboard [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)\n3. Corriger le mapping ou le pipeline selon le motif (runbook, scénario 3)\n\n## Dashboards\n\n- [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)\n\n## Discover sessions\n\n- [[Pass Emploi] Logs Hors-Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/e5bec6b4-0ae3-47b1-8bb5-2e9bf77493a4)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)\n"
    },
    "dashboards": [
      {
        "id": "logstash-4bbf4a50-6ece-11ee-910d-eb0006359086"
      }
    ]
  },
  "schedule": {
    "interval": "5m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "",
        "language": "kuery"
      },
      "index": {
        "id": "3bdd37f9-03a0-4247-94fd-6e6252d21a47",
        "title": "logs-logstash-dlq-staging-default,logs-logstash-dlq-perf-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "Logs Logstash Hors-Prod - Dead Letter Queue",
        "allowHidden": true,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 5,
    "timeWindowUnit": "m",
    "threshold": [
      0
    ],
    "thresholdComparator": ">",
    "size": 100,
    "aggType": "count",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": []
  },
  "actions": [
    {
      "group": "query matched",
      "id": "c4a313b3-aa42-4e07-8196-c007625ce8af",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-staging",
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
            "query matched": r'''{
  "text": "⚠️ **Logs hors prod non indexés : échec de process Logstash indéterminé** — des logs de staging/perf ne sont pas consultables dans Kibana, sans erreur détectée par Logstash.",
  "attachments": [
    {
      "color": "#f2c744",
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
          "title": "À vérifier",
          "value": "1. Pourquoi Elasticsearch a refusé ces logs : le Discover [[Pass Emploi] Logs Hors-Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/e5bec6b4-0ae3-47b1-8bb5-2e9bf77493a4) donne le motif de chaque rejet (mapping, document trop gros…) et l'app d'origine\n2. Si des rejets arrivent encore : le débit et les erreurs de l'output Elasticsearch dans le dashboard [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)\n3. Corriger le mapping ou le pipeline selon le motif (runbook, scénario 3)"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs Hors-Prod - DLQ Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/e5bec6b4-0ae3-47b1-8bb5-2e9bf77493a4)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)"
        }
      ]
    }
  ]
}''',
        }),
    '2a': dict(
        id='dd107070-c841-4580-9923-db2ef37c795d', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 2a — Erreurs prod (Warning, bilan quotidien)",
        regle=json.loads(r'''
{
  "name": "Logstash - Prod - Détection erreurs pipeline process",
  "tags": [
    "prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nLogs de prod non indexés : erreur de transformation Logstash — bilan des 24 h — … logs de prod ne sont pas consultables dans Kibana.\n\n## À vérifier\n\n1. Quels logs n'ont pas pu être transformés : le Discover [[Pass Emploi] Logs de Prod - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/f10de9e3-0fdd-4761-9d44-bacc96504e17) — `tags` donne l'étape en échec, `message` le log d'origine\n2. Quelle app les émet, et depuis quand : la répartition par `service.name` (onglet *Field statistics*) du même Discover\n3. Corriger le filtre Logstash concerné (`logs/` de pass-emploi-tools), puis vérifier que les erreurs cessent dans le même Discover\n\n## Discover sessions\n\n- [[Pass Emploi] Logs de Prod - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/f10de9e3-0fdd-4761-9d44-bacc96504e17)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)\n"
    }
  },
  "schedule": {
    "interval": "1h"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "",
        "language": "kuery"
      },
      "index": {
        "id": "c0721d04-4dc0-4a2f-a89c-dddb02382e1e",
        "title": "logs-logstash-errors-prod-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "Logs Logstash Prod - Index erreurs de traitement Pipeline process",
        "allowHidden": true,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 24,
    "timeWindowUnit": "h",
    "threshold": [
      0
    ],
    "thresholdComparator": ">",
    "size": 100,
    "aggType": "count",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": []
  },
  "actions": [
    {
      "group": "query matched",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onActiveAlert",
        "throttle": null
      },
      "alerts_filter": {
        "timeframe": {
          "days": [
            1,
            2,
            3,
            4,
            5,
            6,
            7
          ],
          "timezone": "Europe/Paris",
          "hours": {
            "start": "09:30",
            "end": "10:30"
          }
        }
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-production",
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
            "query matched": r'''{
  "text": "⚠️ **Logs de prod non indexés : erreur de transformation Logstash — bilan des 24 h** — {{context.value}} logs de prod ne sont pas consultables dans Kibana.",
  "attachments": [
    {
      "color": "#f2c744",
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
          "title": "À vérifier",
          "value": "1. Quels logs n'ont pas pu être transformés : le Discover [[Pass Emploi] Logs de Prod - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/f10de9e3-0fdd-4761-9d44-bacc96504e17) — `tags` donne l'étape en échec, `message` le log d'origine\n2. Quelle app les émet, et depuis quand : la répartition par `service.name` (onglet *Field statistics*) du même Discover\n3. Corriger le filtre Logstash concerné (`logs/` de pass-emploi-tools), puis vérifier que les erreurs cessent dans le même Discover"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs de Prod - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/f10de9e3-0fdd-4761-9d44-bacc96504e17)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)"
        }
      ]
    }
  ]
}''',
        }),
    '2b': dict(
        id='ede49ade-b4ee-4cbb-9dd2-28078e189f7b', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 2b — Erreurs staging / perf (Warning)",
        regle=json.loads(r'''
{
  "name": "Logstash - Hors-Prod - Détection erreurs pipeline process",
  "tags": [
    "hors-prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nLogs hors prod non indexés : erreur de transformation Logstash — des logs de staging/perf ne sont pas consultables dans Kibana.\n\n## À vérifier\n\n1. Quels logs n'ont pas pu être transformés : le Discover [[Pass Emploi] Logs Hors-Prod - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/716175ed-b2a0-4fe1-8f9d-1892d04dbe92) — `tags` donne l'étape en échec, `message` le log d'origine\n2. Quelle app les émet, et depuis quand : la répartition par `service.name` (onglet *Field statistics*) du même Discover\n3. Corriger le filtre Logstash concerné (`logs/` de pass-emploi-tools), puis vérifier que les erreurs cessent dans le même Discover\n\n## Discover sessions\n\n- [[Pass Emploi] Logs Hors-Prod - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/716175ed-b2a0-4fe1-8f9d-1892d04dbe92)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)\n"
    }
  },
  "schedule": {
    "interval": "5m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "",
        "language": "kuery"
      },
      "index": {
        "id": "1ed38454-c7e7-4726-9db4-434106a710d4",
        "title": "logs-logstash-errors-staging-default,logs-logstash-errors-perf-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "Logs Logstash Hors-Prod - Index erreurs de traitement Pipeline process",
        "allowHidden": true,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 5,
    "timeWindowUnit": "m",
    "threshold": [
      0
    ],
    "thresholdComparator": ">",
    "size": 100,
    "aggType": "count",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": []
  },
  "actions": [
    {
      "group": "query matched",
      "id": "c4a313b3-aa42-4e07-8196-c007625ce8af",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-staging",
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
            "query matched": r'''{
  "text": "⚠️ **Logs hors prod non indexés : erreur de transformation Logstash** — des logs de staging/perf ne sont pas consultables dans Kibana.",
  "attachments": [
    {
      "color": "#f2c744",
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
          "title": "À vérifier",
          "value": "1. Quels logs n'ont pas pu être transformés : le Discover [[Pass Emploi] Logs Hors-Prod - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/716175ed-b2a0-4fe1-8f9d-1892d04dbe92) — `tags` donne l'étape en échec, `message` le log d'origine\n2. Quelle app les émet, et depuis quand : la répartition par `service.name` (onglet *Field statistics*) du même Discover\n3. Corriger le filtre Logstash concerné (`logs/` de pass-emploi-tools), puis vérifier que les erreurs cessent dans le même Discover"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Logs Hors-Prod - Erreurs de traitement Logstash Process](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/716175ed-b2a0-4fe1-8f9d-1892d04dbe92)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-3--rejet-de-mapping--dead-letter-queue)"
        }
      ]
    }
  ]
}''',
        }),
    '3a': dict(
        id='139c93c3-b744-4bd7-8274-bb88f77305c7', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 3a — Absence dans `logs-prod-default`",
        regle=json.loads(r'''
{
  "name": "Logstash - Prod - Détection absence ingestion logs applicatifs",
  "tags": [
    "prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nSilence Logstash — aucun log dans `logs-prod-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.\n\n## À vérifier\n\n1. Logstash reçoit-il encore des logs : les débits d'entrée et de sortie dans le dashboard [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n2. Une seule source ou toute l'ingestion : si les logs du router arrivent toujours (pas d'alerte de silence de leur côté), le drain d'une app est en quarantaine ; sinon, Logstash est arrêté ou a redémarré (son activité dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'agent qui remonte les métriques de Logstash fonctionne-t-il : le dashboard [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824), sinon les débits ci-dessus sont aveugles\n\n## Dashboards\n\n- [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)\n"
    },
    "dashboards": [
      {
        "id": "logstash-79270240-48ee-11ee-8cb5-99927777c522"
      },
      {
        "id": "elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824"
      }
    ]
  },
  "schedule": {
    "interval": "2m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "",
        "language": "kuery"
      },
      "index": {
        "id": "42d38a6d-609d-4f7b-b93c-10737cc4dc5f",
        "title": "logs-prod-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "logs-prod-default",
        "allowHidden": false,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 5,
    "timeWindowUnit": "m",
    "threshold": [
      0
    ],
    "thresholdComparator": "<=",
    "size": 100,
    "aggType": "count",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": []
  },
  "actions": [
    {
      "group": "query matched",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "group": "recovered",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
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
          "workflowId": "tchap-o11y-production",
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
            "query matched": r'''{
  "text": "🚨 **Silence Logstash** — aucun log dans `logs-prod-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.",
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
          "title": "À vérifier",
          "value": "1. Logstash reçoit-il encore des logs : les débits d'entrée et de sortie dans le dashboard [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n2. Une seule source ou toute l'ingestion : si les logs du router arrivent toujours (pas d'alerte de silence de leur côté), le drain d'une app est en quarantaine ; sinon, Logstash est arrêté ou a redémarré (son activité dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'agent qui remonte les métriques de Logstash fonctionne-t-il : le dashboard [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824), sinon les débits ci-dessus sont aveugles"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)"
        }
      ]
    }
  ]
}''',
            "recovered": r'''{
  "text": "✅ **Silence Logstash résolu** — les logs sont revenus dans `logs-prod-default`.",
  "attachments": [
    {
      "color": "#2eb886",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "À vérifier",
          "value": "1. Logstash reçoit-il encore des logs : les débits d'entrée et de sortie dans le dashboard [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n2. Une seule source ou toute l'ingestion : si les logs du router arrivent toujours (pas d'alerte de silence de leur côté), le drain d'une app est en quarantaine ; sinon, Logstash est arrêté ou a redémarré (son activité dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'agent qui remonte les métriques de Logstash fonctionne-t-il : le dashboard [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824), sinon les débits ci-dessus sont aveugles"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)"
        }
      ]
    }
  ]
}''',
        }),
    '3b': dict(
        id='6c2a2a83-9c40-4f40-af8d-911402932417', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 3b — Absence dans `logs-router-prod-default`",
        regle=json.loads(r'''
{
  "name": "Logstash - Prod - Détection absence ingestion logs router",
  "tags": [
    "prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nSilence Logstash — aucun log router dans `logs-router-prod-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.\n\n## À vérifier\n\n1. Logstash reçoit-il encore des logs : les débits d'entrée et de sortie dans le dashboard [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n2. Une seule source ou toute l'ingestion : si les logs applicatifs arrivent toujours (pas d'alerte de silence de leur côté), le drain d'une app est en quarantaine ; sinon, Logstash est arrêté ou a redémarré (son activité dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'agent qui remonte les métriques de Logstash fonctionne-t-il : le dashboard [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824), sinon les débits ci-dessus sont aveugles\n\n## Dashboards\n\n- [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)\n"
    },
    "dashboards": [
      {
        "id": "logstash-79270240-48ee-11ee-8cb5-99927777c522"
      },
      {
        "id": "elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824"
      }
    ]
  },
  "schedule": {
    "interval": "2m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "",
        "language": "kuery"
      },
      "index": {
        "id": "5044caf1-8ad5-456a-a48c-1783c51160c5",
        "title": "logs-router-prod-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "logs-router-prod-default",
        "allowHidden": false,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 5,
    "timeWindowUnit": "m",
    "threshold": [
      0
    ],
    "thresholdComparator": "<=",
    "size": 100,
    "aggType": "count",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": []
  },
  "actions": [
    {
      "group": "query matched",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "group": "recovered",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
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
          "workflowId": "tchap-o11y-production",
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
            "query matched": r'''{
  "text": "🚨 **Silence Logstash** — aucun log router dans `logs-router-prod-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.",
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
          "title": "À vérifier",
          "value": "1. Logstash reçoit-il encore des logs : les débits d'entrée et de sortie dans le dashboard [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n2. Une seule source ou toute l'ingestion : si les logs applicatifs arrivent toujours (pas d'alerte de silence de leur côté), le drain d'une app est en quarantaine ; sinon, Logstash est arrêté ou a redémarré (son activité dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'agent qui remonte les métriques de Logstash fonctionne-t-il : le dashboard [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824), sinon les débits ci-dessus sont aveugles"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)"
        }
      ]
    }
  ]
}''',
            "recovered": r'''{
  "text": "✅ **Silence Logstash résolu** — les logs router sont revenus dans `logs-router-prod-default`.",
  "attachments": [
    {
      "color": "#2eb886",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "À vérifier",
          "value": "1. Logstash reçoit-il encore des logs : les débits d'entrée et de sortie dans le dashboard [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n2. Une seule source ou toute l'ingestion : si les logs applicatifs arrivent toujours (pas d'alerte de silence de leur côté), le drain d'une app est en quarantaine ; sinon, Logstash est arrêté ou a redémarré (son activité dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'agent qui remonte les métriques de Logstash fonctionne-t-il : le dashboard [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824), sinon les débits ci-dessus sont aveugles"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)"
        }
      ]
    }
  ]
}''',
        }),
    '3c': dict(
        id='32b686a2-659f-4b57-b583-e6aedaeea5f5', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 3c — Absence dans `logs-staging-default` / `logs-perf-default`",
        regle=json.loads(r'''
{
  "name": "Logstash - Hors-Prod - Détection absence ingestion logs applicatifs",
  "tags": [
    "hors-prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nSilence Logstash — aucun log dans `logs-staging-default` ou `logs-perf-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.\n\n## À vérifier\n\n1. Logstash reçoit-il encore des logs : les débits d'entrée et de sortie dans le dashboard [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n2. Une seule source ou toute l'ingestion : si les logs du router arrivent toujours (pas d'alerte de silence de leur côté), le drain d'une app est en quarantaine ; sinon, Logstash est arrêté ou a redémarré (son activité dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'agent qui remonte les métriques de Logstash fonctionne-t-il : le dashboard [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824), sinon les débits ci-dessus sont aveugles\n\n## Dashboards\n\n- [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)\n"
    },
    "dashboards": [
      {
        "id": "logstash-79270240-48ee-11ee-8cb5-99927777c522"
      },
      {
        "id": "elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824"
      }
    ]
  },
  "schedule": {
    "interval": "5m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "",
        "language": "kuery"
      },
      "index": {
        "id": "53398744-ca2c-4a5e-9130-17396d3143e0",
        "title": "logs-staging-default,logs-perf-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "Logs Logstash Hors-Prod - Index applicatifs",
        "allowHidden": true,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 5,
    "timeWindowUnit": "m",
    "threshold": [
      0
    ],
    "thresholdComparator": "<=",
    "size": 100,
    "aggType": "count",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": []
  },
  "actions": [
    {
      "group": "query matched",
      "id": "c4a313b3-aa42-4e07-8196-c007625ce8af",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-staging",
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
            "query matched": r'''{
  "text": "⚠️ **Silence Logstash** — aucun log dans `logs-staging-default` ou `logs-perf-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.",
  "attachments": [
    {
      "color": "#f2c744",
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
          "title": "À vérifier",
          "value": "1. Logstash reçoit-il encore des logs : les débits d'entrée et de sortie dans le dashboard [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n2. Une seule source ou toute l'ingestion : si les logs du router arrivent toujours (pas d'alerte de silence de leur côté), le drain d'une app est en quarantaine ; sinon, Logstash est arrêté ou a redémarré (son activité dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'agent qui remonte les métriques de Logstash fonctionne-t-il : le dashboard [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824), sinon les débits ci-dessus sont aveugles"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)"
        }
      ]
    }
  ]
}''',
        }),
    '3d': dict(
        id='f181937f-c75f-4232-bfa4-221997d1cfe1', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 3d — Absence dans `logs-router-staging-default` / `logs-router-perf-default`",
        regle=json.loads(r'''
{
  "name": "Logstash - Hors-Prod - Détection absence ingestion logs router",
  "tags": [
    "hors-prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nSilence Logstash — aucun log router dans `logs-router-staging-default` ou `logs-router-perf-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.\n\n## À vérifier\n\n1. Logstash reçoit-il encore des logs : les débits d'entrée et de sortie dans le dashboard [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n2. Une seule source ou toute l'ingestion : si les logs applicatifs arrivent toujours (pas d'alerte de silence de leur côté), le drain d'une app est en quarantaine ; sinon, Logstash est arrêté ou a redémarré (son activité dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'agent qui remonte les métriques de Logstash fonctionne-t-il : le dashboard [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824), sinon les débits ci-dessus sont aveugles\n\n## Dashboards\n\n- [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)\n"
    },
    "dashboards": [
      {
        "id": "logstash-79270240-48ee-11ee-8cb5-99927777c522"
      },
      {
        "id": "elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824"
      }
    ]
  },
  "schedule": {
    "interval": "5m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "",
        "language": "kuery"
      },
      "index": {
        "id": "d67448bc-e25f-4c2d-bd28-acf2c1861b2b",
        "title": "logs-router-staging-default,logs-router-perf-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "Logs Logstash Hors-Prod - Index router",
        "allowHidden": true,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 5,
    "timeWindowUnit": "m",
    "threshold": [
      0
    ],
    "thresholdComparator": "<=",
    "size": 100,
    "aggType": "count",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": []
  },
  "actions": [
    {
      "group": "query matched",
      "id": "c4a313b3-aa42-4e07-8196-c007625ce8af",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-staging",
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
            "query matched": r'''{
  "text": "⚠️ **Silence Logstash** — aucun log router dans `logs-router-staging-default` ou `logs-router-perf-default` depuis 5 min. Drain en quarantaine ou Logstash crashé.",
  "attachments": [
    {
      "color": "#f2c744",
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
          "title": "À vérifier",
          "value": "1. Logstash reçoit-il encore des logs : les débits d'entrée et de sortie dans le dashboard [[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n2. Une seule source ou toute l'ingestion : si les logs applicatifs arrivent toujours (pas d'alerte de silence de leur côté), le drain d'une app est en quarantaine ; sinon, Logstash est arrêté ou a redémarré (son activité dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'agent qui remonte les métriques de Logstash fonctionne-t-il : le dashboard [[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824), sinon les débits ci-dessus sont aveugles"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Logstash Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-79270240-48ee-11ee-8cb5-99927777c522)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Elastic Agent] Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-a148dc70-6b3c-11ed-98de-67bdecd21824)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)"
        }
      ]
    }
  ]
}''',
        }),
    '4a': dict(
        id='204d560c-b6a6-4b5c-b4af-8d1fa6ce345c', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 4a — Backpressure prod (Critical)",
        regle=json.loads(r'''
{
  "name": "Logstash - Prod - Détection backpressure ingest (inputs bloqués)",
  "tags": [
    "prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nBackpressure Logstash prod — le pipeline `ingest` a au moins un thread HTTP bloqué en continu depuis 15 min (`queue_backpressure ≥ 1`) : l'écriture dans Redis ne suit plus, le drain Scalingo attend.\n\n## À vérifier\n\n1. Où le pipeline `ingest` du nœud bloque : le temps passé à pousser dans la file, dans le dashboard [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n2. Redis répond-il : le statut et la mémoire de l'add-on Redis dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps), puis le temps d'écriture de l'output `redis` dans le dashboard [[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)\n3. Les entrées refusent-elles des logs (429 renvoyés aux drains) : le dashboard [[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975), et l'état de toute la chaîne dans le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n\n## Dashboards\n\n- [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)\n- [[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975)\n- [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-1--backpressure-elasticsearch)\n"
    },
    "dashboards": [
      {
        "id": "logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc"
      },
      {
        "id": "logstash-fe17b800-6eb4-11ee-86f6-d7074508d975"
      },
      {
        "id": "logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975"
      },
      {
        "id": "fd40a516-c323-4e5e-91e5-1328b8b1a78d"
      }
    ]
  },
  "schedule": {
    "interval": "2m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "logstash.pipeline.name: ingest and logstash.pipeline.host.name: pass-emploi-logstash-prod-*",
        "language": "kuery"
      },
      "index": {
        "id": "68ab5f84-55a4-43b9-9e7d-c6154919c39d",
        "title": "metrics-logstash.pipeline-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "metrics-logstash.pipeline-default",
        "allowHidden": false,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 15,
    "timeWindowUnit": "m",
    "threshold": [
      1
    ],
    "thresholdComparator": ">=",
    "size": 100,
    "aggType": "min",
    "groupBy": "top",
    "termSize": 10,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": [],
    "aggField": "logstash.pipeline.total.flow.queue_backpressure.current",
    "termField": "logstash.pipeline.host.name"
  },
  "actions": [
    {
      "group": "query matched",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "group": "recovered",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
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
          "workflowId": "tchap-o11y-production",
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
            "query matched": r'''{
  "text": "🚨 **Backpressure Logstash prod** — le pipeline `ingest` a au moins un thread HTTP bloqué en continu depuis 15 min (`queue_backpressure ≥ 1`) : l'écriture dans Redis ne suit plus, le drain Scalingo attend.",
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
          "title": "Nœud",
          "value": "`{{context.group}}`",
          "short": true
        },
        {
          "title": "À vérifier",
          "value": "1. Où le pipeline `ingest` du nœud bloque : le temps passé à pousser dans la file, dans le dashboard [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n2. Redis répond-il : le statut et la mémoire de l'add-on Redis dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps), puis le temps d'écriture de l'output `redis` dans le dashboard [[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)\n3. Les entrées refusent-elles des logs (429 renvoyés aux drains) : le dashboard [[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975), et l'état de toute la chaîne dans le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)\n[[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975)\n[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-1--backpressure-elasticsearch)"
        }
      ]
    }
  ]
}''',
            "recovered": r'''{
  "text": "✅ **Backpressure Logstash prod résolue** — le pipeline `ingest` n'a plus de thread bloqué en continu.",
  "attachments": [
    {
      "color": "#2eb886",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "À vérifier",
          "value": "1. Où le pipeline `ingest` du nœud bloque : le temps passé à pousser dans la file, dans le dashboard [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n2. Redis répond-il : le statut et la mémoire de l'add-on Redis dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps), puis le temps d'écriture de l'output `redis` dans le dashboard [[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)\n3. Les entrées refusent-elles des logs (429 renvoyés aux drains) : le dashboard [[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975), et l'état de toute la chaîne dans le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)\n[[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975)\n[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)"
        }
      ]
    }
  ]
}''',
        }),
    '4b': dict(
        id='da91356c-39dc-4033-bc47-83421974a049', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 4b — Backpressure staging / perf (Warning)",
        regle=json.loads(r'''
{
  "name": "Logstash - Hors-Prod - Détection backpressure ingest (inputs bloqués)",
  "tags": [
    "hors-prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nBackpressure Logstash staging/perf — le pipeline `ingest` a au moins un thread HTTP bloqué en continu depuis 15 min (`queue_backpressure ≥ 1`).\n\n## À vérifier\n\n1. Où le pipeline `ingest` du nœud bloque : le temps passé à pousser dans la file, dans le dashboard [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n2. Redis répond-il : le statut et la mémoire de l'add-on Redis dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps), puis le temps d'écriture de l'output `redis` dans le dashboard [[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)\n3. Les entrées refusent-elles des logs (429 renvoyés aux drains) : le dashboard [[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975), et l'état de toute la chaîne dans le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n\n## Dashboards\n\n- [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)\n- [[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975)\n- [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-1--backpressure-elasticsearch)\n"
    },
    "dashboards": [
      {
        "id": "logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc"
      },
      {
        "id": "logstash-fe17b800-6eb4-11ee-86f6-d7074508d975"
      },
      {
        "id": "logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975"
      },
      {
        "id": "fd40a516-c323-4e5e-91e5-1328b8b1a78d"
      }
    ]
  },
  "schedule": {
    "interval": "5m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "logstash.pipeline.name: ingest and logstash.pipeline.host.name: (pass-emploi-logstash-staging-* OR pass-emploi-logstash-perf-*)",
        "language": "kuery"
      },
      "index": {
        "id": "32bb011e-69e0-42ed-9dc6-479f2c0e9ee0",
        "title": "metrics-logstash.pipeline-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "metrics-logstash.pipeline-default",
        "allowHidden": false,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 15,
    "timeWindowUnit": "m",
    "threshold": [
      1
    ],
    "thresholdComparator": ">=",
    "size": 100,
    "aggType": "min",
    "groupBy": "top",
    "termSize": 10,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": [],
    "aggField": "logstash.pipeline.total.flow.queue_backpressure.current",
    "termField": "logstash.pipeline.host.name"
  },
  "actions": [
    {
      "group": "query matched",
      "id": "c4a313b3-aa42-4e07-8196-c007625ce8af",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-staging",
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
            "query matched": r'''{
  "text": "⚠️ **Backpressure Logstash staging/perf** — le pipeline `ingest` a au moins un thread HTTP bloqué en continu depuis 15 min (`queue_backpressure ≥ 1`).",
  "attachments": [
    {
      "color": "#f2c744",
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
          "title": "Nœud",
          "value": "`{{context.group}}`",
          "short": true
        },
        {
          "title": "À vérifier",
          "value": "1. Où le pipeline `ingest` du nœud bloque : le temps passé à pousser dans la file, dans le dashboard [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n2. Redis répond-il : le statut et la mémoire de l'add-on Redis dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps), puis le temps d'écriture de l'output `redis` dans le dashboard [[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)\n3. Les entrées refusent-elles des logs (429 renvoyés aux drains) : le dashboard [[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975), et l'état de toute la chaîne dans le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Metrics Logstash] Output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-fe17b800-6eb4-11ee-86f6-d7074508d975)\n[[Metrics Logstash] Input plugin Info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-8f8c78a0-6e9e-11ee-86f6-d7074508d975)\n[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-1--backpressure-elasticsearch)"
        }
      ]
    }
  ]
}''',
        }),
    '5a': dict(
        id='f8ff266d-84dc-4673-b95c-c3d32bf2ff04', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 5a — Heap élevé prod (Critical)",
        regle=json.loads(r'''
{
  "name": "Logstash - Prod - Détection heap JVM élevé",
  "tags": [
    "prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nHeap JVM Logstash prod — le heap reste au-dessus de 90 % depuis 15 min : le GC ne libère plus, pauses stop-the-world et `OutOfMemoryError` en vue.\n\n## À vérifier\n\n1. Le heap du nœud redescend-il, et le GC suit-il : le dashboard [[Metrics Logstash] Single Node Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9d450b10-4680-11ee-9ddc-919f87fe352d)\n2. La configuration mémoire : `LS_JAVA_OPTS` de l'app doit valoir `-Xms256m -Xmx256m` (onglet *Environment* dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'effet sur l'ingestion (débit, backlog Redis) : le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n\n## Dashboards\n\n- [[Metrics Logstash] Single Node Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9d450b10-4680-11ee-9ddc-919f87fe352d)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-2--gel-gc-jvm)\n"
    },
    "dashboards": [
      {
        "id": "logstash-9d450b10-4680-11ee-9ddc-919f87fe352d"
      },
      {
        "id": "fd40a516-c323-4e5e-91e5-1328b8b1a78d"
      }
    ]
  },
  "schedule": {
    "interval": "2m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "host.name: (pass-emploi-logstash-prod-* OR pass-emploi-logstash-process-prod-*)",
        "language": "kuery"
      },
      "index": {
        "id": "6be9c433-8597-4041-b40c-0e5ee1d69962",
        "title": "metrics-logstash.node-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "metrics-logstash.node-default",
        "allowHidden": false,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 15,
    "timeWindowUnit": "m",
    "threshold": [
      90
    ],
    "thresholdComparator": ">=",
    "size": 100,
    "aggType": "min",
    "groupBy": "top",
    "termSize": 10,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": [],
    "aggField": "logstash.node.stats.jvm.mem.heap_used_percent",
    "termField": "host.name"
  },
  "actions": [
    {
      "group": "query matched",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-production",
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
            "query matched": r'''{
  "text": "🚨 **Heap JVM Logstash prod** — le heap reste au-dessus de 90 % depuis 15 min : le GC ne libère plus, pauses stop-the-world et `OutOfMemoryError` en vue.",
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
          "title": "Nœud",
          "value": "`{{context.group}}`",
          "short": true
        },
        {
          "title": "À vérifier",
          "value": "1. Le heap du nœud redescend-il, et le GC suit-il : le dashboard [[Metrics Logstash] Single Node Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9d450b10-4680-11ee-9ddc-919f87fe352d)\n2. La configuration mémoire : `LS_JAVA_OPTS` de l'app doit valoir `-Xms256m -Xmx256m` (onglet *Environment* dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'effet sur l'ingestion (débit, backlog Redis) : le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Single Node Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9d450b10-4680-11ee-9ddc-919f87fe352d)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-2--gel-gc-jvm)"
        }
      ]
    }
  ]
}''',
        }),
    '5b': dict(
        id='9f9c07f9-07a9-40a3-a882-4a701e81b83c', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 5b — Heap élevé staging / perf (Warning)",
        regle=json.loads(r'''
{
  "name": "Logstash - Hors-Prod - Détection heap JVM élevé",
  "tags": [
    "hors-prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nHeap JVM Logstash staging/perf — le heap reste au-dessus de 90 % depuis 15 min : le GC ne libère plus.\n\n## À vérifier\n\n1. Le heap du nœud redescend-il, et le GC suit-il : le dashboard [[Metrics Logstash] Single Node Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9d450b10-4680-11ee-9ddc-919f87fe352d)\n2. La configuration mémoire : `LS_JAVA_OPTS` de l'app doit valoir `-Xms256m -Xmx256m` (onglet *Environment* dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'effet sur l'ingestion (débit, backlog Redis) : le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n\n## Dashboards\n\n- [[Metrics Logstash] Single Node Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9d450b10-4680-11ee-9ddc-919f87fe352d)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-2--gel-gc-jvm)\n"
    },
    "dashboards": [
      {
        "id": "logstash-9d450b10-4680-11ee-9ddc-919f87fe352d"
      },
      {
        "id": "fd40a516-c323-4e5e-91e5-1328b8b1a78d"
      }
    ]
  },
  "schedule": {
    "interval": "5m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "host.name: (pass-emploi-logstash-staging-* OR pass-emploi-logstash-process-staging-* OR pass-emploi-logstash-perf-* OR pass-emploi-logstash-process-perf-*)",
        "language": "kuery"
      },
      "index": {
        "id": "c48fcb9d-2448-42b5-8430-4e55e64b2750",
        "title": "metrics-logstash.node-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "metrics-logstash.node-default",
        "allowHidden": false,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 15,
    "timeWindowUnit": "m",
    "threshold": [
      90
    ],
    "thresholdComparator": ">=",
    "size": 100,
    "aggType": "min",
    "groupBy": "top",
    "termSize": 10,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": [],
    "aggField": "logstash.node.stats.jvm.mem.heap_used_percent",
    "termField": "host.name"
  },
  "actions": [
    {
      "group": "query matched",
      "id": "c4a313b3-aa42-4e07-8196-c007625ce8af",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-staging",
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
            "query matched": r'''{
  "text": "⚠️ **Heap JVM Logstash staging/perf** — le heap reste au-dessus de 90 % depuis 15 min : le GC ne libère plus.",
  "attachments": [
    {
      "color": "#f2c744",
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
          "title": "Nœud",
          "value": "`{{context.group}}`",
          "short": true
        },
        {
          "title": "À vérifier",
          "value": "1. Le heap du nœud redescend-il, et le GC suit-il : le dashboard [[Metrics Logstash] Single Node Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9d450b10-4680-11ee-9ddc-919f87fe352d)\n2. La configuration mémoire : `LS_JAVA_OPTS` de l'app doit valoir `-Xms256m -Xmx256m` (onglet *Environment* dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. L'effet sur l'ingestion (débit, backlog Redis) : le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Logstash] Single Node Overview](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-9d450b10-4680-11ee-9ddc-919f87fe352d)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-2--gel-gc-jvm)"
        }
      ]
    }
  ]
}''',
        }),
    '7a': dict(
        id='07a8ee68-4994-4d70-b9a5-3d47f08297a5', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 7a — Backlog Redis prod (Critical)",
        regle=json.loads(r'''
{
  "name": "Redis - Prod - Backlog logstash:ingest anormal",
  "tags": [
    "prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nBacklog Redis prod — la liste `logstash:ingest` reste au-dessus de 1 000 événements depuis 15 min. Le pipeline `process` ne consomme plus Redis (redémarrage ou blocage de `pass-emploi-logstash-process-prod`, ou backpressure ES sévère).\n\n## À vérifier\n\n1. Le backlog grossit-il encore : le graphe *Lists length* de `logstash:ingest` dans le dashboard [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n2. Pourquoi le pipeline `process` ne consomme plus : les logs de `pass-emploi-logstash-process-prod` dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps) — `Redis::ConnectionError` ou `ECONNRESET`, coupure Redis ; rien, Elasticsearch ralentit l'écriture\n3. Si Elasticsearch ralentit : les erreurs et la latence de l'output Elasticsearch dans le dashboard [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086), et le pipeline `process` dans le dashboard [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n\n## Dashboards\n\n- [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)\n- [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-5--backlog-redis-logstashingest)\n"
    },
    "dashboards": [
      {
        "id": "redis-28969190-0511-11e9-9c60-d582a238e2c5"
      },
      {
        "id": "logstash-4bbf4a50-6ece-11ee-910d-eb0006359086"
      },
      {
        "id": "logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc"
      }
    ]
  },
  "schedule": {
    "interval": "2m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "redis.key.name: \"logstash:ingest\" and agent.name: pass-emploi-elastic-agent-prod-*",
        "language": "kuery"
      },
      "index": {
        "id": "4b443837-1547-4239-a69a-3e0da528546d",
        "title": "metrics-redis.key-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "metrics-redis.key-default",
        "allowHidden": false,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 15,
    "timeWindowUnit": "m",
    "threshold": [
      1000
    ],
    "thresholdComparator": ">",
    "size": 100,
    "aggType": "min",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": [],
    "aggField": "redis.key.length"
  },
  "actions": [
    {
      "group": "query matched",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "group": "recovered",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
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
          "workflowId": "tchap-o11y-production",
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
            "query matched": r'''{
  "text": "🚨 **Backlog Redis prod** — la liste `logstash:ingest` reste au-dessus de 1 000 événements depuis 15 min. Le pipeline `process` ne consomme plus Redis (redémarrage ou blocage de `pass-emploi-logstash-process-prod`, ou backpressure ES sévère).",
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
          "title": "À vérifier",
          "value": "1. Le backlog grossit-il encore : le graphe *Lists length* de `logstash:ingest` dans le dashboard [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n2. Pourquoi le pipeline `process` ne consomme plus : les logs de `pass-emploi-logstash-process-prod` dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps) — `Redis::ConnectionError` ou `ECONNRESET`, coupure Redis ; rien, Elasticsearch ralentit l'écriture\n3. Si Elasticsearch ralentit : les erreurs et la latence de l'output Elasticsearch dans le dashboard [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086), et le pipeline `process` dans le dashboard [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)\n[[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-5--backlog-redis-logstashingest)"
        }
      ]
    }
  ]
}''',
            "recovered": r'''{
  "text": "✅ **Backlog Redis prod résorbé** — la liste `logstash:ingest` est redescendue sous 1 000 événements. Le pipeline `process` a reconnecté et vide le backlog.",
  "attachments": [
    {
      "color": "#2eb886",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "À vérifier",
          "value": "1. Le backlog grossit-il encore : le graphe *Lists length* de `logstash:ingest` dans le dashboard [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n2. Pourquoi le pipeline `process` ne consomme plus : les logs de `pass-emploi-logstash-process-prod` dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps) — `Redis::ConnectionError` ou `ECONNRESET`, coupure Redis ; rien, Elasticsearch ralentit l'écriture\n3. Si Elasticsearch ralentit : les erreurs et la latence de l'output Elasticsearch dans le dashboard [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086), et le pipeline `process` dans le dashboard [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)\n[[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)"
        }
      ]
    }
  ]
}''',
        }),
    '7b': dict(
        id='720d949a-f73f-43e5-bc46-ff22c7b96cfb', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 7b — Backlog Redis staging / perf (Warning)",
        regle=json.loads(r'''
{
  "name": "Redis - Hors-Prod - Backlog logstash:ingest anormal",
  "tags": [
    "hors-prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nBacklog Redis staging/perf — la liste `logstash:ingest` reste au-dessus de 1 000 événements depuis 15 min. Le pipeline `process` ne consomme plus Redis.\n\n## À vérifier\n\n1. Le backlog grossit-il encore : le graphe *Lists length* de `logstash:ingest` dans le dashboard [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n2. Pourquoi le pipeline `process` ne consomme plus : les logs de `pass-emploi-logstash-process-staging` ou `-perf` dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps) — `Redis::ConnectionError` ou `ECONNRESET`, coupure Redis ; rien, Elasticsearch ralentit l'écriture\n3. Si Elasticsearch ralentit : les erreurs et la latence de l'output Elasticsearch dans le dashboard [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086), et le pipeline `process` dans le dashboard [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n\n## Dashboards\n\n- [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)\n- [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-5--backlog-redis-logstashingest)\n"
    },
    "dashboards": [
      {
        "id": "redis-28969190-0511-11e9-9c60-d582a238e2c5"
      },
      {
        "id": "logstash-4bbf4a50-6ece-11ee-910d-eb0006359086"
      },
      {
        "id": "logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc"
      }
    ]
  },
  "schedule": {
    "interval": "5m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "redis.key.name: \"logstash:ingest\" and agent.name: (pass-emploi-elastic-agent-staging-* or pass-emploi-elastic-agent-perf-*)",
        "language": "kuery"
      },
      "index": {
        "id": "06af5e9b-8030-4f22-a35d-dad32f6ffea1",
        "title": "metrics-redis.key-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "metrics-redis.key-default",
        "allowHidden": false,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 15,
    "timeWindowUnit": "m",
    "threshold": [
      1000
    ],
    "thresholdComparator": ">",
    "size": 100,
    "aggType": "min",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": [],
    "aggField": "redis.key.length"
  },
  "actions": [
    {
      "group": "query matched",
      "id": "c4a313b3-aa42-4e07-8196-c007625ce8af",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-staging",
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
            "query matched": r'''{
  "text": "⚠️ **Backlog Redis staging/perf** — la liste `logstash:ingest` reste au-dessus de 1 000 événements depuis 15 min. Le pipeline `process` ne consomme plus Redis.",
  "attachments": [
    {
      "color": "#f2c744",
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
          "title": "À vérifier",
          "value": "1. Le backlog grossit-il encore : le graphe *Lists length* de `logstash:ingest` dans le dashboard [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n2. Pourquoi le pipeline `process` ne consomme plus : les logs de `pass-emploi-logstash-process-staging` ou `-perf` dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps) — `Redis::ConnectionError` ou `ECONNRESET`, coupure Redis ; rien, Elasticsearch ralentit l'écriture\n3. Si Elasticsearch ralentit : les erreurs et la latence de l'output Elasticsearch dans le dashboard [[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086), et le pipeline `process` dans le dashboard [[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)"
        },
        {
          "title": "Dashboards",
          "value": "[[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Metrics Logstash] Elasticsearch output plugin info](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-4bbf4a50-6ece-11ee-910d-eb0006359086)\n[[Metrics Logstash] Logstash Single Pipeline View](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/logstash-bc1a8050-5ee1-11ee-8e78-bf6865bc3ffc)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-5--backlog-redis-logstashingest)"
        }
      ]
    }
  ]
}''',
        }),
    '8a': dict(
        id='bbb9d642-f012-4747-8154-49162245a364', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 8a — Elastic Agent en défaut prod (Critical)",
        regle=json.loads(r'''
{
  "name": "Elastic Agent - Prod - Agent en défaut",
  "tags": [
    "prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nElastic Agent en défaut — prod — les alertes Logstash/Redis (4, 5, 7) peuvent être aveugles.\n\n## À vérifier\n\n1. Quel agent, et dans quel état : le « Détail » ci-dessus, puis le dashboard [[Elastic Agent] Concerning Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824)\n2. Selon l'état : *offline*, l'app Scalingo de l'agent est arrêtée ou a redémarré (le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)) ; *unenrolled*, l'agent a été recréé sans `ELASTIC_AGENT_ID_SUFFIX` (post-mortem du 11/09) ; *unhealthy* ou erreurs d'output, les composants en erreur dans Fleet → Agents\n3. Les métriques reprennent-elles après correction : le dashboard [[Elastic Agent] Agent metrics](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395)\n\n## Dashboards\n\n- [[Elastic Agent] Concerning Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Elastic Agent] Agent metrics](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395)\n\n## Documentation\n\n- [Fleet → Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/fleet/agents)\n- [Pilotage des agents](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/pilotage.md)\n"
    },
    "dashboards": [
      {
        "id": "elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824"
      },
      {
        "id": "elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395"
      }
    ]
  },
  "schedule": {
    "interval": "1m"
  },
  "params": {
    "searchType": "esqlQuery",
    "esqlQuery": {
      "esql": "FROM logs-elastic_agent.status_change-default, metrics-elastic_agent.*beat-*\n| EVAL host = COALESCE(hostname, agent.name)\n| WHERE host LIKE \"*-prod-*\"\n| WHERE health_status IN (\"offline\", \"unenrolled\", \"unhealthy\")\n     OR beat.stats.libbeat.output.write.errors IS NOT NULL\n| STATS statuts = VALUES(health_status),\n        erreurs = MAX(TO_LONG(beat.stats.libbeat.output.write.errors))\n                - MIN(TO_LONG(beat.stats.libbeat.output.write.errors))\n  BY host, component.id\n| STATS statuts = VALUES(statuts), erreurs_output = MAX(erreurs) BY host\n| WHERE statuts IS NOT NULL OR erreurs_output > 25"
    },
    "timeField": "@timestamp",
    "timeWindowSize": 5,
    "timeWindowUnit": "m",
    "threshold": [
      0
    ],
    "thresholdComparator": ">",
    "size": 100,
    "aggType": "count",
    "groupBy": "row",
    "termSize": 5,
    "sourceFields": [],
    "excludeHitsFromPreviousRun": false
  },
  "actions": [
    {
      "group": "query matched",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-production",
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
            "query matched": r'''{
  "text": "🚨 **Elastic Agent en défaut — prod** — les alertes Logstash/Redis (4, 5, 7) peuvent être aveugles.",
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
          "title": "Détail",
          "value": "{{context.message}}"
        },
        {
          "title": "À vérifier",
          "value": "1. Quel agent, et dans quel état : le « Détail » ci-dessus, puis le dashboard [[Elastic Agent] Concerning Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824)\n2. Selon l'état : *offline*, l'app Scalingo de l'agent est arrêtée ou a redémarré (le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)) ; *unenrolled*, l'agent a été recréé sans `ELASTIC_AGENT_ID_SUFFIX` (post-mortem du 11/09) ; *unhealthy* ou erreurs d'output, les composants en erreur dans Fleet → Agents\n3. Les métriques reprennent-elles après correction : le dashboard [[Elastic Agent] Agent metrics](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395)"
        },
        {
          "title": "Dashboards",
          "value": "[[Elastic Agent] Concerning Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Elastic Agent] Agent metrics](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395)"
        },
        {
          "title": "Fleet",
          "value": "[Fleet → Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/fleet/agents)"
        },
        {
          "title": "Doc",
          "value": "[Pilotage des agents](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/pilotage.md)"
        }
      ]
    }
  ]
}''',
        }),
    '8b': dict(
        id='8d593176-8752-4369-a37f-6b42fa3890b2', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 8b — Elastic Agent en défaut staging (Warning)",
        regle=json.loads(r'''
{
  "name": "Elastic Agent - Staging - Agent en défaut",
  "tags": [
    "hors-prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nElastic Agent en défaut — staging — les alertes Logstash/Redis (4, 5, 7) peuvent être aveugles.\n\n## À vérifier\n\n1. Quel agent, et dans quel état : le « Détail » ci-dessus, puis le dashboard [[Elastic Agent] Concerning Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824)\n2. Selon l'état : *offline*, l'app Scalingo de l'agent est arrêtée ou a redémarré (le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)) ; *unenrolled*, l'agent a été recréé sans `ELASTIC_AGENT_ID_SUFFIX` (post-mortem du 11/09) ; *unhealthy* ou erreurs d'output, les composants en erreur dans Fleet → Agents\n3. Les métriques reprennent-elles après correction : le dashboard [[Elastic Agent] Agent metrics](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395)\n\n## Dashboards\n\n- [[Elastic Agent] Concerning Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n- [[Elastic Agent] Agent metrics](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395)\n\n## Documentation\n\n- [Fleet → Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/fleet/agents)\n- [Pilotage des agents](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/pilotage.md)\n"
    },
    "dashboards": [
      {
        "id": "elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824"
      },
      {
        "id": "elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395"
      }
    ]
  },
  "schedule": {
    "interval": "1m"
  },
  "params": {
    "searchType": "esqlQuery",
    "esqlQuery": {
      "esql": "FROM logs-elastic_agent.status_change-default, metrics-elastic_agent.*beat-*\n| EVAL host = COALESCE(hostname, agent.name)\n| WHERE host LIKE \"*-staging-*\"\n| WHERE health_status IN (\"offline\", \"unenrolled\", \"unhealthy\")\n     OR beat.stats.libbeat.output.write.errors IS NOT NULL\n| STATS statuts = VALUES(health_status),\n        erreurs = MAX(TO_LONG(beat.stats.libbeat.output.write.errors))\n                - MIN(TO_LONG(beat.stats.libbeat.output.write.errors))\n  BY host, component.id\n| STATS statuts = VALUES(statuts), erreurs_output = MAX(erreurs) BY host\n| WHERE statuts IS NOT NULL OR erreurs_output > 25"
    },
    "timeField": "@timestamp",
    "timeWindowSize": 5,
    "timeWindowUnit": "m",
    "threshold": [
      0
    ],
    "thresholdComparator": ">",
    "size": 100,
    "aggType": "count",
    "groupBy": "row",
    "termSize": 5,
    "sourceFields": [],
    "excludeHitsFromPreviousRun": false
  },
  "actions": [
    {
      "group": "query matched",
      "id": "c4a313b3-aa42-4e07-8196-c007625ce8af",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-staging",
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
            "query matched": r'''{
  "text": "⚠️ **Elastic Agent en défaut — staging** — les alertes Logstash/Redis (4, 5, 7) peuvent être aveugles.",
  "attachments": [
    {
      "color": "#f2c744",
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
          "title": "Détail",
          "value": "{{context.message}}"
        },
        {
          "title": "À vérifier",
          "value": "1. Quel agent, et dans quel état : le « Détail » ci-dessus, puis le dashboard [[Elastic Agent] Concerning Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824)\n2. Selon l'état : *offline*, l'app Scalingo de l'agent est arrêtée ou a redémarré (le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)) ; *unenrolled*, l'agent a été recréé sans `ELASTIC_AGENT_ID_SUFFIX` (post-mortem du 11/09) ; *unhealthy* ou erreurs d'output, les composants en erreur dans Fleet → Agents\n3. Les métriques reprennent-elles après correction : le dashboard [[Elastic Agent] Agent metrics](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395)"
        },
        {
          "title": "Dashboards",
          "value": "[[Elastic Agent] Concerning Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-0600ffa0-6b5e-11ed-98de-67bdecd21824)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n[[Elastic Agent] Agent metrics](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/elastic_agent-f47f18cc-9c7d-4278-b2ea-a6dee816d395)"
        },
        {
          "title": "Fleet",
          "value": "[Fleet → Agents](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/fleet/agents)"
        },
        {
          "title": "Doc",
          "value": "[Pilotage des agents](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/pilotage.md)"
        }
      ]
    }
  ]
}''',
        }),
    '9a': dict(
        id='3c65ffd4-165f-4d0b-b820-24be398f19fd', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 9a — Mémoire conteneur prod (Critical)",
        regle=json.loads(r'''
{
  "name": "Logstash - Prod - Mémoire conteneur proche de la limite Scalingo",
  "tags": [
    "prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nMémoire conteneur Logstash prod — un conteneur dépasse 95 % de sa limite Scalingo : OOM-kill et redémarrage imminents.\n\n## À vérifier\n\n1. La mémoire du conteneur continue-t-elle de monter : le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n2. Pourquoi : un backlog Redis à rattraper fait consommer le pipeline `process` (le dashboard [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)) ; `LS_JAVA_OPTS` doit rester `-Xms256m -Xmx256m` (onglet *Environment* dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. Si le conteneur a été tué (OOM) : son redémarrage dans l'activité de l'app, puis le silence des logs qui suit\n\n## Dashboards\n\n- [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n- [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)\n"
    },
    "dashboards": [
      {
        "id": "fd40a516-c323-4e5e-91e5-1328b8b1a78d"
      },
      {
        "id": "redis-28969190-0511-11e9-9c60-d582a238e2c5"
      }
    ]
  },
  "schedule": {
    "interval": "1m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "scalingo.app: (pass-emploi-logstash-prod or pass-emploi-logstash-process-prod)",
        "language": "kuery"
      },
      "index": {
        "id": "5a233d4a-ef9c-4d0b-812d-ddcf52007731",
        "title": "logs-scalingo.container_stats-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "logs-scalingo.container_stats-default",
        "allowHidden": false,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 5,
    "timeWindowUnit": "m",
    "threshold": [
      0.95
    ],
    "thresholdComparator": ">=",
    "size": 100,
    "aggType": "max",
    "groupBy": "top",
    "termSize": 10,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": [],
    "aggField": "scalingo.memory.pct",
    "termField": "host.name"
  },
  "actions": [
    {
      "group": "query matched",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "group": "recovered",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
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
          "workflowId": "tchap-o11y-production",
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
            "query matched": r'''{
  "text": "🚨 **Mémoire conteneur Logstash prod** — un conteneur dépasse 95 % de sa limite Scalingo : OOM-kill et redémarrage imminents.",
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
          "title": "Conteneur",
          "value": "`{{context.group}}`",
          "short": true
        },
        {
          "title": "À vérifier",
          "value": "1. La mémoire du conteneur continue-t-elle de monter : le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n2. Pourquoi : un backlog Redis à rattraper fait consommer le pipeline `process` (le dashboard [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)) ; `LS_JAVA_OPTS` doit rester `-Xms256m -Xmx256m` (onglet *Environment* dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. Si le conteneur a été tué (OOM) : son redémarrage dans l'activité de l'app, puis le silence des logs qui suit"
        },
        {
          "title": "Dashboards",
          "value": "[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n[[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)"
        }
      ]
    }
  ]
}''',
            "recovered": r'''{
  "text": "✅ **Mémoire conteneur Logstash prod** — tous les conteneurs sont repassés sous 95 % de leur limite.",
  "attachments": [
    {
      "color": "#2eb886",
      "fields": [
        {
          "title": "Règle",
          "value": "`{{rule.name}}`",
          "short": true
        },
        {
          "title": "À vérifier",
          "value": "1. La mémoire du conteneur continue-t-elle de monter : le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n2. Pourquoi : un backlog Redis à rattraper fait consommer le pipeline `process` (le dashboard [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)) ; `LS_JAVA_OPTS` doit rester `-Xms256m -Xmx256m` (onglet *Environment* dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. Si le conteneur a été tué (OOM) : son redémarrage dans l'activité de l'app, puis le silence des logs qui suit"
        },
        {
          "title": "Dashboards",
          "value": "[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n[[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)"
        }
      ]
    }
  ]
}''',
        }),
    '9b': dict(
        id='895bd492-e02f-4f18-b8e0-f453742c885f', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 9b — Mémoire conteneur staging / perf (Warning)",
        regle=json.loads(r'''
{
  "name": "Logstash - Hors-Prod - Mémoire conteneur proche de la limite Scalingo",
  "tags": [
    "hors-prod",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nMémoire conteneur Logstash staging/perf — un conteneur dépasse 95 % de sa limite Scalingo : OOM-kill imminent.\n\n## À vérifier\n\n1. La mémoire du conteneur continue-t-elle de monter : le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n2. Pourquoi : un backlog Redis à rattraper fait consommer le pipeline `process` (le dashboard [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)) ; `LS_JAVA_OPTS` doit rester `-Xms256m -Xmx256m` (onglet *Environment* dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. Si le conteneur a été tué (OOM) : son redémarrage dans l'activité de l'app, puis le silence des logs qui suit\n\n## Dashboards\n\n- [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n- [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n- [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)\n\n## Documentation\n\n- [Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)\n"
    },
    "dashboards": [
      {
        "id": "fd40a516-c323-4e5e-91e5-1328b8b1a78d"
      },
      {
        "id": "redis-28969190-0511-11e9-9c60-d582a238e2c5"
      }
    ]
  },
  "schedule": {
    "interval": "5m"
  },
  "params": {
    "searchConfiguration": {
      "query": {
        "query": "scalingo.app: (pass-emploi-logstash-staging or pass-emploi-logstash-process-staging or pass-emploi-logstash-perf or pass-emploi-logstash-process-perf)",
        "language": "kuery"
      },
      "index": {
        "id": "daf0b9b1-2d62-40bd-a508-51e9de307aa5",
        "title": "logs-scalingo.container_stats-default",
        "timeFieldName": "@timestamp",
        "sourceFilters": [],
        "fieldFormats": {},
        "runtimeFieldMap": {},
        "allowNoIndex": false,
        "name": "logs-scalingo.container_stats-default",
        "allowHidden": false,
        "managed": false
      }
    },
    "timeField": "@timestamp",
    "searchType": "searchSource",
    "timeWindowSize": 5,
    "timeWindowUnit": "m",
    "threshold": [
      0.95
    ],
    "thresholdComparator": ">=",
    "size": 100,
    "aggType": "max",
    "groupBy": "top",
    "termSize": 10,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": [],
    "aggField": "scalingo.memory.pct",
    "termField": "host.name"
  },
  "actions": [
    {
      "group": "query matched",
      "id": "c4a313b3-aa42-4e07-8196-c007625ce8af",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onThrottleInterval",
        "throttle": "6h"
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-staging",
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
            "query matched": r'''{
  "text": "⚠️ **Mémoire conteneur Logstash staging/perf** — un conteneur dépasse 95 % de sa limite Scalingo : OOM-kill imminent.",
  "attachments": [
    {
      "color": "#f2c744",
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
          "title": "Conteneur",
          "value": "`{{context.group}}`",
          "short": true
        },
        {
          "title": "À vérifier",
          "value": "1. La mémoire du conteneur continue-t-elle de monter : le dashboard [[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n2. Pourquoi : un backlog Redis à rattraper fait consommer le pipeline `process` (le dashboard [[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)) ; `LS_JAVA_OPTS` doit rester `-Xms256m -Xmx256m` (onglet *Environment* dans le dashboard [[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps))\n3. Si le conteneur a été tué (OOM) : son redémarrage dans l'activité de l'app, puis le silence des logs qui suit"
        },
        {
          "title": "Dashboards",
          "value": "[[Pass Emploi] Supervision Stack d'Observabilité](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/fd40a516-c323-4e5e-91e5-1328b8b1a78d)\n[[Metrics Redis] Keys](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/redis-28969190-0511-11e9-9c60-d582a238e2c5)\n[[Scalingo] Dashboard des apps](https://dashboard.scalingo.com/apps)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook scénario](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-logstash.md#scénario-4--crash-du-conteneur-logstash)"
        }
      ]
    }
  ]
}''',
        }),
    '10': dict(
        id='fb66693b-f17a-4cd0-baf5-113e7e153604', fichier='2-rules-stack-observabilite.console', methode='PUT',
        commentaire="# 10 — ILM en échec ou policy sans suppression (Warning, bilan quotidien)",
        regle=json.loads(r'''
{
  "name": "Elasticsearch - ILM en échec ou policy sans suppression",
  "tags": [
    "elasticsearch",
    "o11y"
  ],
  "artifacts": {
    "investigation_guide": {
      "blob": "## Ce que signale l'alerte\n\nRétention ILM — bilan des 24 h — des index n'appliquent pas leur rétention : étape ILM en échec ou policy par défaut sans suppression.\n\n## À vérifier\n\n1. Quels index n'appliquent pas leur rétention : le Discover [[Pass Emploi] Historique ILM - Index hors rétention](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/3f3c69ef-e515-4be4-b679-eff837c92ecb)\n2. Si l'index porte une policy d'Elastic par défaut (`logs@lifecycle`, `metrics@lifecycle`) : il ne sera jamais supprimé, lui rattacher la policy de l'équipe (runbook ILM)\n3. Si une étape ILM a échoué (`success` à `false`) : lire l'erreur de l'étape, corriger, puis relancer ILM sur l'index (runbook ILM)\n\n## Discover sessions\n\n- [[Pass Emploi] Historique ILM - Index hors rétention](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/3f3c69ef-e515-4be4-b679-eff837c92ecb)\n\n## Documentation\n\n- [Runbook ILM](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-ilm.md)\n"
    }
  },
  "schedule": {
    "interval": "1h"
  },
  "params": {
    "searchType": "esqlQuery",
    "esqlQuery": {
      "esql": "FROM .ds-ilm-history-7-*\n| WHERE index LIKE \"*.ds-logs-*\" OR index LIKE \"*.ds-metrics-*\"\n     OR index LIKE \"*.ds-traces-*\" OR index LIKE \"*.ds-heartbeat-*\"\n| EVAL policy_par_defaut = policy IN (\"logs\", \"metrics\", \"logs@lifecycle\", \"metrics@lifecycle\", \"metricbeat\")\n                           OR policy LIKE \"*-default_policy\"\n| WHERE success == false OR policy_par_defaut\n| STATS index_en_echec = COUNT_DISTINCT(index) WHERE success == false,\n        index_policy_par_defaut = COUNT_DISTINCT(index) WHERE policy_par_defaut,\n        policies = VALUES(policy), exemples = VALUES(index)\n| WHERE index_en_echec > 0 OR index_policy_par_defaut > 0\n| EVAL exemples = MV_SLICE(exemples, 0, 9)"
    },
    "timeField": "@timestamp",
    "timeWindowSize": 24,
    "timeWindowUnit": "h",
    "threshold": [
      0
    ],
    "thresholdComparator": ">",
    "size": 100,
    "aggType": "count",
    "groupBy": "row",
    "termSize": 5,
    "sourceFields": [],
    "excludeHitsFromPreviousRun": false
  },
  "actions": [
    {
      "group": "query matched",
      "id": "d2812573-52bf-4b48-9e54-a79a8b5b227d",
      "params": {
        "body": "@@MESSAGE@@"
      },
      "frequency": {
        "summary": false,
        "notify_when": "onActiveAlert",
        "throttle": null
      },
      "alerts_filter": {
        "timeframe": {
          "days": [
            1,
            2,
            3,
            4,
            5,
            6,
            7
          ],
          "timezone": "Europe/Paris",
          "hours": {
            "start": "09:30",
            "end": "10:30"
          }
        }
      }
    },
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-production",
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
            "query matched": r'''{
  "text": "⚠️ **Rétention ILM — bilan des 24 h** — des index n'appliquent pas leur rétention : étape ILM en échec ou policy par défaut sans suppression.",
  "attachments": [
    {
      "color": "#f2c744",
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
          "title": "Détail",
          "value": "{{context.message}}"
        },
        {
          "title": "À vérifier",
          "value": "1. Quels index n'appliquent pas leur rétention : le Discover [[Pass Emploi] Historique ILM - Index hors rétention](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/3f3c69ef-e515-4be4-b679-eff837c92ecb)\n2. Si l'index porte une policy d'Elastic par défaut (`logs@lifecycle`, `metrics@lifecycle`) : il ne sera jamais supprimé, lui rattacher la policy de l'équipe (runbook ILM)\n3. Si une étape ILM a échoué (`success` à `false`) : lire l'erreur de l'étape, corriger, puis relancer ILM sur l'index (runbook ILM)"
        },
        {
          "title": "Discover sessions",
          "value": "[[Pass Emploi] Historique ILM - Index hors rétention](https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/3f3c69ef-e515-4be4-b679-eff837c92ecb)"
        },
        {
          "title": "Runbook",
          "value": "[Runbook ILM](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-ilm.md)"
        }
      ]
    }
  ]
}''',
        }),
    'expiration-bot': dict(
        id='bcd45d7d-6fe6-4303-a73e-7cff877dde96', fichier='5-rules-tchap-expiration-bot.console', methode='POST',
        commentaire="# La règle filtre sur renouveler_a_partir_du (date passée dès J-60) dans une\n# fenêtre de 2 ans : la fenêtre de temps d'une règle ne regarde que le passé,\n# une date d'expiration future n'y entrerait jamais. Pas\n# d'excludeHitsFromPreviousRun : le rappel est quotidien tant que la date n'est\n# pas mise à jour.",
        regle=json.loads(r'''
{
  "name": "Tchap - Expiration du compte bot",
  "tags": [
    "critical",
    "prod",
    "o11y",
    "tchap",
    "tchap-lignes"
  ],
  "schedule": {
    "interval": "1d"
  },
  "params": {
    "searchType": "esQuery",
    "esQuery": "{\"query\":{\"match_all\":{}}}",
    "index": [
      "tchap-expiration-bot"
    ],
    "timeField": "renouveler_a_partir_du",
    "timeWindowSize": 730,
    "timeWindowUnit": "d",
    "threshold": [
      0
    ],
    "thresholdComparator": ">",
    "size": 1,
    "aggType": "count",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": false,
    "sourceFields": []
  },
  "actions": [
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-o11y-production",
          "summaryMode": true,
          "alertStates": {
            "new": true,
            "ongoing": true,
            "recovered": false
          }
        }
      }
    }
  ],
  "rule_type_id": ".es-query",
  "consumer": "alerts"
}
'''),
        messages={
            "principal": r'''{"text": "🚨 **Compte du bot Tchap bientôt expiré** — sans renouvellement, plus aucune alerte n'arrivera dans Tchap.", "attachments": [{"color": "#d00000", "text": "", "fields": [{"title": "À vérifier", "value": "1. Le lien de renouvellement reçu par email sur la boîte du bot : le cliquer avant la date d'expiration\n2. Une fois le compte renouvelé, la nouvelle date d'expiration dans l'index `tchap-expiration-bot`, comme l'indique le runbook"}, {"title": "Runbook", "value": "[Expiration du compte bot Tchap](https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/runbooks/runbook-tchap-expiration-bot.md)"}]}]}''',
        }),
}
