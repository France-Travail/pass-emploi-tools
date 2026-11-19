"""Étape 3 des notifications pour Tchap : charger les messages transformés (étape 2,
2-transformer.py) dans les Workflows Kibana de chaque salon, generated/tchap-<salon>.console de
../../../../workflows/tchap/, et y écrire les rapports quotidiens des jobs.
Les gabarits des Workflows sont dans modeles/, les salons dans salons.json, les rapports des jobs
dans rapports-jobs.json (../../../../workflows/tchap/) : ce script ne fait que les assembler.
Lancé par ../../generer-notifications-tchap.py.
"""
import json, os, re

def module(chemin):
    """Charge un script d'une étape (son nom, numéroté, n'est pas importable tel quel)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(os.path.basename(chemin)[:-3].replace('-', '_'), chemin)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ICI = os.path.dirname(os.path.abspath(__file__))
SUPERVISION = os.path.join(ICI, '..', '..', '..', '..')
TCHAP = os.path.join(SUPERVISION, 'workflows', 'tchap')
SALONS = json.load(open(os.path.join(TCHAP, 'salons.json')))
extraction = module(os.path.join(ICI, '..', '1-extraire.py'))
transformation = module(os.path.join(ICI, '2-transformer.py'))


MODELES = os.path.join(TCHAP, 'modeles')


def modele(nom):
    return open(os.path.join(MODELES, nom)).read()


def gabarit(salon, avec_esql=False):
    """Le Workflow d'un salon (modeles/salon/workflow.console), avec l'étape qui relance la requête des
    règles ES|QL si le salon en a ; @@TEXTE@@ et @@HTML@@ restent à remplir."""
    t = modele('salon/workflow.console')
    t = t.replace('@@SI_ESQL_COMMENTAIRE@@\n', modele('salon/commentaire-esql.console') if avec_esql else '')
    t = t.replace('@@SI_ESQL_ETAPE@@\n', modele('salon/etape-esql.yaml') if avec_esql else '')
    return t.replace('@@ID_SALON@@', SALONS[salon]).replace('@@SALON@@', salon)



GENERES = os.path.join(TCHAP, 'generated')
ENTETE = modele('commun/avertissement-fichier-genere.console')


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


def charger(args=()):
    """Les 3 étapes : extraire les règles qui notifient, transformer leur message, l'écrire
    dans le Workflow de leur salon ; puis les rapports des jobs (sauf --sans-rapports-jobs)."""
    regles = extraction.extraire()
    transformation.MESSAGES.update({r['name']: m for _, r, m, _ in regles})
    par_salon = {s: [] for s in SALONS}
    esql = set()
    for rid, regle, _, cible in regles:
        salon = cible.removeprefix('tchap-')
        if salon not in SALONS:
            raise SystemExit(f"« {regle['name']} » vise le Workflow {cible}, qui ne correspond à aucun salon")
        if regle['params'].get('searchType') == 'esqlQuery' and regle['params'].get('groupBy') == 'all':
            if regle['params'].get('timeField') != '@timestamp':
                raise SystemExit(f"« {regle['name']} » : règle ES|QL dont le champ de temps n'est pas @timestamp")
            esql.add(rid)
        par_salon[salon].append((rid, regle))
    for salon, regles_du_salon in par_salon.items():
        texte = transformation.corps_du_salon(regles_du_salon, False, esql)
        corps = transformation.corps_du_salon(regles_du_salon, True, esql)
        sortie = gabarit(salon, any(rid in esql for rid, _ in regles_du_salon)).replace('@@TEXTE@@', texte).replace('@@HTML@@', corps)
        ecrire(f'tchap-{salon}.console', sortie)
        print(f'tchap-{salon}.console : {len(regles_du_salon)} règle(s), {len(sortie) // 1024} Ko')
    if '--sans-rapports-jobs' in args:
        return
    jobs = jobs_suivis()
    for r in json.load(open(os.path.join(TCHAP, 'rapports-jobs.json'))):
        ecrire(f"tchap-{r['salon']}-rapport.console", rapport(r, jobs))
        print(f"tchap-{r['salon']}-rapport.console : {len(jobs)} jobs suivis")
    retirer_orphelins()


API = os.path.join(SUPERVISION, '..', '..', 'pass-emploi-api')
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
    """Un fragment Liquid de modeles/, écrit une instruction par ligne : recollé en une ligne,
    sans ses lignes de commentaire (« # » en début de ligne)."""
    return ''.join(l for l in modele(nom).split('\n') if not l.startswith('#'))


def rapport(r, jobs):
    """Le Workflow du rapport quotidien des jobs d'un environnement (modeles/rapport-jobs/)."""
    consts = '\n'.join('    - type: ' + j['type'] + '\n      description: "' + j['description'].replace('"', '\\"') + '"'
                       + ''.join(f'\n      {k}: {j[k]}' for k in ('attendues', 'jour', 'semaine', 'minute') if j[k] is not None)
                       for j in jobs)
    valeurs = {'@@ENV@@': r['env'], '@@INDEX@@': r['index'], '@@LIBELLE_ENV@@': r['libelle'],
               '@@SESSION_JOBS@@': r['session_discover_jobs'], '@@RAPPORT_HEURE@@': str(RAPPORT_HEURE)}

    def remplir(texte, echapper=True):
        for repere, valeur in valeurs.items():
            texte = texte.replace(repere, valeur)
        return texte.replace('"', '\\"') if echapper else texte

    jours, statut = colle('rapport-jobs/jour-du-mois-et-de-la-semaine.liquid'), colle('rapport-jobs/statut-d-un-job.liquid')
    html = remplir(colle('rapport-jobs/html.liquid').replace('@@JOUR_DU_MOIS_ET_DE_LA_SEMAINE@@', jours).replace('@@STATUT_D_UN_JOB@@', statut))
    texte = remplir(colle('rapport-jobs/texte.liquid').replace('@@JOUR_DU_MOIS_ET_DE_LA_SEMAINE@@', jours).replace('@@STATUT_D_UN_JOB@@', statut))
    # Entre guillemets simples dans le YAML, sans échappement : le vérificateur ES|QL de
    # l'éditeur de Workflows lit la requête brute, un \\" y passe pour une erreur de syntaxe.
    requete = remplir(modele('rapport-jobs/executions-des-jobs-sur-24h.esql').strip(), echapper=False)
    if "'" in requete:
        raise SystemExit("modeles/rapport-jobs/executions-des-jobs-sur-24h.esql : pas d'apostrophe (la requête est entre guillemets simples dans le YAML)")
    t = modele('rapport-jobs/workflow.console')
    for repere, valeur in [('@@JOBS@@', consts), ('@@REQUETE@@', requete), ('@@TEXTE@@', texte), ('@@HTML@@', html),
                           ('@@ID_SALON@@', SALONS[r['salon']]), ('@@SALON@@', r['salon']), ('@@ENV@@', r['env'])]:
        t = t.replace(repere, valeur)
    return t
