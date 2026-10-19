# Plan 1 — Réorganisation des alertes par périmètre

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Les alertes X1 à X5 disparaissent au profit de règles rangées par périmètre (A4a/A4b applicatif, 6a/6b et 14 stack, V1 sécurité), alimentées par un pipeline qui classe chaque événement Scalingo (`incident` / `infra`), la chaîne de collecte étant documentée à part.

**Architecture:** Le pipeline `ingest-alertes-scalingo` pose `labels.categorie` et un émoji en tête de `message` depuis une table unique. Quatre règles Scalingo (périmètre × environnement) listent les lignes `message` de leurs apps ; elles se distinguent par un filtre sur `service.name`. La collecte (pipelines, accès, failure store) quitte `supervision/` pour `collecte/evenements-externes/`. Les règles sont générées depuis une définition structurée unique par un script de travail (hors repo), qui vérifie la cohérence étapes ↔ sections.

**Tech Stack:** Elasticsearch / Kibana 9.4.7 (ingest pipelines Painless, Alerting `.es-query`, Saved objects, Workflows), fichiers `.console` (Dev Tools), Python 3 pour les scripts de travail, pile locale Docker (harnais existant).

**Spec:** [`docs/superpowers/specs/2026-10-19-migration-mattermost-tchap-design.md`](../specs/2026-10-19-migration-mattermost-tchap-design.md) (§2 D1–D5, D9 ; §4 ; §7 principes). Plans suivants : 2 (versionnement et revue des étapes d'investigation de toutes les règles), 3 (déploiement prod et sources), 4 (Tchap et bascule).

## Global Constraints

- **Rien n'est appliqué en prod dans ce plan** : tout est dans le repo et testé sur la pile locale. Le déploiement est le plan 3.
- **Aucune règle supprimée** ; les **IDs sont conservés** : A4a = `1b97f0e0-870f-498d-8dd7-1c2f9aeba665` (ex-X1), A4b = `07c9c5d7-e8fe-4964-ac8d-684b1c4c39b8` (ex-X3), 6a = `c16f2ab5-6103-4f69-bdc3-b4a10a38deb0` (ex-X2), V1 = `67846c2c-45d1-45be-89f5-ce9a340240a0` (ex-X4), 14 = `ae398f47-0ed9-427e-a090-cf774acc7d16` (ex-X5) ; 6b = `5d1f7c2a-9b3e-4f6a-8c1d-2e7b4a9f0c63` (nouvelle).
- **Convention `{n}a` = prod, `{n}b` = staging/perf.**
- **Apps de la stack** : `pass-emploi-logstash`, `pass-emploi-logstash-process`, `pass-emploi-elastic-agent`, `pass-emploi-heartbeat` (valeurs de `service.name`, sans suffixe d'environnement). Applicatif = tout le reste.
- **Connecteurs Mattermost (transition)** : A4a, V1 → `12e46700-6e45-11ec-9757-c9700cd1bb4e` (`#monitoring-production`) ; A4b → `4cb10f00-22d9-4cf0-bda1-e288c4abb339` (`Mattermost-monitoring-staging`) ; 6a, 14 → `d2812573-52bf-4b48-9e54-a79a8b5b227d` (`#o11y-production`) ; 6b → `c4a313b3-aa42-4e07-8196-c007625ce8af` (`#o11y-staging`).
- **Workflows Tchap** : A4a, V1 → `tchap-monitoring-production` ; A4b → `tchap-monitoring-staging` ; 6a, 14 → `tchap-o11y-production` ; 6b → `tchap-o11y-staging`.
- **Format des messages Mattermost** (validé le 2026-10-15) : un champ par section (« À vérifier », « Dashboards », « Discover sessions »), une ligne par élément via `\n{{!` / `}}`, titres au pluriel, « À vérifier » numérotés (3 au plus), sections cohérentes avec les étapes, section absente si vide, **jamais de Discover non enregistré** (`{{context.link}}`), dashboards préfixés par leur origine. Investigation guide et Related dashboards = mêmes contenus.
- **Principes d'investigation (spec §7)** : une étape = une question (fait → erreur d'origine → impact), uniquement le périmètre de la règle ; dashboard de diagnostic avant les sessions ; sessions existantes conservées.
- Commentaires : faits non évidents seulement (CLAUDE.md).
- Commit et push après chaque tâche, sur la branche `ops/o11y-centralisation-alertes-exterieures-dans-kibana`.

## Review Focus

- **Un événement d'une app de la stack ne doit jamais apparaître dans A4a/A4b, ni l'inverse** → test dédié (Task 4, Task 5) : une injection par famille, vérifiée dans le Mattermost simulé de chaque connecteur.
- **Un redémarrage volontaire (`user_restart`) n'est pas un incident**, un redémarrage par la plateforme si → `_simulate` dédiés (Task 1).
- **Un type d'événement Scalingo inconnu** (`scalingo_<type>`) est classé `infra` avec une ligne lisible, sans `null` → `_simulate` dédié (Task 1).
- **Une nouvelle app applicative** (absente des listes) est couverte par A4a/A4b par défaut → test avec `pass-emploi-nouvelle-app` (Task 4).
- **Les data views des sessions et des règles partagent leurs IDs** : sans data stream, les règles tombent en erreur (« no longer contains a time field ») → les tests créent les data streams avant les règles et vérifient `execution_status: ok` (Task 4, Task 5).

---

## Task 0: Harnais local

Le harnais existe dans `/home/alexandre-tingaud/.claude/jobs/10d0628e/tmp/harnais/` (`pile.sh`, `replay.py`, `synapse_init.py`, `salon.py`, `liens.py`). Cette tâche y ajoute un connecteur Mattermost simulé **par connecteur réel**, pour vérifier qu'une règle poste dans le bon canal.

**Files (hors repo) :**
- Modify: `$HARNAIS/pile.sh` (création des connecteurs simulés)
- Create: `$HARNAIS/mm.py` (lecture des messages reçus par connecteur)

**Interfaces:**
- Produces: un index `mm-<8 premiers caractères de l'id du connecteur>` par connecteur Mattermost simulé (`12e46700`, `4cb10f00`, `d2812573`, `c4a313b3`) ; `python3 -I $HARNAIS/mm.py <id8>` affiche, pour chaque message reçu, le titre puis les lignes `attachments[0].text`.

- [ ] **Step 1: Un index par connecteur simulé**

Dans `pile.sh`, remplacer la boucle de création des connecteurs simulés par :

```bash
    for c in 12e46700-6e45-11ec-9757-c9700cd1bb4e 4cb10f00-22d9-4cf0-bda1-e288c4abb339 c4a313b3-aa42-4e07-8196-c007625ce8af d2812573-52bf-4b48-9e54-a79a8b5b227d; do
      curl -s -u elastic:testpass123 -H kbn-xsrf:true -H Content-Type:application/json "localhost:15601/api/actions/connector/$c" \
        -d '{"name":"Mattermost-simule-'"${c:0:8}"'","connector_type_id":".webhook","config":{"url":"http://th-es:9200/mm-'"${c:0:8}"'/_doc","method":"post","hasAuth":true,"authType":"webhook-authentication-basic","headers":{"Content-Type":"application/json"}},"secrets":{"user":"elastic","password":"testpass123"}}' >/dev/null
    done
```

- [ ] **Step 2: Écrire `mm.py`**

```python
#!/usr/bin/env python3
import base64, json, sys, urllib.request

AUTH = 'Basic ' + base64.b64encode(b'elastic:testpass123').decode()
request = urllib.request.Request(f'http://127.0.0.1:19200/mm-{sys.argv[1]}/_search?size=50&sort=_doc', headers={'Authorization': AUTH})
try:
    hits = json.load(urllib.request.urlopen(request))['hits']['hits']
except urllib.error.HTTPError:
    hits = []
print(f'{len(hits)} message(s)')
for hit in hits:
    body = hit['_source']
    print('#', body['text'])
    print(body['attachments'][0]['text'])
```

- [ ] **Step 3: Démarrer la pile**

Run: `H=/home/alexandre-tingaud/.claude/jobs/10d0628e/tmp/harnais; $H/pile.sh down; $H/pile.sh up && python3 -I $H/synapse_init.py >/dev/null && echo ok`
Expected: `pile prête` puis `ok`.

---

## Task 1: Catégorie et émoji dans le pipeline Scalingo

**Files:**
- Modify: `docs/observabilite/supervision/pipelines/ingest-alertes-scalingo.console` (processeur `message`, attendus, documents de test). Ce fichier est déplacé en Task 3 : le modifier ici, à son emplacement actuel.

**Interfaces:**
- Produces: sur chaque document Scalingo, `labels.categorie` ∈ {`incident`, `infra`} et `message` = `<émoji> <ligne actuelle>` ; émoji : `🚨` (`app_crashed`, `app_crashed_repeatedly`, `app_stopped`), `⚠️` (`resource_threshold_exceeded`, `app_restarted` sans `event.reason: user_restart`), `ℹ️` (tout le reste).

- [ ] **Step 1: Mettre à jour les attendus et ajouter les cas**

Dans la section TESTS, ajouter `labels.categorie` et l'émoji à chaque `message` attendu des commentaires, et ajouter au second `_simulate` :

```json
    { "_source": {"id":"test-redemarrage-plateforme","created_at":"2026-10-19T08:00:00.000Z","type":"restart","app_id":"test","app_name":"pass-emploi-logstash-prod","user":{"username":"scalingo-platform"},"type_data":{"scope":["web"],"reason":"crash"}} },
    { "_source": {"id":"test-deploiement","created_at":"2026-10-19T08:00:00.000Z","type":"deployment","app_id":"test","app_name":"pass-emploi-web-staging","user":{"username":"prenom.nom"},"type_data":{}} }
```

Attendus correspondants (commentaire) :

```
# redémarrage par la plateforme → labels.categorie: incident,
#   message: "⚠️ pass-emploi-logstash-prod : app_restarted (crash) sur web, par scalingo-platform"
# déploiement → labels.categorie: infra,
#   message: "ℹ️ pass-emploi-web-staging : app_deployed, par prenom.nom"
```

- [ ] **Step 2: Écrire le test**

```bash
cat > $HARNAIS/test_categorie.py <<'EOF'
import json, sys
expected = [
    ("incident", "⚠️ pass-emploi-logstash-perf : RAM à 96.96 % (seuil ≥ 90.0 %) sur web-1"),
    ("infra", "ℹ️ pass-emploi-logstash-perf : app_scaled web=1:L worker=0:L → web=0:L worker=0:L, par prenom.nom"),
    ("infra", "ℹ️ pass-emploi-logstash-perf : app_restarted (user_restart) sur web, par prenom.nom"),
    ("incident", "🚨 pass-emploi-api-prod : app_crashed (oom) sur web, par scalingo-platform"),
    ("infra", "ℹ️ pass-emploi-api-staging : scalingo_new_variable"),
    ("infra", "ℹ️ pass-emploi-api-prod : RAM revenue à 45.00 % (seuil ≥ 90.0 %) sur web-1"),
    ("incident", "⚠️ pass-emploi-api-prod : CPU (seuil inconnu)"),
    ("incident", "⚠️ pass-emploi-logstash-prod : app_restarted (crash) sur web, par scalingo-platform"),
    ("infra", "ℹ️ pass-emploi-web-staging : app_deployed, par prenom.nom"),
]
docs = [d['doc']['_source'] for r in json.load(open(sys.argv[1])) if r['path'].endswith('_simulate') for d in r['response']['docs']]
actual = [(d.get('labels', {}).get('categorie'), d.get('message')) for d in docs]
for e, a in zip(expected, actual):
    print('OK ' if e == a else 'KO ', a, '' if e == a else '≠ ' + str(e))
sys.exit(0 if actual == expected else 1)
EOF
```

- [ ] **Step 3: Vérifier que le test échoue**

Run: `cd docs/observabilite/supervision && python3 -I $HARNAIS/replay.py pipelines/ingest-alertes-scalingo.console --sortie $HARNAIS/categorie.json && python3 -I $HARNAIS/test_categorie.py $HARNAIS/categorie.json`
Expected: lignes `KO` (catégorie `None`, pas d'émoji), code 1.

- [ ] **Step 4: Classer et préfixer**

Dans le processeur « message », remplacer la dernière ligne `ctx.message = line.toString();` par :

```
          String action = ctx.event.action;
          boolean redemarrageSubi = action == 'app_restarted' && ctx.event.reason != 'user_restart';
          String emoji = 'ℹ️';
          if (params.critiques.contains(action)) {
            emoji = '🚨';
          } else if (action == 'resource_threshold_exceeded' || redemarrageSubi) {
            emoji = '⚠️';
          }
          labels.categorie = emoji == 'ℹ️' ? 'infra' : 'incident';
          ctx.message = emoji + ' ' + line.toString();
```

et ajouter au processeur, à côté de `"source"` :

```json
        "params": {
          "critiques": ["app_crashed", "app_crashed_repeatedly", "app_stopped"]
        },
```

Mettre à jour la `description` du processeur : `"message et labels.categorie : la ligne de notification de l'événement et sa catégorie (incident ou infra), en texte brut"`.

- [ ] **Step 5: Vérifier que le test passe**

Run: la commande du Step 3.
Expected: 9 `OK`, code 0. Rejouer aussi les 3 `ingest-alertes-scalingo-<env>-default.console` : leurs `_simulate` donnent un `message` préfixé.

- [ ] **Step 6: Vérifier le mapping de `labels.categorie`**

Run :
```bash
curl -s -u elastic:testpass123 -XPUT localhost:19200/_data_stream/logs-alertes-scalingo-staging-default >/dev/null
curl -s -u elastic:testpass123 -H Content-Type:application/json "localhost:19200/logs-alertes-scalingo-staging-default/_doc?refresh=true" -d '{"id":"t","created_at":"2026-10-19T08:00:00Z","type":"deployment","app_id":"t","app_name":"pass-emploi-web-staging","type_data":{}}' >/dev/null
curl -s -u elastic:testpass123 -H Content-Type:application/json "localhost:19200/logs-alertes-scalingo-staging-default/_count" -d '{"query":{"term":{"labels.categorie":"infra"}}}'
```
(templates et pipelines rejoués au préalable : `stockage/logs/2-…`, `3-…` blocs `logs-alertes`, puis les pipelines).
Expected: `"count":1` — le champ est requêtable.

- [ ] **Step 7: Commit**

```bash
git add docs/observabilite/supervision/pipelines/ingest-alertes-scalingo.console
git commit -m "feat(collecte): catégorie incident/infra et émoji sur les événements Scalingo"
git push
```

---

## Task 2: Sessions Discover par catégorie

**Files:**
- Modify: `docs/observabilite/supervision/discovers/alertes-externes/discover-session-prod-alertes-scalingo.ndjson`
- Modify: `docs/observabilite/supervision/discovers/alertes-externes/discover-session-hors-prod-alertes-scalingo.ndjson`

**Interfaces:**
- Produces: sessions `bb62451a-d9e9-4141-ab6f-2bda0e384e87` (prod) et `33bed466-9d68-4789-a723-aeea34e6cd93` (hors prod), mêmes IDs et titres, onglets « Incidents » (`labels.categorie : "incident"`) puis « Infra » (`labels.categorie : "infra"`), colonnes `message`, `service.name`, `event.action`.

- [ ] **Step 1: Écrire le test**

```bash
cat > $HARNAIS/test_sessions.py <<'EOF'
import base64, json, sys, urllib.request
AUTH = 'Basic ' + base64.b64encode(b'elastic:testpass123').decode()
ok = True
for sid in ['bb62451a-d9e9-4141-ab6f-2bda0e384e87', '33bed466-9d68-4789-a723-aeea34e6cd93']:
    req = urllib.request.Request(f'http://127.0.0.1:15601/api/saved_objects/resolve/search/{sid}', headers={'Authorization': AUTH})
    tabs = json.load(urllib.request.urlopen(req))['saved_object']['attributes']['tabs']
    got = [(t['label'], json.loads(t['attributes']['kibanaSavedObjectMeta']['searchSourceJSON'])['query']['query'], t['attributes']['columns']) for t in tabs]
    want = [('Incidents', 'labels.categorie : "incident"', ['message', 'service.name', 'event.action']),
            ('Infra', 'labels.categorie : "infra"', ['message', 'service.name', 'event.action'])]
    print(sid[:8], 'OK' if got == want else f'KO {got}')
    ok &= got == want
sys.exit(0 if ok else 1)
EOF
```

- [ ] **Step 2: Vérifier que le test échoue**

Run: importer les deux fichiers (`curl … /api/saved_objects/_import?overwrite=true -F file=@…`), puis `python3 -I $HARNAIS/test_sessions.py`.
Expected: `KO` (onglets « Crashs, redémarrages et arrêts » / « Seuils de ressource »).

- [ ] **Step 3: Remplacer les onglets**

Pour chaque fichier, avec ce script (les IDs d'onglet sont conservés, les attributs de premier niveau suivent le premier onglet) :

```python
import json, sys
p = sys.argv[1]
objs = [json.loads(l) for l in open(p)]
for o in objs:
    if o.get('type') != 'search':
        continue
    tabs = o['attributes']['tabs']
    for tab, (label, q) in zip(tabs, [('Incidents', 'labels.categorie : "incident"'), ('Infra', 'labels.categorie : "infra"')]):
        tab['label'] = label
        ss = json.loads(tab['attributes']['kibanaSavedObjectMeta']['searchSourceJSON'])
        ss['query'] = {'query': q, 'language': 'kuery'}
        tab['attributes']['kibanaSavedObjectMeta']['searchSourceJSON'] = json.dumps(ss, ensure_ascii=False)
        tab['attributes']['columns'] = ['message', 'service.name', 'event.action']
        tab['attributes']['breakdownField'] = 'service.name'
    for k in ('columns', 'breakdownField', 'kibanaSavedObjectMeta'):
        o['attributes'][k] = tabs[0]['attributes'][k]
with open(p, 'w') as f:
    for o in objs:
        f.write(json.dumps(o, ensure_ascii=False, separators=(',', ':')) + '\n')
```

Run: `python3 -I <script> <fichier>` pour les deux fichiers.

- [ ] **Step 4: Vérifier que le test passe**

Run: réimporter les deux fichiers, puis `python3 -I $HARNAIS/test_sessions.py`.
Expected: `bb62451a OK`, `33bed466 OK`.

- [ ] **Step 5: Commit**

```bash
git add docs/observabilite/supervision/discovers/alertes-externes/
git commit -m "feat(discovers): sessions Événements Scalingo par catégorie (Incidents, Infra)"
git push
```

---

## Task 3: Collecte des événements externes, séparée des alertes

**Files:**
- Move: `docs/observabilite/supervision/pipelines/` → `docs/observabilite/collecte/evenements-externes/pipelines/`
- Move: `docs/observabilite/supervision/security/` → `docs/observabilite/collecte/evenements-externes/security/`
- Move: `docs/observabilite/supervision/discovers/alertes-externes/` → `docs/observabilite/supervision/discovers/evenements-externes/`
- Create: `docs/observabilite/collecte/evenements-externes/README.md`
- Modify: les en-têtes « Spécification : ../alertes-externes.md » des `.console` déplacés et de `stockage/logs/2-component-templates.console`, `3-index-templates.console` ; `stockage/logs/README.md` ; `docs/observabilite/README.md`

**Interfaces:**
- Produces: `collecte/evenements-externes/README.md`, avec les ancres `#la-chaîne`, `#champs-ecs-produits`, `#mise-en-service` citées par les docs d'alertes (Tasks 4 à 6).

- [ ] **Step 1: Déplacer**

```bash
cd docs/observabilite
mkdir -p collecte/evenements-externes
git mv supervision/pipelines collecte/evenements-externes/pipelines
git mv supervision/security collecte/evenements-externes/security
git mv supervision/discovers/alertes-externes supervision/discovers/evenements-externes
```

- [ ] **Step 2: Écrire `collecte/evenements-externes/README.md`**

Contenu : les sections de `supervision/alertes-externes.md` qui décrivent la **collecte**, reprises telles quelles puis adaptées :
- titre `# Collecte des événements externes (Scalingo, GitHub)` et introduction : les notifiers Scalingo et `security-alerts.yml` écrivent dans des data streams `logs-alertes-*` ; les alertes qui les lisent sont dans leur périmètre (liens vers `alertes-applicatives.md#a4a…`, `alertes-stack-observabilite.md#alerte-6…`, `#alerte-14…`, `alertes-securite.md`) ;
- `## La chaîne` (schéma : émetteurs → data streams → pipelines → failure store ; plus de mention X1–X5) ;
- tableau des fichiers (chemins `pipelines/…`, `security/…`, `../../stockage/logs/…`) ;
- `## Champs ECS produits` (ajouter `labels.categorie` et l'émoji de `message`, avec la table de la Task 1) ;
- `## Mise en service` : étapes Stockage, Pipelines, Accès, Test sans Scalingo, Notifiers Scalingo (nom « Elastic monitoring … » et même sélection que le notifier `Mattermost*`, spec §4.3), GitHub Actions ;
- `## Points ouverts` (types Scalingo non capturés, identifiants dans l'URL du notifier).

Les sections « Récapitulatif des règles » et les spécifications de règles **ne** sont **pas** reprises : elles vont dans les docs de périmètre (Tasks 4 à 6).

- [ ] **Step 3: Mettre à jour les références**

```bash
cd docs/observabilite
sed -i 's#Spécification : ../alertes-externes.md#Spécification : ../README.md#' collecte/evenements-externes/pipelines/*.console collecte/evenements-externes/security/*.console
sed -i 's#\.\./\.\./supervision/alertes-externes\.md#../../collecte/evenements-externes/README.md#g; s#supervision/alertes-externes\.md#collecte/evenements-externes/README.md#g' stockage/logs/*.console stockage/logs/README.md README.md
grep -rn "alertes-externes\.md\|supervision/pipelines\|supervision/security\|discovers/alertes-externes" .. --include=*.md --include=*.console --include=*.ndjson | grep -v superpowers
```
Expected (dernière commande) : seules restent les références de `supervision/alertes-externes.md` lui-même et de `rules/3-rules-alertes-externes.console`, supprimés en Task 6.

- [ ] **Step 4: Vérifier les liens**

Run: `python3 -I $HARNAIS/liens.py docs/observabilite/collecte/evenements-externes/README.md docs/observabilite/README.md docs/observabilite/stockage/logs/README.md`
Expected: aucune ligne `cassé:` (les liens vers les sections de règles des Tasks 4 à 6 sont vérifiés en Task 6).

- [ ] **Step 5: Vérifier que les pipelines se rejouent depuis leur nouvel emplacement**

Run: `cd docs/observabilite/collecte/evenements-externes && for f in pipelines/*.console; do python3 -I $HARNAIS/replay.py $f >/dev/null && echo "ok $f"; done`
Expected: `ok` pour les 5 fichiers.

- [ ] **Step 6: Commit**

```bash
git add -A docs/observabilite
git commit -m "refactor(collecte): la collecte des événements Scalingo et GitHub quitte supervision/"
git push
```

---

## Task 4: Générateur de règles et règles applicatives A4a / A4b

Les corps de règles (requête, body Mattermost, Investigation guide, Related dashboards, actions) sont produits par un script de travail depuis une définition par règle : le format validé est complexe (Mustache, commentaires de retour à la ligne, cohérence étapes ↔ sections) et se recopie mal à la main.

**Files:**
- Create (hors repo) : `$HARNAIS/../generer_regles.py`
- Modify: `docs/observabilite/supervision/rules/1-rules-applicatives.console` (ajout de A4a, A4b en fin de fichier)
- Modify: `docs/observabilite/supervision/alertes-applicatives.md` (récapitulatif, section A4a/A4b)

**Interfaces:**
- Consumes: Task 1 (`labels.categorie`, émoji), Task 2 (sessions), Task 3 (`collecte/evenements-externes/README.md`).
- Produces: `python3 -I generer_regles.py <regle> …` écrit sur la sortie standard le bloc `.console` (`PUT kbn:/api/alerting/rule/<id>` + corps) de chaque règle demandée ; règles connues : `A4a`, `A4b`, `6a`, `6b`, `14`, `V1`.

- [ ] **Step 1: Écrire le générateur**

```python
#!/usr/bin/env python3
import json, re, sys

KD = 'https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/discover#/view/'
KB = 'https://pass-emploi.kb.eu-west-3.aws.elastic-cloud.com/app/dashboards#/view/'
GH = 'https://github.com/France-Travail/pass-emploi-tools/blob/master/docs/observabilite/'
STACK_APPS = ['pass-emploi-logstash', 'pass-emploi-logstash-process', 'pass-emploi-elastic-agent', 'pass-emploi-heartbeat']
SESSIONS = {
    'evp': ('[Pass Emploi] Alertes externes de Prod - Événements Scalingo', 'bb62451a-d9e9-4141-ab6f-2bda0e384e87'),
    'evh': ('[Pass Emploi] Alertes externes Hors-Prod - Événements Scalingo', '33bed466-9d68-4789-a723-aeea34e6cd93'),
    'cve': ('[Pass Emploi] Alertes externes - CVE Dependabot', 'ece3e409-0679-4bcb-a675-ae7dfb092c19'),
    'rej': ('[Pass Emploi] Alertes externes - Rejets (failure store)', '861dbdf4-5086-498b-aff6-4d9d68ceb1f4'),
    '5xx': ('[Pass Emploi] Logs de Prod - Erreurs serveur 5xx', 'd076df50-1625-443b-978c-1aa9a1288e73'),
    'dlqp': ('[Pass Emploi] Logs de Prod - DLQ Logstash Process', '97e2d85f-7bd2-49df-86b3-2ffc290bbe69'),
    'trp': ('[Pass Emploi] Logs de PROD - Erreurs de traitement Logstash Process', 'f10de9e3-0fdd-4761-9d44-bacc96504e17'),
    'dlqh': ('[Pass Emploi] Logs Hors-Prod - DLQ Logstash Process', 'e5bec6b4-0ae3-47b1-8bb5-2e9bf77493a4'),
    'trh': ('[Pass Emploi] Logs Hors-Prod - Erreurs de traitement Logstash Process', '716175ed-b2a0-4fe1-8f9d-1892d04dbe92'),
}
DASHBOARDS = {
    'entree': ("[Pass Emploi] Diagnostic d'erreurs - Entrée", KB + 'eb348ed9-3bc2-4204-a5c2-c31465731c74', 'eb348ed9-3bc2-4204-a5c2-c31465731c74'),
    'stack': ("[Pass Emploi] Supervision Stack d'Observabilité", KB + 'fd40a516-c323-4e5e-91e5-1328b8b1a78d', 'fd40a516-c323-4e5e-91e5-1328b8b1a78d'),
    'scalingo': ('[Scalingo] Dashboard des apps', 'https://dashboard.scalingo.com/apps', None),
}
DV = {
    'prod': {'id': 'd327d85c-91ea-4092-867f-08a940504c96', 'title': 'logs-alertes-scalingo-prod-default', 'name': 'Alertes Scalingo - Prod', 'allowHidden': False},
    'hors-prod': {'id': 'a67a2388-a6a3-42e3-b1c4-15dc61bf5585', 'title': 'logs-alertes-scalingo-staging-default,logs-alertes-scalingo-perf-default', 'name': 'Alertes Scalingo - Hors-Prod', 'allowHidden': False},
    'github': {'id': '8a589b67-53bc-407d-9d76-c68b41271bbe', 'title': 'logs-alertes-github-default', 'name': 'Alertes GitHub - CVE', 'allowHidden': False},
    'rejets': {'id': '0f25bbf6-abdf-41f9-8bab-4a4911c13ebc', 'title': 'logs-alertes-scalingo-prod-default::failures,logs-alertes-scalingo-staging-default::failures,logs-alertes-scalingo-perf-default::failures,logs-alertes-github-default::failures', 'name': 'Alertes externes - rejets (failure store)', 'allowHidden': True},
}
def s(k): return f'[{SESSIONS[k][0]}]({KD}{SESSIONS[k][1]})'
def d(k): return f'[{DASHBOARDS[k][0]}]({DASHBOARDS[k][1]})'
STACK_KQL = 'service.name : (' + ' or '.join(f'"{a}"' for a in STACK_APPS) + ')'
SCALINGO_LIGNES = '{{#context.hits}}{{_source.message}}\\n{{/context.hits}}'
DOC_COLLECTE = f'[Collecte des événements externes]({GH}collecte/evenements-externes/README.md)'

REGLES = {
    'A4a': dict(id='1b97f0e0-870f-498d-8dd7-1c2f9aeba665', commentaire='# A4a — Événements Scalingo des apps applicatives, prod (Warning)',
        name='Scalingo - Prod - Événements des apps applicatives', tags=['warning', 'prod', 'applicatif', 'scalingo'],
        dv='prod', kql='not ' + STACK_KQL, interval='1m', fenetre=5, mm='12e46700-6e45-11ec-9757-c9700cd1bb4e', couleur='#ffa500',
        titre='Événements Scalingo des apps de prod', workflow='tchap-monitoring-production', lignes=SCALINGO_LIGNES,
        intro="Un événement Scalingo sur une app applicative de prod : incident (🚨 crash ou arrêt, ⚠️ seuil ou redémarrage subi) ou opération d'infra (ℹ️ déploiement, variable, scaling…).",
        steps=[f"1. Le Discover {s('evp')}, onglet « Incidents » ou « Infra » : l'événement, sa raison et son auteur",
               f"2. Pour un incident, l'impact sur les utilisateurs : le dashboard {d('entree')}, puis le Discover {s('5xx')}",
               f"3. L'activité de l'app (onglet Activity) dans le dashboard {d('scalingo')}"],
        sessions=['evp', '5xx'], dashboards=['entree', 'scalingo'], doc=('Collecte des événements externes', 'collecte/evenements-externes/README.md')),
    'A4b': dict(id='07c9c5d7-e8fe-4964-ac8d-684b1c4c39b8', commentaire='# A4b — Événements Scalingo des apps applicatives, staging / perf (Warning)',
        name='Scalingo - Hors-Prod - Événements des apps applicatives', tags=['warning', 'hors-prod', 'applicatif', 'scalingo'],
        dv='hors-prod', kql='not ' + STACK_KQL, interval='5m', fenetre=10, mm='4cb10f00-22d9-4cf0-bda1-e288c4abb339', couleur='#ffa500',
        titre='Événements Scalingo des apps hors prod', workflow='tchap-monitoring-staging', lignes=SCALINGO_LIGNES,
        intro="Un événement Scalingo sur une app applicative de staging ou de perf : incident ou opération d'infra.",
        steps=[f"1. Le Discover {s('evh')}, onglet « Incidents » ou « Infra » : l'événement, sa raison et son auteur",
               f"2. L'activité de l'app (onglet Activity) dans le dashboard {d('scalingo')}"],
        sessions=['evh'], dashboards=['scalingo'], doc=('Collecte des événements externes', 'collecte/evenements-externes/README.md')),
    '6a': dict(id='c16f2ab5-6103-4f69-bdc3-b4a10a38deb0', commentaire='# 6a — Événements Scalingo des apps de la stack, prod (Warning)',
        name='Scalingo - Prod - Événements des apps de la stack', tags=['warning', 'prod', 'o11y', 'scalingo'],
        dv='prod', kql=STACK_KQL, interval='1m', fenetre=5, mm='d2812573-52bf-4b48-9e54-a79a8b5b227d', couleur='#ffa500',
        titre='Événements Scalingo des apps de la stack, prod', workflow='tchap-o11y-production', lignes=SCALINGO_LIGNES,
        intro="Un événement Scalingo sur une app de la stack d'observabilité de prod (Logstash, Elastic Agent, Heartbeat) : incident ou opération d'infra.",
        steps=[f"1. Le Discover {s('evp')}, onglet « Incidents » ou « Infra » : l'événement, sa raison et son auteur",
               f"2. Pour un incident, l'impact sur l'ingestion : le dashboard {d('stack')}, puis les Discover {s('dlqp')} et {s('trp')} (logs non indexés)",
               f"3. Les métriques (onglet Metrics) et l'activité (onglet Activity) de l'app dans le dashboard {d('scalingo')}"],
        sessions=['evp', 'dlqp', 'trp'], dashboards=['stack', 'scalingo'], doc=("Alertes de la stack d'observabilité", 'supervision/alertes-stack-observabilite.md')),
    '6b': dict(id='5d1f7c2a-9b3e-4f6a-8c1d-2e7b4a9f0c63', commentaire='# 6b — Événements Scalingo des apps de la stack, staging / perf (Warning)',
        name='Scalingo - Hors-Prod - Événements des apps de la stack', tags=['warning', 'hors-prod', 'o11y', 'scalingo'],
        dv='hors-prod', kql=STACK_KQL, interval='5m', fenetre=10, mm='c4a313b3-aa42-4e07-8196-c007625ce8af', couleur='#ffa500',
        titre='Événements Scalingo des apps de la stack, hors prod', workflow='tchap-o11y-staging', lignes=SCALINGO_LIGNES,
        intro="Un événement Scalingo sur une app de la stack d'observabilité de staging ou de perf : incident ou opération d'infra.",
        steps=[f"1. Le Discover {s('evh')}, onglet « Incidents » ou « Infra » : l'événement, sa raison et son auteur",
               f"2. Pour un incident, l'impact sur l'ingestion : le dashboard {d('stack')}, puis les Discover {s('dlqh')} et {s('trh')} (logs non indexés)",
               f"3. Les métriques (onglet Metrics) et l'activité (onglet Activity) de l'app dans le dashboard {d('scalingo')}"],
        sessions=['evh', 'dlqh', 'trh'], dashboards=['stack', 'scalingo'], doc=("Alertes de la stack d'observabilité", 'supervision/alertes-stack-observabilite.md')),
    '14': dict(id='ae398f47-0ed9-427e-a090-cf774acc7d16', commentaire="# 14 — Événement externe rejeté par son pipeline ou par Elasticsearch (Warning). L'émetteur\n# reçoit 201 même quand le document part au failure store.",
        name='Événements externes - Payload rejeté (failure store)', tags=['warning', 'prod', 'o11y'],
        dv='rejets', kql='', interval='5m', fenetre=10, mm='d2812573-52bf-4b48-9e54-a79a8b5b227d', couleur='#ffa500',
        titre="Événements externes rejetés — des notifications Scalingo ou GitHub ne sont pas arrivées dans Kibana : leur émetteur a pourtant reçu un succès", workflow='tchap-o11y-production',
        lignes='{{#context.hits}}• `{{_source.error.type}}` : {{_source.error.message}}\\n{{/context.hits}}',
        intro="Une notification Scalingo ou GitHub a été rejetée par son ingest pipeline et rangée dans le failure store : l'alerte qu'elle portait n'a pas été levée.",
        steps=[f"1. Le Discover {s('rej')} : `error.type` et `error.message` donnent le motif du rejet",
               "2. Le payload d'origine (`document.source`) : adapter le pipeline, puis le rejouer en `_simulate`"],
        sessions=['rej'], dashboards=[], doc=('Collecte des événements externes', 'collecte/evenements-externes/README.md')),
    'V1': dict(id='67846c2c-45d1-45be-89f5-ce9a340240a0', commentaire='# V1 — CVE high/critical encore ouvertes, à chaque passage de security-alerts.yml (Critical)',
        name='GitHub - CVE high ou critical ouverte', tags=['critical', 'prod', 'securite'],
        dv='github', kql='vulnerability.severity : ("high" or "critical")', interval='5m', fenetre=10, mm='12e46700-6e45-11ec-9757-c9700cd1bb4e', couleur='#d00000',
        titre='CVE high/critical ouvertes', workflow='tchap-monitoring-production', emoji='🚨',
        lignes='{{#context.hits}}• `{{_source.service.name}}` : **{{_source.vulnerability.id}}** — {{_source.package.name}} ({{_source.vulnerability.severity}}) : {{_source.vulnerability.description}} — [Voir]({{_source.vulnerability.reference}})\\n{{/context.hits}}',
        intro='Une CVE high ou critical est encore ouverte sur un repo (alertes Dependabot envoyées par `security-alerts.yml`).',
        steps=[f"1. Le Discover {s('cve')}, liste les CVE ouvertes par repo avec leur score",
               "2. L'alerte Dependabot de chaque CVE (lien Voir), à traiter selon sa sévérité"],
        sessions=['cve'], dashboards=[], doc=('Alertes de sécurité', 'supervision/alertes-securite.md')),
}

def coherence(r):
    texte = '\n'.join(r['steps'])
    cites_s = set(re.findall(r'discover#/view/([0-9a-f-]+)', texte))
    cites_d = set(re.findall(r'\]\((https://[^)]*dashboard[^)]*)\)', texte))
    assert cites_s == {SESSIONS[k][1] for k in r['sessions']}, r['name']
    assert cites_d == {DASHBOARDS[k][1] for k in r['dashboards']}, r['name']
    assert len(r['steps']) <= 3, r['name']

def valeur_multiligne(lignes, pad):
    return ('\\n{{!\n' + ' ' * pad + '}}').join(json.dumps(l, ensure_ascii=False)[1:-1] for l in lignes)

def body(r):
    pad = len('          "value": "') - 2
    def champ(titre, valeurs, short=False):
        v = valeur_multiligne(valeurs, pad)
        out = '        {\n          "title": ' + json.dumps(titre, ensure_ascii=False) + ',\n          "value": "' + v + '"'
        return out + (',\n          "short": true\n        }' if short else '\n        }')
    champs = [champ('Règle', ['`{{rule.name}}`'], True), champ('Déclenchée à', ['`{{date}}`'], True), champ('À vérifier', r['steps'])]
    dash = [d(k) for k in r['dashboards']]
    if dash:
        champs.append(champ('Dashboards', dash))
    champs.append(champ('Discover sessions', [s(k) for k in r['sessions']]))
    emoji = r.get('emoji', '⚠️')
    return ('{\n  "text": ' + json.dumps(f"{emoji} **{r['titre']}** ({{{{context.value}}}})", ensure_ascii=False) + ',\n'
            '  "attachments": [\n    {\n      "color": "' + r['couleur'] + '",\n'
            '      "text": "' + r['lignes'] + '",\n      "fields": [\n' + ',\n'.join(champs) + '\n      ]\n    }\n  ]\n}')

def guide(r):
    dash = [d(k) for k in r['dashboards']]
    md = "## Ce que signale l'alerte\n\n" + r['intro'] + "\n\n## À vérifier\n\n" + '\n'.join(r['steps'])
    if dash:
        md += "\n\n## Dashboards\n\n" + '\n'.join('- ' + x for x in dash)
    md += "\n\n## Discover sessions\n\n" + '\n'.join('- ' + s(k) for k in r['sessions'])
    md += f"\n\n## Documentation\n\n[{r['doc'][0]}]({GH}{r['doc'][1]})\n"
    return md

def bloc(nom):
    r = REGLES[nom]
    coherence(r)
    artifacts = {'investigation_guide': {'blob': guide(r)}}
    ids = [DASHBOARDS[k][2] for k in r['dashboards'] if DASHBOARDS[k][2]]
    if ids:
        artifacts['dashboards'] = [{'id': i} for i in ids]
    dv = DV[r['dv']]
    regle = {
        'name': r['name'], 'tags': r['tags'], 'artifacts': artifacts, 'schedule': {'interval': r['interval']},
        'params': {
            'searchConfiguration': {'query': {'query': r['kql'], 'language': 'kuery'},
                'index': {'id': dv['id'], 'title': dv['title'], 'timeFieldName': '@timestamp', 'sourceFilters': [], 'fieldFormats': {}, 'runtimeFieldMap': {}, 'allowNoIndex': False, 'name': dv['name'], 'allowHidden': dv['allowHidden'], 'managed': False}},
            'timeField': '@timestamp', 'searchType': 'searchSource', 'timeWindowSize': r['fenetre'], 'timeWindowUnit': 'm',
            'threshold': [0], 'thresholdComparator': '>', 'size': 20, 'aggType': 'count', 'groupBy': 'all', 'termSize': 5,
            'excludeHitsFromPreviousRun': True, 'sourceFields': []},
        'actions': [
            {'group': 'query matched', 'id': r['mm'], 'params': {'body': '@@BODY@@'}, 'frequency': {'summary': False, 'notify_when': 'onActiveAlert', 'throttle': None}},
            {'id': 'system-connector-.workflows', 'params': {'subAction': 'run', 'subActionParams': {'workflowId': r['workflow'], 'summaryMode': True, 'alertStates': {'new': True, 'ongoing': True, 'recovered': False}}}}],
    }
    texte = json.dumps(regle, ensure_ascii=False, indent=2).replace('"@@BODY@@"', '"""' + body(r) + '"""')
    return r['commentaire'] + '\nPUT kbn:/api/alerting/rule/' + r['id'] + '\n' + texte + '\n'

if __name__ == '__main__':
    print('\n'.join(bloc(n) for n in sys.argv[1:]))
```

- [ ] **Step 2: Écrire le test de bout en bout des règles Scalingo**

```bash
cat > $HARNAIS/test_regles_scalingo.sh <<'EOF'
#!/bin/bash
# Injecte un événement par famille et vérifie qu'il n'arrive que dans le canal de sa règle.
H=$(dirname "$0"); NOW=$(date -u +%FT%T.%3NZ)
inj() { curl -s -u elastic:testpass123 -H Content-Type:application/json "localhost:19200/logs-alertes-scalingo-$1-default/_doc?refresh=true" \
  -d "{\"id\":\"$2\",\"created_at\":\"$NOW\",\"type\":\"$3\",\"app_id\":\"t\",\"app_name\":\"$4\",\"user\":{\"username\":\"scalingo-platform\"},\"type_data\":{\"scope\":[\"web\"],\"reason\":\"$5\"}}" >/dev/null; }
inj prod t-api crash pass-emploi-api-prod oom
inj prod t-ls restart pass-emploi-logstash-prod crash
inj prod t-new deployment pass-emploi-nouvelle-app-prod ""
inj staging t-web deployment pass-emploi-web-staging ""
inj perf t-ls-perf restart pass-emploi-logstash-perf user_restart
for r in 1b97f0e0-870f-498d-8dd7-1c2f9aeba665 07c9c5d7-e8fe-4964-ac8d-684b1c4c39b8 c16f2ab5-6103-4f69-bdc3-b4a10a38deb0 5d1f7c2a-9b3e-4f6a-8c1d-2e7b4a9f0c63; do
  curl -s -u elastic:testpass123 -H kbn-xsrf:true -H x-elastic-internal-origin:kibana -XPOST localhost:15601/internal/alerting/rule/$r/_run_soon >/dev/null; done
sleep 35
for c in 12e46700 4cb10f00 d2812573 c4a313b3; do echo "== $c"; python3 -I $H/mm.py $c; done
for r in 1b97f0e0-870f-498d-8dd7-1c2f9aeba665 07c9c5d7-e8fe-4964-ac8d-684b1c4c39b8 c16f2ab5-6103-4f69-bdc3-b4a10a38deb0 5d1f7c2a-9b3e-4f6a-8c1d-2e7b4a9f0c63; do
  curl -s -u elastic:testpass123 localhost:15601/api/alerting/rule/$r | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get("name","ABSENTE"), d.get("execution_status",{}).get("status"))'; done
EOF
chmod +x $HARNAIS/test_regles_scalingo.sh
```

Attendu (Task 5 terminée) :
- `12e46700` (A4a) : un message, lignes `🚨 pass-emploi-api-prod : app_crashed (oom) sur web, par scalingo-platform` et `ℹ️ pass-emploi-nouvelle-app-prod : app_deployed, par scalingo-platform`, **sans** ligne Logstash ;
- `4cb10f00` (A4b) : `ℹ️ pass-emploi-web-staging : app_deployed, par scalingo-platform` ;
- `d2812573` (6a) : `⚠️ pass-emploi-logstash-prod : app_restarted (crash) sur web, par scalingo-platform`, **sans** ligne api ;
- `c4a313b3` (6b) : `ℹ️ pass-emploi-logstash-perf : app_restarted (user_restart) sur web, par scalingo-platform` ;
- les 4 règles en `ok` ou `active`, jamais `error`.

- [ ] **Step 3: Préparer la pile et vérifier que le test échoue**

Run (depuis `docs/observabilite`) : rejouer `stockage/logs/2-…` et `3-index-templates.console` (blocs `logs-alertes` et data streams), les pipelines de `collecte/evenements-externes/pipelines/`, importer les sessions de `supervision/discovers/evenements-externes/` et `supervision/dashboards/*.ndjson`, rejouer `workflows/tchap/connecteur-tchap.console` (jeton et URL Synapse substitués), `tchap-client.console` et les 4 Workflows de salon, puis `$HARNAIS/test_regles_scalingo.sh`.
Expected: aucun message, règles `ABSENTE`.

- [ ] **Step 4: Ajouter A4a et A4b**

Ajouter à la fin de `rules/1-rules-applicatives.console` la sortie de `python3 -I generer_regles.py A4a A4b`. Dans l'en-tête du fichier, compléter : « A4a / A4b : événements Scalingo des apps applicatives, `#monitoring-production` / `Mattermost-monitoring-staging` ; créées avec `.es-query` / `alerts`. »

Dans `alertes-applicatives.md` :
- introduction : ajouter une troisième couche **« événements Scalingo »** (A4a, A4b) ;
- récapitulatif : lignes A4a (`logs-alertes-scalingo-prod-default`, apps hors stack, tout événement, 1 min, `#monitoring-production`, ⚠️ Warning) et A4b (`…-{staging,perf}-default`, 5 min, canal staging, ⚠️ Warning) ;
- nouvelle section `## Événements Scalingo — ce qui arrive aux apps` avec `### A4a …` et `### A4b …` : objectif, données (renvoi à [la collecte](../collecte/evenements-externes/README.md)), lignes 🚨 / ⚠️ / ℹ️ (table de la Task 1), étapes « À vérifier », et la note « Sortir l'infra des salons de monitoring » de la spec §6.

Pour créer les règles sur la pile locale (cluster vide), écrire une fois `$HARNAIS/creer_local.py`, qui transforme les `PUT` d'un fichier `.console` en `POST` de création, en ne gardant que les règles demandées :

```python
#!/usr/bin/env python3
import re, sys
texte, ids = open(sys.argv[1]).read(), set(sys.argv[2:])
lignes, sortie, i = texte.split('\n'), [], 0
while i < len(lignes):
    m = re.match(r'PUT (kbn:/api/alerting/rule/(\S+))$', lignes[i])
    if m and m.group(2) in ids:
        fin = lignes.index('}', i)
        bloc = lignes[i:fin + 1]
        bloc[0] = 'POST ' + m.group(1)
        bloc[-2] = bloc[-2].rstrip() + ','
        bloc[-1:] = ['  "rule_type_id": ".es-query",', '  "consumer": "alerts"', '}']
        sortie += bloc + ['']
        i = fin + 1
    else:
        i += 1
print('\n'.join(sortie))
```

Usage : `python3 -I $HARNAIS/creer_local.py rules/1-rules-applicatives.console 1b97f0e0-870f-498d-8dd7-1c2f9aeba665 07c9c5d7-e8fe-4964-ac8d-684b1c4c39b8 > $HARNAIS/a4.console && python3 -I $HARNAIS/replay.py $HARNAIS/a4.console`.

- [ ] **Step 5: Vérifier (A4a/A4b)**

Run: créer A4a, A4b sur la pile, puis `$HARNAIS/test_regles_scalingo.sh`.
Expected: les attendus `12e46700` et `4cb10f00` du Step 2 ; `d2812573` et `c4a313b3` sans message (6a/6b viennent en Task 5).

- [ ] **Step 6: Commit**

```bash
git add docs/observabilite/supervision/rules/1-rules-applicatives.console docs/observabilite/supervision/alertes-applicatives.md
git commit -m "feat(alertes-applicatives): A4a et A4b, événements Scalingo des apps applicatives"
git push
```

---

## Task 5: Règles de la stack 6a / 6b / 14

**Files:**
- Modify: `docs/observabilite/supervision/rules/2-rules-stack-observabilite.console` (6a, 6b après 5b ; 14 après 10)
- Modify: `docs/observabilite/supervision/alertes-stack-observabilite.md` (récapitulatif lignes 6 → 6a/6b et nouvelle ligne 14 ; section « Alerte 6 » réécrite ; nouvelle section « Alerte 14 » ; avertissement d'en-tête sur Mattermost mis à jour)

**Interfaces:**
- Consumes: `generer_regles.py` (Task 4).
- Produces: règles 6a (`c16f2ab5…`), 6b (`5d1f7c2a…`), 14 (`ae398f47…`).

- [ ] **Step 1: Insérer les blocs**

`python3 -I generer_regles.py 6a 6b` inséré après le bloc « 5b » ; `python3 -I generer_regles.py 14` inséré après le bloc « 10 ».

- [ ] **Step 2: Documentation**

Dans `alertes-stack-observabilite.md` :
- récapitulatif : remplacer la ligne 6 par 6a (`logs-alertes-scalingo-prod-default`, apps de la stack, 1 min, `#o11y-production`, ⚠️) et 6b (hors prod, 5 min, `#o11y-staging`, ⚠️) ; ajouter 14 (les 4 `::failures`, tout document, 5 min, `#o11y-production`, ⚠️) ;
- section « Alerte 6 » : remplacer la configuration manuelle des notifiers Scalingo vers Mattermost par la description des règles 6a/6b (Kibana Rules sur les événements Scalingo des apps de la stack, catégories, étapes) ; garder la capture de payload ; renvoyer à [la collecte](../collecte/evenements-externes/README.md#mise-en-service) pour les notifiers ;
- nouvelle section « Alerte 14 — Événement externe rejeté » (reprise de X5) ;
- en-tête : l'avertissement « Mattermost est décommissionné… » ne mentionne plus l'alerte 6 comme hors Kibana ; seules 11 et 12 (AutoOps) le restent.

- [ ] **Step 3: Vérifier**

Run: créer 6a, 6b, 14 sur la pile (POST + `rule_type_id` / `consumer`), purger les index `mm-*`, puis `$HARNAIS/test_regles_scalingo.sh`.
Expected: les 4 attendus du Task 4 Step 2 exactement ; aucune ligne Logstash dans `12e46700`, aucune ligne api dans `d2812573`.

Puis, pour 14 : injecter un payload invalide (`logs-alertes-scalingo-staging-default/_doc` avec `{"app_name":"pass-emploi-api-prod","type":"restart"}`), `_run_soon` de `ae398f47…`, `python3 -I $HARNAIS/mm.py d2812573`.
Expected: un message « Événements externes rejetés … » avec une ligne `fail_processor_exception`.

- [ ] **Step 4: Commit**

```bash
git add docs/observabilite/supervision/rules/2-rules-stack-observabilite.console docs/observabilite/supervision/alertes-stack-observabilite.md
git commit -m "feat(alertes-stack): 6a/6b événements Scalingo de la stack, 14 événements externes rejetés"
git push
```

---

## Task 6: Sécurité V1, suppression des X et des références

**Files:**
- Create: `docs/observabilite/supervision/alertes-securite.md`
- Create: `docs/observabilite/supervision/rules/3-rules-securite.console`
- Delete: `docs/observabilite/supervision/rules/3-rules-alertes-externes.console`, `docs/observabilite/supervision/alertes-externes.md`
- Modify: `docs/observabilite/supervision/objets-kibana.md`, `docs/observabilite/README.md`, `docs/observabilite/routine-surveillance.md`, `docs/observabilite/supervision/workflows/tchap/README.md`, `docs/decisions/ADR-004-notifications-tchap-kibana-workflows.md`, `docs/superpowers/specs/2026-10-19-migration-mattermost-tchap-design.md` (statut, écarts)

**Interfaces:**
- Consumes: `generer_regles.py` (V1), docs des Tasks 3 à 5.

- [ ] **Step 1: V1**

`rules/3-rules-securite.console` : en-tête (« Règles Kibana des alertes de sécurité. Spécification : ../alertes-securite.md. PUT met à jour ; sur un cluster vide, POST avec "rule_type_id": ".es-query", "consumer": "alerts". ») puis `python3 -I generer_regles.py V1`.

`alertes-securite.md` : titre, introduction (périmètre : vulnérabilités des dépendances), récapitulatif (V1), section V1 reprise de X4 de `alertes-externes.md` (signal, données, « À vérifier », comportement : notifiée à chaque passage de `security-alerts.yml`), renvoi à [la collecte](../collecte/evenements-externes/README.md).

- [ ] **Step 2: Supprimer les X**

```bash
git rm docs/observabilite/supervision/rules/3-rules-alertes-externes.console docs/observabilite/supervision/alertes-externes.md
grep -rn "alertes-externes\.md\|3-rules-alertes-externes\|X[1-5]\b" docs --include=*.md --include=*.console | grep -v "docs/superpowers"
```
Expected: les occurrences restantes sont à corriger dans les fichiers listés en tête de tâche (objets-kibana : tableau des requêtes Dev Tools et sessions → `discovers/evenements-externes/`, `rules/3-rules-securite.console` ; observabilite/README : lignes `alertes-externes.md` → collecte et `alertes-securite.md` ; routine-surveillance ; README Tchap : exemples X1 → A4a ; ADR-004 : liens). Corriger jusqu'à ce que la commande ne renvoie plus rien.

- [ ] **Step 3: Vérifier les liens**

Run: `python3 -I $HARNAIS/liens.py $(git ls-files 'docs/*.md' | grep -v superpowers)`
Expected: seules les fausses alertes connues (`${EVENT_LINK}` d'AutoOps dans `alertes-stack-observabilite.md`) ; aucun autre `cassé:`.

- [ ] **Step 4: Rejeu complet sur cluster vide**

Run: `$HARNAIS/pile.sh down && $HARNAIS/pile.sh up`, puis rejouer dans l'ordre de la mise en service (`collecte/evenements-externes/README.md#mise-en-service`) : stockage, pipelines, accès, sessions, Workflows Tchap, puis `rules/1-…` (A4a, A4b seulement), `2-…` (6a, 6b, 14 seulement), `3-rules-securite.console` (POST), et `$HARNAIS/test_regles_scalingo.sh`.
Expected: les 4 attendus du Task 4 Step 2 ; V1 en `ok`.

- [ ] **Step 5: Mettre à jour la spec**

Dans la spec : statut « Plan 1 implémenté le <date> » ; §8 étape 1 cochée pour la partie réorganisation ; section « Écarts » si un choix du plan a divergé.

- [ ] **Step 6: Commit**

```bash
git add -A docs
git commit -m "refactor(alertes): V1 dans alertes-securite, fin des alertes X1 à X5"
git push
```

- [ ] **Step 7: Arrêter la pile**

Run: `$HARNAIS/pile.sh down`
