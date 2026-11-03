"""Lancer depuis la racine du repo : python3 -I -m unittest discover -s docs/observabilite/supervision/tests -v"""
import os, re, unittest

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
CIBLES = ('elastic-agent/', 'docs/observabilite/supervision/agents/')
LIEN = re.compile(r'\]\(([^)\s]+)\)')


def ancre(titre):
    return re.sub(r'[^\w\- ]', '', titre.strip().lower()).replace(' ', '-')


def titres(chemin):
    return {ancre(l.lstrip('#')) for l in open(chemin, encoding='utf-8') if re.match(r'^#{1,6} ', l)}


def documents():
    for dossier, sous_dossiers, fichiers in os.walk(RACINE):
        sous_dossiers[:] = [d for d in sous_dossiers if d not in ('.git', '.superpowers', 'node_modules', 'superpowers')]
        for f in fichiers:
            if f.endswith('.md'):
                yield os.path.join(dossier, f)


class TestLiensVersLesAgents(unittest.TestCase):
    def test_liens_vers_elastic_agent_et_supervision_agents(self):
        for document in documents():
            for lien in LIEN.findall(open(document, encoding='utf-8').read()):
                if lien.startswith(('http', '#', 'mailto:')):
                    continue
                chemin, _, fragment = lien.partition('#')
                cible = os.path.normpath(os.path.join(os.path.dirname(document), chemin))
                if not os.path.relpath(cible, RACINE).replace(os.sep, '/').startswith(CIBLES):
                    continue
                with self.subTest(f'{os.path.relpath(document, RACINE)} → {lien}'):
                    self.assertTrue(os.path.exists(cible), 'fichier absent')
                    if fragment and cible.endswith('.md'):
                        self.assertIn(fragment, titres(cible), 'titre absent')


if __name__ == '__main__':
    unittest.main()
