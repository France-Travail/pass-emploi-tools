"""Génère les dashboards « [Pass Emploi] Bases de données » (PostgreSQL et Redis) dans dashboard-bases-de-donnees.ndjson.

Usage :
  python3 -I generer-dashboards-bases.py              génère, sans réseau (colonnes lues dans modeles/bases/colonnes.json)
  python3 -I generer-dashboards-bases.py --valider    exécute chaque requête contre Elasticsearch (ES_URL, ES_API_KEY)
                                                      et compare ses colonnes au catalogue
  python3 -I generer-dashboards-bases.py --valider --sauf <motif>   sans interroger les index dont le nom contient le motif
Sources : ../agents/bases.json (sélecteurs « Base »), modeles/bases/ (encadrés, colonnes).
"""
import argparse, hashlib, json, os, sys, urllib.error, urllib.request, uuid

ICI = os.path.dirname(os.path.abspath(__file__))
ID_PG = '66b0c0ac-d034-489b-ab0a-7b07539074ff'
ID_REDIS = '86b702ee-b9c7-4344-91ef-a10a50405ed5'
TAG = '6f50f54f-9d1d-4f0b-a096-7916343f976e'
TRANCHE = 'tranche = BUCKET(@timestamp, 50, ?_tstart, ?_tend)'
BASE = 'MV_CONTAINS(?base, labels.base)'
BASE_INSTANCE = 'MV_CONTAINS(?base, scalingo.database.nom)'
CATALOGUE = os.path.join(ICI, 'modeles', 'bases', 'colonnes.json')
COLONNES = json.load(open(CATALOGUE, encoding='utf-8'))
REQUETES = {}
DASHBOARD_EN_COURS = []


def bases(type_):
    """Noms des bases de ce type, par environnement, dans l'ordre de ../agents/bases.json : [(env, app, nom)]."""
    resultat = []
    for env, apps in json.load(open(os.path.join(ICI, '..', 'agents', 'bases.json'), encoding='utf-8')).items():
        for app, types in apps.items():
            for t in types:
                if (t == 'postgresql') == (type_ == 'postgresql'):
                    resultat.append((env, app, f"{type_}-{app.removeprefix('pass-emploi-').removesuffix('-' + env)}-{env}"))
    return resultat


def modele(nom):
    return open(os.path.join(ICI, 'modeles', 'bases', nom), encoding='utf-8').read().rstrip('\n')


def colonnes(titre):
    cle = DASHBOARD_EN_COURS[-1] + ' / ' + titre
    if cle not in COLONNES:
        sys.exit(f'{cle} : colonnes absentes de {CATALOGUE} (lancer --valider pour les relever)')
    return [tuple(c) for c in COLONNES[cle]]


LIBELLES = {
    'requete': 'Requête', 'span.name': 'Requête SQL tronquée (opération et table)', 'moyenne_ms': 'Moyenne (ms)',
    'p95_ms': 'P95 (ms)', 'p99_ms': 'P99 (ms)', 'appels': 'Appels', 'temps_total_s': 'Temps total (s)',
    'sql.metrics.table': 'Table', 'sql.metrics.index': 'Index', 'utilisations': 'Utilisations',
    'taille_mo': 'Taille (Mo)', 'derniere_remise_a_zero': 'Depuis', 'lignes_lues_sans_index': 'Lignes lues sans index',
    'lectures_sans_index': 'Lectures sans index', 'lectures_par_index': 'Lectures par index', 'lignes': 'Lignes',
    'derniere': 'Dernière', 'scans': 'Scans', 'lignes_par_scan': 'Lignes lues par scan', 'part_table_par_scan': 'Part de la table par scan (%)', 'part_recuperee': 'Part récupérée (%)', 'index_de_la_table': 'Index', 'taille_index_mo': 'Index (Mo)', 'taille_table_mo': 'Table (Mo)', 'poids_index_table': 'Index / table', 'probleme': 'Problème', 'part_lignes_mortes': 'Lignes mortes (%)', 'part_modifiee': 'Modifiée depuis ANALYZE (%)', 'sql.metrics.last_autoanalyze': 'Dernier autoanalyze', 'sql.metrics.last_analyze': 'Dernier ANALYZE', 'sql.metrics.last_autovacuum': 'Dernier autovacuum', 'sql.metrics.last_vacuum': 'Dernier VACUUM', 'sql.metrics.n_live_tup': 'Lignes', 'expire_le': 'Expire le', 'jours_restants': 'Jours restants', 'statistiques': 'Statistiques', 'depuis': 'Depuis', 'component.id': 'Intégration', 'erreur': 'Erreur', 'occurrences': 'Occurrences',
    'base': 'Base', 'politique': 'Politique mémoire', 'maxmemory': 'maxmemory',
}


def type_lens(es_type):
    return {'date': 'date', 'keyword': 'string', 'text': 'string', 'boolean': 'boolean'}.get(es_type, 'number')


def panneau(titre, description, esql, params, vis, x, y, w, h, abscisse=None, series=(), decoupe=None, borne=None):
    couche = str(uuid.uuid5(uuid.NAMESPACE_URL, titre))
    REQUETES[DASHBOARD_EN_COURS[-1] + ' / ' + titre] = (esql, params)
    cols = colonnes(titre)
    index = esql.split('\n')[0].replace('FROM ', '').strip()
    id_vue = hashlib.sha256(index.encode()).hexdigest()
    lens_cols = [{'columnId': n, 'fieldName': n, 'label': LIBELLES.get(n, n), 'customLabel': n in LIBELLES,
                  'meta': {'type': type_lens(t), 'esType': t},
                  **({'inMetricDimension': True} if n in series else {})} for n, t in cols]
    if vis == 'lnsXY':
        visualisation = {
            'legend': {'isVisible': True, 'position': 'right'}, 'valueLabels': 'hide', 'fittingFunction': 'Linear',
            'axisTitlesVisibilitySettings': {'x': True, 'yLeft': True, 'yRight': True},
            'tickLabelsVisibilitySettings': {'x': True, 'yLeft': True, 'yRight': True},
            'labelsOrientation': {'x': 0, 'yLeft': 0, 'yRight': 0},
            'gridlinesVisibilitySettings': {'x': True, 'yLeft': True, 'yRight': True},
            'preferredSeriesType': 'line',
            'layers': [{'layerId': couche, 'seriesType': 'line', 'xAccessor': abscisse,
                        'splitAccessors': [decoupe] if decoupe else [], 'accessors': list(series),
                        'layerType': 'data'}],
        }
        if borne:
            visualisation['yLeftExtent'] = {'mode': 'custom', 'lowerBound': 0, 'upperBound': borne}
    else:
        texte_long = {'requete', 'span.name'}
        visualisation = {'columns': [{'columnId': n, 'isTransposed': False, 'isMetric': type_lens(t) == 'number',
                                      **({'width': 620} if n in texte_long else {})}
                                     for n, t in cols],
                         'layerId': couche, 'layerType': 'data', 'showRowNumbers': True,
                         'rowHeight': 'custom', 'rowHeightLines': 2}
    vue = {'id': id_vue, 'title': index, 'timeFieldName': '@timestamp', 'sourceFilters': [], 'type': 'esql',
           'fieldFormats': {}, 'runtimeFieldMap': {}, 'allowNoIndex': False, 'name': index,
           'allowHidden': False, 'managed': False}
    indice = str(uuid.uuid5(uuid.NAMESPACE_URL, 'panneau ' + titre))
    return {
        'type': 'vis',
        'embeddableConfig': {
            'attributes': {
                'title': titre, 'references': [],
                'state': {
                    'datasourceStates': {'textBased': {
                        'layers': {couche: {'index': id_vue, 'query': {'esql': esql}, 'columns': lens_cols,
                                            'timeField': '@timestamp'}},
                        'indexPatternRefs': [{'id': id_vue, 'title': index, 'timeField': '@timestamp'}]}},
                    'filters': [], 'query': {'esql': esql}, 'visualization': visualisation,
                    'adHocDataViews': {id_vue: vue}, 'needsRefresh': False},
                'visualizationType': vis, 'version': 2},
            'title': titre, 'description': description, 'drilldowns': []},
        'panelIndex': indice,
        'gridData': {'x': x, 'y': y, 'w': w, 'h': h, 'i': indice},
    }


def controle(*definitions):
    def config(nom_variable, titre, valeurs, defaut):
        commun = {'selected_options': defaut, 'single_select': True, 'title': titre, 'variable_name': nom_variable}
        if isinstance(valeurs, str):
            return {**commun, 'control_type': 'VALUES_FROM_QUERY', 'esql_query': valeurs, 'variable_type': 'values'}
        return {**commun, 'control_type': 'STATIC_VALUES', 'available_options': valeurs, 'variable_type': 'multi_values'}
    return {'panels': {str(uuid.uuid5(uuid.NAMESPACE_URL, 'controle ' + definition[0])): {
        'config': config(*definition), 'grow': False, 'order': ordre, 'type': 'esql_control', 'width': 'medium'}
        for ordre, definition in enumerate(definitions)}}


TABLES_A_CHAUD = ('FROM metrics-sql.postgresql_table_stats-*\n| WHERE @timestamp > NOW() - 1 day\n'
                  '| STATS tables = VALUES(sql.metrics.table)\n| EVAL table = MV_APPEND("toutes", MV_SORT(tables))\n'
                  '| MV_EXPAND table\n| KEEP table')


def dashboard(id_, titre, description, panneaux, controles):
    return {
        'attributes': {
            'description': description,
            'kibanaSavedObjectMeta': {'searchSourceJSON': '{"query":{"query":"","language":"kuery"}}'},
            'optionsJSON': json.dumps({'autoApplyFilters': True, 'hidePanelBorders': False, 'hidePanelTitles': False,
                                       'syncColors': True, 'syncCursor': True, 'syncTooltips': True,
                                       'useMargins': True}),
            'panelsJSON': json.dumps(panneaux, ensure_ascii=False),
            'pinned_panels': controles, 'timeRestore': True, 'timeFrom': 'now-3h', 'timeTo': 'now',
            'refreshInterval': {'pause': True, 'value': 60000}, 'title': titre},
        'coreMigrationVersion': '8.8.0', 'id': id_, 'managed': False,
        'references': [{'id': TAG, 'name': 'tag-ref-' + TAG, 'type': 'tag'}],
        'type': 'dashboard', 'typeMigrationVersion': '10.3.0'}


def encadre(contenu, hauteur, x=0, y=0, largeur=48):
    indice = str(uuid.uuid5(uuid.NAMESPACE_URL, 'encadre ' + contenu[:40]))
    return {'type': 'markdown', 'embeddableConfig': {'content': contenu, 'settings': {'open_links_in_new_tab': True}},
            'panelIndex': indice, 'gridData': {'x': x, 'y': y, 'w': largeur, 'h': hauteur, 'i': indice}}


def sous_l_encadre(encadre_, panneaux):
    for panneau_ in panneaux:
        panneau_['gridData']['y'] += encadre_['gridData']['h']
    return [encadre_] + panneaux


def erreurs_de_collecte(composants, y, p):
    filtre = ' OR '.join(f'component.id LIKE "{c}*"' for c in composants)
    return panneau('Erreurs de collecte', 'Erreurs de l\'Elastic Agent sur ces intégrations : une base qui ne répond plus (mot de passe changé, certificat, réseau) se voit ici, pas comme une base sans activité.',
                   f'FROM logs-elastic_agent.metricbeat-*, logs-elastic_agent.filebeat-*\n| WHERE log.level == "error" AND ({filtre})\n| EVAL erreur = SUBSTRING(message, 1, 300)\n| STATS occurrences = COUNT(*), derniere = MAX(@timestamp) BY component.id, erreur\n| SORT derniere DESC\n| KEEP derniere, component.id, erreur, occurrences\n| LIMIT 20',
                   p, 'lnsDatatable', 0, y, 48, 10)


FILTRE_TABLE_REQUETE = ('(?table == "toutes" OR LOCATE(sql.metrics.requete, CONCAT("\\"", ?table, "\\"")) > 0'
                        ' OR LOCATE(sql.metrics.requete, CONCAT(" ", ?table, " ")) > 0'
                        ' OR LOCATE(sql.metrics.requete, CONCAT(" ", ?table, ",")) > 0)')


def postgresql():
    return [encadre(modele('investiguer-postgresql-infrastructure.md'), 9, largeur=36),
            encadre(modele('investiguer-postgresql-requetes.md'), 16, y=56, largeur=36)] + panneaux_postgresql()


def panneaux_postgresql():
    p = {'base': json.dumps(bases('postgresql')[0][2]), 'table': '"toutes"'}
    instances = f'FROM logs-scalingo.database_stats-*\n| WHERE scalingo.database.nom LIKE "postgresql-*" AND scalingo.database.role == "donnees" AND {BASE_INSTANCE}'
    requetes = ('FROM metrics-sql.postgresql_statements-*\n'
                f'| WHERE {BASE} AND NOT sql.metrics.requete LIKE "COPY *" AND {FILTRE_TABLE_REQUETE}\n'
                '| STATS appels = MAX(sql.metrics.calls) - MIN(sql.metrics.calls), temps_ms = MAX(TO_DOUBLE(sql.metrics.total_exec_time_ms)) - MIN(TO_DOUBLE(sql.metrics.total_exec_time_ms)), requete = MAX(sql.metrics.requete) BY sql.metrics.queryid, sql.metrics.stats_reset\n'
                '| STATS appels = SUM(appels), temps_ms = SUM(temps_ms), requete = MAX(requete) BY sql.metrics.queryid\n'
                '| WHERE appels > 0 AND temps_ms >= 0\n'
                '| EVAL moyenne_ms = ROUND(temps_ms / appels, 1), temps_total_s = ROUND(temps_ms / 1000, 0)\n')
    return [
        panneau('Mémoire des nœuds de données (% de la limite)', 'Mémoire du conteneur de chaque nœud de données, rapportée à sa limite (API des bases Scalingo). 100 % la nuit est normal : le cache des sauvegardes et exports compte dans cette mémoire et se libère au besoin. Le signal d\'alarme est le swap qui monte (panneau Swap).',
                instances + f'\n| STATS memoire_pct = MAX(scalingo.memory.pct) * 100 BY {TRANCHE}, scalingo.database.instance',
                p, 'lnsXY', 0, 9, 16, 12, 'tranche', ['memoire_pct'], 'scalingo.database.instance', 100),
        panneau('Disque des nœuds de données (% du quota du plan)', 'Place sur disque rapportée au disque inclus dans le plan (prod : 160 Go par nœud ; perf : 10 Go). Quota facturé au-delà, pas une limite qui bloque la base.',
                instances + f'\n| STATS disque_pct = MAX(scalingo.disk.pct) * 100 BY {TRANCHE}, scalingo.database.instance',
                p, 'lnsXY', 16, 9, 16, 12, 'tranche', ['disque_pct'], 'scalingo.database.instance', 100),
        panneau('CPU des nœuds de données (%)', 'CPU du conteneur de chaque nœud de données (API des bases Scalingo).',
                instances + f'\n| STATS cpu_pct = MAX(scalingo.cpu.usage) BY {TRANCHE}, scalingo.database.instance',
                p, 'lnsXY', 32, 9, 16, 12, 'tranche', ['cpu_pct'], 'scalingo.database.instance'),
        panneau('Connexions ouvertes (max du plan : 480 en prod, 30 en perf)', 'Connexions de tout le serveur (base de l\'app et bases système), au relevé le plus chargé de chaque tranche : c\'est ce total que borne le plan.',
                f'FROM metrics-postgresql.database-*\n| WHERE {BASE}\n| STATS serveur = SUM(postgresql.database.number_of_backends) BY @timestamp\n| STATS connexions = MAX(serveur) BY {TRANCHE}',
                p, 'lnsXY', 16, 21, 16, 12, 'tranche', ['connexions']),
        panneau('Connexions en train d\'exécuter une requête', 'Connexions actives ou ouvertes dans une transaction (idle in transaction), au relevé le plus chargé de chaque tranche. Elles grimpent quand les requêtes s\'empilent ; le total des connexions, lui, reste plat.',
                f'FROM metrics-postgresql.activity-*\n| WHERE {BASE} AND postgresql.activity.state IN ("active", "idle in transaction")\n| STATS n = COUNT(*) BY @timestamp, postgresql.activity.state\n| STATS connexions = MAX(n) BY {TRANCHE}, postgresql.activity.state',
                p, 'lnsXY', 32, 21, 16, 12, 'tranche', ['connexions'], 'postgresql.activity.state'),
        panneau('Requêtes les plus lentes, en moyenne (pg_stat_statements)', 'Temps moyen par appel sur la période (écart entre relevés, par segment entre deux remises à zéro), relevé toutes les 10 min : choisir au moins 20 min. Exports COPY exclus.',
                requetes + '| SORT moyenne_ms DESC\n| KEEP requete, moyenne_ms, appels, temps_total_s\n| LIMIT 20',
                p, 'lnsDatatable', 0, 72, 24, 16),
        panneau('Requêtes SQL les plus lentes, P95 et P99 (APM, par table)', 'Centiles des requêtes SQL de l\'api vues par l\'APM, regroupées par le résumé de l\'agent APM (opération et première table). Le texte complet n\'est pas affiché ici : celui de l\'APM contient les valeurs en clair. La requête complète, sans valeurs, est dans le tableau « Requêtes les plus lentes, en moyenne (pg_stat_statements) » : choisir la table dans le sélecteur « Table » en haut du dashboard, les deux tableaux n\'affichent alors que les requêtes de cette table. Traces conservées 21 j.',
                'FROM traces-apm*\n| WHERE span.subtype == "postgresql" AND service.name LIKE "pass-emploi-api-*" AND MV_CONTAINS(?base, CASE(' + ', '.join(f'service.name == "{app}", "{nom}"' for _, app, nom in bases('postgresql')) + ', "autre"))\n| EVAL table_apm = REPLACE(REPLACE(MV_LAST(SPLIT(span.name, " ")), "\\"", ""), ",", "")\n| WHERE ?table == "toutes" OR table_apm == ?table\n| STATS p95_ms = ROUND(PERCENTILE(span.duration.us, 95) / 1000, 1), p99_ms = ROUND(PERCENTILE(span.duration.us, 99) / 1000, 1), appels = COUNT(*) BY span.name\n| SORT p95_ms DESC\n| KEEP span.name, p95_ms, p99_ms, appels\n| LIMIT 20',
                p, 'lnsDatatable', 24, 72, 24, 16),
        panneau('Requêtes les plus appelées', 'Nombre d\'appels sur la période (écart entre relevés), relevé toutes les 10 min.',
                requetes + '| SORT appels DESC\n| KEEP requete, appels, moyenne_ms, temps_total_s\n| LIMIT 20',
                p, 'lnsDatatable', 0, 88, 24, 16),
        panneau('Tables les plus lues sans index', 'Lignes parcourues sans index sur la période (seq_tup_read) : candidates à un index. Relevé toutes les 10 min.',
                f'FROM metrics-sql.postgresql_table_stats-*\n| WHERE {BASE}\n| STATS lignes_lues_sans_index = MAX(sql.metrics.seq_tup_read) - MIN(sql.metrics.seq_tup_read), lectures_sans_index = MAX(sql.metrics.seq_scan) - MIN(sql.metrics.seq_scan), lectures_par_index = MAX(sql.metrics.idx_scan) - MIN(sql.metrics.idx_scan), lignes = MAX(sql.metrics.n_live_tup) BY sql.metrics.table, sql.metrics.stats_reset\n| STATS lignes_lues_sans_index = SUM(lignes_lues_sans_index), lectures_sans_index = SUM(lectures_sans_index), lectures_par_index = SUM(lectures_par_index), lignes = MAX(lignes) BY sql.metrics.table\n| WHERE lignes_lues_sans_index > 0\n| SORT lignes_lues_sans_index DESC\n| KEEP sql.metrics.table, lignes_lues_sans_index, lectures_sans_index, lectures_par_index, lignes\n| LIMIT 20',
                p, 'lnsDatatable', 24, 88, 24, 16),
        panneau('Index jamais utilisés (hors contraintes)', 'Index sans aucune utilisation depuis la dernière remise à zéro des statistiques (colonne « Depuis » : une date récente, après une bascule de nœud ou un redémarrage, ne prouve rien), qui ne garantissent ni clé primaire ni unicité : candidats à la suppression, à vérifier avant.',
                f'FROM metrics-sql.postgresql_index_stats-*\n| WHERE {BASE} AND sql.metrics.contrainte == false\n| INLINE STATS derniere_remise_a_zero = MAX(sql.metrics.stats_reset)\n| WHERE sql.metrics.stats_reset == derniere_remise_a_zero\n| STATS utilisations = MAX(sql.metrics.idx_scan), taille_mo = ROUND(MAX(sql.metrics.taille_octets) / 1048576.0, 1) BY sql.metrics.table, sql.metrics.index, derniere_remise_a_zero\n| WHERE utilisations == 0\n| SORT taille_mo DESC\n| KEEP sql.metrics.table, sql.metrics.index, taille_mo, derniere_remise_a_zero',
                p, 'lnsDatatable', 0, 104, 48, 10),
        panneau('Sélectivité des index', 'Sur la période (écarts entre relevés, par segment de remise à zéro) : lignes lues par scan, part de la table lue à chaque scan, part des lignes lues réellement récupérées. Un index qui lit une grande part de sa table à chaque scan est peu sélectif.',
                f'FROM metrics-sql.postgresql_index_stats-*\n| WHERE {BASE}\n| STATS scans = MAX(sql.metrics.idx_scan) - MIN(sql.metrics.idx_scan), lues = MAX(sql.metrics.idx_tup_read) - MIN(sql.metrics.idx_tup_read), recuperees = MAX(sql.metrics.idx_tup_fetch) - MIN(sql.metrics.idx_tup_fetch), lignes = MAX(sql.metrics.lignes_table) BY sql.metrics.table, sql.metrics.index, sql.metrics.stats_reset\n| STATS scans = SUM(scans), lues = SUM(lues), recuperees = SUM(recuperees), lignes = MAX(lignes) BY sql.metrics.table, sql.metrics.index\n| WHERE scans > 0\n| EVAL lignes_par_scan = ROUND(lues / scans, 0), part_table_par_scan = CASE(lignes > 0, ROUND(lues * 100.0 / scans / lignes, 1), null), part_recuperee = CASE(lues > 0, ROUND(recuperees * 100.0 / lues, 1), null)\n| SORT part_table_par_scan DESC\n| KEEP sql.metrics.table, sql.metrics.index, scans, lignes_par_scan, part_table_par_scan, part_recuperee\n| LIMIT 20',
                p, 'lnsDatatable', 0, 114, 48, 14),
        panneau('Hygiène des index', 'Par table, au dernier relevé (toutes les heures) : nombre d\'index, poids des index face à la table, écritures depuis la remise à zéro. Beaucoup d\'index sur une table très écrite, ou plus lourds qu\'elle : à alléger.',
                f'FROM metrics-sql.postgresql_index_hygiene-*\n| WHERE {BASE}\n| INLINE STATS dernier = MAX(@timestamp)\n| WHERE @timestamp == dernier\n| STATS index_de_la_table = MAX(sql.metrics.index_de_la_table), index_octets = MAX(sql.metrics.taille_index_table_octets), table_octets = MAX(sql.metrics.taille_table_octets) BY sql.metrics.table\n| EVAL poids_index_table = CASE(table_octets > 0, ROUND(index_octets * 1.0 / table_octets, 2), null), taille_index_mo = ROUND(index_octets / 1048576.0, 1), taille_table_mo = ROUND(table_octets / 1048576.0, 1)\n| SORT poids_index_table DESC NULLS LAST, taille_index_mo DESC\n| KEEP sql.metrics.table, index_de_la_table, taille_index_mo, taille_table_mo, poids_index_table\n| LIMIT 20',
                p, 'lnsDatatable', 0, 128, 24, 14),
        panneau('Index invalides ou en doublon', 'Au dernier relevé : index invalide (création interrompue, ignoré par le planificateur) ou en doublon d\'un autre (mêmes colonnes ou colonnes en préfixe, même prédicat). Vide : rien à signaler.',
                f'FROM metrics-sql.postgresql_index_hygiene-*\n| WHERE {BASE}\n| INLINE STATS dernier = MAX(@timestamp)\n| WHERE @timestamp == dernier AND (sql.metrics.valide == false OR sql.metrics.doublon_de != "")\n| EVAL probleme = CASE(sql.metrics.valide == false, "invalide", CONCAT("doublon de ", sql.metrics.doublon_de)), taille_mo = ROUND(sql.metrics.taille_index_octets / 1048576.0, 1)\n| KEEP sql.metrics.table, sql.metrics.index, probleme, taille_mo',
                p, 'lnsDatatable', 24, 128, 24, 14),
        panneau('Entretien des tables', 'Au dernier relevé, tables d\'au moins 1 000 lignes : part de lignes mortes, modifications depuis le dernier ANALYZE, derniers ANALYZE et VACUUM (manuels ou automatiques). En tête, les tables les plus en retard.',
                f'FROM metrics-sql.postgresql_table_stats-*\n| WHERE {BASE}\n| INLINE STATS dernier = MAX(@timestamp)\n| WHERE @timestamp == dernier AND sql.metrics.n_live_tup + sql.metrics.n_dead_tup >= 1000\n| EVAL part_lignes_mortes = CASE(sql.metrics.n_live_tup + sql.metrics.n_dead_tup > 0, ROUND(sql.metrics.n_dead_tup * 100.0 / (sql.metrics.n_live_tup + sql.metrics.n_dead_tup), 1), 0.0), part_modifiee = CASE(sql.metrics.n_live_tup > 0, ROUND(sql.metrics.n_mod_since_analyze * 100.0 / sql.metrics.n_live_tup, 1), 0.0)\n| SORT part_lignes_mortes DESC, part_modifiee DESC\n| KEEP sql.metrics.table, part_lignes_mortes, part_modifiee, sql.metrics.last_autoanalyze, sql.metrics.last_analyze, sql.metrics.last_autovacuum, sql.metrics.last_vacuum, sql.metrics.n_live_tup\n| LIMIT 20',
                p, 'lnsDatatable', 0, 142, 48, 14),
        panneau('Verrous et transactions longues', 'Chaque minute : plus vieille transaction ouverte, sessions ouvertes dans une transaction sans rien faire, sessions qui attendent un verrou. Une transaction qui dure bloque le vacuum et peut bloquer les écritures.',
                f'FROM metrics-sql.postgresql_activite-*\n| WHERE {BASE}\n| STATS transaction_la_plus_longue_s = MAX(sql.metrics.plus_vieille_transaction_s), sessions_idle_in_transaction = MAX(sql.metrics.sessions_idle_in_transaction), sessions_en_attente_de_verrou = MAX(sql.metrics.sessions_en_attente_verrou) BY {TRANCHE}',
                p, 'lnsXY', 0, 33, 32, 12, 'tranche', ['transaction_la_plus_longue_s', 'sessions_idle_in_transaction', 'sessions_en_attente_de_verrou']),
        panneau('Deadlocks (cumul)', 'Deadlocks de la base depuis la remise à zéro des statistiques : une pente = des deadlocks en cours.',
                f'FROM metrics-postgresql.database-*\n| WHERE {BASE} AND postgresql.database.name IS NOT NULL AND postgresql.database.name NOT IN ("postgres", "template0", "template1", "")\n| STATS deadlocks = MAX(TO_LONG(postgresql.database.deadlocks)) BY {TRANCHE}',
                p, 'lnsXY', 32, 33, 16, 12, 'tranche', ['deadlocks']),
        panneau('Swap des nœuds de données', 'Le vrai signal de manque de mémoire : un swap qui monte. La mémoire à 100 % la nuit, elle, est le cache des sauvegardes.',
                instances + f'\n| STATS swap_mo = MAX(scalingo.swap.usage.bytes) / 1048576.0 BY {TRANCHE}, scalingo.database.instance',
                p, 'lnsXY', 0, 21, 16, 12, 'tranche', ['swap_mo'], 'scalingo.database.instance'),
        panneau('Certificat de l\'autorité', 'Autorité de certification des bases Scalingo, qui sert à vérifier le serveur (verify-full) : date d\'expiration et jours restants.',
                instances + '\n| STATS expire_le = MAX(scalingo.database.ca_expire_le)\n| EVAL jours_restants = DATE_DIFF("day", NOW(), expire_le)',
                p, 'lnsDatatable', 36, 0, 12, 9),
        panneau('Remise à zéro des statistiques', 'Depuis quand les compteurs courent : pg_stat_statements (requêtes) et statistiques de la base (tables, index). Jamais = depuis la création de la base.',
                f'FROM metrics-sql.postgresql_statements-*, metrics-sql.postgresql_table_stats-*\n| WHERE {BASE}\n| EVAL statistiques = CASE(data_stream.dataset == "sql.postgresql_statements", "requêtes", "tables et index")\n| STATS depuis = MAX(sql.metrics.stats_reset) BY statistiques',
                p, 'lnsDatatable', 36, 56, 12, 16),
        erreurs_de_collecte(['postgresql', 'sql'], 45, p),
    ]


def redis():
    return sous_l_encadre(encadre(modele('investiguer-redis.md'), 9), panneaux_redis())


def panneaux_redis():
    p = {'base': json.dumps(bases('redis')[0][2])}
    instances = 'FROM logs-scalingo.database_stats-*\n| WHERE scalingo.database.role == "donnees" AND MV_CONTAINS(?base, scalingo.database.nom)'
    info = 'FROM metrics-redis.info-*\n| EVAL base = labels.base\n| WHERE MV_CONTAINS(?base, base)'
    return [
        panneau('Mémoire des nœuds de données (% de la limite du conteneur)', 'Mémoire du conteneur rapportée à sa limite (API des bases Scalingo). Ces Redis n\'ont pas de limite propre (maxmemory 0, noeviction) : mémoire pleine = conteneur tué.',
                instances + f'\n| STATS memoire_pct = MAX(scalingo.memory.pct) * 100 BY {TRANCHE}, scalingo.database.instance',
                p, 'lnsXY', 0, 0, 24, 12, 'tranche', ['memoire_pct'], 'scalingo.database.instance', 100),
        panneau('Mémoire occupée par Redis (Mo)', 'used_memory (données) et used_memory_rss (réservée au système). Ne pas comparer à total_system_memory, qui est la mémoire de l\'hôte.',
                info + f'\n| STATS donnees_mo = MAX(redis.info.memory.used.value) / 1048576.0, rss_mo = MAX(redis.info.memory.used.rss) / 1048576.0 BY {TRANCHE}',
                p, 'lnsXY', 24, 0, 24, 12, 'tranche', ['donnees_mo', 'rss_mo']),
        panneau('Commandes par seconde', 'Activité du Redis (instantaneous_ops_per_sec).',
                info + f'\n| STATS commandes_par_s = MAX(redis.info.stats.instantaneous.ops_per_sec) BY {TRANCHE}',
                p, 'lnsXY', 0, 12, 16, 12, 'tranche', ['commandes_par_s']),
        panneau('Clients connectés, connexions refusées (cumul)', 'Connexions refusées depuis le démarrage du Redis : une pente = des refus en cours, signe de saturation ; une chute = un redémarrage.',
                info + f'\n| STATS clients = MAX(redis.info.clients.connected), refusees_cumul = MAX(TO_LONG(redis.info.stats.connections.rejected)) BY {TRANCHE}',
                p, 'lnsXY', 16, 12, 16, 12, 'tranche', ['clients', 'refusees_cumul']),
        panneau('Clés évincées et expirées (cumul)', 'Depuis le démarrage du Redis : la pente donne le rythme, une chute = un redémarrage. Avec noeviction, aucune éviction : Redis refuse d\'écrire quand la mémoire est pleine.',
                info + f'\n| STATS evincees_cumul = MAX(TO_LONG(redis.info.stats.keys.evicted)), expirees_cumul = MAX(TO_LONG(redis.info.stats.keys.expired)) BY {TRANCHE}',
                p, 'lnsXY', 32, 12, 16, 12, 'tranche', ['evincees_cumul', 'expirees_cumul']),
        panneau('Nombre de clés', 'Nombre total de clés : leur croissance continue signale une purge qui ne se fait pas.',
                f'FROM metrics-redis.keyspace-*\n| WHERE {BASE}\n| STATS cles = MAX(redis.keyspace.keys) BY {TRANCHE}',
                p, 'lnsXY', 0, 24, 24, 12, 'tranche', ['cles']),
        panneau('Files de jobs Bull (Redis de l\'api)', 'Longueur des files wait, active, delayed, failed, completed. Une file vide n\'existe pas dans Redis et n\'apparaît pas.',
                f'FROM metrics-redis.key-*\n| WHERE {BASE} AND redis.key.name LIKE "bull:JobQueue:*"\n| STATS longueur = MAX(redis.key.length) BY {TRANCHE}, redis.key.name',
                p, 'lnsXY', 24, 24, 24, 12, 'tranche', ['longueur'], 'redis.key.name'),
        panneau('CPU des nœuds de données (%)', 'CPU du conteneur (API des bases Scalingo).',
                instances + f'\n| STATS cpu_pct = MAX(scalingo.cpu.usage) BY {TRANCHE}, scalingo.database.instance',
                p, 'lnsXY', 0, 36, 24, 12, 'tranche', ['cpu_pct'], 'scalingo.database.instance'),
        panneau('Politique mémoire', 'maxmemory 0 = pas de limite côté Redis ; noeviction = écritures refusées plutôt qu\'évictions.',
                info + '\n| STATS politique = MAX(redis.info.memory.max.policy), maxmemory = MAX(redis.info.memory.max.value) BY base\n| KEEP base, politique, maxmemory',
                p, 'lnsDatatable', 24, 36, 24, 12),
        panneau('Swap des nœuds de données', 'Le vrai signal de manque de mémoire : un swap qui monte.',
                instances + f'\n| STATS swap_mo = MAX(scalingo.swap.usage.bytes) / 1048576.0 BY {TRANCHE}, scalingo.database.instance',
                p, 'lnsXY', 0, 48, 24, 10, 'tranche', ['swap_mo'], 'scalingo.database.instance'),
        panneau('Certificat de l\'autorité', 'Autorité de certification des bases Scalingo : date d\'expiration et jours restants.',
                instances + '\n| STATS expire_le = MAX(scalingo.database.ca_expire_le)\n| EVAL jours_restants = DATE_DIFF("day", NOW(), expire_le)',
                p, 'lnsDatatable', 24, 48, 24, 10),
        erreurs_de_collecte(['redis'], 58, p),
    ]



def dashboards():
    DASHBOARD_EN_COURS.append('PostgreSQL')
    postgres = dashboard(ID_PG, '[Pass Emploi] Bases de données - PostgreSQL',
                         'PostgreSQL de l\'api : santé de l\'instance, requêtes lentes et les plus appelées, requêtes à optimiser.',
                         postgresql(), controle(('base', 'Base', [n for _, _, n in bases('postgresql')], [bases('postgresql')[0][2]]),
                                                ('table', 'Table', TABLES_A_CHAUD, ['toutes'])))
    DASHBOARD_EN_COURS.append('Redis')
    redis_ = dashboard(ID_REDIS, '[Pass Emploi] Bases de données - Redis',
                       'Redis de l\'api (jobs Bull) et de connect (authentification) : mémoire, activité, clés, files de jobs.',
                       redis(), controle(('base', 'Base', [n for _, _, n in bases('redis')], [bases('redis')[0][2]])))
    return [postgres, redis_]


def executer(esql, params):
    texte = esql
    for nom, valeur in params.items():
        texte = texte.replace('?' + nom, valeur)
    texte = texte.replace('?_tstart', 'NOW() - 1 hour').replace('?_tend', 'NOW()')
    premiere, _, reste = texte.partition('\n')
    texte = premiere + '\n| WHERE @timestamp > NOW() - 1 hour\n' + reste
    requete = urllib.request.Request(os.environ['ES_URL'].rstrip('/') + '/_query', data=json.dumps({'query': texte}).encode(),
                                     method='POST', headers={'Authorization': 'ApiKey ' + os.environ['ES_API_KEY'],
                                                             'Content-Type': 'application/json'})
    return [[c['name'], c['type']] for c in json.load(urllib.request.urlopen(requete, timeout=120))['columns']]


def valider(sauf=()):
    ecarts = 0
    for cle, (esql, params) in sorted(REQUETES.items()):
        if any(motif in esql.partition('\n')[0] for motif in sauf):
            print(f'{cle} : ignorée (--sauf)')
            continue
        try:
            reelles = executer(esql, params)
        except urllib.error.HTTPError as e:
            print(f'{cle} : requête invalide, {e.read().decode(errors="replace")[:300]}')
            ecarts += 1
            continue
        if reelles != COLONNES.get(cle):
            print(f'{cle} : colonnes {reelles}, catalogue {COLONNES.get(cle)}')
            ecarts += 1
    print(f'{len(REQUETES)} requêtes, {ecarts} écart(s)')
    return 1 if ecarts else 0


if __name__ == '__main__':
    analyse = argparse.ArgumentParser()
    analyse.add_argument('--sortie', default=os.path.join(ICI, 'dashboard-bases-de-donnees.ndjson'))
    analyse.add_argument('--valider', action='store_true')
    analyse.add_argument('--sauf', action='append', default=[], help='avec --valider : ne pas interroger les index dont le nom contient ce motif')
    arguments = analyse.parse_args()
    objets = dashboards()
    if arguments.valider:
        sys.exit(valider(arguments.sauf))
    with open(arguments.sortie, 'w', encoding='utf-8') as sortie:
        for objet in objets:
            sortie.write(json.dumps(objet, ensure_ascii=False) + '\n')
    print(f'{len(objets)} dashboards écrits dans {os.path.relpath(arguments.sortie)}')
