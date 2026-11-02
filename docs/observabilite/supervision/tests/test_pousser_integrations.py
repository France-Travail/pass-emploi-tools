"""Lancer depuis la racine du repo : python3 -I -m unittest discover -s docs/observabilite/supervision/tests -v
« pousser » et « verifier » contre un faux Scalingo et un faux Fleet locaux (faux_plateforme.py).
"""
import importlib.util, io, json, os, shutil, subprocess, sys, unittest, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import faux_plateforme

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agents', 'generer-integrations.py')
GENERE = os.path.join(os.path.dirname(SCRIPT), 'generated', 'perf')
MOT_DE_PASSE = 's3cr3t-test'


class TestPousserIntegrations(unittest.TestCase):
    def setUp(self):
        self.plateforme = faux_plateforme.Plateforme(MOT_DE_PASSE)
        self.addCleanup(self.plateforme.arreter)

    def lancer(self, *args, sans=()):
        url = self.plateforme.url
        env = {**{k: v for k, v in os.environ.items() if k != 'KIBANA_FLEET_API_KEY'}, 'SCALINGO_API_TOKEN': 'token-scalingo', 'SCALINGO_API_URL': url,
               'SCALINGO_AUTH_URL': url + '/v1/tokens/exchange', 'SCALINGO_DB_API_URL': url,
               'KIBANA_URL': url, 'ES_API_KEY': 'cle-elastic'}
        env = {k: v for k, v in env.items() if k not in sans}
        return subprocess.run([sys.executable, '-I', SCRIPT, *args], capture_output=True, text=True, env=env, timeout=60)

    def ecritures(self, methode):
        return [a[2] for a in self.plateforme.appels if a[0] == methode and len(a) == 3]

    def test_cree_l_integration_absente(self):
        sortie = self.lancer('pousser', '--env', 'perf')
        self.assertEqual(sortie.returncode, 0, sortie.stderr)
        self.assertEqual(sorted(self.ecritures('POST')), sorted(f[:-5] for f in os.listdir(GENERE)))
        policy = json.load(open(os.path.join(os.path.dirname(SCRIPT), 'policies.json')))['perf']
        self.assertTrue(all(i['policy_ids'] == [policy] for i in self.plateforme.integrations))

    def test_met_a_jour_l_integration_existante_par_son_nom(self):
        self.plateforme.integrations.append({'id': 'deja-la', 'name': 'redis-api-perf', 'policy_ids': ['autre'], 'inputs': {}})
        sortie = self.lancer('pousser', '--env', 'perf')
        self.assertEqual(sortie.returncode, 0, sortie.stderr)
        self.assertIn('redis-api-perf', self.ecritures('PUT'))
        self.assertNotIn('redis-api-perf', self.ecritures('POST'))
        self.assertIn(('PUT', '/api/fleet/package_policies/deja-la', 'redis-api-perf'), self.plateforme.appels)

    def test_ne_supprime_jamais(self):
        self.plateforme.integrations.append({'id': 'manuelle', 'name': 'redis-logstash-perf', 'policy_ids': ['x'], 'inputs': {}})
        self.lancer('pousser', '--env', 'perf')
        self.assertEqual([a for a in self.plateforme.appels if a[0] == 'DELETE'], [])
        self.assertIn('redis-logstash-perf', [i['name'] for i in self.plateforme.integrations])

    def test_repere_rempli_depuis_scalingo(self):
        self.lancer('pousser', '--env', 'perf')
        redis = next(i for i in self.plateforme.integrations if i['name'] == 'redis-api-perf')
        self.assertEqual(redis['inputs']['redis-redis/metrics']['vars']['hosts'], ['redis-api.exemple:30002'])
        self.assertEqual(redis['inputs']['redis-redis/metrics']['vars']['password'], MOT_DE_PASSE)
        self.assertNotIn('_avertissement', redis)
        cel = next(i for i in self.plateforme.integrations if i['name'] == 'scalingo-database-stats-perf')
        etat = cel['inputs']['cel-cel']['streams']['cel.cel']['vars']['state']
        self.assertIn('ca_expire_le: "2037-07-29T09:57:55Z"', etat)
        self.assertIn('addon_id: "ad-pg"', etat)
        self.assertIn('disque_inclus_octets: 10737418240', etat)
        self.assertIn('connexions_max: 30', etat)
        self.assertNotIn('@@', json.dumps(self.plateforme.integrations))

    def test_variable_absente_isole_la_base(self):
        del self.plateforme.apps['pass-emploi-connect-perf']['variables']['SCALINGO_REDIS_URL']
        sortie = self.lancer('pousser', '--env', 'perf')
        self.assertEqual(sortie.returncode, 1)
        self.assertIn('redis-connect-perf', sortie.stderr)
        self.assertNotIn('redis-connect-perf', self.ecritures('POST'))
        self.assertIn('redis-api-perf', self.ecritures('POST'))

    def test_mot_de_passe_jamais_affiche(self):
        self.plateforme.refus_fleet = True
        sortie = self.lancer('pousser', '--env', 'perf')
        self.assertNotEqual(sortie.returncode, 0)
        self.assertNotIn(MOT_DE_PASSE, sortie.stdout + sortie.stderr)
        self.assertNotIn('token-scalingo', sortie.stdout + sortie.stderr)

    def test_verifier_ignore_les_reglages_d_un_flux_desactive(self):
        self.lancer('pousser', '--env', 'perf')
        redis = next(i for i in self.plateforme.integrations if i['name'] == 'redis-connect-perf')
        redis['inputs']['redis-redis/metrics']['streams']['redis.key']['vars']['period'] = '10s'
        sortie = self.lancer('verifier', '--env', 'perf')
        self.assertEqual(sortie.returncode, 0, sortie.stdout)

    def test_verifier_signale_un_ecart(self):
        self.lancer('pousser', '--env', 'perf')
        self.plateforme.integrations.append({'id': 'manuelle', 'name': 'redis-logstash-perf', 'policy_ids': ['6eee0d15-68d9-4135-96fe-e20d467f0042'], 'inputs': {}})
        sortie = self.lancer('verifier', '--env', 'perf')
        self.assertEqual(sortie.returncode, 0, sortie.stdout + sortie.stderr)
        self.assertIn('redis-logstash-perf', sortie.stdout)
        cel = next(i for i in self.plateforme.integrations if i['name'] == 'scalingo-database-stats-perf')
        cel['inputs']['cel-cel']['streams']['cel.cel']['vars']['program'] = 'ancien programme'
        sortie = self.lancer('verifier', '--env', 'perf')
        self.assertEqual(sortie.returncode, 1)
        self.assertIn('scalingo-database-stats-perf', sortie.stdout + sortie.stderr)


    def test_cel_existant_garde_toutes_ses_bases_si_une_base_echoue(self):
        self.plateforme.integrations.append({'id': 'cel-la', 'name': 'scalingo-database-stats-perf', 'policy_ids': ['x'], 'inputs': {}})
        del self.plateforme.apps['pass-emploi-connect-perf']['variables']['SCALINGO_REDIS_URL']
        sortie = self.lancer('pousser', '--env', 'perf')
        self.assertEqual(sortie.returncode, 1)
        self.assertNotIn('scalingo-database-stats-perf', self.ecritures('PUT'))
        self.assertIn('scalingo-database-stats-perf', sortie.stderr)

    def test_fichier_genere_sans_base_jamais_pousse(self):
        orphelin = os.path.join(GENERE, 'redis-orpheline-perf.json')
        shutil.copy(os.path.join(GENERE, 'redis-api-perf.json'), orphelin)
        self.addCleanup(os.remove, orphelin)
        sortie = self.lancer('pousser', '--env', 'perf')
        self.assertEqual(sortie.returncode, 1)
        self.assertNotIn('redis-orpheline-perf', self.ecritures('POST') + self.ecritures('PUT'))
        self.assertIn('redis-orpheline-perf', sortie.stderr)


    def redis_connect(self, url):
        self.plateforme.apps['pass-emploi-connect-perf']['variables']['SCALINGO_REDIS_URL'] = url

    def pousse_sans_connect(self, sortie):
        self.assertEqual(sortie.returncode, 1)
        self.assertIn('redis-connect-perf', sortie.stderr)
        self.assertNotIn('redis-connect-perf', self.ecritures('POST'))
        self.assertIn('redis-api-perf', self.ecritures('POST'))

    def test_url_sans_mot_de_passe_isole_la_base(self):
        self.redis_connect('redis://redis-connect.exemple:30003')
        self.pousse_sans_connect(self.lancer('pousser', '--env', 'perf'))

    def test_schema_inattendu_isole_la_base(self):
        self.redis_connect(f'http://user:{MOT_DE_PASSE}@redis-connect.exemple:30003')
        self.pousse_sans_connect(self.lancer('pousser', '--env', 'perf'))

    def test_rediss_accepte(self):
        self.redis_connect(f'rediss://user:{MOT_DE_PASSE}@redis-connect.exemple:30003')
        self.assertEqual(self.lancer('pousser', '--env', 'perf').returncode, 0)
        self.assertIn('redis-connect-perf', self.ecritures('POST'))

    def test_mot_de_passe_encode_est_decode(self):
        self.redis_connect('redis://user:p%40ss@redis-connect.exemple:30003')
        self.assertEqual(self.lancer('pousser', '--env', 'perf').returncode, 0)
        redis = next(i for i in self.plateforme.integrations if i['name'] == 'redis-connect-perf')
        self.assertEqual(redis['inputs']['redis-redis/metrics']['vars']['password'], 'p@ss')

    def test_mot_de_passe_mal_forme_jamais_affiche(self):
        self.redis_connect('redis://:zz9secret#x@redis-connect.exemple:30003')
        sortie = self.lancer('pousser', '--env', 'perf')
        self.pousse_sans_connect(sortie)
        self.assertNotIn('zz9secret', sortie.stdout + sortie.stderr)

    def test_plan_sans_max_connexions(self):
        plans = faux_plateforme.PLANS['postgresql']
        self.addCleanup(faux_plateforme.PLANS.__setitem__, 'postgresql', plans)
        faux_plateforme.PLANS['postgresql'] = [{'name': 'postgresql-starter-512', 'description': '<li>Includes 10GB disk space</li>'}]
        self.assertEqual(self.lancer('pousser', '--env', 'perf').returncode, 0)
        cel = next(i for i in self.plateforme.integrations if i['name'] == 'scalingo-database-stats-perf')
        etat = cel['inputs']['cel-cel']['streams']['cel.cel']['vars']['state']
        self.assertNotIn('connexions_max', etat)
        self.assertNotIn('None', etat)

    def test_variable_manquante_message_clair(self):
        sortie = self.lancer('pousser', '--env', 'perf', sans=('SCALINGO_API_TOKEN',))
        self.assertNotEqual(sortie.returncode, 0)
        self.assertIn('SCALINGO_API_TOKEN', sortie.stderr)
        self.assertNotIn('Traceback', sortie.stderr)

    def test_verifier_signale_une_ligne_ajoutee_a_l_etat_cel(self):
        self.lancer('pousser', '--env', 'perf')
        cel = next(i for i in self.plateforme.integrations if i['name'] == 'scalingo-database-stats-perf')
        cel['inputs']['cel-cel']['streams']['cel.cel']['vars']['state'] += '  - {app: autre, addon_id: "ad-x", nom: redis-autre-perf, disque_inclus_octets: 1}\n'
        self.assertEqual(self.lancer('verifier', '--env', 'perf').returncode, 1)

    def test_verifier_signale_une_autre_policy(self):
        self.lancer('pousser', '--env', 'perf')
        redis = next(i for i in self.plateforme.integrations if i['name'] == 'redis-api-perf')
        redis['policy_ids'] = redis['policy_ids'] + ['autre-policy']
        sortie = self.lancer('verifier', '--env', 'perf')
        self.assertEqual(sortie.returncode, 1)
        self.assertIn('policy_ids', sortie.stdout)

class TestMasquage(unittest.TestCase):
    def test_secret_a_cheval_sur_la_troncature_jamais_affiche(self):
        spec = importlib.util.spec_from_file_location('generer_integrations', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.SECRETS.add(MOT_DE_PASSE)
        erreur = urllib.error.HTTPError('http://fleet', 400, 'Bad Request', {}, io.BytesIO(('x' * 495 + MOT_DE_PASSE).encode()))
        self.assertNotIn(MOT_DE_PASSE[:5], module.masquer(module.detail(erreur)))

if __name__ == '__main__':
    unittest.main()
