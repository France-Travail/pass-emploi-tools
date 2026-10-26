"""Tests des générateurs de règles Kibana et de Workflows Tchap.

Lancer depuis la racine du repo : python3 -I -m unittest discover -s docs/observabilite/supervision/tests -v
Chaque test travaille sur une copie de rules/ et de workflows/tchap/ dans un répertoire
temporaire : il ne modifie jamais le repo. Ni Kibana, ni pass-emploi-api ne sont nécessaires.
"""
import glob, json, os, shutil, subprocess, sys, tempfile, unittest, warnings

SUPERVISION = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = 'system-connector-.workflows'
SALONS = list(json.load(open(os.path.join(SUPERVISION, 'workflows', 'tchap', 'salons.json'))))


def setUpModule():
    warnings.simplefilter('ignore', ResourceWarning)


class CopieDuRepo:
    """Copie de rules/ et workflows/tchap/ ; lance les générateurs dans la copie."""

    def __enter__(self):
        self.dossier = tempfile.mkdtemp()
        for chemin in ('rules', os.path.join('workflows', 'tchap')):
            shutil.copytree(os.path.join(SUPERVISION, chemin), os.path.join(self.dossier, chemin))
        return self

    def __exit__(self, *erreur):
        shutil.rmtree(self.dossier)

    def chemin(self, *morceaux):
        return os.path.join(self.dossier, *morceaux)

    def generer_regles(self, *options, mattermost=True):
        env = {k: v for k, v in os.environ.items() if k != 'FEATURE_NOTIFIER_ALERTES_MATTERMOST'}
        if mattermost:
            env['FEATURE_NOTIFIER_ALERTES_MATTERMOST'] = 'true'
        return subprocess.run([sys.executable, '-I', self.chemin('rules', 'generer-regles.py'), *options], capture_output=True, text=True, env=env)

    def generer_workflows(self):
        return subprocess.run([sys.executable, '-I', self.chemin('workflows', 'tchap', 'generer-workflows.py'), '--sans-rapports-jobs'], capture_output=True, text=True)

    def workflow(self, salon):
        return open(self.chemin('workflows', 'tchap', 'generated', f'tchap-{salon}.console')).read()

    def regle_json(self, dossier, code):
        return self.chemin('rules', dossier, f'{code}.json')


def requetes(texte):
    sys.path.insert(0, os.path.join(SUPERVISION, 'workflows', 'tchap'))
    import importlib.util
    spec = importlib.util.spec_from_file_location('gw', os.path.join(SUPERVISION, 'workflows', 'tchap', 'generer-workflows.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.requetes(texte))


class TestFichiersGeneresAJour(unittest.TestCase):
    def test_regles_generees_identiques_a_leurs_sources(self):
        with CopieDuRepo() as repo:
            r = repo.generer_regles('--verifier')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_workflows_generes_identiques_a_leurs_sources(self):
        with CopieDuRepo() as repo:
            r = repo.generer_workflows()
            self.assertEqual(r.returncode, 0, r.stderr)
            for salon in SALONS:
                self.assertEqual(repo.workflow(salon), open(os.path.join(SUPERVISION, 'workflows', 'tchap', 'generated', f'tchap-{salon}.console')).read(), salon)


class TestFeatureMattermost(unittest.TestCase):
    """FEATURE_NOTIFIER_ALERTES_MATTERMOST, active seulement à « true »."""

    def test_sans_la_feature_aucune_action_mattermost(self):
        with CopieDuRepo() as repo:
            r = repo.generer_regles(mattermost=False)
            self.assertEqual(r.returncode, 0, r.stderr)
            for fichier in glob.glob(repo.chemin('rules', 'generated', '*.console')):
                for _, corps in requetes(open(fichier).read()):
                    for action in (corps or {}).get('actions', []):
                        self.assertEqual(action['id'], WORKFLOWS, f'{os.path.basename(fichier)} : {corps["name"]}')

    def test_sans_la_feature_les_messages_tchap_ne_changent_pas(self):
        """Le 1er novembre : les règles régénérées sans Mattermost, les Workflows restent identiques."""
        with CopieDuRepo() as repo:
            avant = {}
            self.assertEqual(repo.generer_workflows().returncode, 0)
            avant = {s: repo.workflow(s) for s in SALONS}
            self.assertEqual(repo.generer_regles(mattermost=False).returncode, 0)
            r = repo.generer_workflows()
            self.assertEqual(r.returncode, 0, r.stderr)
            for salon in SALONS:
                self.assertEqual(repo.workflow(salon), avant[salon], salon)


class TestControlesDesGenerateurs(unittest.TestCase):
    def test_json_de_regle_invalide(self):
        with CopieDuRepo() as repo:
            open(repo.regle_json('1-securite', 'V1'), 'a').write('}')
            r = repo.generer_regles()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('V1.json : JSON invalide', r.stdout + r.stderr)

    def test_regle_placee_dans_aucun_modele(self):
        with CopieDuRepo() as repo:
            shutil.copy(repo.regle_json('1-securite', 'V1'), repo.regle_json('1-securite', 'V2'))
            r = repo.generer_regles()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('V2', r.stdout + r.stderr)

    def test_code_defini_deux_fois(self):
        with CopieDuRepo() as repo:
            shutil.copy(repo.regle_json('1-securite', 'V1'), repo.regle_json('2-applicatives', 'V1'))
            r = repo.generer_regles()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('code déjà défini', r.stdout + r.stderr)

    def test_fichier_genere_modifie_a_la_main(self):
        with CopieDuRepo() as repo:
            chemin = repo.chemin('rules', 'generated', '1-rules-securite.console')
            open(chemin, 'a').write('\n# modification à la main\n')
            r = repo.generer_regles('--verifier')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('diffère de ses sources', r.stdout)

    def test_salon_inconnu(self):
        with CopieDuRepo() as repo:
            chemin = repo.regle_json('1-securite', 'V1')
            regle = json.load(open(chemin))
            for action in regle['actions']:
                if action['id'] == WORKFLOWS:
                    action['params']['subActionParams']['workflowId'] = 'tchap-salon-inconnu'
            json.dump(regle, open(chemin, 'w'), ensure_ascii=False, indent=2)
            self.assertEqual(repo.generer_regles().returncode, 0)
            r = repo.generer_workflows()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('ne correspond à aucun salon', r.stderr)

    def test_regle_esql_sans_gabarit_de_ligne(self):
        with CopieDuRepo() as repo:
            chemin = repo.regle_json('2-applicatives', 'A6')
            regle = json.load(open(chemin))
            del regle['_tchap']
            json.dump(regle, open(chemin, 'w'), ensure_ascii=False, indent=2)
            self.assertEqual(repo.generer_regles().returncode, 0)
            r = repo.generer_workflows()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('_tchap.ligne', r.stderr)

    def test_regle_sans_message(self):
        with CopieDuRepo() as repo:
            chemin = repo.regle_json('5-tchap-expiration-bot', 'expiration-bot')
            regle = json.load(open(chemin))
            del regle['_message']
            json.dump(regle, open(chemin, 'w'), ensure_ascii=False, indent=2)
            self.assertEqual(repo.generer_regles().returncode, 0)
            r = repo.generer_workflows()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('Expiration du compte bot', r.stderr)


class TestMessages(unittest.TestCase):
    def test_messages_des_regles_generees_en_json_valide(self):
        """L'éditeur de règle de Kibana lit le body comme du JSON brut."""
        for fichier in glob.glob(os.path.join(SUPERVISION, 'rules', 'generated', '*.console')):
            for _, corps in requetes(open(fichier).read()):
                for action in (corps or {}).get('actions', []):
                    if 'body' in action.get('params', {}):
                        json.loads(action['params']['body'])


if __name__ == '__main__':
    unittest.main()
