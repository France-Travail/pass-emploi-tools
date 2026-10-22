#!/usr/bin/env python3
"""Génère les fichiers de règles Kibana de generated/, à coller dans Kibana → Dev Tools.

Sources, dans un répertoire par périmètre (<n>-<périmètre>/) :
  - <code>.json : une règle, au format de Kibana (son message en objet JSON dans son action
    Mattermost), plus des clés « _ » retirées à la génération (cf. README.md) ;
  - _modele.console : le texte du fichier généré autour des règles, où @@REGLE <code>@@
    marque la place de chaque règle.

Usage : FEATURE_NOTIFIER_ALERTES_MATTERMOST=true python3 -I generer-regles.py [--verifier]
  sans option : écrit generated/<n>-rules-<périmètre>.console ;
  --verifier  : compare generated/ à ses sources, code de sortie 1 au moindre écart (CI).
Puis : ../workflows/tchap/generer-workflows.py, qui lit les messages des règles ici.
"""
import json, os, re, sys

ICI = os.path.dirname(os.path.abspath(__file__))
GENERES = os.path.join(ICI, 'generated')
WORKFLOWS = 'system-connector-.workflows'

# Feature flipping, selon la convention des apps : active seulement si la variable vaut « true ».
# FEATURE_NOTIFIER_ALERTES_MATTERMOST : les règles générées gardent leurs actions Mattermost.
# Absente, elles n'ont plus que leur action Tchap (après le décommissionnement de Mattermost).
FEATURES = {'notifierAlertesMattermost': os.environ.get('FEATURE_NOTIFIER_ALERTES_MATTERMOST') == 'true'}


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


def corps(code):
    """Le corps de la règle tel que Kibana le reçoit : sans les clés « _ »."""
    return {k: v for k, v in REGLES[code].items() if not k.startswith('_')}


def actions_envoyees(actions):
    """Les actions de la règle, sans ses actions Mattermost si la feature est inactive."""
    if FEATURES['notifierAlertesMattermost']:
        return actions
    return [a for a in actions if a['id'] == WORKFLOWS]


def bloc(code):
    d = REGLES[code]
    regle = json.loads(json.dumps(corps(code)))
    regle['actions'] = actions_envoyees(regle.get('actions', []))
    morceaux = {}
    for i, a in enumerate(regle['actions']):
        if isinstance(a.get('params', {}).get('body'), (dict, list)):
            morceaux[f'@@BODY{i}@@'] = json.dumps(a['params']['body'], ensure_ascii=False, indent=2)
            a['params']['body'] = f'@@BODY{i}@@'
    esql = regle.get('params', {}).get('esqlQuery', {}).get('esql')
    if esql:
        morceaux['@@ESQL@@'] = esql
        regle['params']['esqlQuery']['esql'] = '@@ESQL@@'
    texte = json.dumps(regle, ensure_ascii=False, indent=2)
    for repere, contenu in morceaux.items():
        texte = texte.replace(f'"{repere}"', '"""' + contenu + '"""')
    entete = ''.join(l + '\n' for l in d.get('_commentaire', []))
    return entete + d.get('_methode', 'PUT') + ' kbn:/api/alerting/rule/' + d['_id'] + '\n' + texte + '\n'


def messages(code):
    """Le message de la règle par groupe d'action, et « principal » (celui de sa première action
    Mattermost, à défaut sa clé _message) : la source que lisent les Workflows Tchap, présente
    même sans Mattermost."""
    m = {}
    for a in REGLES[code].get('actions', []):
        if a['id'] != WORKFLOWS and isinstance(a.get('params', {}).get('body'), (dict, list)):
            texte = json.dumps(a['params']['body'], ensure_ascii=False)
            m.setdefault('principal', texte)
            m[a.get('group')] = texte
    if '_message' in REGLES[code]:
        m.setdefault('principal', json.dumps(REGLES[code]['_message'], ensure_ascii=False))
    return m


def nom_fichier(dossier):
    n, perimetre = dossier.split('-', 1)
    return f'{n}-rules-{perimetre}.console'


def entete(dossier):
    return f"""# ⚠️ FICHIER GÉNÉRÉ par ../generer-regles.py : NE PAS LE MODIFIER, il serait écrasé.
# À modifier à la place, dans ../{dossier}/ :
#   - une règle : son fichier <code>.json (le JSON de la règle Kibana) ;
#   - le texte autour des règles (commentaires, autres requêtes) : _modele.console.
# Puis : FEATURE_NOTIFIER_ALERTES_MATTERMOST=true python3 -I ../generer-regles.py
#        python3 -I ../../workflows/tchap/generer-workflows.py
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


def main(args):
    verifier = '--verifier' in args
    if not FEATURES['notifierAlertesMattermost']:
        print('FEATURE_NOTIFIER_ALERTES_MATTERMOST absente ou différente de « true » : règles SANS action Mattermost', file=sys.stderr)
    fichiers = assembler()
    ecarts = 0
    for nom, contenu in fichiers.items():
        chemin = os.path.join(GENERES, nom)
        actuel = open(chemin).read() if os.path.exists(chemin) else None
        if verifier:
            if actuel != contenu:
                ecarts += 1
                print(f'generated/{nom} : ' + ('absent' if actuel is None else 'diffère de ses sources'))
            continue
        os.makedirs(GENERES, exist_ok=True)
        open(chemin, 'w').write(contenu)
        print(f'generated/{nom} : {len(re.findall(r"^(?:PUT|POST) kbn:/api/alerting/rule/", contenu, flags=re.M))} règle(s)')
    attendus = set(fichiers)
    for nom in sorted(os.listdir(GENERES)) if os.path.isdir(GENERES) else []:
        if nom.endswith('.console') and nom not in attendus:
            ecarts += 1
            print(f'generated/{nom} : sans source, à supprimer')
    if verifier:
        print('identiques' if not ecarts else f'{ecarts} fichier(s) différent(s) : lancer FEATURE_NOTIFIER_ALERTES_MATTERMOST=true python3 -I generer-regles.py')
    sys.exit(1 if ecarts and verifier else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
