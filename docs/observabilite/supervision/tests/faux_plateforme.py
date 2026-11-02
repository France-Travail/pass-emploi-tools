import json, os, re, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

CA = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'donnees', 'ca-bases-scalingo.pem')).read()
PLANS = {
    'postgresql': [{'name': 'postgresql-starter-512', 'description': '<li>512MB RAM</li> <li>Includes 10GB disk space</li> <li>Max connections: 30</li>'}],
    'redis': [{'name': 'redis-starter-256', 'description': '<p>256 MB RAM<br> Includes 5 GB disk space<br></p>'}],
}


class Plateforme:
    """Faux Scalingo (API, auth, API des bases) et faux Fleet, sur un seul port local."""

    def __init__(self, mot_de_passe='s3cr3t-test'):
        self.appels = []
        self.integrations = []
        self.refus_fleet = False
        self.apps = {
            'pass-emploi-api-perf': {
                'addons': [{'id': 'ad-pg', 'addon_provider': {'id': 'postgresql'}, 'plan': {'name': 'postgresql-starter-512'}},
                           {'id': 'ad-redis-api', 'addon_provider': {'id': 'redis'}, 'plan': {'name': 'redis-starter-256'}}],
                'variables': {'SCALINGO_POSTGRESQL_URL': f'postgres://pa_back_perf:{mot_de_passe}@pg.exemple:30001/pa_back_perf?sslmode=prefer',
                              'SCALINGO_REDIS_URL': f'redis://user:{mot_de_passe}@redis-api.exemple:30002'},
            },
            'pass-emploi-connect-perf': {
                'addons': [{'id': 'ad-redis-connect', 'addon_provider': {'id': 'redis'}, 'plan': {'name': 'redis-starter-256'}}],
                'variables': {'SCALINGO_REDIS_URL': f'redis://user:{mot_de_passe}@redis-connect.exemple:30003'},
            },
        }
        self.force_tls = {'ad-redis-api': False, 'ad-redis-connect': False, 'ad-pg': False}
        plateforme = self

        class Gestionnaire(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def repondre(self, code, corps, brut=False):
                donnees = (corps if brut else json.dumps(corps)).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(donnees)))
                self.end_headers()
                self.wfile.write(donnees)

            def corps(self):
                taille = int(self.headers.get('Content-Length', 0))
                return json.loads(self.rfile.read(taille) or b'{}')

            def do_GET(self):
                chemin = urlparse(self.path).path
                plateforme.appels.append(('GET', chemin))
                if m := re.fullmatch(r'/v1/apps/([^/]+)/addons', chemin):
                    return self.repondre(200, {'addons': plateforme.apps[m.group(1)]['addons']})
                if m := re.fullmatch(r'/v1/apps/([^/]+)/variables', chemin):
                    return self.repondre(200, {'variables': [{'name': k, 'value': v} for k, v in plateforme.apps[m.group(1)]['variables'].items()]})
                if m := re.fullmatch(r'/v1/addon_providers/([^/]+)/plans', chemin):
                    return self.repondre(200, {'plans': PLANS[m.group(1)]})
                if chemin == '/api/ca_certificate':
                    return self.repondre(200, CA, brut=True)
                if m := re.fullmatch(r'/api/databases/([^/]+)', chemin):
                    statut = 'ACTIVATED' if plateforme.force_tls[m.group(1)] else 'DISABLED'
                    return self.repondre(200, {'database': {'id': m.group(1), 'features': [{'name': 'force-ssl', 'status': statut}]}})
                if chemin == '/api/fleet/package_policies':
                    return self.repondre(200, {'items': plateforme.integrations, 'total': len(plateforme.integrations)})
                self.repondre(404, {'error': 'not found'})

            def do_POST(self):
                chemin = urlparse(self.path).path
                if chemin == '/v1/tokens/exchange':
                    plateforme.appels.append(('POST', chemin))
                    return self.repondre(200, {'token': 'jwt'})
                if m := re.fullmatch(r'/v1/apps/([^/]+)/addons/([^/]+)/token', chemin):
                    plateforme.appels.append(('POST', chemin))
                    return self.repondre(200, {'addon': {'id': m.group(2), 'token': 'db-' + m.group(2)}})
                if chemin == '/api/fleet/package_policies':
                    corps = self.corps()
                    plateforme.appels.append(('POST', chemin, corps['name']))
                    if plateforme.refus_fleet:
                        return self.repondre(400, {'message': 'refus : ' + json.dumps(corps)})
                    plateforme.integrations.append({**corps, 'id': 'id-' + corps['name']})
                    return self.repondre(200, {'item': corps})
                self.repondre(404, {'error': 'not found'})

            def do_PUT(self):
                chemin = urlparse(self.path).path
                if m := re.fullmatch(r'/api/fleet/package_policies/([^/]+)', chemin):
                    corps = self.corps()
                    plateforme.appels.append(('PUT', chemin, corps['name']))
                    if plateforme.refus_fleet:
                        return self.repondre(400, {'message': 'refus : ' + json.dumps(corps)})
                    plateforme.integrations = [{**corps, 'id': m.group(1)} if i['id'] == m.group(1) else i for i in plateforme.integrations]
                    return self.repondre(200, {'item': corps})
                self.repondre(404, {'error': 'not found'})

            def do_DELETE(self):
                plateforme.appels.append(('DELETE', urlparse(self.path).path))
                self.repondre(200, {})

        self.serveur = ThreadingHTTPServer(('127.0.0.1', 0), Gestionnaire)
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.serveur.server_port}'

    def arreter(self):
        self.serveur.shutdown()
