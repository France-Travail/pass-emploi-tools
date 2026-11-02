"""Génère les intégrations Fleet de l'agent dédié, une par fichier dans generated/<env>/, et les pousse dans Fleet.

Usage :
  python3 -I generer-integrations.py                    génère, sans réseau ni secret
  python3 -I generer-integrations.py pousser --env perf  remplit les repères depuis Scalingo et écrit dans Fleet
                                                         (SCALINGO_API_TOKEN, KIBANA_URL, KIBANA_FLEET_API_KEY)
  python3 -I generer-integrations.py verifier --env prod compare Fleet au généré (KIBANA_URL, ES_API_KEY)
Sources : bases.json (bases à superviser), policies.json, requetes-sql.json, modeles/, integrations/.
"""
import argparse, copy, json, os, re, shutil, sys, urllib.error
from urllib.parse import quote

ICI = os.path.dirname(os.path.abspath(__file__))
TYPES = ('postgresql', 'redis', 'redis-bull')


def lire(*chemin):
    with open(os.path.join(ICI, *chemin), encoding='utf-8') as f:
        return f.read()


def json_de(*chemin):
    return json.loads(lire(*chemin))


def nom_de_base(type_, app, env):
    prefixe = 'postgresql' if type_ == 'postgresql' else 'redis'
    return f"{prefixe}-{app.removeprefix('pass-emploi-').removesuffix('-' + env)}-{env}"


def avec_nom_de_base(integration, base):
    processeur = f'- add_fields:\n    target: labels\n    fields:\n      base: {base}\n'
    for entree in integration['inputs'].values():
        for flux in (entree.get('streams') or {}).values():
            if flux.get('enabled'):
                flux.setdefault('vars', {})['processors'] = processeur
    return integration


def integration(modele, nom, policy):
    return {'_avertissement': json_de('modeles', 'commun', 'avertissement.json'), 'name': nom, 'namespace': '',
            'description': 'Généré par docs/observabilite/supervision/agents/generer-integrations.py',
            'policy_ids': [policy], **copy.deepcopy(modele)}


def bases_de(env, apps):
    erreurs, bases = [], []
    for app, types in sorted(apps.items()):
        for type_ in types:
            if type_ not in TYPES:
                erreurs.append(f'{env} / {app} : type de base inconnu « {type_} » (connus : {", ".join(TYPES)})')
            else:
                bases.append((nom_de_base(type_, app, env), type_, app))
    if sum(1 for _, t, _ in bases if t == 'postgresql') > 1:
        erreurs.append(f'{env} : une seule base PostgreSQL par environnement (noms des SQL Input)')
    return bases, erreurs


def requete_yaml(fichier):
    return '- query: |\n' + ''.join('    ' + l if l.strip() else '\n' for l in lire('integrations', 'postgresql', fichier).splitlines(True)) + '  response_format: table\n'


def etat_cel(bases):
    lignes = ['auth_url: https://auth.scalingo.com/v1/tokens/exchange', 'db_api_url: https://db-api.osc-secnum-fr1.scalingo.com',
              'ca_expire_le: "@@CA_EXPIRE_LE@@"', 'bases:']
    for nom, type_, app in bases:
        connexions = f', connexions_max: @@CONNEXIONS_MAX:{nom}@@' if type_ == 'postgresql' else ''
        lignes.append(f'  - {{app: {app}, addon_id: "@@ADDON_ID:{nom}@@", nom: {nom}, disque_inclus_octets: @@DISQUE_INCLUS:{nom}@@{connexions}}}')
    return '\n'.join(lignes) + '\n'


def integrations_de(env, policy, bases):
    resultat = {}
    for nom, type_, app in bases:
        if type_ == 'postgresql':
            resultat[nom] = avec_nom_de_base(integration(json_de('modeles', 'postgresql.json'), nom, policy), nom)
            for requete in json_de('requetes-sql.json'):
                nom_sql = f"postgresql-{requete['nom']}-{env}"
                sql = integration(json_de('modeles', 'sql.json'), nom_sql, policy)
                variables = sql['inputs']['sql-sql/metrics']['streams']['sql.sql']['vars']
                variables.update(dataset_periode_requete(requete))
                resultat[nom_sql] = avec_nom_de_base(sql, nom)
        else:
            redis = integration(json_de('modeles', 'redis.json'), nom, policy)
            if type_ == 'redis-bull':
                cle = redis['inputs']['redis-redis/metrics']['streams']['redis.key']
                cle['enabled'] = True
                cle['vars']['key.patterns'] = lire('modeles', 'redis-files-bull.yaml')
            resultat[nom] = avec_nom_de_base(redis, nom)
    cel = integration(json_de('modeles', 'cel-database-stats.json'), f'scalingo-database-stats-{env}', policy)
    variables = cel['inputs']['cel-cel']['streams']['cel.cel']['vars']
    variables['program'] = lire('integrations', 'scalingo-database-stats.cel')
    variables['state'] = etat_cel(bases)
    resultat[cel['name']] = cel
    return resultat


def dataset_periode_requete(requete):
    return {'data_stream.dataset': requete['dataset'], 'period': requete['periode'], 'sql_queries': requete_yaml(requete['fichier'])}


def generer(dossier_sortie):
    policies, tout, erreurs = json_de('policies.json'), {}, []
    for env, apps in sorted(json_de('bases.json').items()):
        if env not in policies:
            erreurs.append(f'{env} : aucune policy Fleet dans policies.json')
            continue
        bases, erreurs_env = bases_de(env, apps)
        erreurs += erreurs_env
        tout[env] = integrations_de(env, policies[env], bases)
    if erreurs:
        sys.exit('\n'.join(erreurs))
    if os.path.isdir(dossier_sortie):
        shutil.rmtree(dossier_sortie)
    ecrits = []
    for env, integrations_env in tout.items():
        os.makedirs(os.path.join(dossier_sortie, env))
        for nom, contenu in sorted(integrations_env.items()):
            chemin = os.path.join(dossier_sortie, env, nom + '.json')
            with open(chemin, 'w', encoding='utf-8') as f:
                f.write(json.dumps(contenu, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
            ecrits.append(chemin)
    return ecrits


SECRETS = set()


def masquer(texte):
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            texte = texte.replace(secret, '***').replace(quote(secret, safe=''), '***')
    return texte


def dire(texte, erreur=False):
    print(masquer(texte), file=sys.stderr if erreur else sys.stdout)


def detail(exception):
    if isinstance(exception, urllib.error.HTTPError):
        return f'HTTP {exception.code} {masquer(exception.read().decode(errors="replace"))[:500]}'
    return masquer(str(exception))


def remplacer(valeur, reperes):
    if isinstance(valeur, str):
        for nom, remplacement in reperes.items():
            valeur = valeur.replace(f'@@{nom}@@', str(remplacement))
        return valeur
    if isinstance(valeur, list):
        return [remplacer(v, reperes) for v in valeur]
    if isinstance(valeur, dict):
        return {k: remplacer(v, reperes) for k, v in valeur.items()}
    return valeur


def generees(env):
    dossier = os.path.join(ICI, 'generated', env)
    if not os.path.isdir(dossier):
        sys.exit(f'{dossier} absent : lancer d\'abord la génération')
    return {f[:-5]: json_de('generated', env, f) for f in sorted(os.listdir(dossier)) if f.endswith('.json')}


def reperes_de_base(nom, type_, info, pem):
    if type_ == 'postgresql':
        adresse = f"{info['hote']}:{info['port']}/{info['base_de_donnees']}?sslmode=verify-full&sslrootcert=/app/certs/postgresql-ca.pem"
        identifiants = f"{quote(info['utilisateur'], safe='')}:{quote(info['mot_de_passe'], safe='')}@"
        return {'URL_SANS_IDENTIFIANTS': 'postgres://' + adresse, 'URL_AVEC_IDENTIFIANTS': 'postgres://' + identifiants + adresse,
                'UTILISATEUR': info['utilisateur'], 'MOT_DE_PASSE': info['mot_de_passe']}
    ssl_ = 'ssl.certificate_authorities: |\n' + ''.join('  ' + l for l in pem.splitlines(True)) if info['force_tls'] else ''
    return {'HOTE_PORT': f"{info['hote']}:{info['port']}", 'MOT_DE_PASSE': info['mot_de_passe'], 'SSL': ssl_}


def pousser(env):
    import fleet as fleet_, scalingo as scalingo_
    token, cle = os.environ['SCALINGO_API_TOKEN'], os.environ['KIBANA_FLEET_API_KEY']
    SECRETS.update((token, cle))
    bases, erreurs = bases_de(env, json_de('bases.json')[env])
    if erreurs:
        sys.exit('\n'.join(erreurs))
    echecs = 0
    try:
        plateforme = scalingo_.Scalingo(token)
        pem, ca_expire_le = scalingo_.autorite_de_certification()
    except Exception as e:
        dire(f'Scalingo inaccessible : {detail(e)}', erreur=True)
        return 1
    infos, reperes, reperes_cel = {}, {}, {'CA_EXPIRE_LE': ca_expire_le, 'API_TOKEN': token}
    for nom, type_, app in bases:
        try:
            info = plateforme.base(app, 'postgresql' if type_ == 'postgresql' else 'redis')
        except Exception as e:
            dire(f'{nom} : non poussée, {detail(e)}', erreur=True)
            echecs += 1
            continue
        SECRETS.add(info['mot_de_passe'])
        infos[nom] = info
        reperes[nom] = reperes_de_base(nom, type_, info, pem)
        reperes_cel.update({f'ADDON_ID:{nom}': info['addon_id'], f'DISQUE_INCLUS:{nom}': info['disque_inclus_octets'],
                            f'CONNEXIONS_MAX:{nom}': info['connexions_max']})
    base_postgresql = next((nom for nom, t, _ in bases if t == 'postgresql'), None)
    base_de = {nom: nom for nom, _, _ in bases}
    if base_postgresql:
        base_de.update({f"postgresql-{requete['nom']}-{env}": base_postgresql for requete in json_de('requetes-sql.json')})
    client = fleet_.Fleet(cle)
    try:
        existantes = client.toutes()
    except Exception as e:
        dire(f'Fleet inaccessible : {detail(e)}', erreur=True)
        return 1
    for nom, contenu in generees(env).items():
        corps = {k: v for k, v in contenu.items() if not k.startswith('_')}
        if nom == f'scalingo-database-stats-{env}':
            if len(infos) < len(bases) and (nom in existantes or not infos):
                dire(f'{nom} : non poussée, une base n\'a pas pu être lue dans Scalingo ; la version dans Fleet est gardée', erreur=True)
                echecs += 1
                continue
            variables = corps['inputs']['cel-cel']['streams']['cel.cel']['vars']
            variables['state'] = ''.join(l for l in variables['state'].splitlines(True)
                                         if not re.search(r'@@ADDON_ID:([^@]+)@@', l) or re.search(r'@@ADDON_ID:([^@]+)@@', l).group(1) in infos)
            corps = remplacer(corps, reperes_cel)
        else:
            base = base_de.get(nom)
            if base is None:
                dire(f'{nom} : non poussée, aucune base de bases.json ne lui correspond (régénérer ?)', erreur=True)
                echecs += 1
                continue
            if base not in reperes:
                dire(f'{nom} : non poussée, la base {base} n\'a pas pu être lue dans Scalingo', erreur=True)
                continue
            corps = remplacer(corps, reperes[base])
        if '@@' in json.dumps(corps):
            dire(f'{nom} : non poussée, des repères @@…@@ restent à remplir', erreur=True)
            echecs += 1
            continue
        try:
            if nom in existantes:
                client.mettre_a_jour(existantes[nom]['id'], corps)
                dire(f'{nom} : mise à jour')
            else:
                client.creer(corps)
                dire(f'{nom} : créée')
        except Exception as e:
            dire(f'{nom} : échec Fleet, {detail(e)}', erreur=True)
            echecs += 1
    return 1 if echecs else 0


def ecarts(attendu, reel, chemin=''):
    if isinstance(reel, dict) and reel.get('isSecretRef') and '@@' in json.dumps(attendu):
        return []
    if isinstance(attendu, dict):
        if not isinstance(reel, dict):
            return [chemin or '.']
        if attendu.get('enabled') is False:
            return [] if reel.get('enabled') is False else [f'{chemin}.enabled'.lstrip('.')]
        return [e for k, v in attendu.items() if not k.startswith('_') for e in ecarts(v, reel.get(k), f'{chemin}.{k}'.lstrip('.'))]
    if isinstance(attendu, list):
        if not isinstance(reel, list) or len(attendu) != len(reel):
            return [chemin]
        return [e for i, (a, r) in enumerate(zip(attendu, reel)) for e in ecarts(a, r, f'{chemin}[{i}]')]
    if isinstance(attendu, str) and '@@' in attendu:
        if isinstance(reel, dict) and reel.get('isSecretRef'):
            return []
        motif = re.escape(attendu)
        motif = re.sub(r'@@[^@]+@@', '.*?', motif.replace(re.escape('@@'), '@@'))
        return [] if isinstance(reel, str) and re.fullmatch(motif, reel, re.S) else [chemin]
    if isinstance(attendu, str) and isinstance(reel, str):
        return [] if attendu.strip() == reel.strip() else [chemin]
    return [] if attendu == reel else [chemin]


def verifier(env):
    import fleet as fleet_
    cle = os.environ['ES_API_KEY']
    SECRETS.add(cle)
    policy = json_de('policies.json')[env]
    client = fleet_.Fleet(cle)
    try:
        existantes, de_la_policy = client.toutes(), client.integrations(policy)
    except Exception as e:
        dire(f'Fleet inaccessible : {detail(e)}', erreur=True)
        return 1
    attendues, nb_ecarts = generees(env), 0
    for nom, contenu in attendues.items():
        if nom not in existantes:
            dire(f'{nom} : absente de Fleet')
            nb_ecarts += 1
            continue
        champs = ecarts({k: contenu[k] for k in ('inputs', 'package') if k in contenu}, existantes[nom])
        champs = [c for c in champs if not c.startswith('package.') or c == 'package.name']
        if champs:
            nb_ecarts += 1
            dire(f'{nom} : écart sur {", ".join(champs[:5])}')
    for nom in sorted(set(de_la_policy) - set(attendues)):
        dire(f'{nom} : présente dans la policy, non gérée par ce script')
    dire(f'{nb_ecarts} écart(s)')
    return 1 if nb_ecarts else 0


if __name__ == '__main__':
    sys.path.insert(0, ICI)
    analyse = argparse.ArgumentParser()
    analyse.add_argument('commande', nargs='?', choices=('pousser', 'verifier'))
    analyse.add_argument('--env')
    arguments = analyse.parse_args()
    if arguments.commande is None:
        for chemin in generer(os.path.join(ICI, 'generated')):
            print(os.path.relpath(chemin, ICI))
    else:
        if arguments.env not in json_de('policies.json'):
            sys.exit(f'--env : un environnement de policies.json ({", ".join(json_de("policies.json"))})')
        sys.exit((pousser if arguments.commande == 'pousser' else verifier)(arguments.env))
