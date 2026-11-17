#!/usr/bin/env python3
"""Génère les fichiers de règles Kibana de ../rules/generated/, à coller dans Kibana → Dev Tools.

Sources, dans ../rules/, un répertoire par périmètre (<n>-<périmètre>/) :
  - <code>.json : une règle, au format de Kibana, plus des clés « _ » retirées à la génération
    (cf. ../rules/README.md), dont « _message », son message au format pivot ;
  - _modele.console : le texte du fichier généré autour des règles, où @@REGLE <code>@@
    marque la place de chaque règle.

Usage : python3 -I generer-regles-alerting.py [--verifier]
  sans option : écrit ../rules/generated/<n>-rules-<périmètre>.console ;
  --verifier  : compare ../rules/generated/ à ses sources, code de sortie 1 au moindre écart (CI).
Puis : generer-notifications-tchap.py, qui lit les règles générées et leur message.
"""
import importlib.util, json, os, re, sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('extraire', os.path.join(SCRIPTS, 'notifications', '1-extraire.py'))
pivot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pivot)

ICI = os.path.join(SCRIPTS, '..', 'rules')
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


def verifier_messages():
    """Une règle qui notifie a un message au format pivot valide."""
    for code, d in sorted(REGLES.items()):
        if not any(a['id'] == WORKFLOWS for a in d.get('actions', [])):
            continue
        ecarts = pivot.erreurs(d.get('_message'))
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
    entete = ''.join(l + '\n' for l in d.get('_commentaire', []))
    return entete + d.get('_methode', 'PUT') + ' kbn:/api/alerting/rule/' + d['_id'] + '\n' + texte + '\n'


def message(code):
    """Le message de la règle au format pivot (sa clé « _message »), ou None si elle n'en a pas."""
    return REGLES[code].get('_message')


def nom_fichier(dossier):
    n, perimetre = dossier.split('-', 1)
    return f'{n}-rules-{perimetre}.console'


def entete(dossier):
    return f"""# ⚠️ FICHIER GÉNÉRÉ par ../../scripts/generer-regles-alerting.py : NE PAS LE MODIFIER, il serait écrasé.
# À modifier à la place, dans ../{dossier}/ :
#   - une règle : son fichier <code>.json (le JSON de la règle Kibana) ;
#   - le texte autour des règles (commentaires, autres requêtes) : _modele.console.
# Puis : python3 -I ../../scripts/generer-regles-alerting.py
#        python3 -I ../../scripts/generer-notifications-tchap.py
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
    verifier_messages()
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
        print('identiques' if not ecarts else f'{ecarts} fichier(s) différent(s) : lancer python3 -I generer-regles-alerting.py')
    sys.exit(1 if ecarts and verifier else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
