"""Génère les intégrations Fleet de l'agent dédié, une par fichier dans generated/<env>/.

Usage : python3 -I generer-integrations.py
Sources : bases.json (bases à superviser), policies.json, requetes-sql.json, modeles/, integrations/.
Aucun accès réseau ni secret : les repères @@…@@ restent dans les fichiers générés, « pousser » les remplit.
"""
import copy, json, os, shutil, sys

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


if __name__ == '__main__':
    for chemin in generer(os.path.join(ICI, 'generated')):
        print(os.path.relpath(chemin, ICI))
