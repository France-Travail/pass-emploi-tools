"""Tests des générateurs de règles Kibana et de Workflows Tchap.

Lancer depuis la racine du repo : python3 -I -m unittest discover -s docs/observabilite/supervision/tests -v
Chaque test travaille sur une copie de rules/, slo/ et workflows/tchap/ dans un répertoire
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
        for chemin in ('rules', 'slo', os.path.join('workflows', 'tchap')):
            shutil.copytree(os.path.join(SUPERVISION, chemin), os.path.join(self.dossier, chemin))
        return self

    def __exit__(self, *erreur):
        shutil.rmtree(self.dossier)

    def chemin(self, *morceaux):
        return os.path.join(self.dossier, *morceaux)

    def generer_regles(self, *options):
        return subprocess.run([sys.executable, '-I', self.chemin('rules', 'scripts', 'generer-regles-alerting.py'), *options], capture_output=True, text=True)

    def generer_workflows(self):
        return subprocess.run([sys.executable, '-I', self.chemin('rules', 'scripts', 'generer-notifications-tchap.py'), '--sans-rapports-jobs'], capture_output=True, text=True)

    def workflow(self, salon):
        return open(self.chemin('workflows', 'tchap', 'generated', f'tchap-{salon}.console')).read()

    def regle_json(self, dossier, code):
        return self.chemin('rules', dossier, f'{code}.json')


def requetes(texte):
    import importlib.util
    spec = importlib.util.spec_from_file_location('extraire', os.path.join(SUPERVISION, 'rules', 'scripts', 'notifications', '1-extraire.py'))
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


class TestReglesGenerees(unittest.TestCase):
    def test_seule_l_action_tchap_est_envoyee(self):
        """Le message vit dans « _message », au format pivot : aucune action de messagerie dans les règles."""
        with CopieDuRepo() as repo:
            r = repo.generer_regles()
            self.assertEqual(r.returncode, 0, r.stderr)
            for fichier in glob.glob(repo.chemin('rules', 'generated', '*.console')):
                for _, corps in requetes(open(fichier).read()):
                    for action in (corps or {}).get('actions', []):
                        self.assertEqual(action['id'], WORKFLOWS, f'{os.path.basename(fichier)} : {corps["name"]}')


class TestSeuilsDesSlo(unittest.TestCase):
    """slo/seuils.json : la seule source de l'objectif et des seuils de burn rate d'un SLO."""

    def seuils(self, repo, modifier):
        chemin = repo.chemin('slo', 'seuils.json')
        seuils = json.load(open(chemin))
        modifier(seuils)
        json.dump(seuils, open(chemin, 'w'), ensure_ascii=False, indent=2)

    def test_un_objectif_change_le_slo_sa_regle_et_son_message(self):
        with CopieDuRepo() as repo:
            self.seuils(repo, lambda s: s['SLO3-conseiller-france-travail'].update(objectif=0.98))
            r = repo.generer_regles()
            self.assertEqual(r.returncode, 0, r.stderr)
            slo = open(repo.chemin('slo', 'generated', '1-slos.console')).read()
            bloc = slo.split('slos/9afea251-1cf9-423f-a374-ca43c3e751ac')[1].split('\nPUT ')[0]
            self.assertIn('"objective": { "target": 0.98 }', bloc)
            regles = open(repo.chemin('rules', 'generated', '2-rules-applicatives.console')).read()
            self.assertIn('"maxBurnRateThreshold": 50.0', regles)
            self.assertEqual(repo.generer_workflows().returncode, 0)
            self.assertIn("98 % des connexions des conseillers France Travail aboutissent", repo.workflow('monitoring-production'))

    def test_un_seuil_de_burn_rate_change_la_regle(self):
        with CopieDuRepo() as repo:
            self.seuils(repo, lambda s: s['SLO3-invite']['burn_rate'].update(high=3))
            self.assertEqual(repo.generer_regles().returncode, 0)
            regles = open(repo.chemin('rules', 'generated', '2-rules-applicatives.console')).read()
            self.assertRegex(regles, r'"burnRateThreshold": 3,\s*"maxBurnRateThreshold": 10.0')

    def test_seuils_incomplets(self):
        for modifier, attendu in ((lambda s: s.pop('SLO2'), 'pas de seuils pour la règle SLO2'),
                                  (lambda s: s['SLO1']['burn_rate'].pop('low'), 'SLO1 : burn_rate doit donner un seuil'),
                                  (lambda s: s.update({'SLO9': {'objectif': 0.9, 'burn_rate': {}}}), 'SLO9 ne correspond à aucune règle'),
                                  (lambda s: s['SLO1'].update(objectif=99.5), 'SLO1 : objectif entre 0 et 1')):
            with self.subTest(attendu), CopieDuRepo() as repo:
                self.seuils(repo, modifier)
                r = repo.generer_regles()
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(attendu, r.stderr)


class TestControlesDesGenerateurs(unittest.TestCase):
    def test_json_de_regle_invalide(self):
        with CopieDuRepo() as repo:
            open(repo.regle_json('1-securite', 'S1'), 'a').write('}')
            r = repo.generer_regles()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('S1.json : JSON invalide', r.stdout + r.stderr)

    def test_regle_placee_dans_aucun_modele(self):
        with CopieDuRepo() as repo:
            shutil.copy(repo.regle_json('1-securite', 'S1'), repo.regle_json('1-securite', 'V2'))
            r = repo.generer_regles()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('V2', r.stdout + r.stderr)

    def test_code_defini_deux_fois(self):
        with CopieDuRepo() as repo:
            shutil.copy(repo.regle_json('1-securite', 'S1'), repo.regle_json('2-applicatives', 'S1'))
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
            chemin = repo.regle_json('1-securite', 'S1')
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
            del regle['_message']['resultat']
            json.dump(regle, open(chemin, 'w'), ensure_ascii=False, indent=2)
            self.assertEqual(repo.generer_regles().returncode, 0)
            r = repo.generer_workflows()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('_message.resultat.ligne', r.stderr)

    def test_fenetres_d_une_regle_burn_rate(self):
        for modifier, attendu in ((lambda m: m['fenetres'].update(medium={'gravite': 'rouge'}), 'fenetres « medium »'),
                                  (lambda m: m['fenetres'].update(enorme={'gravite': 'critique'}), "la règle n'a pas cette fenêtre"),
                                  (lambda m: m['essentiel'].update(sections=['Inconnue']), 'section « Inconnue » absente')):
            with self.subTest(attendu), CopieDuRepo() as repo:
                chemin = repo.regle_json('2-applicatives', 'SLO1')
                regle = json.load(open(chemin))
                modifier(regle['_message'])
                json.dump(regle, open(chemin, 'w'), ensure_ascii=False, indent=2)
                r = repo.generer_regles()
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(attendu, r.stderr)

    def test_une_fenetre_absente_n_est_pas_notifiee(self):
        with CopieDuRepo() as repo:
            self.assertEqual(repo.generer_regles().returncode, 0)
            self.assertEqual(repo.generer_workflows().returncode, 0)
            w = repo.workflow('monitoring-production')
            self.assertIn("{% when 'slo.burnRate.medium' %}", w)
            self.assertNotIn("{% when 'slo.burnRate.low' %}", w)
            self.assertIn('previous_action_group', w)

    def test_regle_sans_message(self):
        with CopieDuRepo() as repo:
            chemin = repo.regle_json('5-tchap-expiration-bot', 'expiration-bot')
            regle = json.load(open(chemin))
            del regle['_message']
            json.dump(regle, open(chemin, 'w'), ensure_ascii=False, indent=2)
            r = repo.generer_regles()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('expiration-bot.json : _message invalide', r.stderr)

    def test_message_pivot_invalide(self):
        for modifier, attendu in ((lambda m: m.update(gravite='rouge'), '« gravite »'),
                                  (lambda m: m.update(titre=m['titre'] + ' {inconnue}'), 'variable inconnue {inconnue}'),
                                  (lambda m: m['liens'].update(Runbook=[]), 'section vide'),
                                  (lambda m: m.update(fenetres={'alert': {'gravite': 'critique'}}), '« gravite » et « fenetres »')):
            with self.subTest(attendu), CopieDuRepo() as repo:
                chemin = repo.regle_json('2-applicatives', 'A8')
                regle = json.load(open(chemin))
                modifier(regle['_message'])
                json.dump(regle, open(chemin, 'w'), ensure_ascii=False, indent=2)
                r = repo.generer_regles()
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(attendu, r.stderr)


class TestRenvoisVersLesBasesDeDonnees(unittest.TestCase):
    PG = '66b0c0ac-d034-489b-ab0a-7b07539074ff'
    REDIS = '86b702ee-b9c7-4344-91ef-a10a50405ed5'

    def regle(self, code):
        return json.load(open(os.path.join(SUPERVISION, 'rules', '2-applicatives', f'{code}.json')))

    def champs(self, regle):
        m = regle['_message']
        champs = {s['titre']: '\n'.join(s['lignes']) for s in m.get('sections', [])}
        champs.update({titre: '\n'.join(l['url'] for l in liens) for titre, liens in m.get('liens', {}).items()})
        return champs

    def etapes(self, guide):
        return guide.split('## À vérifier')[1].split('## ')[0].strip().splitlines()

    def test_a6_part_du_dashboard_postgresql(self):
        regle = self.regle('A6')
        guide = regle['artifacts']['investigation_guide']['blob']
        self.assertIn(self.PG, self.etapes(guide)[0])
        self.assertIn(self.PG, self.champs(regle)['À vérifier'].splitlines()[0])
        self.assertIn(self.PG, self.champs(regle)['Dashboards'])
        self.assertIn({'id': self.PG}, regle['artifacts']['dashboards'])
        self.assertNotIn('dashboard.scalingo.com', guide)

    def test_a2_cite_les_bases_sans_depasser_trois_etapes(self):
        regle = self.regle('A2')
        guide = regle['artifacts']['investigation_guide']['blob']
        etapes = self.etapes(guide)
        self.assertLessEqual(len(etapes), 3)
        for id_ in (self.PG, self.REDIS):
            self.assertIn(id_, etapes[1])
            self.assertIn(id_, self.champs(regle)['Dashboards'])
            self.assertIn({'id': id_}, regle['artifacts']['dashboards'])


if __name__ == '__main__':
    unittest.main()
