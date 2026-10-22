# Règles de generated/5-rules-tchap-expiration-bot.console définies au format de Kibana : la règle d'expiration du compte bot Tchap.
# Le corps JSON de chaque règle (regle), et son message à part (messages, un par groupe
# d'action) : il reste disponible pour Tchap quand l'action Mattermost disparaît.
# Les autres règles du fichier sont définies champ par champ dans generer-regles.py.
# Modifier ici, puis : FEATURE_NOTIFIER_ALERTES_MATTERMOST=true python3 -I generer-regles.py
#                     python3 -I ../workflows/tchap/generer-workflows.py
# (cf. README.md)
import json

REGLES_FORMAT_KIBANA = {
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
