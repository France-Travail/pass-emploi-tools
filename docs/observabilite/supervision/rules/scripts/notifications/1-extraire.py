"""Étape 1 des notifications, commune à tous les canaux : extraire les règles qui notifient et
leur message au format pivot (clé « _message » de leur fichier JSON, ../../rules/<n>-<périmètre>/),
et le valider. Spécification : ../../rules/README.md, « Le message d'une règle ».
Les étapes 2 (transformer) et 3 (charger) sont propres à chaque canal : tchap/.
"""
import glob, json, os, re

SUPERVISION = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
REGLES = os.path.join(SUPERVISION, 'rules')
WORKFLOWS = 'system-connector-.workflows'

GRAVITES = ('critique', 'avertissement', 'information')
CLES = {'titre', 'gravite', 'sections', 'liens', 'retablissement', 'resultat'}
CLES_RETABLISSEMENT = {'titre', 'sections', 'liens'}
VARIABLES = {
    'regle', 'debut', 'valeur', 'raison', 'groupe', 'detail', 'url_slo', 'seuil',
    'burn_rate_long', 'fenetre_longue', 'burn_rate_court', 'fenetre_courte', 'jours_restants',
    'resume_certificat',
}
VARIABLE = re.compile(r'\{([a-z_]+(?:\.[A-Za-z_]+)?)\}')


def variables(texte):
    """Les variables citées dans un texte du pivot : {valeur}, {etat.monitorUrl}…"""
    return VARIABLE.findall(texte)


def est_variable(nom):
    return nom in VARIABLES or nom.startswith('etat.')


def textes(bloc):
    """Tous les textes d'un bloc (message ou rétablissement), là où une variable peut apparaître."""
    yield bloc.get('titre', '')
    for s in bloc.get('sections', []):
        yield s.get('titre', '')
        yield from s.get('lignes', [])
    for titre, liens in bloc.get('liens', {}).items():
        yield titre
        for lien in liens:
            yield lien.get('nom', '')
            yield lien.get('url', '')


def erreurs(message):
    """Les écarts d'un message au format pivot (liste vide : il est valide)."""
    if not isinstance(message, dict):
        return ['« _message » absent ou qui n\'est pas un objet']
    e = [f'clé inconnue « {k} »' for k in sorted(set(message) - CLES)]
    if not message.get('titre'):
        e.append('« titre » absent')
    if message.get('gravite') not in GRAVITES:
        e.append(f"« gravite » : {message.get('gravite')!r}, attendu l'une de {', '.join(GRAVITES)}")
    blocs = [message]
    if 'retablissement' in message:
        r = message['retablissement']
        e += [f'retablissement : clé inconnue « {k} »' for k in sorted(set(r) - CLES_RETABLISSEMENT)]
        if not r.get('titre'):
            e.append('retablissement : « titre » absent')
        blocs.append(r)
    for bloc in blocs:
        for s in bloc.get('sections', []):
            if not s.get('titre') or not isinstance(s.get('lignes'), list) or not s['lignes']:
                e.append(f"section {s.get('titre')!r} : « titre » et « lignes » (liste non vide) attendus")
        for titre, liens in bloc.get('liens', {}).items():
            if not liens:
                e.append(f'liens « {titre} » : section vide')
            for lien in liens:
                if set(lien) != {'nom', 'url'} or not lien['nom'] or not lien['url']:
                    e.append(f'liens « {titre} » : chaque lien a un « nom » et une « url », rien d\'autre')
        for texte in textes(bloc):
            e += [f'variable inconnue {{{v}}}' for v in variables(texte) if not est_variable(v)]
    resultat = message.get('resultat')
    if resultat is not None and (not isinstance(resultat, dict) or not resultat.get('ligne') or set(resultat) - {'ligne', 'vide'}):
        e.append('« resultat » : « ligne » (et « vide », facultatif) attendus')
    return e


def requetes(texte):
    """Les règles d'un fichier .console généré : (id, corps de la règle)."""
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


def messages():
    """{nom de règle : message au format pivot}, lus dans les fichiers JSON des règles."""
    m = {}
    for chemin in sorted(glob.glob(os.path.join(REGLES, '*-*', '*.json'))):
        d = json.load(open(chemin))
        if '_message' in d:
            m[d['name']] = d['_message']
    return m


def extraire():
    """Les règles qui notifient (action .workflows), telles que déployées (rules/generated/),
    chacune avec son message validé : [(id, règle, message, Workflow visé)]."""
    tous = messages()
    regles = []
    for chemin in sorted(glob.glob(os.path.join(REGLES, 'generated', '*.console'))):
        for rid, regle in requetes(open(chemin).read()):
            w = [a for a in regle.get('actions', []) if a['id'] == WORKFLOWS]
            if not w:
                continue
            m = tous.get(regle['name'])
            if m is None:
                raise SystemExit(f"« {regle['name']} » notifie sans « _message » dans son fichier JSON de rules/<n>-<périmètre>/")
            ecarts = erreurs(m)
            if ecarts:
                raise SystemExit(f"« {regle['name']} » : _message invalide : " + ' ; '.join(ecarts))
            regles.append((rid, regle, m, w[0]['params']['subActionParams']['workflowId']))
    return regles
