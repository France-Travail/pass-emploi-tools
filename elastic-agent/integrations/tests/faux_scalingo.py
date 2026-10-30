"""Imite l'API Scalingo (échange de token, token d'addon) et l'API des bases (métriques)."""
import json, re, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN_REFUSE = 'token-refuse'
ADDON_EN_ERREUR = 'addon-en-erreur'
ADDON_SANS_STATS = 'addon-sans-stats'
ADDON_CLUSTER = 'addon-cluster'

METRIQUES = {
    'cpu_usage': 0,
    'memory': {'memory_usage': 156426240, 'swap_usage': 20480, 'memory_limit': 536870912,
               'swap_limit': 536870912, 'max_memory_usage': 222314496, 'max_swap_usage': 0},
    'database_stats': {'data_size': 11044896},
    'real_disk_size': 37825858,
    'instances_metrics': {
        '9f20c633-3507-4585-8cd0-f9ada91165c0': {
            'instance_id': '9f20c633-3507-4585-8cd0-f9ada91165c0',
            'instance_address': '9f20c633.my-db-1234.postgresql.dbs.scalingo.com:31376',
            'real_disk_size': 37825858,
            'cpu': {'usage_in_percents': 12},
            'memory': {'memory_usage': 156426240, 'swap_usage': 20480, 'memory_limit': 536870912,
                       'swap_limit': 536870912, 'max_memory_usage': 222314496, 'max_swap_usage': 0},
        }
    },
}


class Gestionnaire(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def repondre(self, code, corps):
        donnees = json.dumps(corps).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)

    def do_POST(self):
        self.server.appels.append(('POST', self.path))
        if self.path == '/v1/tokens/exchange':
            refuse = TOKEN_REFUSE.encode() in __import__('base64').b64decode(self.headers.get('Authorization', 'Basic ').split(' ', 1)[1] or b'')
            return self.repondre(401, {'error': 'unauthorized'}) if refuse else self.repondre(200, {'token': 'jwt'})
        addon = re.fullmatch(r'/v1/apps/[^/]+/addons/([^/]+)/token', self.path)
        if addon and self.headers.get('Authorization') == 'Bearer jwt':
            if addon.group(1) == ADDON_EN_ERREUR:
                return self.repondre(401, {'error': 'unauthorized'})
            return self.repondre(200, {'addon': {'id': addon.group(1), 'token': 'db-' + addon.group(1)}})
        self.repondre(404, {'error': 'not found'})

    def do_GET(self):
        self.server.appels.append(('GET', self.path))
        base = re.fullmatch(r'/api/databases/([^/]+)/metrics', self.path)
        if base and self.headers.get('Authorization') == 'Bearer db-' + base.group(1):
            if base.group(1) == ADDON_CLUSTER:
                donnees = METRIQUES['instances_metrics']['9f20c633-3507-4585-8cd0-f9ada91165c0']
                auxiliaire = {**donnees, 'instance_id': 'aux-1', 'real_disk_size': 0}
                return self.repondre(200, {**METRIQUES, 'instances_metrics': {'donnees': donnees, 'aux-1': auxiliaire}})
            if base.group(1) == ADDON_SANS_STATS:
                return self.repondre(200, {k: v for k, v in METRIQUES.items() if k != 'database_stats'})
            return self.repondre(200, METRIQUES)
        self.repondre(404, {'error': 'not found'})


def demarrer():
    serveur = ThreadingHTTPServer(('127.0.0.1', 0), Gestionnaire)
    serveur.appels = []
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    return serveur
