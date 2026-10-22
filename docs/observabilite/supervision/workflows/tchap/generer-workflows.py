#!/usr/bin/env python3
"""Génère, dans generated/, les Workflows de salon tchap-<salon>.console depuis les règles
de ../../rules/generated/, et les rapports des jobs tchap-jobs-<env>-rapport.console.

Chaque règle qui a une action .workflows reçoit, dans le Workflow de son salon, son message,
lu dans son fichier JSON (../../rules/<n>-<périmètre>/<code>.json) et traduit en Liquid.
Les gabarits des Workflows sont dans modeles/, les salons dans salons.json, les rapports
des jobs dans rapports-jobs.json : ce script ne fait que les assembler.

Usage : python3 -I generer-workflows.py [--sans-rapports-jobs]
  --sans-rapports-jobs : ne régénère pas les rapports des jobs (pas besoin de pass-emploi-api ;
  utilisé par les tests).
"""
import glob, html, json, os, re

ICI = os.path.dirname(os.path.abspath(__file__))
REGLES = os.path.join(ICI, '..', '..', 'rules')
SALONS = json.load(open(os.path.join(ICI, 'salons.json')))
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
# Résumé d'un certificat (règle TLS), en anglais et en durée relative de moment.js :
# « expires on Nov 14, 2026  in 25 days. », « … in a month. », « … in 21 hours. ».
# Seule la date est gardée ; les jours sont recalculés (date contre date, arrondie
# pour les changements d'heure).
TLS_RESUME = ("{% assign etat = " + ALERTE + ".state %}{% if etat.status == 'expiring' %}"
              "{% assign le = etat.summary | remove_first: 'expires on ' | split: ' in ' | first | strip %}"
              "{% assign fin = le | date: '%s' | plus: 0 %}{% assign jour = 'now' | date: '%b %d, %Y' | date: '%s' | plus: 0 %}"
              "{% assign n = fin | minus: jour | plus: 43200 | divided_by: 86400 | floor %}{% assign date_fr = le | date: '%d/%m/%Y' %}"
              "{% if n <= 0 %}expire aujourd'hui, le {{ date_fr }}{% elsif n == 1 %}expire demain, le {{ date_fr }}"
              "{% else %}expire le {{ date_fr }}, dans {{ n }} jours{% endif %}"
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
            fixe = m.replace('\\', '\\\\').replace('=', '＝')
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


# Messages des règles, lus dans leur fichier JSON (../../rules/<n>-<périmètre>/<code>.json), par nom de règle.
MESSAGES_DEFINITIONS = {}


def corps_message(regle, groupe=None):
    """Le message de la règle (du groupe d'action demandé), lu dans sa définition de
    ../../rules/<n>-<périmètre>/<code>.json, présent même si son action Mattermost disparaît des règles générées."""
    definition = MESSAGES_DEFINITIONS.get(regle['name'])
    if definition is None:
        raise SystemExit(f"« {regle['name']} » est branchée sur Tchap sans fichier JSON dans ../../rules/<n>-<périmètre>/ : pas de message")
    cle = 'recovered' if groupe == 'recovered' else 'principal' if groupe is None else groupe
    if not definition.get(cle):
        raise SystemExit(f"« {regle['name']} » : pas de message « {cle} » dans sa définition")
    return definition[cle]


def message(regle, en_html, lignes_esql=None, groupe=None):
    """Titre en couleur, date, détail, explications ; puis toutes les sections de liens,
    et la règle en dernier. groupe : le message de ce groupe d'action (« recovered »)."""
    brut = corps_message(regle, groupe)
    corps = json.loads(re.sub(r'\{\{!.*?\}\}', '', brut, flags=re.S))
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
    prefixe = fenetre(regle) + (BURN_RATE if 'context.longWindow' in brut or 'context.shortWindow' in brut else '')
    if en_html:
        couleur = piece.get('color', '#808080')
        tete = '<p><font data-mx-color=\\"' + couleur + '\\" color=\\"' + couleur + '\\">' + titre.replace('"', '\\"') + '</font></p>'
        return prefixe + tete + date + (lignes_esql or lignes(True)) + milieu + fin
    return prefixe + titre.replace('"', '\\"') + date + (lignes_esql or lignes(False)) + milieu + fin


def avec_retablissement(regle, en_html):
    """Une règle qui a un message au rétablissement (Uptime) envoie celui-ci pour une alerte rétablie."""
    if 'recovered' not in MESSAGES_DEFINITIONS.get(regle['name'], {}):
        return message(regle, en_html)
    return ("{% if " + ALERTE + ".status == 'recovered' %}" + message(regle, en_html, groupe='recovered') +
            "{% else %}" + message(regle, en_html) + "{% endif %}")


MODELES = os.path.join(ICI, 'modeles')


def modele(nom):
    return open(os.path.join(MODELES, nom)).read()


def gabarit(salon, avec_esql=False):
    """Le Workflow d'un salon (modeles/salon.console), avec l'étape qui relance la requête des
    règles ES|QL si le salon en a ; @@TEXTE@@ et @@HTML@@ restent à remplir."""
    t = modele('salon.console')
    t = t.replace('@@SI_ESQL_COMMENTAIRE@@\n', modele('salon-esql-commentaire.console') if avec_esql else '')
    t = t.replace('@@SI_ESQL_ETAPE@@\n', modele('salon-esql-etape.yaml') if avec_esql else '')
    return t.replace('@@ID_SALON@@', SALONS[salon]).replace('@@SALON@@', salon)



GENERES = os.path.join(ICI, 'generated')
ENTETE = modele('entete.console')


ECRITS = set()


def ecrire(nom_fichier, contenu):
    os.makedirs(GENERES, exist_ok=True)
    open(os.path.join(GENERES, nom_fichier), 'w').write(ENTETE + contenu)
    ECRITS.add(nom_fichier)


def retirer_orphelins():
    """Supprime de generated/ les fichiers que cette génération n'a pas produits (Workflow
    renommé ou supprimé) : la suppression apparaît dans le diff, et le CI la voit."""
    for nom in sorted(os.listdir(GENERES)):
        if nom.endswith('.console') and nom not in ECRITS:
            os.remove(os.path.join(GENERES, nom))
            print(f'generated/{nom} : sans source, supprimé')


def main(args=()):
    regles_generees = generateur_regles()
    MESSAGES_DEFINITIONS.update({r['name']: regles_generees.messages(code) for code, r in regles_generees.REGLES.items()})
    par_salon = {s: [] for s in SALONS}
    esql = set()
    for chemin in sorted(glob.glob(os.path.join(REGLES, 'generated', '*.console'))) + sorted(glob.glob(os.path.join(REGLES, '*.console'))):
        for rid, regle in requetes(open(chemin).read()):
            w = [a for a in regle.get('actions', []) if a['id'] == 'system-connector-.workflows']
            mattermost = [a for a in regle.get('actions', []) if a['id'] != 'system-connector-.workflows']
            for action in mattermost:
                try:
                    json.loads(action['params']['body'])
                except (KeyError, json.JSONDecodeError) as e:
                    raise SystemExit(f"« {regle.get('name')} » : le message de son action {action.get('group')} n'est pas du JSON valide "
                                     f"tel quel ({e}) ; l'éditeur de règle de Kibana ne pourrait pas l'afficher")
            if not w:
                continue
            corps_message(regle)
            cible = w[0]['params']['subActionParams']['workflowId']
            salon = cible.removeprefix('tchap-')
            if salon not in SALONS:
                raise SystemExit(f"« {regle['name']} » vise le Workflow {cible}, qui ne correspond à aucun salon")
            if regle['params'].get('searchType') == 'esqlQuery' and regle['params'].get('groupBy') == 'all':
                if regle['params'].get('timeField') != '@timestamp':
                    raise SystemExit(f"« {regle['name']} » : règle ES|QL dont le champ de temps n'est pas @timestamp")
                esql.add(rid)
            par_salon[salon].append((rid, regle))
    definitions = {v['_id']: v for v in regles_generees.REGLES.values()}

    def cas(rid, r, en_html):
        if rid not in esql:
            return avec_retablissement(r, en_html)
        tchap = definitions[rid].get('_tchap')
        if not tchap or not tchap.get('ligne'):
            raise SystemExit(f"« {r['name']} » : règle ES|QL en groupBy all sans « _tchap.ligne » dans son fichier JSON (gabarit d'une ligne de résultat)")
        return message(r, en_html, lignes_resultat(tchap['ligne'], en_html, tchap.get('vide', VIDE)))

    for salon, regles in par_salon.items():
        cas_t = ''.join("{% when '" + rid + "' %}" + cas(rid, r, False) for rid, r in regles)
        cas_h = ''.join("{% when '" + rid + "' %}" + cas(rid, r, True) for rid, r in regles)
        defaut_t = "{{ event.rule.name" + EGAL + " }}\\n{{ " + ALERTE + ".reason" + EGAL + " }}\\n{{ event.ruleUrl }}"
        defaut_h = "<p><strong>{{ event.rule.name" + EGAL + " | escape }}</strong></p><p>{{ " + ALERTE + ".reason" + EGAL + " | escape }}</p><p>{{ event.ruleUrl }}</p>"
        texte = '{% case event.rule.id %}' + cas_t + '{% else %}' + defaut_t + '{% endcase %}'
        corps = '{% case event.rule.id %}' + cas_h + '{% else %}' + defaut_h + '{% endcase %}'
        sortie = gabarit(salon, any(rid in esql for rid, _ in regles)).replace('@@TEXTE@@', texte).replace('@@HTML@@', corps)
        ecrire(f'tchap-{salon}.console', sortie)
        print(f'tchap-{salon}.console : {len(regles)} règle(s), {len(sortie) // 1024} Ko')
    if '--sans-rapports-jobs' in args:
        return
    jobs = jobs_suivis()
    for r in json.load(open(os.path.join(ICI, 'rapports-jobs.json'))):
        ecrire(f"tchap-{r['salon']}-rapport.console", rapport(r, jobs))
        print(f"tchap-{r['salon']}-rapport.console : {len(jobs)} jobs suivis")
    retirer_orphelins()


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


def colle(nom):
    """Un fragment Liquid de modeles/, écrit une instruction par ligne : recollé en une ligne."""
    return ''.join(modele(nom).split('\n'))


def rapport(r, jobs):
    """Le Workflow du rapport quotidien des jobs d'un environnement (modeles/rapport-jobs*)."""
    consts = '\n'.join('    - type: ' + j['type'] + '\n      description: "' + j['description'].replace('"', '\\"') + '"'
                       + ''.join(f'\n      {k}: {j[k]}' for k in ('attendues', 'jour', 'semaine', 'minute') if j[k] is not None)
                       for j in jobs)
    valeurs = {'@@ENV@@': r['env'], '@@INDEX@@': r['index'], '@@LIBELLE_ENV@@': r['libelle'],
               '@@SESSION_JOBS@@': r['session_discover_jobs'], '@@RAPPORT_HEURE@@': str(RAPPORT_HEURE)}

    def remplir(texte):
        for repere, valeur in valeurs.items():
            texte = texte.replace(repere, valeur)
        return texte.replace('"', '\\"')

    dates, calcul = colle('rapport-jobs-dates.liquid'), colle('rapport-jobs-calcul.liquid')
    html = remplir(colle('rapport-jobs-html.liquid').replace('@@DATES@@', dates).replace('@@CALCUL@@', calcul))
    texte = remplir(colle('rapport-jobs-texte.liquid').replace('@@DATES@@', dates).replace('@@CALCUL@@', calcul))
    requete = remplir(modele('rapport-jobs-requete.esql').strip())
    t = modele('rapport-jobs.console')
    for repere, valeur in [('@@JOBS@@', consts), ('@@REQUETE@@', requete), ('@@TEXTE@@', texte), ('@@HTML@@', html),
                           ('@@ID_SALON@@', SALONS[r['salon']]), ('@@SALON@@', r['salon']), ('@@ENV@@', r['env'])]:
        t = t.replace(repere, valeur)
    return t


VIDE = "Sous le seuil à la relecture : l'incident est peut-être en train de se résorber."


def generateur_regles():
    import importlib.util
    spec = importlib.util.spec_from_file_location('generer_regles', os.path.join(REGLES, 'generer-regles.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lignes_resultat(gabarit, en_html, vide=VIDE):
    """Une ligne par ligne du résultat ES|QL ; {0}, {1}… désignent ses colonnes."""
    e = ' | escape' if en_html else ''
    ligne = re.sub(r'\{(\d+)\}', lambda m: '{{ v[' + m.group(1) + ']' + EGAL + e + ' }}', gabarit)
    if en_html:
        ligne = markdown(ligne, True)
        return '<ul>{% for v in steps.requete.output.values %}<li>' + ligne + '</li>{% else %}<li>' + html.escape(vide, quote=False) + '</li>{% endfor %}</ul>'
    return '{% for v in steps.requete.output.values %}\\n• ' + markdown(ligne, False) + '{% else %}\\n• ' + vide + '{% endfor %}'


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
