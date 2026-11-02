"""Lecture et écriture des intégrations (package policies) de Fleet, au format simplifié de l'API."""
import json, os, urllib.request


class Fleet:
    def __init__(self, cle):
        self.url = os.environ['KIBANA_URL'].rstrip('/')
        self.cle = cle

    def _appel(self, methode, chemin, corps=None):
        requete = urllib.request.Request(self.url + chemin, method=methode,
                                         data=json.dumps(corps).encode() if corps is not None else None,
                                         headers={'Authorization': 'ApiKey ' + self.cle, 'kbn-xsrf': 'true',
                                                  'Content-Type': 'application/json'})
        with urllib.request.urlopen(requete, timeout=60) as reponse:
            return json.loads(reponse.read() or b'{}')

    def integrations(self, policy):
        items = self._appel('GET', '/api/fleet/package_policies?perPage=1000&format=simplified')['items']
        return {i['name']: i for i in items if policy in (i.get('policy_ids') or [])}

    def toutes(self):
        return {i['name']: i for i in self._appel('GET', '/api/fleet/package_policies?perPage=1000&format=simplified')['items']}

    def creer(self, corps):
        return self._appel('POST', '/api/fleet/package_policies?format=simplified', corps)

    def mettre_a_jour(self, identifiant, corps):
        return self._appel('PUT', f'/api/fleet/package_policies/{identifiant}?format=simplified', corps)
