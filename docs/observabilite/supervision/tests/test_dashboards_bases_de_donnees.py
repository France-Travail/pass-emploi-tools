"""Lancer depuis la racine du repo : python3 -I -m unittest discover -s docs/observabilite/supervision/tests -v"""
import json, os, unittest

FICHIER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboards', 'dashboard-bases-de-donnees.ndjson')


def dashboards():
    for ligne in open(FICHIER):
        objet = json.loads(ligne)
        attributs = objet['attributes']
        requetes = {p['embeddableConfig']['attributes']['title']: p['embeddableConfig']['attributes']['state']['query']['esql']
                    for p in json.loads(attributs['panelsJSON']) if p['type'] == 'vis'}
        controles = {c['config']['variable_name']: c['config'] for c in attributs['pinned_panels']['panels'].values()}
        yield attributs['title'], attributs, requetes, controles


class TestDashboardsBasesDeDonnees(unittest.TestCase):
    def test_ouverts_sur_trois_heures(self):
        for titre, attributs, _, _ in dashboards():
            with self.subTest(titre):
                self.assertTrue(attributs['timeRestore'])
                self.assertEqual(attributs['timeFrom'], 'now-3h')

    def test_une_seule_base_ou_un_seul_environnement_a_la_fois(self):
        for titre, _, _, controles in dashboards():
            for nom, config in controles.items():
                with self.subTest(f'{titre} / {nom}'):
                    self.assertTrue(config['single_select'])

    def test_panneau_des_erreurs_de_collecte(self):
        for titre, _, requetes, _ in dashboards():
            with self.subTest(titre):
                self.assertTrue(any(t.startswith('Erreurs de collecte') for t in requetes))

    def test_compteurs_remis_a_zero_jamais_compares_entre_segments(self):
        for titre, _, requetes, _ in dashboards():
            for panneau, requete in requetes.items():
                if any(source in requete for source in ('postgresql_statements', 'postgresql_index_stats', 'postgresql_table_stats')) and ') - MIN(' in requete:
                    with self.subTest(f'{titre} / {panneau}'):
                        self.assertIn('stats_reset', requete)
                with self.subTest(f'{titre} / {panneau} (Redis)'):
                    self.assertNotIn('MIN(TO_LONG', requete)

    def test_connexions_de_tout_le_serveur(self):
        for titre, _, requetes, _ in dashboards():
            for panneau, requete in requetes.items():
                if 'number_of_backends' in requete:
                    with self.subTest(f'{titre} / {panneau}'):
                        self.assertIn('SUM(postgresql.database.number_of_backends) BY @timestamp', requete)

    def test_selecteur_table_alimente_a_chaud(self):
        for titre, _, requetes, controles in dashboards():
            if 'PostgreSQL' not in titre:
                continue
            self.assertEqual(controles['table']['control_type'], 'VALUES_FROM_QUERY')
            self.assertIn('postgresql_table_stats', controles['table']['esql_query'])
            for panneau, requete in requetes.items():
                if 'sql.metrics.requete' in requete or 'traces-apm' in requete:
                    with self.subTest(panneau):
                        self.assertIn('?table', requete)

    def test_texte_sql_de_l_apm_jamais_affiche(self):
        for titre, _, requetes, _ in dashboards():
            for panneau, requete in requetes.items():
                with self.subTest(f'{titre} / {panneau}'):
                    self.assertNotIn('span.db.statement', requete)

    def test_encadre_investiguer_en_tete(self):
        for ligne in open(FICHIER):
            attributs = json.loads(ligne)['attributes']
            premier = min(json.loads(attributs['panelsJSON']), key=lambda p: (p['gridData']['y'], p['gridData']['x']))
            with self.subTest(attributs['title']):
                self.assertEqual(premier['type'], 'markdown')
                contenu = premier['embeddableConfig']['content']
                self.assertTrue(contenu.startswith('**Investiguer**'))
                self.assertLessEqual(sum(1 for l in contenu.splitlines() if l.lstrip()[:2] in ('- ', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')), 10)

    def test_panneaux_d_investigation_presents(self):
        attendus = {
            'PostgreSQL': ['Sélectivité des index', 'Hygiène des index', 'Entretien des tables', 'Verrous et transactions longues',
                           'Swap des nœuds de données', 'Certificat de l\'autorité'],
            'Redis': ['Swap des nœuds de données', 'Certificat de l\'autorité'],
        }
        for titre, _, requetes, _ in dashboards():
            for type_de_base, panneaux in attendus.items():
                if type_de_base in titre:
                    for panneau in panneaux:
                        with self.subTest(f'{titre} / {panneau}'):
                            self.assertIn(panneau, requetes)

    @unittest.skipUnless(os.environ.get('MOTS_INTERDITS'), 'MOTS_INTERDITS absent : mots propres au client du support d\'audit, fournis hors du repo')
    def test_aucune_donnee_du_support(self):
        contenu = open(FICHIER).read().lower()
        for mot in filter(None, (m.strip().lower() for m in os.environ['MOTS_INTERDITS'].split(','))):
            with self.subTest(mot):
                self.assertNotIn(mot, contenu)


if __name__ == '__main__':
    unittest.main()
