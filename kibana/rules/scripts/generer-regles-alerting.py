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

Usage : python3 -I generer-regles-alerting.py [--verifier]
  sans option : écrit ../generated/<n>-rules-<périmètre>.console ;
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
    entete = ''.join(l + '\n' for l in d.get('_commentaire', []))
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


def main(args):
    verifier = '--verifier' in args
    verifier_messages()
    appliquer_seuils()
    fichiers = assembler()
    sorties = [(os.path.join(GENERES, nom), f'generated/{nom}', contenu) for nom, contenu in fichiers.items()]
    sorties.append((os.path.join(SLO, 'generated', '1-slos.console'), 'slo/generated/1-slos.console', slo_genere()))
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
