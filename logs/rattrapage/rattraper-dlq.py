#!/usr/bin/env python3
"""Rattrape les logs restés dans la DLQ : réindexe chaque document de
logs-logstash-dlq-<env>-default dans le data stream où le pipeline « process » l'aurait écrit.
Mode d'emploi : README.md.

Usage : python3 -I rattraper-dlq.py --env prod [--depuis 2026-11-16T21:00:00Z] [--jusqu-a …]
                                       [--simuler] [--supprimer]
Variables : ES_URL, ES_API_KEY (clé avec écriture sur logs-*-default et lecture de la DLQ).
"""
import argparse, collections, json, os, sys, urllib.error, urllib.request

# Routage du bloc output de ../pipeline-process.conf (vérifié par test_rattraper_dlq.py).
CIBLE_ROUTEUR = 'logs-router-{env}-default'
CIBLE_PAR_DEFAUT = 'logs-{env}-default'
DLQ = 'logs-logstash-dlq-{env}-default'
LOT = 500


def cible(document, env):
    """Le data stream du document, comme le pipeline « process » le choisit."""
    return (CIBLE_ROUTEUR if 'router' in (document.get('tags') or []) else CIBLE_PAR_DEFAUT).format(env=env)


def document_d_origine(source_dlq):
    """Le document tel que le pipeline « process » a voulu l'indexer (event.original de la DLQ)."""
    return json.loads(source_dlq['event']['original'])


def actions_bulk(hits, env):
    """Les lignes _bulk qui réindexent les documents de la DLQ : create, avec l'id du document
    de DLQ."""
    lignes = []
    for h in hits:
        lignes.append(json.dumps({'create': {'_index': cible(document_d_origine(h['_source']), env), '_id': h['_id']}}))
        lignes.append(json.dumps(document_d_origine(h['_source']), ensure_ascii=False))
    return '\n'.join(lignes) + '\n'


def bilan(reponse_bulk):
    """(id rattrapés, id déjà présents, {raison : nombre} des refus), d'une réponse _bulk."""
    rattrapes, deja, refus = [], [], collections.Counter()
    for item in reponse_bulk['items']:
        r = item['create']
        if r['status'] == 201:
            rattrapes.append(r['_id'])
        elif r['status'] == 409:
            deja.append(r['_id'])
        else:
            refus[r.get('error', {}).get('type', str(r['status']))] += 1
    return rattrapes, deja, refus


def appel(methode, chemin, corps=None, ndjson=False):
    url = os.environ['ES_URL'].rstrip('/') + '/' + chemin
    donnees = corps.encode() if ndjson else (json.dumps(corps).encode() if corps is not None else None)
    entetes = {'Authorization': 'ApiKey ' + os.environ['ES_API_KEY'],
               'Content-Type': 'application/x-ndjson' if ndjson else 'application/json'}
    with urllib.request.urlopen(urllib.request.Request(url, data=donnees, method=methode, headers=entetes), timeout=120) as r:
        return json.load(r)


def deja_presents(hits, env):
    """Les id de la DLQ déjà présents dans leur data stream cible. Un id n'est unique que dans un
    même index d'un data stream : après un rollover, un create le recréerait (doublon)."""
    par_cible = collections.defaultdict(list)
    for h in hits:
        par_cible[cible(document_d_origine(h['_source']), env)].append(h['_id'])
    presents = set()
    for nom, ids in par_cible.items():
        r = appel('POST', nom + '/_search', {'size': len(ids), '_source': False, 'query': {'ids': {'values': ids}}})
        presents |= {h['_id'] for h in r['hits']['hits']}
    return presents


def documents_de_la_dlq(env, depuis, jusqu_a):
    """Les documents de la DLQ de la période, par lots (point in time + search_after)."""
    pit = appel('POST', DLQ.format(env=env) + '/_pit?keep_alive=5m')['id']
    periode = {k: v for k, v in (('gte', depuis), ('lte', jusqu_a)) if v}
    requete = {'size': LOT, 'pit': {'id': pit, 'keep_alive': '5m'}, 'sort': [{'@timestamp': 'asc'}, {'_shard_doc': 'asc'}],
               'query': {'range': {'@timestamp': periode}} if periode else {'match_all': {}}}
    try:
        while True:
            hits = appel('POST', '_search', requete)['hits']['hits']
            if not hits:
                return
            yield hits
            requete['search_after'] = hits[-1]['sort']
    finally:
        appel('DELETE', '_pit', {'id': pit})


def main(args):
    p = argparse.ArgumentParser(description='Rattrape les logs restés dans la DLQ de Logstash.')
    p.add_argument('--env', required=True, choices=['prod', 'staging', 'perf'])
    p.add_argument('--depuis', help='début de la période, sur @timestamp (date du log)')
    p.add_argument('--jusqu-a', dest='jusqu_a', help='fin de la période')
    p.add_argument('--simuler', action='store_true', help="compter sans rien écrire")
    p.add_argument('--supprimer', action='store_true', help='retirer de la DLQ les documents rattrapés ou déjà présents')
    o = p.parse_args(args)
    total = collections.Counter()
    refus = collections.Counter()
    for hits in documents_de_la_dlq(o.env, o.depuis, o.jusqu_a):
        for h in hits:
            total['lus → ' + cible(document_d_origine(h['_source']), o.env)] += 1
        if o.simuler:
            continue
        presents = deja_presents(hits, o.env)
        a_ecrire = [h for h in hits if h['_id'] not in presents]
        rattrapes, deja, r = bilan(appel('POST', '_bulk', actions_bulk(a_ecrire, o.env), ndjson=True)) if a_ecrire else ([], [], collections.Counter())
        deja += list(presents)
        total['rattrapés'] += len(rattrapes)
        total['déjà présents'] += len(deja)
        refus.update(r)
        if o.supprimer and (rattrapes or deja):
            a_retirer = set(rattrapes) | set(deja)
            lignes = ''.join(json.dumps({'delete': {'_index': h['_index'], '_id': h['_id']}}) + '\n' for h in hits if h['_id'] in a_retirer)
            appel('POST', '_bulk', lignes, ndjson=True)
            total['retirés de la DLQ'] += len(a_retirer)
    for k, v in sorted(total.items()):
        print(f'{k} : {v}')
    for k, v in refus.most_common():
        print(f'refusés ({k}) : {v} — laissés dans la DLQ')
    if o.simuler:
        print('simulation : rien n\'a été écrit')
    return 1 if refus else 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except urllib.error.HTTPError as e:
        sys.exit(f'Elasticsearch a répondu {e.code} : {e.read().decode()[:300]}')
