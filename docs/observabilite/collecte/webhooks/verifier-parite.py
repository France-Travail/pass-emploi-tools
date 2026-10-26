#!/usr/bin/env python3
"""Parité notifiers Scalingo → Elasticsearch, avant de désactiver les notifiers Mattermost*.

Pour chaque app qui a un notifier « Elastic … », compare son historique Scalingo
(scalingo timeline) aux documents de logs-alertes-scalingo-<env>-default sur la
même période, puis liste le failure store. Lecture seule.

Usage :
    set -a; . ~/.config/pass-emploi/elastic-claude.env; set +a   # ES_URL, ES_API_KEY
    python3 -I verifier-parite.py --depuis 2026-10-19T17:00:00Z [--app pass-emploi-api-prod]
"""
import argparse, base64, datetime, json, os, re, subprocess, sys, time, urllib.request

APPS = {
    'osc-secnum-fr1': ['pass-emploi-api-prod', 'pass-emploi-web-prod', 'pass-emploi-connect-prod', 'pass-emploi-metabase-prod',
                       'pass-emploi-logstash-prod', 'pass-emploi-logstash-process-prod', 'pass-emploi-heartbeat-prod',
                       'pass-emploi-logstash-perf', 'pass-emploi-logstash-process-perf', 'pass-emploi-keycloak-staging'],
    'osc-fr1': ['pass-emploi-api-staging', 'pass-emploi-web-staging', 'pass-emploi-connect-staging'],
}
# Libellé de « scalingo timeline » → préfixes des événements de notifier qui le couvrent.
LIBELLES = {
    'Restart': ['app_restarted'], 'Crash': ['app_crashed'], 'Deployment': ['app_deployed'], 'Scale': ['app_scaled'],
    'Stop': ['app_stopped'], 'Run': ['app_command_ran'], 'Alert': ['app_alert'],
    'New Variable': ['variable_'], 'Edit Variable': ['variable_'], 'Edit Variables': ['variable_'], 'Delete Variable': ['variable_'],
    'New Notifier': ['notifier_'], 'Edit Notifier': ['notifier_'], 'Delete Notifier': ['notifier_'],
}
TOLERANCE = 120


def scalingo(region, app, *args):
    for _ in range(4):
        out = subprocess.run(['scalingo', '--region', region, '--app', app] + list(args), capture_output=True, text=True).stdout
        if out.strip():
            return re.sub(r'\x1b\[[0-9;]*m', '', out)
        time.sleep(5)
    return ''


def selection(region, app):
    sortie = scalingo(region, app, 'notifiers')
    if not sortie:
        return 'injoignable'
    for line in sortie.splitlines():
        m = re.match(r'│ (no-[0-9a-f-]+) │ webhook +│ Elastic[^│]*│ (\w+) +│ (\w+)', line)
        if m:
            if m.group(3) == 'true':
                return 'tous'
            details = scalingo(region, app, 'notifiers-details', m.group(1))
            partie = re.split(r'Selected events', details, 1, flags=re.I)[-1]
            return set(re.findall(r'\b[a-z]+(?:_[a-z]+)+\b', partie))
    return None


def historique(region, app, depuis):
    evenements = []
    for page in range(1, 6):
        for line in scalingo(region, app, 'timeline', '--per-page', '50', '--page', str(page)).splitlines():
            m = re.match(r'\* (\w{3} \w{3} \d{2} \d{4} \d{2}:\d{2}:\d{2}) - (.+?) +- ', line)
            if not m:
                continue
            quand = datetime.datetime.strptime(m.group(1), '%a %b %d %Y %H:%M:%S').replace(tzinfo=datetime.timezone.utc)
            if quand < depuis:
                return evenements
            evenements.append((quand, m.group(2).strip()))
    return evenements


def selectionne(libelle, choix):
    if choix == 'tous':
        return True
    return any(e.startswith(p) for p in LIBELLES.get(libelle, ['?']) for e in choix)


def es(chemin, corps):
    requete = urllib.request.Request(os.environ['ES_URL'].rstrip('/') + chemin, data=json.dumps(corps).encode(), method='POST',
                                     headers={'Authorization': 'ApiKey ' + os.environ['ES_API_KEY'], 'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(requete))


def documents(app, depuis):
    nom, env = app.rsplit('-', 1)
    reponse = es(f'/logs-alertes-scalingo-{env}-default/_search', {
        'size': 500, 'sort': [{'@timestamp': 'asc'}], '_source': ['@timestamp', 'message', 'event.action'],
        'query': {'bool': {'filter': [{'range': {'@timestamp': {'gte': depuis.isoformat()}}}, {'term': {'service.name': nom}}, {'term': {'service.environment': env}}]}}})
    return [(datetime.datetime.fromisoformat(h['_source']['@timestamp'].replace('Z', '+00:00')), h['_source'].get('message', ''))
            for h in reponse['hits']['hits']]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--depuis', required=True, help='début de la période, ISO 8601 UTC')
    parser.add_argument('--app', action='append')
    args = parser.parse_args()
    depuis = datetime.datetime.fromisoformat(args.depuis.replace('Z', '+00:00'))
    ecarts = 0
    for region, apps in APPS.items():
        for app in apps:
            if args.app and app not in args.app:
                continue
            choix = selection(region, app)
            if choix == 'injoignable':
                print(f'== {app} : Scalingo injoignable (relancer avec --app {app})')
                ecarts += 1
                continue
            if choix is None:
                print(f'== {app} : pas de notifier Elastic')
                ecarts += 1
                continue
            attendus = [(q, l) for q, l in historique(region, app, depuis) if selectionne(l, choix)]
            recus = documents(app, depuis)
            libres = list(recus)
            manquants = []
            for quand, libelle in attendus:
                proche = next((d for d in libres if abs((d[0] - quand).total_seconds()) <= TOLERANCE), None)
                if proche:
                    libres.remove(proche)
                else:
                    manquants.append((quand, libelle))
            ecarts += len(manquants) + len(libres)
            print(f'== {app} : {len(attendus)} attendu(s), {len(recus)} reçu(s), {len(manquants)} manquant(s), {len(libres)} en trop')
            for quand, libelle in manquants:
                print(f'   manquant  {quand:%Y-%m-%d %H:%M:%S} {libelle}')
            for quand, message in libres:
                print(f'   en trop   {quand:%Y-%m-%d %H:%M:%S} {message}')
    rejets = es('/logs-alertes-scalingo-*-default::failures/_search', {
        'size': 50, 'sort': [{'@timestamp': 'desc'}], '_source': ['@timestamp', 'document.index', 'error.message'],
        'query': {'range': {'@timestamp': {'gte': depuis.isoformat()}}}})['hits']['hits']
    print(f'== failure store : {len(rejets)} rejet(s)')
    for h in rejets:
        s = h['_source']
        print(f"   {s['@timestamp']} {s.get('document', {}).get('index')} : {s.get('error', {}).get('message')}")
    sys.exit(1 if ecarts or rejets else 0)


if __name__ == '__main__':
    main()
