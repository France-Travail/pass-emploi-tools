#!/usr/bin/env python3
"""Génère les fichiers de règles Kibana de ../generated/, à coller dans Kibana → Dev Tools.

Sources, dans ../, un répertoire par périmètre (<n>-<périmètre>/) :
  - <code>.json : une règle, au format de Kibana, plus des clés « _ » retirées à la génération
    (cf. ../README.md), dont « _message », son message au format pivot ;
  - _modele.console : le texte du fichier généré autour des règles, où @@REGLE <code>@@
    marque la place de chaque règle.
Et les SLO : ../../slo/_modele.console, dont l'objectif de chacun (@@OBJECTIF@@) vient de
../../slo/seuils.json, comme les seuils de burn rate de sa règle (SLO*.json) : écrit
../../slo/generated/1-slos.console.

Et le catalogue de toutes les alertes, ../../../docs/observabilite/catalogue-alertes.md, depuis la
question (« _question ») et les paramètres de chaque règle, et ce qui écrit chaque index lu (SOURCES).

Usage : python3 -I generer-regles-alerting.py [--verifier]
  sans option : écrit ../generated/<n>-rules-<périmètre>.console, le fichier des SLO et le catalogue ;
  --verifier  : compare ../generated/ à ses sources, code de sortie 1 au moindre écart (CI).
Puis : generer-notifications-tchap.py, qui lit les règles générées et leur message.
"""
import importlib.util, json, os, re, sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('extraire', os.path.join(SCRIPTS, 'notifications', '1-extraire.py'))
pivot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pivot)

ICI = os.path.join(SCRIPTS, '..')
GENERES = os.path.join(ICI, 'generated')
WORKFLOWS = 'system-connector-.workflows'


def perimetres():
    return sorted(d for d in os.listdir(ICI) if re.match(r'^\d+-', d) and os.path.isfile(os.path.join(ICI, d, '_modele.console')))


def charger():
    """{code: définition} de toutes les règles, avec le répertoire de chacune."""
    regles = {}
    for dossier in perimetres():
        for nom in sorted(os.listdir(os.path.join(ICI, dossier))):
            if not nom.endswith('.json'):
                continue
            code = nom[:-5]
            if code in regles:
                raise SystemExit(f'{dossier}/{nom} : code déjà défini dans {regles[code]["_dossier"]}/')
            try:
                d = json.load(open(os.path.join(ICI, dossier, nom)))
            except json.JSONDecodeError as e:
                raise SystemExit(f'{dossier}/{nom} : JSON invalide ({e})')
            regles[code] = dict(d, _dossier=dossier)
    return regles


REGLES = charger()
SLO = os.path.join(ICI, '..', 'slo')
SEUILS = json.load(open(os.path.join(SLO, 'seuils.json')))


def codes_slo():
    """{id du SLO : code de sa règle burn rate}."""
    return {d['params']['sloId']: c for c, d in REGLES.items() if d.get('params', {}).get('sloId')}


def appliquer_seuils():
    """Pose dans chaque règle burn rate les seuils de ../../slo/seuils.json : seuil de chaque
    fenêtre, et seuil maximal, 1 / (1 - objectif), que Kibana exige."""
    codes = set(codes_slo().values())
    for c in sorted(codes - set(SEUILS)):
        raise SystemExit(f'slo/seuils.json : pas de seuils pour la règle {c}')
    for c in sorted(set(SEUILS) - codes):
        raise SystemExit(f'slo/seuils.json : {c} ne correspond à aucune règle burn rate (SLO*.json)')
    for c in sorted(codes):
        s = SEUILS[c]
        if not 0 < s.get('objectif', 0) < 1:
            raise SystemExit(f'slo/seuils.json : {c} : objectif entre 0 et 1 attendu (0.99 pour 99 %)')
        fenetres = REGLES[c]['params']['windows']
        if {w['id'] for w in fenetres} != set(s.get('burn_rate', {})):
            raise SystemExit(f"slo/seuils.json : {c} : burn_rate doit donner un seuil pour chacune des fenêtres de la règle ({', '.join(w['id'] for w in fenetres)})")
        guide = REGLES[c].get('artifacts', {}).get('investigation_guide')
        if guide:
            guide['blob'] = guide['blob'].replace('{objectif}', pivot.objectif_en_texte(s['objectif']))
        for i, w in enumerate(fenetres):
            debut = {k: w[k] for k in ('id', 'actionGroup')}
            fenetres[i] = dict(debut, burnRateThreshold=s['burn_rate'][w['id']], maxBurnRateThreshold=round(1 / (1 - s['objectif']), 2),
                               **{k: v for k, v in w.items() if k not in debut})


def slo_genere():
    """../../slo/generated/1-slos.console : le modèle, avec l'objectif de chaque SLO."""
    modele = open(os.path.join(SLO, '_modele.console')).read()
    codes = codes_slo()

    def objectif(m):
        code = codes.get(m.group(1))
        if code is None:
            raise SystemExit(f'slo/_modele.console : le SLO {m.group(1)} n\'a pas de règle burn rate (SLO*.json), donc pas d\'objectif')
        objectif = SEUILS[code]['objectif']
        corps = m.group(2).replace('@@OBJECTIF@@', json.dumps(objectif)).replace('@@OBJECTIF_TEXTE@@', pivot.objectif_en_texte(objectif))
        return (f'DELETE kbn:/api/observability/slos/{m.group(1)}\nPOST kbn:/api/observability/slos\n'
                + '{\n  "id": "' + m.group(1) + '",' + corps[1:])
    texte = re.sub(r'^@@SLO (\S+)@@\n(\{.*?\n\})', objectif, modele, flags=re.M | re.S)
    if '@@OBJECTIF' in texte:
        raise SystemExit('slo/_modele.console : repère @@OBJECTIF@@ hors du corps d\'un SLO')
    return ("# ⚠️ FICHIER GÉNÉRÉ par ../../rules/scripts/generer-regles-alerting.py : NE PAS LE MODIFIER, il serait écrasé.\n"
            "# À modifier à la place : l'objectif d'un SLO dans ../seuils.json, le reste dans ../_modele.console.\n"
            "# La CI de chaque PR vérifie que ce fichier correspond à ses sources.\n#\n" + texte)


def verifier_questions():
    """Chaque règle dit à quelle question elle répond, pour le catalogue."""
    for code, d in sorted(REGLES.items()):
        q = d.get('_question')
        if not isinstance(q, str) or not q.endswith('?'):
            raise SystemExit(f"{d['_dossier']}/{code}.json : « _question » attendue, une question terminée par « ? »")
        if not isinstance(d.get('_gravite', ''), str):
            raise SystemExit(f"{d['_dossier']}/{code}.json : « _gravite » : un texte, ou absente")


def verifier_messages():
    """Une règle qui notifie a un message au format pivot valide."""
    for code, d in sorted(REGLES.items()):
        if not any(a['id'] == WORKFLOWS for a in d.get('actions', [])):
            continue
        ecarts = pivot.erreurs(d.get('_message'))
        fenetres = {w['id'] for w in d.get('params', {}).get('windows', [])}
        ecarts += [f'fenetres « {f} » : la règle n\'a pas cette fenêtre ({", ".join(sorted(fenetres))})'
                   for f in (d.get('_message') or {}).get('fenetres', {}) if f not in fenetres]
        if ecarts:
            raise SystemExit(f"{d['_dossier']}/{code}.json : _message invalide : " + ' ; '.join(ecarts))


def corps(code):
    """Le corps de la règle tel que Kibana le reçoit : sans les clés « _ »."""
    return {k: v for k, v in REGLES[code].items() if not k.startswith('_')}


def bloc(code):
    d = REGLES[code]
    regle = json.loads(json.dumps(corps(code)))
    morceaux = {}
    esql = regle.get('params', {}).get('esqlQuery', {}).get('esql')
    if esql:
        morceaux['@@ESQL@@'] = esql
        regle['params']['esqlQuery']['esql'] = '@@ESQL@@'
    texte = json.dumps(regle, ensure_ascii=False, indent=2)
    for repere, contenu in morceaux.items():
        texte = texte.replace(f'"{repere}"', '"""' + contenu + '"""')
    manquants = [k for k in ('rule_type_id', 'consumer') if k not in regle]
    if manquants:
        raise SystemExit(f"{d['_dossier']}/{code}.json : {' et '.join(manquants)} attendus (la règle est recréée par POST)")
    entete = f"# {code} — {d['_question']}\n" + ''.join(l + '\n' for l in d.get('_commentaire', []))
    url = 'kbn:/api/alerting/rule/' + d['_id']
    return entete + 'DELETE ' + url + '\nPOST ' + url + '\n' + texte + '\n'


def message(code):
    """Le message de la règle au format pivot (sa clé « _message »), ou None si elle n'en a pas."""
    return REGLES[code].get('_message')


def nom_fichier(dossier):
    n, perimetre = dossier.split('-', 1)
    return f'{n}-rules-{perimetre}.console'


def entete(dossier):
    return f"""# ⚠️ FICHIER GÉNÉRÉ par ../scripts/generer-regles-alerting.py : NE PAS LE MODIFIER, il serait écrasé.
# À modifier à la place, dans ../{dossier}/ :
#   - une règle : son fichier <code>.json (le JSON de la règle Kibana) ;
#   - le texte autour des règles (commentaires, autres requêtes) : _modele.console.
# Puis : python3 -I ../scripts/generer-regles-alerting.py
#        python3 -I ../scripts/generer-notifications-tchap.py
# La CI de chaque PR vérifie que ce fichier correspond à ses sources.
# Ce fichier se colle tel quel dans Kibana → Dev Tools. Mode d'emploi : ../README.md.
#
"""


def assembler():
    """{nom de fichier: contenu généré}, un fichier par périmètre."""
    fichiers, places = {}, set()
    for dossier in perimetres():
        texte = open(os.path.join(ICI, dossier, '_modele.console')).read()
        for code in re.findall(r'^@@REGLE (\S+)@@$', texte, flags=re.M):
            if REGLES.get(code, {}).get('_dossier') != dossier:
                raise SystemExit(f'{dossier}/_modele.console : repère @@REGLE {code}@@ sans fichier {dossier}/{code}.json')
            if code in places:
                raise SystemExit(f'{dossier}/_modele.console : règle {code} placée deux fois')
            places.add(code)
            texte = texte.replace(f'@@REGLE {code}@@', bloc(code).rstrip('\n'))
        fichiers[nom_fichier(dossier)] = entete(dossier) + texte
    oubliees = sorted(set(REGLES) - places)
    if oubliees:
        raise SystemExit(f"règles placées dans aucun _modele.console : {', '.join(oubliees)}")
    return fichiers


CATALOGUE = os.path.join(ICI, '..', '..', 'docs', 'observabilite', 'catalogue-alertes.md')
SECTIONS = {
    '1-securite': ('Sécurité', '[alertes de sécurité](alertes-securite.md)'),
    '2-applicatives': ('Applicatives', '[alertes applicatives](alertes.md), [SLO](slo.md)'),
    '3-stack-observabilite': ("Stack d'observabilité", '[alertes de la stack](infra/alertes-stack-observabilite.md)'),
    '4-tchap': ('Tchap', '[chemin jusqu\'à Tchap](fonctionnement.md)'),
    '5-tchap-expiration-bot': ('Tchap : compte du bot', '[runbook d\'expiration](runbooks/runbook-tchap-expiration-bot.md)'),
}
EMOJIS = {'critique': '🚨', 'avertissement': '⚠️', 'information': 'ℹ️'}

ENV = '(prod|staging|perf)'
ROUTAGE = '[routage en sortie](infra/process/logs/pipeline.md#routage-en-sortie)'
WEBHOOK = '[collecte par webhook](infra/collecte/webhooks/README.md#la-chaîne)'
SOURCES = [
    (rf'logs-{ENV}-default', '`logs-<env>-default`',
     'Logstash `process`, sortie par défaut : les lignes des apps, reçues par le drain Scalingo', ROUTAGE),
    (rf'logs-router-{ENV}-default', '`logs-router-<env>-default`', 'Logstash `process` : les lignes du routeur Scalingo', ROUTAGE),
    (rf'logs-logstash-errors-{ENV}-default', '`logs-logstash-errors-<env>-default`',
     'Logstash `process` : les lignes dont un filtre a échoué', ROUTAGE),
    (rf'logs-logstash-dlq-{ENV}-default', '`logs-logstash-dlq-<env>-default`',
     'Logstash `dead_letter_queue` : les documents refusés par Elasticsearch',
     '[Dead Letter Queue](infra/process/logs/pipeline.md#dead-letter-queue)'),
    (rf'logs-alertes-scalingo-{ENV}-default(::failures)?', '`logs-alertes-scalingo-<env>-default`',
     'notifiers Scalingo, par webhook, sans Logstash', WEBHOOK),
    (r'logs-alertes-github-default(::failures)?', '`logs-alertes-github-default`',
     'workflow GitHub des CVE Dependabot, sans Logstash', WEBHOOK),
    (r'logs-apm\.error-.*', '`logs-apm.error-*`', 'agent APM du web conseiller', '[traces APM](infra/collecte/traces/README.md)'),
    (r'metrics-(logstash|redis)\..*', '`metrics-logstash.*`, `metrics-redis.*`', 'Elastic Agent, intégrations Fleet',
     '[métriques de la stack](infra/collecte/metriques/stack-observabilite.md#data-streams)'),
    (r'(metrics|logs)-elastic_agent\..*', '`metrics-elastic_agent.*`, `logs-elastic_agent.*`', 'Elastic Agent, sur lui-même',
     "[savoir qu'un agent a décroché](infra/pilotage.md#savoir-quun-agent-a-décroché)"),
    (r'logs-scalingo\.container_stats-default', '`logs-scalingo.container_stats-default`',
     "Elastic Agent, intégration Custom API sur l'API Scalingo",
     '[mémoire des conteneurs](../../kibana/agents/README.md#mémoire-des-conteneurs-scalingo-intégration-custom-api)'),
    ('heartbeat', 'sondes Heartbeat', 'Heartbeat', '[disponibilité](infra/collecte/metriques/disponibilite.md)'),
    (r'tchap-expiration-bot', '`tchap-expiration-bot`', 'date posée à la main au renouvellement du compte',
     '[runbook](runbooks/runbook-tchap-expiration-bot.md)'),
    (r'\.ds-ilm-history-.*|\.workflows-executions', 'index internes', 'Elasticsearch et Kibana eux-mêmes', '—'),
]


def slos_du_modele():
    """{id du SLO : (son nom, l'index qu'il lit)}, lus dans ../../slo/_modele.console."""
    texte = open(os.path.join(SLO, '_modele.console')).read()
    blocs = re.split(r'^@@SLO (\S+)@@\n', texte, flags=re.M)[1:]
    return {i: (re.search(r'"name": "([^"]*)"', b).group(1), re.search(r'"index": "([^"]*)"', b).group(1))
            for i, b in zip(blocs[::2], blocs[1::2])}


def gravite(d):
    if '_gravite' in d:
        return d['_gravite']
    m = d.get('_message')
    if not m:
        return 'aucune notification'
    if 'fenetres' not in m:
        return EMOJIS[m['gravite']]
    duree = {w['id']: f"{w['longWindow']['value']} {w['longWindow']['unit']}" for w in d['params']['windows']}
    return ' · '.join(f"{EMOJIS[f['gravite']]} sur {duree[w]}" for w, f in m['fenetres'].items())


def noms(liste):
    return [n.strip() for n in (liste if isinstance(liste, list) else liste.split(',')) if n.strip()]


def code_inline(liste):
    return ', '.join(f'`{n}`' for n in liste)


def lecture(code, d, slos):
    """(ce que lit la règle, en clair ; les index qu'elle lit, « heartbeat » pour une sonde)."""
    t, p = d['rule_type_id'], d['params']
    if t == 'slo.rules.burnRate':
        nom, index = slos[p['sloId']]
        return f'burn rate du SLO « {nom} »', [index]
    if t == 'xpack.uptime.alerts.monitorStatus':
        return 'sonde Heartbeat ' + code_inline(re.findall(r'monitor\.id\s*:\s*(\S+)', p['search'])), ['heartbeat']
    if t == 'xpack.uptime.alerts.tlsCertificate':
        return 'certificats vus par les sondes Heartbeat', ['heartbeat']
    if p.get('searchType') == 'esqlQuery':
        index = noms(re.search(r'FROM\s+(.+)', p['esqlQuery']['esql']).group(1).split('|')[0])
        return 'ES|QL sur ' + code_inline(index), index
    if p.get('searchType') == 'searchSource':
        index = noms(p['searchConfiguration']['index']['title'])
        return 'KQL sur ' + code_inline(index), index
    if p.get('searchType') == 'esQuery':
        index = noms(p['index'])
        return 'requête Elasticsearch sur ' + code_inline(index), index
    raise SystemExit(f"{d['_dossier']}/{code}.json : type de règle inconnu du catalogue ({t})")


def lecteurs_des_sources(slos):
    """{n° de la source dans SOURCES : codes des règles qui la lisent}."""
    lecteurs = {i: [] for i in range(len(SOURCES))}
    for code, d in sorted(REGLES.items(), key=lambda r: ordre_naturel(r[0])):
        for index in lecture(code, d, slos)[1]:
            i = next((i for i, (motif, *_) in enumerate(SOURCES) if re.fullmatch(motif, index)), None)
            if i is None:
                raise SystemExit(f"{d['_dossier']}/{code}.json : {index} absent de SOURCES dans generer-regles-alerting.py"
                                 " (qui l'écrit, et où lire comment)")
            if code not in lecteurs[i]:
                lecteurs[i].append(code)
    for i, codes in lecteurs.items():
        if not codes:
            raise SystemExit(f'SOURCES dans generer-regles-alerting.py : {SOURCES[i][1]} lue par aucune règle, retirer sa ligne')
    return lecteurs


def salon(d):
    w = [a['params']['subActionParams']['workflowId'] for a in d.get('actions', []) if a['id'] == WORKFLOWS]
    return ', '.join(x.removeprefix('tchap-') for x in w) or '—'


def ordre_naturel(code):
    return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', code)]


def catalogue():
    """../../../docs/observabilite/catalogue-alertes.md : un tableau par périmètre."""
    slos = slos_du_modele()
    cellule = lambda texte: texte.replace('|', '\\|')
    texte = ("<!-- ⚠️ FICHIER GÉNÉRÉ par kibana/rules/scripts/generer-regles-alerting.py : NE PAS LE MODIFIER. -->\n"
             "# Catalogue des alertes\n\n"
             "Toutes les règles d'alerte Kibana. Généré depuis leurs fichiers JSON\n"
             "([`kibana/rules/`](../../kibana/rules/README.md)) : la question d'une alerte est la clé\n"
             "`_question` de son fichier. Le pourquoi, les seuils et le calibrage : la page de\n"
             "chaque périmètre. Les gravités : [alertes applicatives](alertes.md#gravités). Ce qui\n"
             "remplit les index lus : [sources des données](#sources-des-données).\n")
    for dossier in perimetres():
        if dossier not in SECTIONS:
            raise SystemExit(f'{dossier}/ : périmètre absent de SECTIONS dans generer-regles-alerting.py (titre du catalogue)')
        titre, detail = SECTIONS[dossier]
        texte += f'\n## {titre}\n\nDétail : {detail}.\n\n| Code | À quoi elle sert | Gravité | Basée sur | Salon | Règle |\n|---|---|---|---|---|---|\n'
        for code in sorted((c for c, d in REGLES.items() if d['_dossier'] == dossier), key=ordre_naturel):
            d = REGLES[code]
            texte += '| ' + ' | '.join(cellule(x) for x in (code, d['_question'], gravite(d), lecture(code, d, slos)[0], salon(d), d['name'])) + ' |\n'
    texte += ('\n## Sources des données\n\n'
              "Ce qui écrit chaque index lu par une règle, et où lire comment un document y arrive.\n\n"
              '| Source | Écrite par | Comment elle est remplie | Lue par |\n|---|---|---|---|\n')
    for i, codes in lecteurs_des_sources(slos).items():
        _, source, ecrite_par, comment = SOURCES[i]
        texte += '| ' + ' | '.join(cellule(x) for x in (source, ecrite_par, comment, ', '.join(codes))) + ' |\n'
    return texte + ('\n## Hors règles Kibana\n\n'
                    '- Disque et indexation Elasticsearch (M11, M12) : notifications AutoOps d\'Elastic Cloud, cf.\n'
                    '  [alertes de la stack](infra/alertes-stack-observabilite.md#notifications-autoops-m11-et-m12).\n'
                    '- Alertes de métriques Scalingo (5xx au routeur, trafic, RAM) : relayées par A4a, A4b, M6a, M6b.\n')


def main(args):
    verifier = '--verifier' in args
    verifier_questions()
    verifier_messages()
    appliquer_seuils()
    fichiers = assembler()
    sorties = [(os.path.join(GENERES, nom), f'generated/{nom}', contenu) for nom, contenu in fichiers.items()]
    sorties.append((os.path.join(SLO, 'generated', '1-slos.console'), 'slo/generated/1-slos.console', slo_genere()))
    sorties.append((CATALOGUE, 'docs/observabilite/catalogue-alertes.md', catalogue()))
    ecarts = 0
    for chemin, nom, contenu in sorties:
        actuel = open(chemin).read() if os.path.exists(chemin) else None
        if verifier:
            if actuel != contenu:
                ecarts += 1
                print(f'{nom} : ' + ('absent' if actuel is None else 'diffère de ses sources'))
            continue
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        open(chemin, 'w').write(contenu)
        if chemin == CATALOGUE:
            print(f'{nom} : {len(REGLES)} règle(s)')
        else:
            print(f'{nom} : {len(re.findall(r"^POST kbn:/api/(?:alerting/rule/|observability/slos$)", contenu, flags=re.M))} objet(s)')
    attendus = set(fichiers)
    for nom in sorted(os.listdir(GENERES)) if os.path.isdir(GENERES) else []:
        if nom.endswith('.console') and nom not in attendus:
            ecarts += 1
            print(f'generated/{nom} : sans source, à supprimer')
    if verifier:
        print('identiques' if not ecarts else f'{ecarts} fichier(s) différent(s) : lancer python3 -I generer-regles-alerting.py')
    sys.exit(1 if ecarts and verifier else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
