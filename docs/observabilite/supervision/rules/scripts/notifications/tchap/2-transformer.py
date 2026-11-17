"""Étape 2 des notifications pour Tchap : transformer le message au format pivot d'une règle
(étape 1, ../1-extraire.py) en texte et en HTML Matrix, écrits en Liquid pour les Workflows
Kibana : variables, relance ES|QL, burn rate des SLO en français, échéance des certificats TLS,
« = » remplacé, échappement HTML, un seul lien cliquable par message (pare-feu devant Tchap).
"""
import html, os, re

def module(chemin):
    """Charge un script d'une étape (son nom, numéroté, n'est pas importable tel quel)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(os.path.basename(chemin)[:-3].replace('-', '_'), chemin)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pivot = module(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '1-extraire.py'))

ALERTE = 'foreach.item.kibana.alert'
# Le pare-feu de Tchap rejette un message qui contient un « = » et un lien https.
EGAL = " | replace: '=', '＝'"
DETAIL_ESQL = ('{% for g in ' + ALERTE + '.grouping %}{% unless g[0] == "labels" %}'
               '{{ g[0] | replace: "_", " " }} : {{ g[1]' + EGAL + 'ECHAP }}SEP{% endunless %}{% endfor %}')
# Variables du format pivot → Liquid, sur le document d'alerte que reçoit le Workflow.
VARIABLES = {
    'regle': '{{ event.rule.name' + EGAL + 'ECHAP }}',
    'debut': '{{ ' + ALERTE + '.start }}',
    'valeur': '{{ ' + ALERTE + '.evaluation.value }}',
    'raison': '{{ ' + ALERTE + '.reason' + EGAL + 'ECHAP }}',
    'groupe': '{{ ' + ALERTE + '.instance.id' + EGAL + 'ECHAP }}',
    'url_slo': 'https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/slos/{{ foreach.item.slo.id }}',
    'burn_rate_long': "{{ lb | append: '' | replace: '.', ',' }}",
    'fenetre_longue': "{{ ld | replace: 'h', ' h' | replace: 'm', ' min' }}",
    'burn_rate_court': "{{ sb | append: '' | replace: '.', ',' }}",
    'fenetre_courte': "{{ sd | replace: 'h', ' h' | replace: 'm', ' min' }}",
    'seuil': '{{ seuil }}',
}
BURN_RATE_VARIABLES = {'burn_rate_long', 'fenetre_longue', 'burn_rate_court', 'fenetre_courte', 'seuil', 'jours_restants'}
# Gravité du pivot → émoji en tête du titre et couleur du titre.
GRAVITES = {'critique': ('🚨 ', '#d00000'), 'avertissement': ('⚠️ ', '#f2c744'),
            'information': ('', '#808080'), 'retablissement': ('✅ ', '#2eb886')}
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


def liquide(texte, en_html):
    """Texte du pivot → Liquid : ses variables {…} deviennent du Liquid, le texte fixe est
    échappé en HTML."""
    sortie = []
    for i, m in enumerate(pivot.VARIABLE.split(texte)):
        if i % 2 == 0:
            fixe = m.replace('\\', '\\\\').replace('=', '＝')
            sortie.append(html.escape(fixe, quote=False) if en_html else fixe)
        elif m in VARIABLES:
            sortie.append(VARIABLES[m].replace('ECHAP', ' | escape' if en_html else ''))
        elif m == 'resume_certificat':
            sortie.append(TLS_RESUME.replace('ECHAP', ' | escape' if en_html else ''))
        elif m.startswith('etat.'):
            sortie.append('{{ ' + ALERTE + '.state.' + m[5:] + EGAL + (' | escape' if en_html else '') + ' }}')
        elif m == 'detail':
            sortie.append('@@DETAIL@@')
        elif m == 'jours_restants':
            sortie.append('@@JOURS@@')
        else:
            raise ValueError('variable du pivot sans rendu Tchap : {' + m + '}')
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
    v = v.replace('@@DETAIL@@', detail(en_html))
    return v.replace('@@JOURS@@', "{{ 30.0 | divided_by: lb | round: 1 | append: '' | replace: '.', ',' }}")


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


# Messages des règles au format pivot, par nom de règle : rempli par l'étape 1 (extraire).
MESSAGES = {}


def pivot_de(regle):
    return MESSAGES[regle['name']]


def en_markdown(liens):
    """Les liens d'une section du pivot, une ligne « [nom](url) » chacun, la syntaxe des textes du pivot."""
    return '\n'.join(f"[{l['nom']}]({l['url']})" for l in liens)


def message(regle, en_html, lignes_esql=None, retabli=False):
    """Titre en couleur, date, détail, explications ; puis toutes les sections de liens,
    et la règle en dernier. retabli : le message de rétablissement du pivot."""
    m = pivot_de(regle)
    bloc = m['retablissement'] if retabli else m
    emoji, couleur = GRAVITES['retablissement' if retabli else m['gravite']]
    titre = remplir(markdown(liquide(emoji + bloc['titre'], en_html), en_html), en_html)
    liens = bloc.get('liens', {})
    noms = [n for n in ORDRE_LIENS if n in liens] + [n for n in liens if n not in ORDRE_LIENS]
    libelle, quand = ('Rétablie à', 'end') if retabli else ('Déclenchée à', 'start')
    date = ('<p><strong>' + libelle + '</strong> : {{ ' + ALERTE + '.' + quand + ' }}</p>') if en_html else ('\\n' + libelle + ' : {{ ' + ALERTE + '.' + quand + ' }}')
    regle_lien = ('<p><strong>Règle</strong><br/>{{ event.rule.name' + EGAL + ' | escape }} - {{ event.ruleUrl }}</p>') if en_html else \
                 ('\\nRègle :\\n{{ event.rule.name' + EGAL + ' }} - {{ event.ruleUrl }}')
    milieu = ''.join(section(s['titre'], '\n'.join(s['lignes']), en_html, gras=True) for s in bloc.get('sections', []))
    fin = ''.join(section(n, en_markdown(liens[n]), en_html) for n in noms) + pages_dependabot(en_html) + regle_lien
    cites = {v for texte in pivot.textes(bloc) for v in pivot.variables(texte)}
    prefixe = fenetre(regle) + (BURN_RATE if cites & BURN_RATE_VARIABLES else '')
    if en_html:
        tete = '<p><font data-mx-color=\\"' + couleur + '\\" color=\\"' + couleur + '\\">' + titre.replace('"', '\\"') + '</font></p>'
        return prefixe + tete + date + (lignes_esql or lignes(True)) + milieu + fin
    return prefixe + titre.replace('"', '\\"') + date + (lignes_esql or lignes(False)) + milieu + fin


def avec_retablissement(regle, en_html):
    """Une règle qui a un message de rétablissement (Uptime) envoie celui-ci pour une alerte rétablie."""
    if 'retablissement' not in pivot_de(regle):
        return message(regle, en_html)
    return ("{% if " + ALERTE + ".status == 'recovered' %}" + message(regle, en_html, retabli=True) +
            "{% else %}" + message(regle, en_html) + "{% endif %}")


VIDE = "Sous le seuil à la relecture : l'incident est peut-être en train de se résorber."


def lignes_resultat(gabarit, en_html, vide=VIDE):
    """Une ligne par ligne du résultat ES|QL ; {0}, {1}… désignent ses colonnes."""
    e = ' | escape' if en_html else ''
    ligne = re.sub(r'\{(\d+)\}', lambda m: '{{ v[' + m.group(1) + ']' + EGAL + e + ' }}', gabarit)
    if en_html:
        ligne = markdown(ligne, True)
        return '<ul>{% for v in steps.requete.output.values %}<li>' + ligne + '</li>{% else %}<li>' + html.escape(vide, quote=False) + '</li>{% endfor %}</ul>'
    return '{% for v in steps.requete.output.values %}\\n• ' + markdown(ligne, False) + '{% else %}\\n• ' + vide + '{% endfor %}'


def message_de_la_regle(rid, regle, en_html, esql):
    """Le message d'une règle ; esql : les id des règles ES|QL en groupBy all, dont le Workflow
    relance la requête."""
    if rid not in esql:
        return avec_retablissement(regle, en_html)
    resultat = pivot_de(regle).get('resultat')
    if not resultat:
        raise SystemExit(f"« {regle['name']} » : règle ES|QL en groupBy all sans « _message.resultat.ligne » dans son fichier JSON (gabarit d'une ligne de résultat)")
    return message(regle, en_html, lignes_resultat(resultat['ligne'], en_html, resultat.get('vide', VIDE)))


def corps_du_salon(regles, en_html, esql):
    """Le texte (ou le HTML) du Workflow d'un salon : le message de chacune de ses règles,
    choisi par l'id de la règle, et un message générique pour une règle inconnue."""
    cas = ''.join("{% when '" + rid + "' %}" + message_de_la_regle(rid, r, en_html, esql) for rid, r in regles)
    if en_html:
        defaut = "<p><strong>{{ event.rule.name" + EGAL + " | escape }}</strong></p><p>{{ " + ALERTE + ".reason" + EGAL + " | escape }}</p><p>{{ event.ruleUrl }}</p>"
    else:
        defaut = "{{ event.rule.name" + EGAL + " }}\\n{{ " + ALERTE + ".reason" + EGAL + " }}\\n{{ event.ruleUrl }}"
    return '{% case event.rule.id %}' + cas + '{% else %}' + defaut + '{% endcase %}'
