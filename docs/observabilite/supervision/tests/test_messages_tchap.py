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

    def setUp(self):
        self.connecteurs = json.load(open(os.path.join(AUTOOPS, 'connecteurs.json'), encoding='utf-8'))['connecteurs']

    def test_chaque_alerte_autoops_a_son_connecteur(self):
        self.assertEqual(sorted(c['alerte'] for c in self.connecteurs), ['M11', 'M12'])

    def test_le_salon_est_un_salon_reference(self):
        for c in self.connecteurs:
            with self.subTest(c['alerte']):
                self.assertIn(c['salon'], SALONS, f"{c['alerte']} : salon absent de workflows/tchap/salons.json")

    def test_l_url_poste_dans_le_salon_choisi(self):
        for c in self.connecteurs:
            with self.subTest(c['alerte']):
                attendue = URL_ENVOI.format(quote(SALONS.get(c['salon'], '?'), safe=''))
                self.assertEqual(c['url'], attendue, f"{c['alerte']} : url et salon ne concordent pas, les modifier ensemble")
                self.assertEqual(c['methode'], 'POST', 'AutoOps ne sait pas produire de txnId : POST sans txnId')

    def test_le_corps_est_un_message_matrix_qui_passe_le_pare_feu(self):
        for c in self.connecteurs:
            with self.subTest(c['alerte']):
                corps = json.load(open(os.path.join(AUTOOPS, c['body']), encoding='utf-8'))
                self.assertEqual(corps.get('msgtype'), 'm.text')
                self.assertEqual(corps.get('format'), 'org.matrix.custom.html')
                self.assertTrue(corps.get('body'), 'texte brut absent')
                self.assertEqual(ecarts_au_pare_feu(corps.get('formatted_body', '')), [])

    def test_les_en_tetes_sont_ceux_de_matrix_sans_le_jeton(self):
        for c in self.connecteurs:
            with self.subTest(c['alerte']):
                self.assertEqual({e['nom']: e['valeur'] for e in c['en_tetes']},
                                 {'Content-Type': 'application/json', 'Authorization': 'Bearer <jeton du bot Tchap>'},
                                 'le jeton du bot est un secret : jamais versionné, à saisir dans AutoOps')

    def test_aucun_corps_orphelin(self):
        cites = {c['body'] for c in self.connecteurs}
        presents = {os.path.basename(p) for p in glob.glob(os.path.join(AUTOOPS, '*-tchap.json'))}
        self.assertEqual(presents, cites)


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
