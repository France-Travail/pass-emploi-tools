"""Messages Tchap : règle du pare-feu et connecteurs AutoOps.

Lancer depuis la racine du repo : python3 -I -m unittest discover -s docs/observabilite/supervision/tests -v

Le pare-feu devant Tchap rejette par une page HTML 403, sans erreur Matrix, un message à
plusieurs liens HTML <a>, ou à un lien <a> et une couleur (cf. workflows/tchap/README.md,
« Pièges »). Les connecteurs AutoOps sont saisis à la main dans la console Elastic Cloud :
ce test garde leur source versionnée cohérente avec les salons référencés.
"""
import glob, json, os, re, unittest
from urllib.parse import quote

SUPERVISION = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTOOPS = os.path.join(SUPERVISION, 'connecteurs', 'autoops')
TCHAP = os.path.join(SUPERVISION, 'workflows', 'tchap')
SALONS = json.load(open(os.path.join(TCHAP, 'salons.json'), encoding='utf-8'))
URL_ENVOI = 'https://matrix.agent.tchap.gouv.fr/_matrix/client/v3/rooms/{}/send/m.room.message'
COULEUR = re.compile(r'data-mx-color|<font\b|<span\b', re.I)
SEVERITES_AUTOOPS = ('Critical', 'High', 'Medium', 'Low', 'Info')


def ecarts_au_pare_feu(html):
    """Les raisons pour lesquelles le pare-feu devant Tchap rejetterait ce HTML (vide : il passe)."""
    liens = len(re.findall(r'<a\b', html, re.I))
    ecarts = []
    if liens > 1:
        ecarts.append(f'{liens} liens <a> (un seul toléré, les suivants en URL brutes)')
    if liens and COULEUR.search(html):
        ecarts.append('un lien <a> et une couleur')
    return ecarts


class TestRegleDuPareFeu(unittest.TestCase):

    def test_un_seul_lien_sans_couleur_passe(self):
        self.assertEqual(ecarts_au_pare_feu('<p><a href="https://x">x</a> puis https://y</p>'), [])

    def test_deux_liens_sont_rejetes(self):
        self.assertTrue(ecarts_au_pare_feu('<a href="https://x">x</a> <a href="https://y">y</a>'))

    def test_un_lien_et_une_couleur_sont_rejetes(self):
        self.assertTrue(ecarts_au_pare_feu('<font data-mx-color="#f00">🚨</font> <a href="https://x">x</a>'))

    def test_une_couleur_sans_lien_passe(self):
        self.assertEqual(ecarts_au_pare_feu('<font data-mx-color="#f00">🚨</font> https://x'), [])


class TestConnecteursAutoOps(unittest.TestCase):
    """connecteurs/autoops/ : un fichier par objet de la console AutoOps (connectors/, filters/).
    Un filtre par sévérité, qui ne contient que ses événements ; un Low passager (snapshot) ne
    doit pas arriver dans Tchap."""

    def setUp(self):
        lire = lambda d: {os.path.basename(p)[:-5]: json.load(open(p, encoding='utf-8')) for p in glob.glob(os.path.join(AUTOOPS, d, '*.json'))}
        self.connecteurs, self.filtres = lire('connectors'), lire('filters')
        self.par_nom = {c['nom']: c for c in self.connecteurs.values()}
        self.tchap = {n: c for n, c in self.connecteurs.items() if c['type'] == 'Webhook'}

    def test_un_filtre_par_severite_autoops(self):
        for n, f in self.filtres.items():
            with self.subTest(n):
                self.assertIn(f['severite'], SEVERITES_AUTOOPS)
                self.assertEqual(n, f['severite'].lower())

    def test_un_filtre_ne_cite_que_des_connecteurs_existants(self):
        for n, f in self.filtres.items():
            with self.subTest(n):
                self.assertLessEqual(set(f['connecteurs']), set(self.par_nom))

    def test_chaque_filtre_a_l_email_et_son_seul_connecteur_tchap(self):
        for n, f in self.filtres.items():
            with self.subTest(n):
                types = sorted(self.par_nom[c]['type'] for c in f['connecteurs'] if c in self.par_nom)
                self.assertEqual(types, ['Email', 'Webhook'])

    def test_chaque_connecteur_tchap_sert_un_seul_filtre(self):
        cites = [c for f in self.filtres.values() for c in f['connecteurs'] if self.par_nom.get(c, {}).get('type') == 'Webhook']
        self.assertEqual(sorted(cites), sorted(c['nom'] for c in self.tchap.values()))

    def test_un_evenement_n_est_que_dans_un_filtre(self):
        tous = [e for f in self.filtres.values() for e in f['evenements']]
        self.assertEqual(len(tous), len(set(tous)))

    def test_low_et_info_attendent_avant_d_envoyer(self):
        """30 min : la file de gestion monte pendant les snapshots d'Elastic Cloud, puis retombe."""
        for n, f in self.filtres.items():
            with self.subTest(n):
                self.assertGreaterEqual(f['delai_minutes'], 30 if f['severite'] in ('Low', 'Info') else 0)

    def test_le_titre_porte_l_emoji_de_sa_severite(self):
        emojis = {'Critical': '🚨 ', 'High': '⚠️ ', 'Medium': '', 'Low': ''}
        for f in self.filtres.values():
            for c in f['connecteurs']:
                if self.par_nom.get(c, {}).get('type') == 'Webhook':
                    with self.subTest(c):
                        self.assertTrue(self.par_nom[c]['corps']['body'].startswith(emojis[f['severite']] + 'AutoOps'))

    def test_l_url_poste_dans_le_salon_choisi(self):
        for n, c in self.tchap.items():
            with self.subTest(n):
                self.assertIn(c['salon'], SALONS, 'salon absent de workflows/tchap/salons.json')
                self.assertEqual(c['url'], URL_ENVOI.format(quote(SALONS.get(c['salon'], '?'), safe='')),
                                 'url et salon ne concordent pas, les modifier ensemble')
                self.assertEqual(c['methode'], 'POST', 'AutoOps ne sait pas produire de txnId : POST sans txnId')

    def test_les_en_tetes_sont_ceux_de_matrix_sans_le_jeton(self):
        for n, c in self.tchap.items():
            with self.subTest(n):
                self.assertEqual({e['nom']: e['valeur'] for e in c['en_tetes']},
                                 {'Content-Type': 'application/json', 'Authorization': 'Bearer <jeton du bot Tchap>'},
                                 'le jeton du bot est un secret : jamais versionné, à saisir dans AutoOps')

    def test_le_corps_est_la_derniere_cle_pour_se_copier_d_un_bloc(self):
        for n, c in self.tchap.items():
            with self.subTest(n):
                self.assertEqual(list(c)[-1], 'corps')

    def test_le_corps_est_un_message_matrix_qui_passe_le_pare_feu(self):
        for n, c in self.tchap.items():
            with self.subTest(n):
                self.assertEqual(c['corps'].get('msgtype'), 'm.text')
                self.assertEqual(c['corps'].get('format'), 'org.matrix.custom.html')
                self.assertTrue(c['corps'].get('body'), 'texte brut absent')
                self.assertEqual(ecarts_au_pare_feu(c['corps'].get('formatted_body', '')), [])

    def test_l_email_ne_versionne_pas_les_adresses(self):
        for c in self.connecteurs.values():
            if c['type'] == 'Email':
                self.assertEqual(c['destinataires'], ["<adresses de l'équipe>"])


class TestWorkflowsTchap(unittest.TestCase):
    """Plus strict que le pare-feu : la règle porte sur tout le gabarit HTML d'un Workflow,
    qui réunit les messages de toutes ses règles, et pas sur un seul message."""

    def test_les_gabarits_html_passent_le_pare_feu(self):
        fichiers = sorted(glob.glob(os.path.join(TCHAP, 'generated', '*.console')) + [os.path.join(TCHAP, 'tchap-client.console')]
                          + glob.glob(os.path.join(TCHAP, 'modeles', '**', '*.liquid'), recursive=True))
        self.assertTrue(fichiers)
        for fichier in fichiers:
            with self.subTest(os.path.relpath(fichier, TCHAP)):
                texte = open(fichier, encoding='utf-8').read()
                gabarits = re.findall(r'^\s*html: (.*)$', texte, re.M) if fichier.endswith('.console') else [texte]
                for gabarit in gabarits:
                    self.assertEqual(ecarts_au_pare_feu(gabarit), [])


if __name__ == '__main__':
    unittest.main()
