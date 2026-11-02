"""Lancer depuis la racine du repo : python3 -I -m unittest discover -s docs/observabilite/supervision/tests -v
Chaque test travaille sur une copie de agents/ dans un répertoire temporaire : il ne modifie jamais le repo.
"""
import filecmp, json, os, shutil, subprocess, sys, tempfile, unittest

AGENTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agents')
ATTENDUES_PROD = ['postgresql-activite-prod', 'postgresql-api-prod', 'postgresql-index-hygiene-prod',
                  'postgresql-index-stats-prod', 'postgresql-statements-prod', 'postgresql-table-stats-prod',
                  'redis-api-prod', 'redis-connect-prod', 'scalingo-database-stats-prod']


class CopieDesAgents:
    def __enter__(self):
        self.dossier = tempfile.mkdtemp()
        shutil.copytree(AGENTS, os.path.join(self.dossier, 'agents'))
        return self

    def __exit__(self, *erreur):
        shutil.rmtree(self.dossier)

    def chemin(self, *morceaux):
        return os.path.join(self.dossier, 'agents', *morceaux)

    def generer(self):
        return subprocess.run([sys.executable, '-I', self.chemin('generer-integrations.py')], capture_output=True, text=True)

    def generees(self, env):
        dossier = self.chemin('generated', env)
        return sorted(f[:-5] for f in os.listdir(dossier) if f.endswith('.json')) if os.path.isdir(dossier) else []


class TestGenerateurIntegrations(unittest.TestCase):
    def test_genere_les_integrations_de_prod_attendues(self):
        with CopieDesAgents() as copie:
            sortie = copie.generer()
            self.assertEqual(sortie.returncode, 0, sortie.stderr)
            self.assertEqual(copie.generees('prod'), ATTENDUES_PROD)

    def test_requetes_sql_reprises_des_fichiers(self):
        with CopieDesAgents() as copie:
            copie.generer()
            for nom, fichier in (('statements', 'statements'), ('index-stats', 'index_stats'), ('table-stats', 'table_stats'),
                                 ('index-hygiene', 'index_hygiene'), ('activite', 'activite')):
                with self.subTest(nom):
                    integration = json.load(open(copie.chemin('generated', 'prod', f'postgresql-{nom}-prod.json')))
                    flux = integration['inputs']['sql-sql/metrics']['streams']['sql.sql']['vars']
                    attendue = open(copie.chemin('integrations', 'postgresql', f'{fichier}.sql')).read()
                    self.assertIn(attendue.strip().splitlines()[0], flux['sql_queries'])
                    self.assertEqual([l.strip() for l in flux['sql_queries'].splitlines()[1:-1] if l.strip()],
                                     [l.strip() for l in attendue.splitlines() if l.strip()])

    def test_aucun_secret_ni_hote(self):
        with CopieDesAgents() as copie:
            copie.generer()
            for env in ('prod', 'perf'):
                for nom in copie.generees(env):
                    contenu = open(copie.chemin('generated', env, nom + '.json')).read()
                    with self.subTest(f'{env}/{nom}'):
                        for interdit in ('postgres://', 'redis://', 'scalingo-dbs.com', 'dbs.scalingo.com', 'isSecretRef'):
                            self.assertNotIn(interdit, contenu)

    def test_nom_de_la_base_pose_sur_chaque_flux(self):
        with CopieDesAgents() as copie:
            copie.generer()
            for nom in copie.generees('perf'):
                integration = json.load(open(copie.chemin('generated', 'perf', nom + '.json')))
                for entree in integration['inputs'].values():
                    for flux, reglages in (entree.get('streams') or {}).items():
                        if reglages.get('enabled') and flux != 'cel.cel':
                            with self.subTest(f'{nom} / {flux}'):
                                self.assertIn('labels', reglages['vars']['processors'])

    def test_programme_cel_pose_le_nom_de_la_base(self):
        with CopieDesAgents() as copie:
            copie.generer()
            integration = json.load(open(copie.chemin('generated', 'prod', 'scalingo-database-stats-prod.json')))
            self.assertIn('"labels": {"base": base.nom}', integration['inputs']['cel-cel']['streams']['cel.cel']['vars']['program'])

    def test_generation_deterministe(self):
        with CopieDesAgents() as premiere, CopieDesAgents() as seconde:
            premiere.generer(); seconde.generer()
            comparaison = filecmp.dircmp(premiere.chemin('generated'), seconde.chemin('generated'))
            self.assertEqual(comparaison.diff_files, [])
            for sous in comparaison.subdirs.values():
                self.assertEqual(sous.diff_files, [])

    def test_type_de_base_inconnu(self):
        with CopieDesAgents() as copie:
            bases = json.load(open(copie.chemin('bases.json')))
            bases['perf']['pass-emploi-api-perf'].append('mysql')
            json.dump(bases, open(copie.chemin('bases.json'), 'w'))
            shutil.rmtree(copie.chemin('generated'), ignore_errors=True)
            sortie = copie.generer()
            self.assertNotEqual(sortie.returncode, 0)
            self.assertIn('pass-emploi-api-perf', sortie.stderr)
            self.assertIn('mysql', sortie.stderr)
            self.assertFalse(os.path.isdir(copie.chemin('generated')))

    def test_fichiers_generes_a_jour(self):
        with CopieDesAgents() as copie:
            copie.generer()
            comparaison = filecmp.dircmp(copie.chemin('generated'), os.path.join(AGENTS, 'generated'))
            self.assertEqual(comparaison.left_only + comparaison.right_only + comparaison.diff_files, [])
            for sous in comparaison.subdirs.values():
                self.assertEqual(sous.left_only + sous.right_only + sous.diff_files, [])


if __name__ == '__main__':
    unittest.main()
