"""Lancer depuis la racine du repo : python3 -I -m unittest discover -s docs/observabilite/supervision/tests -v"""
import json, os, subprocess, sys, tempfile, unittest

SUPERVISION = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SUPERVISION, 'dashboards', 'generer-dashboards-bases.py')
VERSIONNE = os.path.join(SUPERVISION, 'dashboards', 'dashboard-bases-de-donnees.ndjson')


def generer():
    with tempfile.TemporaryDirectory() as dossier:
        sortie = os.path.join(dossier, 'dashboards.ndjson')
        resultat = subprocess.run([sys.executable, '-I', SCRIPT, '--sortie', sortie], capture_output=True, text=True,
                                  env={k: v for k, v in os.environ.items() if k not in ('ES_URL', 'ES_API_KEY')})
        return resultat, (open(sortie).read() if os.path.exists(sortie) else '')


class TestGenerateurDashboardsBases(unittest.TestCase):
    def test_dashboards_generes_a_jour(self):
        resultat, contenu = generer()
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertEqual(contenu, open(VERSIONNE).read())

    def test_aucune_adresse_de_base_en_dur(self):
        contenu = open(VERSIONNE).read()
        for interdit in ('scalingo-dbs.com', 'dbs.scalingo.com', 'pa-back-prod', 'pass-emploi-connect-3919', 'service.address'):
            with self.subTest(interdit):
                self.assertNotIn(interdit, contenu)

    def test_selecteurs_issus_de_bases_json(self):
        bases = json.load(open(os.path.join(SUPERVISION, 'agents', 'bases.json')))
        noms = {'postgresql': set(), 'redis': set()}
        for env, apps in bases.items():
            for app, types in apps.items():
                for type_ in types:
                    prefixe = 'postgresql' if type_ == 'postgresql' else 'redis'
                    noms[prefixe].add(f"{prefixe}-{app.removeprefix('pass-emploi-').removesuffix('-' + env)}-{env}")
        for ligne in open(VERSIONNE):
            attributs = json.loads(ligne)['attributes']
            controles = {c['config']['variable_name']: c['config'] for c in attributs['pinned_panels']['panels'].values()}
            type_ = 'postgresql' if 'PostgreSQL' in attributs['title'] else 'redis'
            with self.subTest(attributs['title']):
                self.assertEqual(set(controles['base']['available_options']), noms[type_])
