#!/usr/bin/env python3
"""Génère les blocs des règles Kibana décrites dans REGLES, au format des fichiers .console.

Usage : python3 -I generer-regles.py [--verifier | --ecrire] <code>…
  sans option : écrit les blocs sur la sortie standard ;
  --verifier : sort en erreur si un bloc diffère de celui de son fichier ;
  --ecrire : remplace le bloc dans son fichier (l'ajoute en fin de fichier s'il est nouveau).
Après toute modification : ../workflows/tchap/generer-workflows.py.
"""
import json, os, re, sys

KD = 'https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/'
KB = 'https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/'
GH = 'https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/'
STACK_APPS = ['pass-emploi-logstash', 'pass-emploi-logstash-process', 'pass-emploi-elastic-agent', 'pass-emploi-heartbeat']
SESSIONS = {
    'evp': ('[Pass Emploi] Alertes externes de Prod - Événements Scalingo', 'bb62451a-d9e9-4141-ab6f-2bda0e384e87'),
    'evh': ('[Pass Emploi] Alertes externes Hors-Prod - Événements Scalingo', '33bed466-9d68-4789-a723-aeea34e6cd93'),
    'cve': ('[Pass Emploi] Alertes externes - CVE Dependabot', 'ece3e409-0679-4bcb-a675-ae7dfb092c19'),
    'rej': ('[Pass Emploi] Alertes externes - Rejets (failure store)', '861dbdf4-5086-498b-aff6-4d9d68ceb1f4'),
    '5xx': ('[Pass Emploi] Logs de Prod - Erreurs serveur 5xx', 'd076df50-1625-443b-978c-1aa9a1288e73'),
    'dlqp': ('[Pass Emploi] Logs de Prod - DLQ Logstash Process', '97e2d85f-7bd2-49df-86b3-2ffc290bbe69'),
    'trp': ('[Pass Emploi] Logs de Prod - Erreurs de traitement Logstash Process', 'f10de9e3-0fdd-4761-9d44-bacc96504e17'),
    'dlqh': ('[Pass Emploi] Logs Hors-Prod - DLQ Logstash Process', 'e5bec6b4-0ae3-47b1-8bb5-2e9bf77493a4'),
    'trh': ('[Pass Emploi] Logs Hors-Prod - Erreurs de traitement Logstash Process', '716175ed-b2a0-4fe1-8f9d-1892d04dbe92'),
    'auth': ("[Pass Emploi] Logs de Prod - Erreurs d'authentification", '1c0dfc0f-0534-4031-81c6-cee0d1c55de8'),
    'part': ('[Pass Emploi] Logs de Prod - Échecs partenaires', 'a28897ac-ecb1-4b4f-b413-0340c7241293'),
    'jobp': ('[Pass Emploi] Logs de Prod - Jobs', 'c0d38bba-66ef-4b68-8a10-4d786f6a9f4a'),
    'jobh': ('[Pass Emploi] Logs Hors-Prod - Jobs', '16da36f4-a88e-4c01-b34f-e361a5292740'),
}
DASHBOARDS = {
    'entree': ("[Pass Emploi] Diagnostic d'erreurs - Entrée", KB + 'eb348ed9-3bc2-4204-a5c2-c31465731c74', 'eb348ed9-3bc2-4204-a5c2-c31465731c74'),
    'apps': ("[Pass Emploi] Diagnostic d'erreurs - Apps", KB + '014dae91-507a-44de-b782-72e5eddbab74', '014dae91-507a-44de-b782-72e5eddbab74'),
    'stack': ("[Pass Emploi] Supervision Stack d'Observabilité", KB + 'fd40a516-c323-4e5e-91e5-1328b8b1a78d', 'fd40a516-c323-4e5e-91e5-1328b8b1a78d'),
    'scalingo': ('[Scalingo] Dashboard des apps', 'https://dashboard.scalingo.com/apps', None),
    'dep-api': ('[GitHub] Alertes Dependabot - pass-emploi-api', 'https://github.com/France-Travail/pass-emploi-api/security/dependabot', None),
    'dep-web': ('[GitHub] Alertes Dependabot - pass-emploi-web', 'https://github.com/France-Travail/pass-emploi-web/security/dependabot', None),
    'dep-connect': ('[GitHub] Alertes Dependabot - pass-emploi-connect', 'https://github.com/France-Travail/pass-emploi-connect/security/dependabot', None),
}
DV = {
    'prod': {'id': 'd327d85c-91ea-4092-867f-08a940504c96', 'title': 'logs-alertes-scalingo-prod-default', 'name': 'Alertes Scalingo - Prod', 'allowHidden': False},
    'hors-prod': {'id': 'a67a2388-a6a3-42e3-b1c4-15dc61bf5585', 'title': 'logs-alertes-scalingo-staging-default,logs-alertes-scalingo-perf-default', 'name': 'Alertes Scalingo - Hors-Prod', 'allowHidden': False},
    'logs-prod': {'id': '0208fbaf-2541-4ba2-b405-af62cebd9de7', 'title': 'logs-prod-default,logs-router-prod-default', 'name': 'Logs apps prod', 'allowHidden': False},
    'logs-hors-prod': {'id': '9ef69e58-9ad1-43e4-87e1-cf1a68e38c09', 'title': 'logs-staging-default,logs-perf-default', 'name': 'Logs apps hors prod', 'allowHidden': False},
    'github': {'id': '8a589b67-53bc-407d-9d76-c68b41271bbe', 'title': 'logs-alertes-github-default', 'name': 'Alertes GitHub - CVE', 'allowHidden': False},
    'rejets': {'id': '0f25bbf6-abdf-41f9-8bab-4a4911c13ebc', 'title': 'logs-alertes-scalingo-prod-default::failures,logs-alertes-scalingo-staging-default::failures,logs-alertes-scalingo-perf-default::failures,logs-alertes-github-default::failures', 'name': 'Alertes externes - rejets (failure store)', 'allowHidden': True},
}
def s(k): return f'[{SESSIONS[k][0]}]({KD}{SESSIONS[k][1]})'
def d(k): return f'[{DASHBOARDS[k][0]}]({DASHBOARDS[k][1]})'
STACK_KQL = 'service.name : (' + ' or '.join(f'"{a}"' for a in STACK_APPS) + ')'
SCALINGO_LIGNES = '{{#context.hits}}{{_source.message}}\\n{{/context.hits}}'
DOC_COLLECTE = f'[Collecte des événements externes]({GH}collecte/evenements-externes/README.md)'

JOBS_KQL = 'service.name : "pass-emploi-api" and event.action : ("job_crashed" or "job_handler_not_found")'
JOBS_LIGNES = '{{#context.hits}}❌ `{{_source.labels.job_type}}` : {{_source.event.action}} — {{_source.error.message}}\\n{{/context.hits}}'

RUNBOOK_APPLICATIF = ('Runbook', [f'[Investiguer un incident applicatif]({GH}runbooks/investigation-incident.md)'])

REGLES = {
    'A3': dict(id='ad326ad3-aea7-4ef8-be28-31008c4aebce', commentaire='# A3 — Pic d\'authentifications refusées (Critical)',
        name="API - Prod - Pic d'auth refusées", tags=['prod', 'applicatif'], interval='5m', fenetre=8, unite='d',
        esql='FROM logs-prod-default\n| WHERE event.action == "auth_failed"\n| EVAL recent = @timestamp >= NOW() - 10 minutes,\n       meme_heure = @timestamp < NOW() - 1 day\n                AND DATE_EXTRACT("HOUR_OF_DAY", @timestamp) == DATE_EXTRACT("HOUR_OF_DAY", NOW())\n| STATS refus = COUNT(*) WHERE recent, historique = COUNT(*) WHERE meme_heure\n| EVAL reference = ROUND(historique / 42.0, 1)\n| WHERE refus >= 20 AND refus > 3 * reference',
        mm='12e46700-6e45-11ec-9757-c9700cd1bb4e', couleur='#d00000', emoji='🚨',
        titre="Pic d'authentifications refusées — prod", suite='plus de 3 × la normale sur 10 min : IDP ou Keycloak probablement en cause.',
        lignes='{{#context.hits}}{{_source.refus}} refus en 10 min, contre {{_source.reference}} d\'habitude à cette heure\\n{{/context.hits}}',
        tchap="{0} refus en 10 min, contre {2} d'habitude à cette heure",
        intro="Pic d'authentifications refusées — prod — plus de 3 × la normale sur 10 min : IDP ou Keycloak probablement en cause.",
        steps=[f"1. Quel mode de connexion est touché, et pourquoi : le Discover {s('auth')}, onglet *Field statistics* (répartition par fournisseur d'identité et par motif)",
               f"2. Si un seul fournisseur d'identité concentre les refus (France Travail Connect, Milo…) : sa disponibilité dans le dashboard {d('entree')}",
               f"3. Si tous les modes sont touchés : Keycloak ou pass-emploi-connect, dans le dashboard {d('apps')}"],
        sessions=['auth'], dashboards=['entree', 'apps'], extra=[RUNBOOK_APPLICATIF],
        doc=('Alertes applicatives', 'supervision/alertes-applicatives.md')),
    'A5a': dict(id='a03feacb-ddf8-4e04-af82-48f77b07a86e', commentaire="# A5a — Jobs en échec, prod (version dégradée : un job qui plante ou introuvable ; un job\n# qui rapporte un échec sans planter n'est pas vu, cf. ../alertes-applicatives.md)",
        name='API - Prod - Jobs en échec', tags=['prod', 'applicatif', 'jobs'],
        dv='logs-prod', kql=JOBS_KQL, interval='1m', fenetre=5, mm='cd0b8285-1b69-4e3a-9c7c-6d35b42e7115', couleur='#808080', emoji='',
        titre='Jobs en échec — prod', workflow='tchap-jobs-production', lignes=JOBS_LIGNES,
        intro="Un job de l'api de prod a planté (`job_crashed`) ou n'a pas de handler (`job_handler_not_found`).",
        steps=[f"1. Le Discover {s('jobp')}, onglet « Jobs en échec » : le job, son erreur et sa stack",
               f"2. L'onglet « Exécutions » de {s('jobp')} : le job échoue-t-il à chaque exécution, ou a-t-il réussi depuis ?"],
        sessions=['jobp'], dashboards=[], doc=('Alertes applicatives', 'supervision/alertes-applicatives.md')),
    'A5b': dict(id='9dbcb316-60cd-481e-8717-33ffe0275e7d', commentaire="# A5b — Jobs en échec, staging / perf (même version dégradée que A5a)",
        name='API - Hors-Prod - Jobs en échec', tags=['hors-prod', 'applicatif', 'jobs'],
        dv='logs-hors-prod', kql=JOBS_KQL, interval='5m', fenetre=10, mm='3f71e705-99b5-4b37-ab14-932e28bc29b4', couleur='#808080', emoji='',
        titre='Jobs en échec — hors prod', workflow='tchap-jobs-staging', lignes=JOBS_LIGNES.replace('` :', '` ({{_source.service.environment}}) :'),
        intro="Un job de l'api de staging ou de perf a planté (`job_crashed`) ou n'a pas de handler (`job_handler_not_found`).",
        steps=[f"1. Le Discover {s('jobh')}, onglet « Jobs en échec » : le job, son environnement, son erreur et sa stack",
               f"2. L'onglet « Exécutions » de {s('jobh')} : le job échoue-t-il à chaque exécution, ou a-t-il réussi depuis ?"],
        sessions=['jobh'], dashboards=[], doc=('Alertes applicatives', 'supervision/alertes-applicatives.md')),
    'A4a': dict(id='1b97f0e0-870f-498d-8dd7-1c2f9aeba665', commentaire='# A4a — Événements Scalingo des apps applicatives, prod (gravité par ligne)',
        name='Scalingo - Prod - Événements des apps applicatives', tags=['prod', 'applicatif', 'scalingo', 'tchap-lignes'],
        dv='prod', kql='not ' + STACK_KQL, interval='1m', fenetre=5, mm='12e46700-6e45-11ec-9757-c9700cd1bb4e', couleur='#808080', emoji='',
        titre='Événements Scalingo des apps de prod', workflow='tchap-monitoring-production', lignes=SCALINGO_LIGNES,
        intro="Un événement Scalingo sur une app applicative de prod : incident (🚨 crash, redémarrage ou arrêt ; ⚠️ seuil dépassé) ou opération d'infra (ℹ️ déploiement, variable, scaling…).",
        steps=[f"1. Le Discover {s('evp')}, onglet « Incidents » ou « Infra » : l'événement, sa raison et son auteur",
               f"2. Pour un incident, l'impact sur les utilisateurs : le dashboard {d('entree')}, puis le Discover {s('5xx')}",
               f"3. L'activité de l'app (onglet Activity) dans le dashboard {d('scalingo')}"],
        sessions=['evp', '5xx'], dashboards=['entree', 'scalingo'], doc=('Collecte des événements externes', 'collecte/evenements-externes/README.md')),
    'A4b': dict(id='07c9c5d7-e8fe-4964-ac8d-684b1c4c39b8', commentaire='# A4b — Événements Scalingo des apps applicatives, staging / perf (gravité par ligne)',
        name='Scalingo - Hors-Prod - Événements des apps applicatives', tags=['hors-prod', 'applicatif', 'scalingo', 'tchap-lignes'],
        dv='hors-prod', kql='not ' + STACK_KQL, interval='5m', fenetre=10, mm='4cb10f00-22d9-4cf0-bda1-e288c4abb339', couleur='#808080', emoji='',
        titre='Événements Scalingo des apps hors prod', workflow='tchap-monitoring-staging', lignes=SCALINGO_LIGNES,
        intro="Un événement Scalingo sur une app applicative de staging ou de perf : incident ou opération d'infra.",
        steps=[f"1. Le Discover {s('evh')}, onglet « Incidents » ou « Infra » : l'événement, sa raison et son auteur",
               f"2. L'activité de l'app (onglet Activity) dans le dashboard {d('scalingo')}"],
        sessions=['evh'], dashboards=['scalingo'], doc=('Collecte des événements externes', 'collecte/evenements-externes/README.md')),
    '6a': dict(id='c16f2ab5-6103-4f69-bdc3-b4a10a38deb0', commentaire='# 6a — Événements Scalingo des apps de la stack, prod (gravité par ligne)',
        name='Scalingo - Prod - Événements des apps de la stack', tags=['prod', 'o11y', 'scalingo', 'tchap-lignes'],
        dv='prod', kql=STACK_KQL, interval='1m', fenetre=5, mm='d2812573-52bf-4b48-9e54-a79a8b5b227d', couleur='#808080', emoji='',
        titre='Événements Scalingo des apps de la stack, prod', workflow='tchap-o11y-production', lignes=SCALINGO_LIGNES,
        intro="Un événement Scalingo sur une app de la stack d'observabilité de prod (Logstash, Elastic Agent, Heartbeat) : incident ou opération d'infra.",
        steps=[f"1. Le Discover {s('evp')}, onglet « Incidents » ou « Infra » : l'événement, sa raison et son auteur",
               f"2. Pour un incident sur une app Logstash, l'impact sur l'ingestion : le dashboard {d('stack')}, puis les Discover {s('dlqp')} et {s('trp')} (logs non indexés)",
               f"3. Les métriques (onglet Metrics) et l'activité (onglet Activity) de l'app dans le dashboard {d('scalingo')}"],
        sessions=['evp', 'dlqp', 'trp'], dashboards=['stack', 'scalingo'], doc=("Alertes de la stack d'observabilité", 'supervision/alertes-stack-observabilite.md')),
    '6b': dict(id='5d1f7c2a-9b3e-4f6a-8c1d-2e7b4a9f0c63', commentaire='# 6b — Événements Scalingo des apps de la stack, staging / perf (gravité par ligne)\n# Nouvelle règle : absente de la prod avant le 2026-10-19, la créer avec POST\n# (même corps plus "rule_type_id": ".es-query" et "consumer": "alerts").',
        name='Scalingo - Hors-Prod - Événements des apps de la stack', tags=['hors-prod', 'o11y', 'scalingo', 'tchap-lignes'],
        dv='hors-prod', kql=STACK_KQL, interval='5m', fenetre=10, mm='c4a313b3-aa42-4e07-8196-c007625ce8af', couleur='#808080', emoji='',
        titre='Événements Scalingo des apps de la stack, hors prod', workflow='tchap-o11y-staging', lignes=SCALINGO_LIGNES,
        intro="Un événement Scalingo sur une app de la stack d'observabilité de staging ou de perf : incident ou opération d'infra.",
        steps=[f"1. Le Discover {s('evh')}, onglet « Incidents » ou « Infra » : l'événement, sa raison et son auteur",
               f"2. Pour un incident sur une app Logstash, l'impact sur l'ingestion : le dashboard {d('stack')}, puis les Discover {s('dlqh')} et {s('trh')} (logs non indexés)",
               f"3. Les métriques (onglet Metrics) et l'activité (onglet Activity) de l'app dans le dashboard {d('scalingo')}"],
        sessions=['evh', 'dlqh', 'trh'], dashboards=['stack', 'scalingo'], doc=("Alertes de la stack d'observabilité", 'supervision/alertes-stack-observabilite.md')),
    '14': dict(id='ae398f47-0ed9-427e-a090-cf774acc7d16', commentaire="# 14 — Événement externe rejeté par son pipeline ou par Elasticsearch (Warning). L'émetteur\n# reçoit 201 même quand le document part au failure store.",
        name='Événements externes - Payload rejeté (failure store)', tags=['warning', 'prod', 'o11y'],
        dv='rejets', kql='', interval='5m', fenetre=10, mm='d2812573-52bf-4b48-9e54-a79a8b5b227d', couleur='#ffa500',
        titre="Événements externes rejetés — des notifications Scalingo ou GitHub ne sont pas arrivées dans Kibana : leur émetteur a pourtant reçu un succès", workflow='tchap-o11y-production',
        lignes='{{#context.hits}}• `{{_source.error.type}}` : {{_source.error.message}}\\n{{/context.hits}}',
        intro="Une notification Scalingo ou GitHub a été rejetée par son ingest pipeline et rangée dans le failure store : l'alerte qu'elle portait n'a pas été levée.",
        steps=[f"1. Le Discover {s('rej')} : `error.type` et `error.message` donnent le motif du rejet",
               "2. Le payload d'origine (`document.source`) : adapter le pipeline, puis le rejouer en `_simulate`"],
        sessions=['rej'], dashboards=[], doc=('Collecte des événements externes', 'collecte/evenements-externes/README.md')),
    'V1': dict(id='67846c2c-45d1-45be-89f5-ce9a340240a0', commentaire='# V1 — CVE high/critical encore ouvertes, à chaque passage de security-alerts.yml (Critical)',
        name='GitHub - CVE high ou critical ouverte', tags=['critical', 'prod', 'securite', 'tchap-lignes'],
        dv='github', kql='vulnerability.severity : ("high" or "critical")', interval='5m', fenetre=10, mm='12e46700-6e45-11ec-9757-c9700cd1bb4e', couleur='#d00000',
        titre='CVE high/critical ouvertes', workflow='tchap-monitoring-production', emoji='🚨',
        lignes='{{#context.hits}}• [{{_source.service.name}}]({{_source.labels.dependabot_url}}) : **{{_source.vulnerability.id}}** — {{_source.package.name}} ({{_source.vulnerability.severity}}) : {{_source.vulnerability.description}} — [Voir]({{_source.vulnerability.reference}})\\n{{/context.hits}}',
        intro='Une CVE high ou critical est encore ouverte sur un repo (alertes Dependabot envoyées par `security-alerts.yml`).',
        steps=[f"1. Le Discover {s('cve')}, liste les CVE ouvertes par repo avec leur score",
               f"2. Les alertes Dependabot du repo concerné, à traiter selon leur sévérité : {d('dep-api')}, {d('dep-web')}, {d('dep-connect')}"],
        steps_message=[f"1. Le Discover {s('cve')}, liste les CVE ouvertes par repo avec leur score",
               "2. Les alertes Dependabot du repo concerné (lien sur le nom du repo de chaque CVE), à traiter selon leur sévérité"],
        dashboards_message=[],
        sessions=['cve'], dashboards=['dep-api', 'dep-web', 'dep-connect'], doc=('Alertes de sécurité', 'supervision/alertes-securite.md')),
}

def coherence(r):
    verifier(r['steps'], r['sessions'], r['dashboards'], r['name'])
    verifier(r.get('steps_message', r['steps']), r['sessions'], r.get('dashboards_message', r['dashboards']), r['name'])

def verifier(steps, sessions, dashboards, nom):
    r = {'steps': steps, 'sessions': sessions, 'dashboards': dashboards, 'name': nom}
    texte = '\n'.join(r['steps'])
    cites_s = set(re.findall(r'discover#/view/([0-9a-f-]+)', texte))
    cites_d = set(re.findall(r'\]\((https://[^)]+)\)', texte)) & {v[1] for v in DASHBOARDS.values()}
    assert cites_s == {SESSIONS[k][1] for k in r['sessions']}, r['name']
    assert cites_d == {DASHBOARDS[k][1] for k in r['dashboards']}, r['name']
    assert len(r['steps']) <= 3, r['name']

def valeur_multiligne(lignes, pad):
    return ('\\n{{!\n' + ' ' * pad + '}}').join(json.dumps(l, ensure_ascii=False)[1:-1] for l in lignes)

def body(r):
    pad = len('          "value": "') - 2
    def champ(titre, valeurs, short=False):
        v = valeur_multiligne(valeurs, pad)
        out = '        {\n          "title": ' + json.dumps(titre, ensure_ascii=False) + ',\n          "value": "' + v + '"'
        return out + (',\n          "short": true\n        }' if short else '\n        }')
    champs = [champ('Règle', ['`{{rule.name}}`'], True), champ('Déclenchée à', ['`{{date}}`'], True), champ('À vérifier', r.get('steps_message', r['steps']))]
    dash = [d(k) for k in r.get('dashboards_message', r['dashboards'])]
    if dash:
        champs.append(champ('Dashboards', dash))
    champs.append(champ('Discover sessions', [s(k) for k in r['sessions']]))
    for titre, valeurs in r.get('extra', []):
        champs.append(champ(titre, valeurs))
    emoji = r.get('emoji', '⚠️')
    prefixe = emoji + ' ' if emoji else ''
    compte = '' if 'esql' in r else ' ({{context.value}})'
    suite = ' — ' + r['suite'] if r.get('suite') else ''
    return ('{\n  "text": ' + json.dumps(f"{prefixe}**{r['titre']}**{compte}{suite}", ensure_ascii=False) + ',\n'
            '  "attachments": [\n    {\n      "color": "' + r['couleur'] + '",\n'
            '      "text": "' + r['lignes'] + '",\n      "fields": [\n' + ',\n'.join(champs) + '\n      ]\n    }\n  ]\n}')

def guide(r):
    dash = [d(k) for k in r['dashboards']]
    md = "## Ce que signale l'alerte\n\n" + r['intro'] + "\n\n## À vérifier\n\n" + '\n'.join(r['steps'])
    if dash:
        md += "\n\n## Dashboards\n\n" + '\n'.join('- ' + x for x in dash)
    md += "\n\n## Discover sessions\n\n" + '\n'.join('- ' + s(k) for k in r['sessions'])
    md += f"\n\n## Documentation\n\n[{r['doc'][0]}]({GH}{r['doc'][1]})\n"
    return md

def bloc(nom):
    r = REGLES[nom]
    coherence(r)
    artifacts = {'investigation_guide': {'blob': guide(r)}}
    ids = [DASHBOARDS[k][2] for k in r['dashboards'] if DASHBOARDS[k][2]]
    if ids:
        artifacts['dashboards'] = [{'id': i} for i in ids]
    if 'esql' in r:
        return bloc_esql(nom, r, artifacts)
    dv = DV[r['dv']]
    regle = {
        'name': r['name'], 'tags': r['tags'], 'artifacts': artifacts, 'schedule': {'interval': r['interval']},
        'params': {
            'searchConfiguration': {'query': {'query': r['kql'], 'language': 'kuery'},
                'index': {'id': dv['id'], 'title': dv['title'], 'timeFieldName': '@timestamp', 'sourceFilters': [], 'fieldFormats': {}, 'runtimeFieldMap': {}, 'allowNoIndex': False, 'name': dv['name'], 'allowHidden': dv['allowHidden'], 'managed': False}},
            'timeField': '@timestamp', 'searchType': 'searchSource', 'timeWindowSize': r['fenetre'], 'timeWindowUnit': 'm',
            'threshold': [0], 'thresholdComparator': '>', 'size': 20, 'aggType': 'count', 'groupBy': 'all', 'termSize': 5,
            'excludeHitsFromPreviousRun': True, 'sourceFields': []},
        'actions': [
            {'group': 'query matched', 'id': r['mm'], 'params': {'body': '@@BODY@@'}, 'frequency': {'summary': False, 'notify_when': 'onActiveAlert', 'throttle': None}},
            {'id': 'system-connector-.workflows', 'params': {'subAction': 'run', 'subActionParams': {'workflowId': r['workflow'], 'summaryMode': True, 'alertStates': {'new': True, 'ongoing': True, 'recovered': False}}}}],
    }
    if not r['workflow']:
        regle['actions'] = regle['actions'][:1]
    texte = json.dumps(regle, ensure_ascii=False, indent=2).replace('"@@BODY@@"', '"""' + body(r) + '"""')
    return r['commentaire'] + '\nPUT kbn:/api/alerting/rule/' + r['id'] + '\n' + texte + '\n'

def bloc_esql(nom, r, artifacts):
    """Une seule alerte par règle (groupBy all) : son identité reste stable pendant un incident,
    le throttle Mattermost et le message Tchap à l'apparition s'appliquent. Le Workflow
    tchap-alerte-<code en minuscules> relance la requête, ses lignes n'étant pas transmises par l'action."""
    regle = {
        'name': r['name'], 'tags': r['tags'], 'artifacts': artifacts, 'schedule': {'interval': r['interval']},
        'params': {
            'searchType': 'esqlQuery', 'esqlQuery': {'esql': '@@ESQL@@'}, 'timeField': '@timestamp',
            'timeWindowSize': r['fenetre'], 'timeWindowUnit': r.get('unite', 'm'),
            'threshold': [0], 'thresholdComparator': '>', 'size': 100, 'groupBy': 'all'},
        'actions': [
            {'group': 'query matched', 'id': r['mm'], 'params': {'body': '@@BODY@@'}, 'frequency': {'summary': False, 'notify_when': 'onThrottleInterval', 'throttle': '1h'}},
            {'id': 'system-connector-.workflows', 'params': {'subAction': 'run', 'subActionParams': {'workflowId': 'tchap-alerte-' + nom.lower(), 'summaryMode': True, 'alertStates': {'new': True, 'ongoing': False, 'recovered': False}}}}],
    }
    texte = json.dumps(regle, ensure_ascii=False, indent=2).replace('"@@BODY@@"', '"""' + body(r) + '"""')
    texte = texte.replace('"@@ESQL@@"', '"""' + r['esql'] + '"""')
    return r['commentaire'] + '\nPUT kbn:/api/alerting/rule/' + r['id'] + '\n' + texte + '\n'


ICI = os.path.dirname(os.path.abspath(__file__))
FICHIERS = {'1-rules-applicatives.console': ('A',), '2-rules-stack-observabilite.console': ('6', '14'), '3-rules-securite.console': ('V',)}


def fichier(nom):
    return os.path.join(ICI, next(f for f, p in FICHIERS.items() if nom.startswith(p)))


def emplacement(lignes, nom):
    """Lignes [début, fin] du bloc : de sa première ligne de commentaire à l'accolade fermante."""
    premiere = REGLES[nom]['commentaire'].split('\n')[0]
    debut = lignes.index(premiere) if premiere in lignes else None
    if debut is None:
        return None
    put = next(i for i in range(debut, len(lignes)) if lignes[i].startswith('PUT kbn:/api/alerting/rule/'))
    return debut, lignes.index('}', put)


def main(args):
    mode = args[0] if args and args[0] in ('--verifier', '--ecrire') else None
    codes = args[1:] if mode else args
    ecarts = 0
    for nom in codes:
        genere = bloc(nom).rstrip('\n').split('\n')
        if not mode:
            print('\n'.join(genere) + '\n')
            continue
        chemin = fichier(nom)
        lignes = open(chemin).read().split('\n')
        place = emplacement(lignes, nom)
        actuel = lignes[place[0]:place[1] + 1] if place else None
        if mode == '--verifier':
            if actuel != genere:
                ecarts += 1
                print(f'{nom} : diffère de {os.path.basename(chemin)}' if actuel else f'{nom} : absent de {os.path.basename(chemin)}')
            continue
        if place:
            lignes[place[0]:place[1] + 1] = genere
        else:
            while lignes and lignes[-1] == '':
                lignes.pop()
            lignes += [''] + genere + ['']
        open(chemin, 'w').write('\n'.join(lignes))
        print(f'{nom} : écrit dans {os.path.basename(chemin)}')
    if mode == '--verifier':
        print('identiques' if not ecarts else f'{ecarts} bloc(s) différent(s)')
    sys.exit(1 if ecarts else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
