#!/usr/bin/env python3
"""Génère les Workflows de salon tchap-<salon>.console depuis les règles de ../../rules/.

Chaque règle qui a une action .workflows reçoit, dans le Workflow de son salon, le
contenu de son message Mattermost (titre, couleur, champs), traduit en Liquid.

Usage : python3 -I generer-workflows.py
"""
import html, json, os, re

ICI = os.path.dirname(os.path.abspath(__file__))
REGLES = os.path.join(ICI, '..', '..', 'rules')
SALONS = {
    'monitoring-production': '!wYxfADtvOcuPbjTOBU:agent.dinum.tchap.gouv.fr',
    'monitoring-staging': '!ZfOFaCZYUWPLIxrYsx:agent.dinum.tchap.gouv.fr',
    'o11y-production': '!GcUrxqTFizBjxwmsBO:agent.dinum.tchap.gouv.fr',
    'o11y-staging': '!EGmOEFBsJoXIngQOvU:agent.dinum.tchap.gouv.fr',
    'jobs-production': '!vZkZkmTRLjAJTdkonL:agent.dinum.tchap.gouv.fr',
    'jobs-staging': '!SmJcAqcZyoguQAJTho:agent.dinum.tchap.gouv.fr',
}
ALERTE = 'foreach.item.kibana.alert'
# Le pare-feu de Tchap rejette un message qui contient un « = » et un lien https.
EGAL = " | replace: '=', '＝'"
DETAIL_ESQL = ('{% for g in ' + ALERTE + '.grouping %}{% unless g[0] == "labels" %}'
               '{{ g[0] | replace: "_", " " }} : {{ g[1]' + EGAL + 'ECHAP }}SEP{% endunless %}{% endfor %}')
VARIABLES = {
    'rule.name': '{{ event.rule.name' + EGAL + 'ECHAP }}',
    'date': '{{ ' + ALERTE + '.start }}',
    'context.value': '{{ ' + ALERTE + '.evaluation.value }}',
    'context.reason': '{{ ' + ALERTE + '.reason' + EGAL + 'ECHAP }}',
    'context.group': '{{ ' + ALERTE + '.instance.id' + EGAL + 'ECHAP }}',
    'context.sloName': '{{ event.rule.name' + EGAL + 'ECHAP }}',
    'context.sloInstanceId': '{{ ' + ALERTE + '.instance.id' + EGAL + 'ECHAP }}',
    'context.viewInAppUrl': 'https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/slos/{{ foreach.item.slo.id }}',
    'context.longWindow.burnRate': "{{ lb | append: '' | replace: '.', ',' }}",
    'context.longWindow.duration': "{{ ld | replace: 'h', ' h' | replace: 'm', ' min' }}",
    'context.shortWindow.burnRate': "{{ sb | append: '' | replace: '.', ',' }}",
    'context.shortWindow.duration': "{{ sd | replace: 'h', ' h' | replace: 'm', ' min' }}",
    'context.burnRateThreshold': '{{ seuil }}',
}
# Absents du document d'alerte d'un SLO : la raison de Kibana les contient, toujours au
# format « …: The burn rate for the past 1h is 18.5 and for the past 5m is 21.3 for …
# Alert when above 14.4 for both windows ».
BURN_RATE = ("{% assign r = " + ALERTE + ".reason | split: ' is ' %}{% assign ld = r[0] | split: ' ' | last %}"
             "{% assign lb = r[1] | split: ' ' | first | plus: 0 %}{% assign sd = r[1] | split: ' ' | last %}"
             "{% assign sb = r[2] | split: ' ' | first | plus: 0 %}{% assign s = " + ALERTE + ".reason | split: 'above ' %}"
             "{% assign seuil = s[1] | split: ' ' | first %}")
# Résumé d'un certificat (règle TLS), toujours en anglais : « expires on Nov 14, 2026  in 25 days. ».
TLS_RESUME = ("{% assign etat = " + ALERTE + ".state %}{% if etat.status == 'expiring' %}{% assign morceaux = etat.summary | remove_first: 'expires on ' | split: ' in ' %}"
              "expire le {{ morceaux[0] | strip | date: '%d/%m/%Y' }}, dans {{ morceaux[1] | remove: 'days.' | remove: 'day.' | strip }} jours"
              "{% else %}{{ etat.summary" + EGAL + "ECHAP }}{% endif %}")
JOURS = r'\{\{#EvalMath\}\}\s*round\(30 / \{\{context\.longWindow\.burnRate\}\}, 1\)\s*\{\{/EvalMath\}\}'
VIA_RAISON = set()


def requetes(texte):
    lignes, i = texte.splitlines(), 0
    while i < len(lignes):
        m = re.match(r'^(PUT|POST) (kbn:/api/alerting/rule/\S+)\s*$', lignes[i])
        i += 1
        if not m or i >= len(lignes) or lignes[i] != '{':
            continue
        debut = i
        while lignes[i] != '}':
            i += 1
        i += 1
        brut = '\n'.join(lignes[debut:i])
        yield m.group(2).rsplit('/', 1)[1], json.loads(re.sub(r'"""(.*?)"""', lambda x: json.dumps(x.group(1)), brut, flags=re.S))


def liquide(modele, en_html):
    """Mustache du message Mattermost → Liquid ; le texte fixe est échappé en HTML."""
    modele = re.sub(r'\{\{#context\.hits\}\}.*?\{\{/context\.hits\}\}', '', modele, flags=re.S)
    modele = re.sub(JOURS, '@@JOURS@@', modele)
    morceaux = re.split(r'(\{\{\s*[^}]+?\s*\}\})', modele)
    sortie = []
    for m in morceaux:
        v = re.fullmatch(r'\{\{\s*([^}]+?)\s*\}\}', m)
        if not v:
            fixe = m.replace('=', '＝')
            sortie.append(html.escape(fixe, quote=False) if en_html else fixe)
        elif v.group(1) in VARIABLES:
            sortie.append(VARIABLES[v.group(1)].replace('ECHAP', ' | escape' if en_html else ''))
        elif v.group(1) == 'state.summary':
            sortie.append(TLS_RESUME.replace('ECHAP', ' | escape' if en_html else ''))
        elif v.group(1).startswith('state.'):
            sortie.append('{{ ' + ALERTE + '.' + v.group(1) + EGAL + (' | escape' if en_html else '') + ' }}')
        elif v.group(1) == 'context.message':
            sortie.append('@@DETAIL@@')
        elif v.group(1) in VIA_RAISON:
            sortie.append('@@RAISON@@')
        else:
            raise ValueError('variable Mustache non traduite : ' + v.group(1))
    return ''.join(sortie)


LIEN = r'\[([^\]]*(?:\[[^\]]*\][^\]]*)?)\]\(((?:https?://|\{\{)(?:[^)\s{]|\{\{[^}]*\}\})*)\)'


# Les dashboards et sessions Kibana s'ouvrent sur la fenêtre de la règle (1 h au moins,
# 7 jours au plus) avant le début de l'alerte, jusqu'à 15 min après. Période encodée :
# la détection des liens de Tchap exclut la parenthèse finale d'une URL.
PERIODE = "?_g=%28time%3A%28from%3A%27{{ t0 }}%27%2Cto%3A%27{{ t1 }}%27%29%29"
UNITES = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}


def fenetre(regle):
    p = regle.get('params', {})
    if 'timeWindowSize' in p:
        secondes = p['timeWindowSize'] * UNITES[p['timeWindowUnit']]
    elif p.get('windows'):
        secondes = max(w['longWindow']['value'] * UNITES[w['longWindow']['unit']] for w in p['windows'])
    else:
        secondes = 3600
    secondes = min(max(secondes, 3600), 7 * 86400)
    return ("{% assign t0 = " + ALERTE + ".start | date: '%s' | minus: " + str(secondes) + " | date: '%Y-%m-%dT%H:%M:%SZ' %}"
            "{% assign t1 = " + ALERTE + ".start | date: '%s' | plus: 900 | date: '%Y-%m-%dT%H:%M:%SZ' %}")


def markdown(texte, en_html, gras=False):
    """Aucun lien HTML : le pare-feu de Tchap rejette un message à plusieurs liens, ou
    à un lien et une couleur (constaté le 2026-10-20). Le nom en gras (gras=True) ou
    « nom - URL brute », que Tchap rend cliquable."""
    texte = re.sub(r'((?:discover|dashboards)#/view/[0-9a-z_-]+)\)', r"\1" + PERIODE + ")", texte)
    if en_html:
        texte = re.sub(LIEN, r'<strong>\1</strong>' if gras else r'\1 - \2', texte)
        texte = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', texte)
        texte = re.sub(r'`([^`]+)`', r'<code>\1</code>', texte)
        return texte.replace('\n', '<br/>')
    texte = re.sub(LIEN, r'\1' if gras else r'\1 - \2', texte)
    return texte.replace('**', '').replace('`', '')


def detail(en_html):
    sep = '<br/>' if en_html else '\\n'
    esql = DETAIL_ESQL.replace('ECHAP', ' | escape' if en_html else '').replace('SEP', sep)
    raison = '{{ ' + ALERTE + '.reason' + EGAL + (' | escape' if en_html else '') + ' }}'
    return '{% if ' + ALERTE + '.grouping %}' + esql + '{% else %}' + raison + '{% endif %}'


def remplir(v, en_html):
    raison = '{{ ' + ALERTE + '.reason' + EGAL + (' | escape' if en_html else '') + ' }}'
    v = v.replace('@@RAISON@@', raison).replace('@@DETAIL@@', detail(en_html))
    return v.replace('@@JOURS@@', "{{ 30.0 | divided_by: lb | round: 1 | append: '' | replace: '.', ',' }}")


def est_lien(valeur):
    return re.sub(LIEN, '', valeur).strip(' \n,;·-') == ''


def section(titre, valeur, en_html, gras=False):
    v = remplir(markdown(liquide(valeur, en_html), en_html, gras=gras), en_html)
    t = titre.replace('=', '＝')
    if en_html:
        return '<p><strong>' + html.escape(t, quote=False) + '</strong><br/>' + v.replace('"', '\\"') + '</p>'
    return '\\n' + t + ' :\\n' + v.replace('\n', '\\n').replace('"', '\\"')


def lignes(en_html):
    e = ' | escape' if en_html else ''
    debut, fin = ('<li>', '</li>') if en_html else ('\\n• ', '')
    jobs = ("{% if foreach.item.labels.job_type %}{% assign jobs = foreach.item.labels.job_type | split: '@@' %}{% assign un = true %}"
            "{% else %}{% assign jobs = foreach.item.labels | map: 'job_type' | uniq %}{% assign un = false %}{% endif %}")
    nombre = ("{% if un %}{% assign nb = 1 %}{% else %}{% assign nb = foreach.item.labels | where: 'job_type', job | size %}{% endif %}")
    erreurs = ("{% if foreach.item.error.message %}" + ("<p><strong>Erreurs</strong><br/>" if en_html else "\\nErreurs :") +
               "{% for m in foreach.item.error.message %}" + ("" if en_html else "\\n") + "{{ m" + EGAL + e + " }}" +
               ("{% unless forloop.last %}<br/>{% endunless %}" if en_html else "") + "{% endfor %}" + ("</p>" if en_html else "") + "{% endif %}")
    if en_html:
        tableau = ("<table><thead><tr><th>Job</th><th>Échecs</th></tr></thead><tbody>{% for job in jobs %}" + nombre +
                   "<tr><td>❌ {{ job" + EGAL + e + " }}</td><td>{{ nb }}</td></tr>{% endfor %}</tbody></table>")
    else:
        tableau = "{% for job in jobs %}" + nombre + "\\n❌ {{ job" + EGAL + " }} : {{ nb }} échec(s){% endfor %}"
    corps_lignes = ("{% for ligne in foreach.item.message %}" + debut + "{{ ligne" + EGAL + e + " }}" + fin + "{% endfor %}")
    if en_html:
        corps_lignes = '<ul>' + corps_lignes + '</ul>'
    return ("{% if event.rule.tags contains 'tchap-lignes' and foreach.item.message %}" + corps_lignes +
            "{% elsif event.rule.tags contains 'jobs' and foreach.item.labels %}" + jobs + tableau + erreurs + "{% endif %}")


def pages_dependabot(en_html):
    """CVE : la page des alertes de chaque repo concerné, « repo - URL brute »."""
    urls = ("{% if foreach.item.labels.dependabot_url %}{% assign pages = foreach.item.labels.dependabot_url | split: '@@' %}"
            "{% else %}{% assign pages = foreach.item.labels | map: 'dependabot_url' | compact | uniq %}{% endif %}")
    if en_html:
        ligne = "{% for u in pages %}{% assign morceaux = u | split: '/' %}{{ morceaux[4] | escape }} - {{ u }}{% unless forloop.last %}<br/>{% endunless %}{% endfor %}"
        return "{% if foreach.item.labels %}" + urls + "{% if pages.size > 0 %}<p><strong>Alertes Dependabot</strong><br/>" + ligne + "</p>{% endif %}{% endif %}"
    ligne = "{% for u in pages %}{% assign morceaux = u | split: '/' %}\\n{{ morceaux[4] }} - {{ u }}{% endfor %}"
    return "{% if foreach.item.labels %}" + urls + "{% if pages.size > 0 %}\\nAlertes Dependabot :" + ligne + "{% endif %}{% endif %}"


ORDRE_LIENS = ['Dashboards', 'Discover sessions']


def message(regle, en_html, lignes_esql=None, groupe=None):
    """Titre en couleur, date, détail, explications ; puis toutes les sections de liens,
    et la règle en dernier. groupe : le message de ce groupe d'action (« recovered »)."""
    mm = [a for a in regle['actions'] if a['id'] != 'system-connector-.workflows' and (groupe is None or a.get('group') == groupe)][0]
    corps = json.loads(re.sub(r'\{\{!.*?\}\}', '', mm['params']['body'], flags=re.S))
    piece = corps['attachments'][0]
    titre = remplir(markdown(liquide(corps['text'], en_html), en_html), en_html)
    champs = [f for f in piece.get('fields', []) if f['title'] not in ('Règle', 'Déclenchée à', 'Rétablie à')]
    explications = [f for f in champs if not est_lien(f['value'])]
    liens = {}
    for f in champs:
        if est_lien(f['value']):
            titre_lien = 'Dashboards' if f['title'] == 'Dashboard' else f['title']
            liens.setdefault(titre_lien, []).append(f['value'])
    noms = [n for n in ORDRE_LIENS if n in liens] + [n for n in liens if n not in ORDRE_LIENS]
    libelle, quand = ('Rétablie à', 'end') if groupe == 'recovered' else ('Déclenchée à', 'start')
    date = ('<p><strong>' + libelle + '</strong> : {{ ' + ALERTE + '.' + quand + ' }}</p>') if en_html else ('\\n' + libelle + ' : {{ ' + ALERTE + '.' + quand + ' }}')
    regle_lien = ('<p><strong>Règle</strong><br/>{{ event.rule.name' + EGAL + ' | escape }} - {{ event.ruleUrl }}</p>') if en_html else \
                 ('\\nRègle :\\n{{ event.rule.name' + EGAL + ' }} - {{ event.ruleUrl }}')
    milieu = ''.join(section(f['title'], f['value'], en_html, gras=True) for f in explications)
    fin = ''.join(section(n, '\n'.join(liens[n]), en_html) for n in noms) + pages_dependabot(en_html) + regle_lien
    prefixe = fenetre(regle) + (BURN_RATE if 'context.longWindow' in mm['params']['body'] or 'context.shortWindow' in mm['params']['body'] else '')
    if en_html:
        couleur = piece.get('color', '#808080')
        tete = '<p><font data-mx-color=\\"' + couleur + '\\" color=\\"' + couleur + '\\">' + titre.replace('"', '\\"') + '</font></p>'
        return prefixe + tete + date + (lignes_esql or lignes(True)) + milieu + fin
    return prefixe + titre.replace('"', '\\"') + date + (lignes_esql or lignes(False)) + milieu + fin


def avec_retablissement(regle, en_html):
    """Une règle qui a un message au rétablissement (Uptime) envoie celui-ci pour une alerte rétablie."""
    if not any(a.get('group') == 'recovered' for a in regle['actions']):
        return message(regle, en_html)
    return ("{% if " + ALERTE + ".status == 'recovered' %}" + message(regle, en_html, groupe='recovered') +
            "{% else %}" + message(regle, en_html) + "{% endif %}")


def gabarit(salon):
    return f'''# Workflow du salon Tchap {salon}, généré par generer-workflows.py depuis les
# règles de ../../rules/ : ne pas modifier à la main. Spécification : README.md.
#
# ID du salon : Tchap → paramètres du salon → Avancé. Ce n'est pas un secret :
# le salon est privé, sur invitation.
# Le foreach écarte les alertes en attente de rétablissement
# (pending_recovered_count > 0) : une alerte qui bagote reste « active », à 0
# document, plusieurs exécutions, et l'action .workflows la transmet quand même.
# Mise à jour : PUT kbn:/api/workflows/workflow/tchap-{salon} avec {{"yaml": …}}.
POST kbn:/api/workflows/workflow
{{
  "id": "tchap-{salon}",
  "yaml": """
name: Tchap - {salon}
description: Envoie les alertes des règles dans le salon Tchap {salon}
enabled: true
triggers:
  - type: alert
consts:
  salon: "{SALONS[salon]}"
steps:
  - name: chaque-alerte
    type: foreach
    foreach: "{{{{ event.alerts | where_exp: 'a', 'a.kibana.alert.pending_recovered_count == blank or a.kibana.alert.pending_recovered_count == 0' | json }}}}"
    steps:
      - name: notifier
        type: workflow.execute
        with:
          workflow-id: tchap-client
          inputs:
            salon: "{{{{ consts.salon }}}}"
            texte: "@@TEXTE@@"
            html: "@@HTML@@"
"""
}}
'''


def main():
    par_salon = {s: [] for s in SALONS}
    esql = []
    for nom in sorted(os.listdir(REGLES)):
        if not nom.endswith('.console'):
            continue
        for rid, regle in requetes(open(os.path.join(REGLES, nom)).read()):
            w = [a for a in regle.get('actions', []) if a['id'] == 'system-connector-.workflows']
            mattermost = [a for a in regle.get('actions', []) if a['id'] != 'system-connector-.workflows']
            if not w or not mattermost:
                continue
            cible = w[0]['params']['subActionParams']['workflowId']
            if cible.startswith('tchap-alerte-'):
                esql.append((cible.removeprefix('tchap-alerte-'), rid, regle, mattermost[0]['id']))
                continue
            par_salon[cible.removeprefix('tchap-')].append((rid, regle))
    for salon, regles in par_salon.items():
        cas_t = ''.join("{% when '" + rid + "' %}" + avec_retablissement(r, False) for rid, r in regles)
        cas_h = ''.join("{% when '" + rid + "' %}" + avec_retablissement(r, True) for rid, r in regles)
        defaut_t = "{{ event.rule.name" + EGAL + " }}\\n{{ " + ALERTE + ".reason" + EGAL + " }}\\n{{ event.ruleUrl }}"
        defaut_h = "<p><strong>{{ event.rule.name" + EGAL + " | escape }}</strong></p><p>{{ " + ALERTE + ".reason" + EGAL + " | escape }}</p><p>{{ event.ruleUrl }}</p>"
        texte = '{% case event.rule.id %}' + cas_t + '{% else %}' + defaut_t + '{% endcase %}'
        corps = '{% case event.rule.id %}' + cas_h + '{% else %}' + defaut_h + '{% endcase %}'
        sortie = gabarit(salon).replace('@@TEXTE@@', texte).replace('@@HTML@@', corps)
        open(os.path.join(ICI, f'tchap-{salon}.console'), 'w').write(sortie)
        print(f'tchap-{salon}.console : {len(regles)} règle(s), {len(sortie) // 1024} Ko')
    definitions = {k.lower(): v for k, v in definitions_regles().items()} if esql else {}
    for code, rid, regle, connecteur in esql:
        salon = CONNECTEUR_SALON[connecteur]
        open(os.path.join(ICI, f'tchap-alerte-{code}.console'), 'w').write(workflow_esql(code, regle, definitions[code]['tchap'], SALONS[salon]))
        print(f'tchap-alerte-{code}.console : salon {salon}')
    jobs = jobs_suivis()
    for env, salon, index in [('prod', 'jobs-production', 'logs-prod-default'), ('staging', 'jobs-staging', 'logs-staging-default')]:
        open(os.path.join(ICI, f'rapport-jobs-{env}.console'), 'w').write(rapport(env, salon, index, jobs))
        print(f'rapport-jobs-{env}.console : {len(jobs)} jobs suivis')


API = os.path.join(ICI, '..', '..', '..', '..', '..', '..', 'pass-emploi-api')
RAPPORT_HEURE = 9 * 60 + 30


def source_api(chemin):
    import subprocess
    return subprocess.run(['git', '-C', API, 'show', 'origin/develop:' + chemin], capture_output=True, text=True, check=True).stdout


def nombre(champ, maximum):
    """Nombre de valeurs d'un champ cron (minute 0-59, heure 0-23)."""
    total = 0
    for morceau in champ.split(','):
        pas = 1
        if '/' in morceau:
            morceau, pas = morceau.split('/')
            pas = int(pas)
        if morceau == '*':
            debut, fin = 0, maximum - 1
        elif '-' in morceau:
            debut, fin = map(int, morceau.split('-'))
        else:
            debut = fin = int(morceau)
        total += len(range(debut, fin + 1, pas))
    return total


def valeurs(champ, nb, debut=0):
    sortie = []
    for morceau in champ.split(','):
        pas = 1
        if '/' in morceau:
            morceau, pas = morceau.split('/')
            pas = int(pas)
        if morceau == '*':
            a, b = debut, debut + nb - 1
        elif '-' in morceau:
            a, b = map(int, morceau.split('-'))
        else:
            a = b = int(morceau)
        sortie += list(range(a, b + 1, pas))
    return sorted(set(sortie))


def jobs_suivis():
    plan = source_api('src/domain/planificateur.ts')
    bloc = plan[plan.index('export const listeCronJobs'):]
    bloc = bloc[:bloc.index('\n]')]
    suivi = source_api('src/domain/suivi-job.ts')
    exclus = set(re.findall(r'JobType\.(\w+)', suivi[suivi.index('export function estJobSuivi'):suivi.index('export function estNotifiable')]))
    jobs = []
    for type_, expr, d1, d2 in re.findall(r"type: Planificateur\.JobType\.(\w+),\s*expression: '([^']+)',(?:\s*dateDebutExecution:[^\n]+)?\s*description:\s*(?:'((?:[^'\\]|\\.)*)'|\"([^\"]*)\")", bloc, re.S):
        if type_ in exclus:
            continue
        minute, heure, jour, mois, semaine = expr.split()
        job = {'type': type_, 'description': (d1 or d2).replace("\\'", "'"), 'attendues': None, 'jour': None, 'semaine': None, 'minute': None}
        par_jour = nombre(minute, 60) * nombre(heure, 24)
        if jour == '*' and mois == '*' and semaine == '*':
            job['attendues'] = par_jour
        elif mois == '*' and par_jour == 1 and (jour == '*') != (semaine == '*'):
            job['minute'] = int(heure) * 60 + int(minute)
            champ, maxi, decalage = (jour, 31, 1) if jour != '*' else (semaine, 7, 0)
            job['jour' if jour != '*' else 'semaine'] = '[' + ', '.join(str(v) for v in valeurs(champ, maxi, decalage)) + ']'
        jobs.append(job)
    return jobs


def rapport(env, salon, index, jobs):
    consts = '\n'.join('    - type: ' + j['type'] + '\n      description: "' + j['description'].replace('"', '\\"') + '"'
                       + ''.join(f'\n      {k}: {j[k]}' for k in ('attendues', 'jour', 'semaine', 'minute') if j[k] is not None)
                       for j in jobs)
    requete = ('FROM ' + index + ' | WHERE @timestamp >= NOW() - 24 hours AND service.name == \\"pass-emploi-api\\" '
               'AND event.action == \\"job_completed\\" | STATS executions = COUNT(*), echecs = COUNT(*) WHERE event.outcome == \\"failure\\", '
               'duree_s = ROUND(AVG(event.duration) / 1000000000, 1) BY job = labels.job_type')
    # Exécutions attendues : fixes par jour, ou 1 si le jour du mois / de la semaine du job
    # tombe dans les 24 h qui précèdent le rapport (9 h 30, heure de Paris).
    calcul = ("{% assign ligne = nil %}{% for v in steps.requete.output.values %}{% if v[3] == j.type %}{% assign ligne = v %}{% endif %}{% endfor %}"
              "{% if ligne %}{% assign n = ligne[0] %}{% assign e = ligne[1] %}{% assign d = ligne[2] | append: ' s' %}{% else %}{% assign n = 0 %}{% assign e = 0 %}{% assign d = '—' %}{% endif %}"
              "{% assign att = j.attendues %}"
              "{% if j.jour %}{% if j.minute < " + str(RAPPORT_HEURE) + " %}{% assign ref = aujourdhui_jour %}{% else %}{% assign ref = hier_jour %}{% endif %}"
              "{% if j.jour contains ref %}{% assign att = 1 %}{% else %}{% assign att = 0 %}{% endif %}{% endif %}"
              "{% if j.semaine %}{% if j.minute < " + str(RAPPORT_HEURE) + " %}{% assign ref = aujourdhui_semaine %}{% else %}{% assign ref = hier_semaine %}{% endif %}"
              "{% if j.semaine contains ref %}{% assign att = 1 %}{% else %}{% assign att = 0 %}{% endif %}{% endif %}"
              "{% if n == att %}{% assign tourne = '✅' %}{% else %}{% assign tourne = '❌' %}{% endif %}"
              "{% if e == 0 %}{% assign ok = '✅' %}{% else %}{% assign ok = '❌' %}{% endif %}")
    dates = ("{% assign t = 'now' | date: '%s' | plus: 7200 %}{% assign aujourdhui_jour = t | date: '%-d' | plus: 0 %}"
             "{% assign aujourdhui_semaine = t | date: '%w' | plus: 0 %}{% assign th = t | minus: 86400 %}"
             "{% assign hier_jour = th | date: '%-d' | plus: 0 %}{% assign hier_semaine = th | date: '%w' | plus: 0 %}")
    html = ("<p><font data-mx-color=\\\"#808080\\\" color=\\\"#808080\\\">ℹ️ <strong>Rapport quotidien des jobs — " + env + "</strong> (24 dernières heures)</font></p>"
            "<table><thead><tr><th>A tourné</th><th>Sans échec</th><th>Job</th><th>Attendues</th><th>Exécutions</th><th>Échecs</th><th>Durée moyenne</th><th>Description</th></tr></thead><tbody>"
            + dates + "{% for j in consts.jobs %}" + calcul +
            "<tr><td>{{ tourne }}</td><td>{{ ok }}</td><td>{{ j.type }}</td><td>{{ att | default: '—' }}</td><td>{{ n }}</td><td>{{ e }}</td><td>{{ d }}</td><td>{{ j.description | escape }}</td></tr>{% endfor %}"
            "{% assign types = consts.jobs | map: 'type' %}{% for v in steps.requete.output.values %}{% unless types contains v[3] %}"
            "{% if v[1] == 0 %}{% assign ok = '✅' %}{% else %}{% assign ok = '❌' %}{% endif %}"
            "<tr><td>—</td><td>{{ ok }}</td><td>{{ v[3] }}</td><td>—</td><td>{{ v[0] }}</td><td>{{ v[1] }}</td><td>{{ v[2] }} s</td><td>Hors CRON (lancé par un autre job ou un événement)</td></tr>{% endunless %}{% endfor %}"
                        "</tbody></table><p><strong>Liens</strong><br/>[Pass Emploi] Logs de " + ('Prod' if env == 'prod' else 'Hors-Prod') + " - Jobs - "
            "https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/" + ('c0d38bba-66ef-4b68-8a10-4d786f6a9f4a' if env == 'prod' else '16da36f4-a88e-4c01-b34f-e361a5292740') + "?_g=%28time%3A%28from%3Anow-24h%2Cto%3Anow%29%29</p>")
    texte = ("ℹ️ Rapport quotidien des jobs — " + env + " (24 dernières heures)" + dates + "{% for j in consts.jobs %}" + calcul +
             "\\n{{ tourne }} {{ ok }} {{ j.type }} : {{ n }} exécution(s){% if att %} sur {{ att }} attendue(s){% endif %}, {{ e }} échec(s)"
             "{% endfor %}{% assign types = consts.jobs | map: 'type' %}{% for v in steps.requete.output.values %}{% unless types contains v[3] %}"
             "\\n— {% if v[1] == 0 %}✅{% else %}❌{% endif %} {{ v[3] }} : {{ v[0] }} exécution(s), {{ v[1] }} échec(s), hors CRON{% endunless %}{% endfor %}")
    return f'''# Rapport quotidien des jobs de pass-emploi-api ({env}), chaque jour à 9 h 30
# (heure de Paris), dans le salon Tchap {salon}. Généré par generer-workflows.py
# depuis la liste des CRON de pass-emploi-api (origin/develop) : ne pas modifier à
# la main. Spécification : ../../alertes-applicatives.md.
POST kbn:/api/workflows/workflow
{{
  "id": "rapport-jobs-{env}",
  "yaml": """
name: Rapport quotidien des jobs - {env}
description: Exécutions des jobs de pass-emploi-api sur 24 h, dans le salon Tchap {salon}
enabled: true
triggers:
  - type: scheduled
    with:
      rrule:
        freq: DAILY
        interval: 1
        tzid: Europe/Paris
        byhour: [9]
        byminute: [30]
consts:
  salon: "{SALONS[salon]}"
  jobs:
{consts}
steps:
  - name: requete
    type: elasticsearch.esql.query
    with:
      query: "{requete}"
  - name: envoyer
    type: workflow.execute
    with:
      workflow-id: tchap-client
      inputs:
        salon: "{{{{ consts.salon }}}}"
        texte: "{texte}"
        html: "{html}"
"""
}}
'''


CONNECTEUR_SALON = {
    '12e46700-6e45-11ec-9757-c9700cd1bb4e': 'monitoring-production', '4cb10f00-22d9-4cf0-bda1-e288c4abb339': 'monitoring-staging',
    'd2812573-52bf-4b48-9e54-a79a8b5b227d': 'o11y-production', 'c4a313b3-aa42-4e07-8196-c007625ce8af': 'o11y-staging',
    'cd0b8285-1b69-4e3a-9c7c-6d35b42e7115': 'jobs-production', '3f71e705-99b5-4b37-ab14-932e28bc29b4': 'jobs-staging',
}
VIDE = "Plus d'erreur au moment de l'envoi : l'incident s'est peut-être résorbé."


def definitions_regles():
    import importlib.util
    spec = importlib.util.spec_from_file_location('generer_regles', os.path.join(REGLES, 'generer-regles.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.REGLES


def lignes_resultat(gabarit, en_html):
    """Une ligne par ligne du résultat ES|QL ; {0}, {1}… désignent ses colonnes."""
    e = ' | escape' if en_html else ''
    ligne = re.sub(r'\{(\d+)\}', lambda m: '{{ v[' + m.group(1) + ']' + EGAL + e + ' }}', gabarit)
    if en_html:
        ligne = markdown(ligne, True)
        return '<ul>{% for v in steps.requete.output.values %}<li>' + ligne + '</li>{% else %}<li>' + html.escape(VIDE, quote=False) + '</li>{% endfor %}</ul>'
    return '{% for v in steps.requete.output.values %}\\n• ' + markdown(ligne, False) + '{% else %}\\n• ' + VIDE + '{% endfor %}'


def requete_esql(regle):
    p = regle['params']
    secondes = p['timeWindowSize'] * UNITES[p['timeWindowUnit']]
    morceaux = [m.strip() for m in p['esqlQuery']['esql'].split('\n') if m.strip()]
    filtre = f'| WHERE @timestamp >= NOW() - {secondes // 60} minutes'
    return ' '.join(morceaux[:1] + [filtre] + morceaux[1:]).replace('\\', '\\\\').replace('"', '\\"')


def workflow_esql(code, regle, gabarit, salon_id):
    texte = message(regle, False, lignes_resultat(gabarit, False)).replace('foreach.item', 'event.alerts[0]')
    corps = message(regle, True, lignes_resultat(gabarit, True)).replace('foreach.item', 'event.alerts[0]')
    return f'''# Workflow Tchap de la règle {code} ({regle['name']}), généré par generer-workflows.py
# depuis ../../rules/ : ne pas modifier à la main. Spécification : README.md.
#
# La règle ES|QL est en groupBy all : son action .workflows ne transmet pas les lignes du
# résultat, le Workflow relance donc la requête sur la fenêtre de la règle.
POST kbn:/api/workflows/workflow
{{
  "id": "tchap-alerte-{code}",
  "yaml": """
name: Tchap - alerte {code}
description: {json.dumps(regle['name'], ensure_ascii=False)}
enabled: true
triggers:
  - type: alert
consts:
  salon: "{salon_id}"
steps:
  - name: requete
    type: elasticsearch.esql.query
    with:
      query: "{requete_esql(regle)}"
  - name: notifier
    type: workflow.execute
    with:
      workflow-id: tchap-client
      inputs:
        salon: "{{{{ consts.salon }}}}"
        texte: "{texte}"
        html: "{corps}"
"""
}}
'''


if __name__ == '__main__':
    main()
