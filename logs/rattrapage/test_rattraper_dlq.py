"""Tests de rattraper-dlq.py. Lancer : python3 -I -m unittest discover -s logs/rattrapage"""
import importlib.util, json, os, re, unittest

ICI = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('rattraper_dlq', os.path.join(ICI, 'rattraper-dlq.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def hit(id_, document, index='.ds-logs-logstash-dlq-prod-default-2026.11.17-000001'):
    return {'_id': id_, '_index': index, '_source': {'event': {'original': json.dumps(document)}, 'service': {'environment': 'prod'}}}


class TestRoutage(unittest.TestCase):

    def test_le_routage_est_celui_du_pipeline_process(self):
        """Le script recopie le bloc output de pipeline-process.conf : les deux doivent concorder."""
        conf = open(os.path.join(ICI, '..', 'pipeline-process.conf'), encoding='utf-8').read()
        sortie = conf[conf.index('\noutput {'):]
        index = lambda bloc: re.search(r'index\s*=>\s*"([^"]+)"', bloc).group(1).replace('%{[@metadata][env]}', '{env}')
        routeur = sortie.split('else if "router" in [tags] {')[1].split('} else {')[0]
        defaut = sortie.split('} else {')[-1]
        self.assertEqual(index(routeur), r.CIBLE_ROUTEUR)
        self.assertEqual(index(defaut), r.CIBLE_PAR_DEFAUT)

    def test_un_log_du_routeur_va_dans_logs_router(self):
        self.assertEqual(r.cible({'tags': ['router', 'scalingo']}, 'prod'), 'logs-router-prod-default')

    def test_un_log_d_app_va_dans_logs(self):
        self.assertEqual(r.cible({'tags': ['app']}, 'staging'), 'logs-staging-default')
        self.assertEqual(r.cible({}, 'prod'), 'logs-prod-default')


class TestRattrapage(unittest.TestCase):

    def test_le_document_rattrape_est_celui_d_origine(self):
        origine = {'@timestamp': '2026-11-16T21:05:00Z', 'message': 'request_completed', 'tags': ['app']}
        lignes = r.actions_bulk([hit('a1', origine)], 'prod').splitlines()
        self.assertEqual(json.loads(lignes[0]), {'create': {'_index': 'logs-prod-default', '_id': 'a1'}})
        self.assertEqual(json.loads(lignes[1]), origine)

    def test_bilan_d_un_bulk(self):
        reponse = {'items': [{'create': {'_id': 'a', 'status': 201}},
                             {'create': {'_id': 'b', 'status': 409}},
                             {'create': {'_id': 'c', 'status': 400, 'error': {'type': 'document_parsing_exception'}}}]}
        self.assertEqual(r.bilan(reponse), (['a'], ['b'], {'document_parsing_exception': 1}))

    def test_un_second_passage_ne_cree_aucun_doublon(self):
        """Même après un rollover du data stream cible : les id déjà présents ne sont pas réécrits."""
        appels = []

        def faux_appel(methode, chemin, corps=None, ndjson=False):
            appels.append((methode, chemin))
            if chemin.endswith('/_pit?keep_alive=5m'):
                return {'id': 'pit'}
            if chemin == '_search':
                faux_appel.pages -= 1
                return {'hits': {'hits': [dict(hit('a', {'tags': []}), sort=[1]), dict(hit('b', {'tags': ['router']}), sort=[2])] if faux_appel.pages >= 0 else []}}
            if chemin.endswith('/_search'):
                return {'hits': {'hits': [{'_id': 'a'}, {'_id': 'b'}]}}
            if chemin == '_bulk':
                raise AssertionError('aucune écriture attendue : tout est déjà présent')
            return {}
        faux_appel.pages = 1
        r.appel = faux_appel
        self.assertEqual(r.main(['--env', 'prod']), 0)
        self.assertNotIn(('POST', '_bulk'), appels)

    def test_simuler_n_ecrit_rien(self):
        def faux_appel(methode, chemin, corps=None, ndjson=False):
            if chemin.endswith('/_pit?keep_alive=5m'):
                return {'id': 'pit'}
            if chemin == '_search':
                faux_appel.pages -= 1
                return {'hits': {'hits': [dict(hit('a', {'tags': []}), sort=[1])] if faux_appel.pages >= 0 else []}}
            if methode == 'DELETE':
                return {}
            raise AssertionError(f'appel inattendu en simulation : {methode} {chemin}')
        faux_appel.pages = 1
        r.appel = faux_appel
        self.assertEqual(r.main(['--env', 'prod', '--simuler']), 0)


if __name__ == '__main__':
    unittest.main()
