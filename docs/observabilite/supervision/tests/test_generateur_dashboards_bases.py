"""Lancer depuis la racine du repo : python3 -I -m unittest discover -s docs/observabilite/supervision/tests -v"""
import http.server, json, os, subprocess, sys, tempfile, threading, unittest

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


class FauxElasticsearch(http.server.BaseHTTPRequestHandler):
    requetes = []

    def do_POST(self):
        FauxElasticsearch.requetes.append(json.loads(self.rfile.read(int(self.headers['Content-Length'])))['query'])
        corps = json.dumps({'columns': []}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        pass


class TestValiderSauf(unittest.TestCase):
    def test_sauf_n_interroge_pas_les_index_exclus(self):
        serveur = http.server.HTTPServer(('127.0.0.1', 0), FauxElasticsearch)
        threading.Thread(target=serveur.serve_forever, daemon=True).start()
        self.addCleanup(serveur.shutdown)
        FauxElasticsearch.requetes = []
        env = {**os.environ, 'ES_URL': f'http://127.0.0.1:{serveur.server_port}', 'ES_API_KEY': 'cle'}
        resultat = subprocess.run([sys.executable, '-I', SCRIPT, '--valider', '--sauf', 'logs-elastic_agent'],
                                  capture_output=True, text=True, env=env, timeout=60)
        self.assertTrue(FauxElasticsearch.requetes)
        self.assertFalse([r for r in FauxElasticsearch.requetes if 'logs-elastic_agent' in r])
        self.assertIn('ignorée', resultat.stdout)
