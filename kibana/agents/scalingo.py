"""Lecture des bases dans Scalingo : addons, URL de connexion, plans, Force TLS, autorité de certification."""
import base64, json, os, re, subprocess, urllib.request
from datetime import datetime
from urllib.parse import unquote, urlparse

API = os.environ.get('SCALINGO_API_URL', 'https://api.osc-secnum-fr1.scalingo.com').rstrip('/')
AUTH = os.environ.get('SCALINGO_AUTH_URL', 'https://auth.scalingo.com/v1/tokens/exchange')
DB_API = os.environ.get('SCALINGO_DB_API_URL', 'https://db-api.osc-secnum-fr1.scalingo.com').rstrip('/')
VARIABLE = {'postgresql': 'SCALINGO_POSTGRESQL_URL', 'redis': 'SCALINGO_REDIS_URL'}
SCHEMAS = {'postgresql': ('postgres', 'postgresql'), 'redis': ('redis', 'rediss')}
GIO = 1024 ** 3


class ErreurBase(Exception):
    pass


def _appel(methode, url, jeton=None, basique=None):
    entetes = {'Accept': 'application/json'}
    if jeton:
        entetes['Authorization'] = 'Bearer ' + jeton
    if basique:
        entetes['Authorization'] = 'Basic ' + base64.b64encode((':' + basique).encode()).decode()
    requete = urllib.request.Request(url, method=methode, headers=entetes, data=b'' if methode == 'POST' else None)
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        return reponse.read().decode()


class Scalingo:
    def __init__(self, token):
        self.jwt = json.loads(_appel('POST', AUTH, basique=token))['token']
        self.plans = {}

    def _json(self, chemin):
        return json.loads(_appel('GET', API + chemin, jeton=self.jwt))

    def base(self, app, fournisseur):
        addons = [a for a in self._json(f'/v1/apps/{app}/addons')['addons'] if a['addon_provider']['id'] == fournisseur]
        if len(addons) != 1:
            raise ErreurBase(f'{len(addons)} addon {fournisseur} sur {app}, 1 attendu')
        variables = {v['name']: v['value'] for v in self._json(f'/v1/apps/{app}/variables')['variables']}
        if VARIABLE[fournisseur] not in variables:
            raise ErreurBase(f'variable {VARIABLE[fournisseur]} absente de {app}')
        url = urlparse(variables[VARIABLE[fournisseur]])
        try:
            hote, port, mot_de_passe = url.hostname, url.port, url.password
        except ValueError:
            raise ErreurBase(f'variable {VARIABLE[fournisseur]} de {app} illisible') from None
        if url.scheme not in SCHEMAS[fournisseur]:
            raise ErreurBase(f'variable {VARIABLE[fournisseur]} de {app} : schéma {url.scheme}, attendu {" ou ".join(SCHEMAS[fournisseur])}')
        if not (hote and port and mot_de_passe):
            raise ErreurBase(f'variable {VARIABLE[fournisseur]} de {app} sans hôte, port ou mot de passe')
        addon = addons[0]
        return {'addon_id': addon['id'], 'hote': hote, 'port': port, 'utilisateur': unquote(url.username or ''),
                'mot_de_passe': unquote(mot_de_passe), 'base_de_donnees': url.path.lstrip('/'),
                **self.plan(fournisseur, addon['plan']['name']), 'force_tls': self.force_tls(app, addon['id'])}

    def plan(self, fournisseur, nom):
        if fournisseur not in self.plans:
            self.plans[fournisseur] = {p['name']: p['description'] for p in self._json(f'/v1/addon_providers/{fournisseur}/plans')['plans']}
        description = self.plans[fournisseur].get(nom, '')
        disque = re.search(r'Includes\s+(\d+)\s*GB disk', description)
        if not disque:
            raise ErreurBase(f'disque inclus introuvable dans le plan {nom}')
        connexions = re.search(r'Max connections:\s*(\d+)', description)
        return {'disque_inclus_octets': int(disque.group(1)) * GIO, 'connexions_max': int(connexions.group(1)) if connexions else None}

    def force_tls(self, app, addon_id):
        jeton = json.loads(_appel('POST', f'{API}/v1/apps/{app}/addons/{addon_id}/token', jeton=self.jwt))['addon']['token']
        base = json.loads(_appel('GET', f'{DB_API}/api/databases/{addon_id}', jeton=jeton))['database']
        return any(f.get('name') == 'force-ssl' and f.get('status') == 'ACTIVATED' for f in base.get('features', []))


def autorite_de_certification():
    pem = _appel('GET', DB_API + '/api/ca_certificate')
    fin = subprocess.run(['openssl', 'x509', '-noout', '-enddate'], input=pem, capture_output=True, text=True, check=True).stdout
    return pem, datetime.strptime(fin.strip().removeprefix('notAfter='), '%b %d %H:%M:%S %Y %Z').strftime('%Y-%m-%dT%H:%M:%SZ')
