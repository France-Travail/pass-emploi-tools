"""Tests du programme CEL des métriques des bases Scalingo, contre un faux Scalingo local.

Lancer depuis la racine du repo : MITO=<chemin de mito> python3 -I -m unittest discover -s elastic-agent/integrations/tests -v
"""
import json, os, shutil, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import faux_scalingo

PROGRAMME = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scalingo-database-stats.cel')
MITO = os.environ.get('MITO') or shutil.which('mito')
GIO = 1024 ** 3


@unittest.skipUnless(MITO, 'mito introuvable : définir MITO ou l\'ajouter au PATH')
class TestScalingoDatabaseStats(unittest.TestCase):
    def setUp(self):
        self.serveur = faux_scalingo.demarrer()
        self.addCleanup(self.serveur.shutdown)
        racine = f'http://127.0.0.1:{self.serveur.server_port}'
        self.etat = {'url': racine, 'auth_url': racine + '/v1/tokens/exchange', 'db_api_url': racine,
                     'secret': {'api_token': 'token-valide'}, 'bases': []}

    def base(self, nom, addon_id, **autres):
        self.etat['bases'].append({'app': 'pass-emploi-api-prod', 'addon_id': addon_id, 'nom': nom,
                                   'disque_inclus_octets': 160 * GIO, **autres})

    def evenements(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(self.etat, f)
        self.addCleanup(os.unlink, f.name)
        sortie = subprocess.run([MITO, '-data', f.name, PROGRAMME], capture_output=True, text=True, timeout=60)
        self.assertEqual(sortie.returncode, 0, sortie.stderr)
        return json.loads(sortie.stdout)['events']

    def test_un_document_par_instance(self):
        self.base('postgresql-api-prod', 'addon-pg')
        evenements = self.evenements()
        self.assertEqual(len(evenements), 1)
        scalingo = evenements[0]['scalingo']
        self.assertEqual(scalingo['memory']['limit']['bytes'], 536870912)
        self.assertEqual(scalingo['disk']['usage']['bytes'], 37825858)
        self.assertEqual(scalingo['database']['nom'], 'postgresql-api-prod')
        self.assertEqual(scalingo['database']['instance'], '9f20c633-3507-4585-8cd0-f9ada91165c0')

    def test_pourcentage_de_disque_sur_le_quota_du_plan(self):
        self.base('postgresql-api-prod', 'addon-pg')
        disque = self.evenements()[0]['scalingo']['disk']
        self.assertEqual(disque['inclus']['bytes'], 160 * GIO)
        self.assertAlmostEqual(disque['pct'], 37825858 / (160 * GIO))

    def test_connexions_max_seulement_quand_le_plan_en_a(self):
        self.base('postgresql-api-prod', 'addon-pg', connexions_max=480)
        self.base('redis-api-prod', 'addon-redis')
        pg, redis = (e['scalingo']['database'] for e in self.evenements())
        self.assertEqual(pg['connexions_max'], 480)
        self.assertNotIn('connexions_max', redis)

    def test_base_sans_taille_des_donnees(self):
        self.base('redis-api-prod', faux_scalingo.ADDON_SANS_STATS)
        base = self.evenements()[0]['scalingo']['database']
        self.assertEqual(base['nom'], 'redis-api-prod')
        self.assertNotIn('data_size', base)

    def test_base_en_erreur_n_arrete_pas_les_autres(self):
        self.base('postgresql-api-prod', 'addon-pg')
        self.base('redis-en-panne', faux_scalingo.ADDON_EN_ERREUR)
        evenements = self.evenements()
        self.assertEqual(len(evenements), 2)
        erreurs = [e for e in evenements if 'error' in e]
        self.assertEqual(len(erreurs), 1)
        self.assertIn('redis-en-panne', erreurs[0]['error']['message'])
        self.assertIn('401', erreurs[0]['error']['message'])

    def test_echange_du_token_refuse(self):
        self.etat['secret']['api_token'] = faux_scalingo.TOKEN_REFUSE
        self.base('postgresql-api-prod', 'addon-pg')
        evenements = self.evenements()
        self.assertEqual(len(evenements), 1)
        self.assertIn('401', evenements[0]['error']['message'])
        self.assertEqual([a for a in self.serveur.appels if a[0] == 'GET'], [])


if __name__ == '__main__':
    unittest.main()
