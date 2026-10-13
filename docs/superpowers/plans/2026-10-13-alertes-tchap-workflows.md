# Notifications d'alertes vers Tchap via Kibana Workflows — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Les règles X1 à X5 notifient Tchap (en plus de Mattermost jusqu'au 1ᵉʳ novembre) via un Workflow Kibana par salon et un Workflow `tchap-client` unique, sans brique hébergée chez nous.

**Architecture:** Les ingest pipelines écrivent une ligne de notification dans `message`. Chaque règle a une action `.workflows` vers le Workflow de son salon (`tchap-<salon>`), qui boucle sur les alertes, construit texte et HTML, et appelle `tchap-client` (`workflow.execute`). `tchap-client` fait le `PUT …/send/m.room.message/{{ execution.id }}` par le connecteur `.http` « Tchap ». Une règle sans action expose les envois en échec.

**Tech Stack:** Elastic Cloud 9.4.7 (licence Enterprise) : ingest pipelines Painless, Kibana Alerting (`.es-query`), Kibana Workflows (YAML, Liquid), connecteur `.http` ; Tchap (Matrix / Synapse). Tests sur une pile locale Docker (Elasticsearch + Kibana 9.4.7 trial + Synapse).

**Spec:** [`docs/superpowers/specs/2026-10-13-alertes-tchap-workflows-design.md`](../specs/2026-10-13-alertes-tchap-workflows-design.md)

## Global Constraints

- Kibana / Elasticsearch **9.4.7** ; les Workflows exigent la licence **Enterprise** (pas de contrôle de licence à la mise en service : décision consignée dans l'ADR-004).
- Fichiers des Workflows **à plat** dans `docs/observabilite/supervision/workflows/tchap/` : `connecteur-tchap.console`, `tchap-client.console`, `tchap-monitoring-production.console`, `tchap-monitoring-staging.console`, `tchap-o11y-production.console`, `tchap-o11y-staging.console`, `README.md`. Pas de sous-répertoire.
- IDs fixes : connecteur Tchap `a81b2350-0d23-4358-b984-2c18ceef8601` ; Workflows `tchap-client`, `tchap-monitoring-production`, `tchap-monitoring-staging`, `tchap-o11y-production`, `tchap-o11y-staging` ; règle de supervision `26888801-090e-41ee-839b-73d2832330a8`.
- Repères à substituer à l'import, **jamais commités** : `<jeton-du-bot>`, `<id-salon-monitoring-production>`, `<id-salon-monitoring-staging>`, `<id-salon-o11y-production>`, `<id-salon-o11y-staging>`.
- URL Tchap : `https://matrix.agent.tchap.gouv.fr`.
- Routage : X1, X2, X4 → `tchap-monitoring-production` ; X3 → `tchap-monitoring-staging` ; X5 → `tchap-o11y-production`. Actions Mattermost **inchangées**.
- Sévérité par tag de règle : `critical` → 🚨 (X1, X4), `warning` → ⚠️ (X2, X3, X5).
- La ligne `message` est du **texte brut sans markdown**.
- Commentaires (CLAUDE.md) : uniquement les faits non évidents ; en-têtes de fichier `.console` au style des fichiers voisins (spécification + fait non évident).
- **Commits** : `docs/observabilite/supervision/pipelines/`, `rules/3-rules-alertes-externes.console`, `alertes-externes.md` sont du travail **non commité** de l'utilisateur sur la branche `ops/o11y-centralisation-alertes-exterieures-dans-kibana`. Avant le premier commit (Task 1), **demander à l'utilisateur** s'il faut committer ces fichiers avec nos modifications ou s'il les committe d'abord lui-même. Ne jamais pousser.

## Review Focus

- **Champ Scalingo absent** (alerte sans `value_text`, scale sans `previous_containers`, événement sans auteur) : la ligne reste lisible, sans `null` → test `_simulate` dédié en Task 1.
- **Alerte avec un seul document** (`message` = valeur unique) ou **sans `message`** (X5, failure store) : une ligne est produite (la valeur, ou `kibana.alert.reason`) → cas testés en Task 4.
- **Caractères HTML dans les données** (`<`, `&`, `"` dans un résumé de CVE ou une raison de crash) : échappés dans le HTML, intacts dans le texte → Task 4.
- **Règle sans tag de sévérité, sans `evaluation.value` ou sans `kibana.alert.url`** (les 29 règles du lot suivant) : message envoyé quand même, sans émoji, sans `()` vide, sans lien cassé → Task 4.
- **Deux événements pendant que l'alerte reste active** : deux messages, sans renvoi du premier (`alertStates.ongoing: true` + `excludeHitsFromPreviousRun`) → Task 5.

---

## Task 0: Harnais de test local (non commité)

Aucun outil du repo ne rejoue les `.console` : ce harnais vit hors du repo, dans le dossier temporaire de la session.

**Files (hors repo, `HARNAIS=/home/alexandre-tingaud/.claude/jobs/10d0628e/tmp/harnais`) :**
- Create: `$HARNAIS/pile.sh` (démarrer / arrêter Elasticsearch, Kibana, Synapse)
- Create: `$HARNAIS/replay.py` (rejouer un `.console`)
- Create: `$HARNAIS/synapse_init.py` (bot, humain, 4 salons → `$HARNAIS/salons.json`)
- Create: `$HARNAIS/salon.py` (lire les derniers messages d'un salon)

**Interfaces:**
- Produces: `replay.py FICHIER [--set ANCIEN=NOUVEAU]... [--seul REGEX] [--tolerer CODE]... [--sortie FICHIER.json]` ; `salon.py NOM [-n N]` (affiche `body` puis `HTML: formatted_body`) ; `salons.json` = `{"bot": "<jeton>", "hum": "<jeton>", "salons": {"monitoring-production": "!…:localhost", …}}` ; mocks Mattermost = index `mattermost-simule`.

- [ ] **Step 1: Écrire `pile.sh`**

```bash
#!/bin/bash
set -e
HARNAIS=$(cd "$(dirname "$0")" && pwd)
case "$1" in
  up)
    mkdir -p "$HARNAIS/synapse-data" && chmod 777 "$HARNAIS/synapse-data"
    [ -f "$HARNAIS/synapse-data/homeserver.yaml" ] || docker run --rm -v "$HARNAIS/synapse-data:/data" -e SYNAPSE_SERVER_NAME=localhost -e SYNAPSE_REPORT_STATS=no matrixdotorg/synapse:latest generate
    docker network create tchap-harnais >/dev/null 2>&1 || true
    docker run -d --rm --name th-synapse --network tchap-harnais -v "$HARNAIS/synapse-data:/data" -p 127.0.0.1:8008:8008 matrixdotorg/synapse:latest >/dev/null
    docker run -d --rm --name th-es --network tchap-harnais -p 127.0.0.1:19200:9200 -m 2g -e discovery.type=single-node -e ELASTIC_PASSWORD=testpass123 -e xpack.security.http.ssl.enabled=false -e xpack.license.self_generated.type=trial -e ES_JAVA_OPTS="-Xms1g -Xmx1g" docker.elastic.co/elasticsearch/elasticsearch:9.4.7 >/dev/null
    until [ "$(curl -s -u elastic:testpass123 -XPOST localhost:19200/_security/user/kibana_system/_password -H 'Content-Type: application/json' -d '{"password":"kibanapass123"}')" = "{}" ]; do sleep 3; done
    docker run -d --rm --name th-kibana --network tchap-harnais -p 127.0.0.1:15601:5601 -e ELASTICSEARCH_HOSTS=http://th-es:9200 -e ELASTICSEARCH_USERNAME=kibana_system -e ELASTICSEARCH_PASSWORD=kibanapass123 -e XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa -e SERVER_PUBLICBASEURL=http://localhost:15601 docker.elastic.co/kibana/kibana:9.4.7 >/dev/null
    until curl -s -u elastic:testpass123 localhost:15601/api/status | grep -q '"level":"available"'; do sleep 4; done
    for c in 12e46700-6e45-11ec-9757-c9700cd1bb4e c4a313b3-aa42-4e07-8196-c007625ce8af d2812573-52bf-4b48-9e54-a79a8b5b227d; do
      curl -s -u elastic:testpass123 -H kbn-xsrf:true -H Content-Type:application/json "localhost:15601/api/actions/connector/$c" \
        -d '{"name":"Mattermost-simule-'"$c"'","connector_type_id":".webhook","config":{"url":"http://th-es:9200/mattermost-simule/_doc","method":"post","hasAuth":true,"authType":"webhook-authentication-basic","headers":{"Content-Type":"application/json"}},"secrets":{"user":"elastic","password":"testpass123"}}' >/dev/null
    done
    echo "pile prête" ;;
  down)
    docker stop th-kibana th-es th-synapse >/dev/null 2>&1 || true
    docker network rm tchap-harnais >/dev/null 2>&1 || true ;;
esac
```

- [ ] **Step 2: Écrire `replay.py`**

```python
#!/usr/bin/env python3
import argparse, base64, json, re, sys, urllib.error, urllib.request

ES = 'http://127.0.0.1:19200'
KIBANA = 'http://127.0.0.1:15601'
AUTH = 'Basic ' + base64.b64encode(b'elastic:testpass123').decode()
REQUEST_LINE = re.compile(r'^(GET|POST|PUT|DELETE) (\S+)\s*$')
TRIPLE_QUOTED = re.compile(r'"""(.*?)"""', re.S)


def requests_of(text):
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        match = REQUEST_LINE.match(lines[i])
        i += 1
        if not match:
            continue
        body = None
        if i < len(lines) and lines[i] == '{':
            start = i
            while lines[i] != '}':
                i += 1
            i += 1
            raw = '\n'.join(lines[start:i])
            body = json.loads(TRIPLE_QUOTED.sub(lambda m: json.dumps(m.group(1)), raw))
        yield match.group(1), match.group(2), body


def send(method, path, body):
    if path.startswith('kbn:'):
        url, headers = KIBANA + path[4:], {'kbn-xsrf': 'true'}
    else:
        url, headers = ES + (path if path.startswith('/') else '/' + path), {}
    headers.update({'Authorization': AUTH, 'Content-Type': 'application/json'})
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read() or b'{}')
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b'{}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('fichier')
    parser.add_argument('--set', action='append', default=[])
    parser.add_argument('--seul')
    parser.add_argument('--tolerer', action='append', type=int, default=[])
    parser.add_argument('--sortie')
    args = parser.parse_args()
    text = open(args.fichier).read()
    for pair in args.set:
        old, new = pair.split('=', 1)
        text = text.replace(old, new)
    results, failed = [], False
    for method, path, body in requests_of(text):
        if args.seul and not re.search(args.seul, path):
            continue
        status, response = send(method, path, body)
        print(status, method, path)
        if status >= 400 and status not in args.tolerer:
            failed = True
            print('  ', json.dumps(response, ensure_ascii=False)[:600])
        results.append({'method': method, 'path': path, 'status': status, 'response': response})
    if args.sortie:
        json.dump(results, open(args.sortie, 'w'), ensure_ascii=False, indent=1)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
```

- [ ] **Step 3: Écrire `synapse_init.py`**

```python
#!/usr/bin/env python3
import json, os, subprocess, urllib.parse, urllib.request

HS = 'http://127.0.0.1:8008'
SALONS = ['monitoring-production', 'monitoring-staging', 'o11y-production', 'o11y-staging']
HERE = os.path.dirname(os.path.abspath(__file__))


def mx(method, path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(HS + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b'{}')


def login(user, password):
    return mx('POST', '/_matrix/client/v3/login', {'type': 'm.login.password', 'identifier': {'type': 'm.id.user', 'user': user}, 'password': password})['access_token']


for user, password in [('alertes-bot', 'botpass123'), ('humain', 'humainpass123')]:
    subprocess.run(['docker', 'exec', 'th-synapse', 'register_new_matrix_user', '-c', '/data/homeserver.yaml', '-u', user, '-p', password, '--no-admin', 'http://localhost:8008'], capture_output=True)
bot, hum = login('alertes-bot', 'botpass123'), login('humain', 'humainpass123')
salons = {}
for name in SALONS:
    room = mx('POST', '/_matrix/client/v3/createRoom', {'name': name, 'preset': 'private_chat'}, hum)['room_id']
    quoted = urllib.parse.quote(room, safe='')
    mx('POST', f'/_matrix/client/v3/rooms/{quoted}/invite', {'user_id': '@alertes-bot:localhost'}, hum)
    mx('POST', f'/_matrix/client/v3/rooms/{quoted}/join', {}, bot)
    salons[name] = room
json.dump({'bot': bot, 'hum': hum, 'salons': salons}, open(os.path.join(HERE, 'salons.json'), 'w'), indent=1)
print(json.dumps(salons, indent=1))
```

- [ ] **Step 4: Écrire `salon.py`**

```python
#!/usr/bin/env python3
import argparse, json, os, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
parser = argparse.ArgumentParser()
parser.add_argument('salon')
parser.add_argument('-n', type=int, default=1)
args = parser.parse_args()
state = json.load(open(os.path.join(HERE, 'salons.json')))
room = urllib.parse.quote(state['salons'][args.salon], safe='')
request = urllib.request.Request(f'http://127.0.0.1:8008/_matrix/client/v3/rooms/{room}/messages?dir=b&limit=50', headers={'Authorization': 'Bearer ' + state['hum']})
events = [e for e in json.load(urllib.request.urlopen(request))['chunk'] if e['type'] == 'm.room.message']
for event in reversed(events[:args.n]):
    print(event['content'].get('body', ''))
    print('HTML:', event['content'].get('formatted_body', ''))
```

- [ ] **Step 5: Démarrer la pile et créer les salons**

Run: `HARNAIS=/home/alexandre-tingaud/.claude/jobs/10d0628e/tmp/harnais; chmod +x $HARNAIS/*.sh $HARNAIS/*.py; $HARNAIS/pile.sh up && python3 -I $HARNAIS/synapse_init.py`
Expected: `pile prête`, puis 4 salons `!…:localhost`.

- [ ] **Step 6: Rejouer l'existant (base de comparaison)**

Run (depuis `docs/observabilite`) :
```bash
for f in stockage/logs/1-ilm-policies.console stockage/logs/2-component-templates.console stockage/logs/3-index-templates.console \
         supervision/pipelines/ingest-alertes-scalingo.console supervision/pipelines/ingest-alertes-scalingo-prod-default.console \
         supervision/pipelines/ingest-alertes-scalingo-staging-default.console supervision/pipelines/ingest-alertes-scalingo-perf-default.console \
         supervision/pipelines/ingest-alertes-github-default.console supervision/rules/3-rules-alertes-externes.console; do
  python3 -I $HARNAIS/replay.py $f --tolerer 409 || echo "ÉCHEC $f"; done
```
Expected: aucun `ÉCHEC`. Un `ÉCHEC` sur un bloc de `stockage/` qui dépend d'un objet propre au cluster Elastic Cloud (policy ILM gérée par Elastic) est acceptable s'il ne concerne pas `logs-alertes*` : le noter et continuer.

Rien à committer (hors repo).

---

## Task 1: Ligne `message` des événements Scalingo

**Files:**
- Modify: `docs/observabilite/supervision/pipelines/ingest-alertes-scalingo.console` (nouveau processeur en fin de `processors`, nouveaux attendus et documents de test)

**Interfaces:**
- Produces: champ `message` (texte brut) sur chaque document des data streams `logs-alertes-scalingo-<env>-default`, lu par les Workflows de salon (Task 4) via `kibana.alert.*`. Le préfixe est le **nom complet de l'app** (`scalingo.app_name`, ex. `pass-emploi-api-prod`), car `service.name` a perdu son suffixe d'environnement et X3 mélange staging et perf.

- [ ] **Step 1: Ajouter les attendus et les documents de test**

Dans la section TESTS, remplacer le commentaire d'attendus du premier `_simulate` par (les 3 lignes d'attendus existantes restent, on ajoute `message`) :

```
# alert → event.kind: alert, event.action: resource_threshold_exceeded,
#   event.outcome: failure, service.name: pass-emploi-logstash,
#   service.environment: perf, service.node.name: web-1, labels.metric: RAM,
#   message: "pass-emploi-logstash-perf : RAM à 96.96 % (seuil ≥ 90.0 %) sur web-1"
# scale → event.action: app_scaled, labels.formation: "web=0:L worker=0:L",
#   labels.formation_before: "web=1:L worker=0:L", labels.scaled_to_zero: "true",
#   message: "pass-emploi-logstash-perf : app_scaled web=1:L worker=0:L → web=0:L worker=0:L, par prenom.nom"
# restart → event.action: app_restarted, event.reason: user_restart,
#   labels.scope: web, pas d'event.outcome (redémarrage volontaire),
#   message: "pass-emploi-logstash-perf : app_restarted (user_restart) sur web, par prenom.nom"
```

Remplacer le commentaire d'attendus du second `_simulate` par :

```
# crash (forme supposée, non capturée) → event.action: app_crashed,
#   event.outcome: failure, service.environment: prod,
#   message: "pass-emploi-api-prod : app_crashed (oom) sur web, par scalingo-platform"
# type inconnu, sans auteur → event.action: scalingo_<type>, indexé quand même,
#   message: "pass-emploi-api-staging : scalingo_new_variable"
# alerte levée → message: "pass-emploi-api-prod : RAM revenue à 45.00 % (seuil ≥ 90.0 %) sur web-1"
# alerte incomplète → message: "pass-emploi-api-prod : CPU (seuil inconnu)", jamais "null"
```

Et ajouter à la fin du tableau `docs` du second `_simulate` :

```json
    { "_source": {"id":"test-retour","created_at":"2026-10-12T08:00:00.000Z","type":"alert","app_id":"test","app_name":"pass-emploi-api-prod","user":{"username":"scalingo-platform"},"type_data":{"sender_name":"web-1","metric":"RAM","limit_text":"≥ 90.0 %","value_text":"45.00 %","activated":false}} },
    { "_source": {"id":"test-incomplet","created_at":"2026-10-12T08:00:00.000Z","type":"alert","app_id":"test","app_name":"pass-emploi-api-prod","type_data":{"metric":"CPU","activated":true}} }
```

(le document précédent du tableau, `test-inconnu`, prend une virgule finale).

- [ ] **Step 2: Vérifier que les tests échouent**

Run (depuis `docs/observabilite`) :
```bash
python3 -I $HARNAIS/replay.py supervision/pipelines/ingest-alertes-scalingo.console --sortie $HARNAIS/scalingo.json
python3 -I - $HARNAIS/scalingo.json <<'EOF'
import json, sys
expected = [
    "pass-emploi-logstash-perf : RAM à 96.96 % (seuil ≥ 90.0 %) sur web-1",
    "pass-emploi-logstash-perf : app_scaled web=1:L worker=0:L → web=0:L worker=0:L, par prenom.nom",
    "pass-emploi-logstash-perf : app_restarted (user_restart) sur web, par prenom.nom",
    "pass-emploi-api-prod : app_crashed (oom) sur web, par scalingo-platform",
    "pass-emploi-api-staging : scalingo_new_variable",
    "pass-emploi-api-prod : RAM revenue à 45.00 % (seuil ≥ 90.0 %) sur web-1",
    "pass-emploi-api-prod : CPU (seuil inconnu)",
]
docs = [d['doc']['_source'] for r in json.load(open(sys.argv[1])) if r['path'].endswith('_simulate') for d in r['response']['docs']]
actual = [d.get('message') for d in docs]
for e, a in zip(expected, actual):
    print('OK ' if e == a else 'KO ', repr(a), '' if e == a else '≠ ' + repr(e))
sys.exit(0 if actual == expected else 1)
EOF
```
Expected: 7 lignes `KO  None`, code de sortie 1.

- [ ] **Step 3: Ajouter le processeur**

Ajouter en dernier élément de `processors` (après le processeur `labels.*`) :

```json
    {
      "script": {
        "description": "message : la ligne de notification de l'événement, en texte brut",
        "source": """
          Map labels = ctx.labels;
          StringBuilder line = new StringBuilder(ctx.scalingo.app_name).append(' : ');
          if (ctx.scalingo.type == 'alert') {
            line.append(labels.getOrDefault('metric', 'ressource'));
            if (labels.value_text != null) {
              line.append(ctx.event.action == 'resource_threshold_exceeded' ? ' à ' : ' revenue à ').append(labels.value_text);
            }
            line.append(' (seuil ').append(labels.getOrDefault('limit_text', 'inconnu')).append(')');
            if (ctx.service.node != null) {
              line.append(' sur ').append(ctx.service.node.name);
            }
          } else {
            line.append(ctx.event.action);
            if (labels.formation_before != null && labels.formation != null) {
              line.append(' ').append(labels.formation_before).append(' → ').append(labels.formation);
            }
            if (ctx.event.reason != null) {
              line.append(' (').append(ctx.event.reason).append(')');
            }
            if (labels.scope != null) {
              line.append(' sur ').append(labels.scope);
            }
            if (ctx.user != null && ctx.user.name != null) {
              line.append(', par ').append(ctx.user.name);
            }
          }
          ctx.message = line.toString();
        """
      }
    }
```

(le processeur précédent prend une virgule finale après sa `}`).

- [ ] **Step 4: Vérifier que les tests passent**

Run: la même commande qu'au Step 2.
Expected: 7 lignes `OK`, code de sortie 0. Rejouer aussi les trois `ingest-alertes-scalingo-<env>-default.console` : chacun doit répondre `200` sur son `PUT` et ses `_simulate` doivent toujours afficher `message`.

- [ ] **Step 5: Commit** (après accord de l'utilisateur sur la stratégie de commit, cf. Global Constraints)

```bash
git add docs/observabilite/supervision/pipelines/ingest-alertes-scalingo.console
git commit -m "feat(alertes-externes): ligne de notification message dans le pipeline Scalingo"
```

---

## Task 2: Ligne `message` des CVE Dependabot

**Files:**
- Modify: `docs/observabilite/supervision/pipelines/ingest-alertes-github-default.console` (fin du script « service, event, vulnerability, package », attendus)

**Interfaces:**
- Produces: `message` sur chaque document de `logs-alertes-github-default`.

- [ ] **Step 1: Ajouter l'attendu**

Remplacer le commentaire d'attendus du `_simulate` par :

```
# Dependabot (alerte fictive, schéma de l'API REST) → event.provider: github,
#   service.name: pass-emploi-api, vulnerability.id: CVE-2026-00000,
#   vulnerability.severity: high, package.name: axios,
#   message: "pass-emploi-api : CVE-2026-00000 — axios (high) : Exemple de vulnérabilité — https://github.com/France-Travail/pass-emploi-api/security/dependabot/42"
# sans dependency.package → message sans le nom du paquet :
#   "pass-emploi-web : GHSA-yyyy-yyyy-yyyy (critical) : Résumé <avec> & \"guillemets\" — https://github.com/France-Travail/pass-emploi-web/security/dependabot/7"
# payload sans security_advisory → erreur (failure store en réel)
```

Et insérer comme 2ᵉ document du `_simulate` :

```json
    { "_source": {"number":7,"state":"open","repository":"pass-emploi-web","html_url":"https://github.com/France-Travail/pass-emploi-web/security/dependabot/7","security_advisory":{"ghsa_id":"GHSA-yyyy-yyyy-yyyy","summary":"Résumé <avec> & \"guillemets\"","severity":"critical"}} },
```

- [ ] **Step 2: Vérifier que le test échoue**

Run :
```bash
python3 -I $HARNAIS/replay.py supervision/pipelines/ingest-alertes-github-default.console --sortie $HARNAIS/github.json
python3 -I - $HARNAIS/github.json <<'EOF'
import json, sys
expected = [
    "pass-emploi-api : CVE-2026-00000 — axios (high) : Exemple de vulnérabilité — https://github.com/France-Travail/pass-emploi-api/security/dependabot/42",
    'pass-emploi-web : GHSA-yyyy-yyyy-yyyy (critical) : Résumé <avec> & "guillemets" — https://github.com/France-Travail/pass-emploi-web/security/dependabot/7',
]
docs = [d for r in json.load(open(sys.argv[1])) if r['path'].endswith('_simulate') for d in r['response']['docs']]
actual = [d['doc']['_source'].get('message') for d in docs[:2]]
print(actual)
sys.exit(0 if actual == expected and 'error' in docs[2] else 1)
EOF
```
Expected: `[None, None]`, code de sortie 1.

- [ ] **Step 3: Écrire `message`**

À la fin du script « service, event, vulnerability, package », après le bloc `if (alert.dependency instanceof Map …) { … }`, ajouter :

```
          String paquet = ctx['package'] instanceof Map ? ' — ' + ctx['package'].name : '';
          ctx.message = repository + ' : ' + vulnerability.id + paquet + ' (' + vulnerability.severity + ') : '
            + vulnerability.description + ' — ' + vulnerability.reference;
```

- [ ] **Step 4: Vérifier que le test passe**

Run: la commande du Step 2.
Expected: les deux lignes attendues, code de sortie 0 (le 3ᵉ document reste en erreur).

- [ ] **Step 5: Commit**

```bash
git add docs/observabilite/supervision/pipelines/ingest-alertes-github-default.console
git commit -m "feat(alertes-externes): ligne de notification message dans le pipeline GitHub"
```

---

## Task 3: Connecteur Tchap et `tchap-client`

**Files:**
- Create: `docs/observabilite/supervision/workflows/tchap/connecteur-tchap.console`
- Create: `docs/observabilite/supervision/workflows/tchap/tchap-client.console`

**Interfaces:**
- Produces: Workflow `tchap-client`, déclenchement `manual`, entrées `salon` (ID `!…`, encodé par le Workflow), `texte` (brut), `html` (déjà échappé). Un appel = un message, `txnId = execution.id`.

- [ ] **Step 1: Écrire le test (exécution manuelle, deux fois)**

Le test, à lancer après l'import : deux exécutions identiques doivent donner **deux** messages (un `txnId` réutilisé serait avalé), et un faux salon doit donner une exécution `failed`.

```bash
cat > $HARNAIS/test_tchap_client.sh <<'EOF'
#!/bin/bash
H=$(dirname "$0"); SALON=$(python3 -c "import json;print(json.load(open('$H/salons.json'))['salons']['monitoring-staging'])")
run() { curl -s -u elastic:testpass123 -H kbn-xsrf:true -H Content-Type:application/json localhost:15601/api/workflows/workflow/tchap-client/run \
  -d "{\"inputs\":{\"salon\":\"$1\",\"texte\":\"test client\",\"html\":\"<b>test client</b>\"}}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["workflowExecutionId"])'; }
run "$SALON" >/dev/null; run "$SALON" >/dev/null; ECHEC=$(run '!inexistant:localhost'); sleep 10
python3 -I $H/salon.py monitoring-staging -n 2
curl -s -u elastic:testpass123 localhost:15601/api/workflows/executions/$ECHEC | python3 -c 'import json,sys;d=json.load(sys.stdin);print("échec:", d["status"], d["error"]["message"])'
EOF
chmod +x $HARNAIS/test_tchap_client.sh
```

- [ ] **Step 2: Vérifier que le test échoue**

Run: `$HARNAIS/test_tchap_client.sh`
Expected: erreur (Workflow `tchap-client` introuvable, `KeyError: 'workflowExecutionId'`).

- [ ] **Step 3: Écrire `connecteur-tchap.console`**

```
# Connecteur .http vers Tchap, le seul utilisé par les Workflows Tchap
# (tchap-client). Spécification : README.md.
#
# Jeton du compte bot : à substituer à <jeton-du-bot> au moment de l'import,
# rangé dans le coffre de l'équipe, JAMAIS commité. Kibana le chiffre et ne le
# renvoie plus, ni par l'API ni dans les exécutions. authType: null est exigé
# avec hasAuth: false (sinon erreur de validation).
# Mise à jour (rotation du jeton) : PUT sur la même URL, même corps SANS
# "connector_type_id".
POST kbn:/api/actions/connector/a81b2350-0d23-4358-b984-2c18ceef8601
{
  "name": "Tchap",
  "connector_type_id": ".http",
  "config": {
    "url": "https://matrix.agent.tchap.gouv.fr",
    "hasAuth": false,
    "authType": null
  },
  "secrets": {
    "secretHeaders": {
      "Authorization": "Bearer <jeton-du-bot>"
    }
  }
}
```

- [ ] **Step 4: Écrire `tchap-client.console`**

```
# Workflow tchap-client : le seul qui parle à Matrix. Appelé par les Workflows
# de salon (tchap-<salon>). Spécification : README.md.
#
# Le txnId de Matrix doit changer à chaque message : un txnId déjà vu est pris
# pour une nouvelle tentative et le message n'est pas posté. execution.id est
# unique par appel.
# Mise à jour : PUT kbn:/api/workflows/workflow/tchap-client avec {"yaml": …}.
POST kbn:/api/workflows/workflow
{
  "id": "tchap-client",
  "yaml": """
name: Tchap - Client
description: Poste un message dans un salon Tchap
enabled: true
triggers:
  - type: manual
inputs:
  - name: salon
    type: string
    required: true
    description: ID du salon (!…:agent.tchap.gouv.fr)
  - name: texte
    type: string
    required: true
    description: Message en texte brut
  - name: html
    type: string
    required: true
    description: Message en HTML, déjà échappé
steps:
  - name: envoyer
    type: http
    connector-id: a81b2350-0d23-4358-b984-2c18ceef8601
    with:
      method: PUT
      path: /_matrix/client/v3/rooms/{{ inputs.salon | url_encode }}/send/m.room.message/{{ execution.id }}
      body:
        msgtype: m.text
        body: "{{ inputs.texte }}"
        format: org.matrix.custom.html
        formatted_body: "{{ inputs.html }}"
"""
}
```

- [ ] **Step 5: Importer et vérifier que le test passe**

Run (depuis `docs/observabilite`) :
```bash
BOT=$(python3 -c "import json;print(json.load(open('$HARNAIS/salons.json'))['bot'])")
python3 -I $HARNAIS/replay.py supervision/workflows/tchap/connecteur-tchap.console --set "<jeton-du-bot>=$BOT" --set "https://matrix.agent.tchap.gouv.fr=http://th-synapse:8008" --tolerer 409
python3 -I $HARNAIS/replay.py supervision/workflows/tchap/tchap-client.console --tolerer 409
$HARNAIS/test_tchap_client.sh
```
Expected : deux fois `test client` / `HTML: <b>test client</b>`, puis `échec: failed [403] Forbidden: User @alertes-bot:localhost not in room !inexistant:localhost`.

- [ ] **Step 6: Vérifier que le jeton n'est relu nulle part**

Run :
```bash
curl -s -u elastic:testpass123 localhost:15601/api/actions/connector/a81b2350-0d23-4358-b984-2c18ceef8601 | grep -c "$BOT"
curl -s -u elastic:testpass123 "localhost:19200/.workflows-*/_search?q=%22$BOT%22&size=0&expand_wildcards=all" | python3 -c 'import json,sys;print(json.load(sys.stdin)["hits"]["total"]["value"])'
```
Expected: `0` et `0`.

- [ ] **Step 7: Commit**

```bash
git add docs/observabilite/supervision/workflows/tchap/connecteur-tchap.console docs/observabilite/supervision/workflows/tchap/tchap-client.console
git commit -m "feat(tchap): connecteur .http et Workflow tchap-client"
```

---

## Task 4: Workflows de salon

**Files:**
- Create: `docs/observabilite/supervision/workflows/tchap/tchap-monitoring-production.console`
- Create: `docs/observabilite/supervision/workflows/tchap/tchap-monitoring-staging.console`
- Create: `docs/observabilite/supervision/workflows/tchap/tchap-o11y-production.console`
- Create: `docs/observabilite/supervision/workflows/tchap/tchap-o11y-staging.console`

**Interfaces:**
- Consumes: `tchap-client` (entrées `salon`, `texte`, `html`) ; `event` fourni par l'action `.workflows` d'une règle : `event.rule.{id,name,tags}`, `event.ruleUrl`, `event.alerts[]` (documents d'alerte : `kibana.alert.evaluation.value`, `kibana.alert.url`, `kibana.alert.reason`, `message` = liste des lignes de Task 1/2, ou valeur unique, ou absent).
- Produces: un message Tchap par alerte, dans le salon du Workflow. Format :
  - texte : `<sévérité> <nom de la règle>[ (<valeur>)]` puis `\n• <ligne>` par ligne (ou `• <reason>`), puis `\n<url Discover>` si présente ;
  - HTML : `<p><sévérité> <strong><nom></strong>[ (<valeur>)]</p><ul><li>…</li></ul><p>[<a href="<url>">Ouvrir dans Discover</a> · ]<a href="<ruleUrl>">Voir la règle</a></p>`.
  - sévérité : `🚨` si tag `critical`, `⚠️` si tag `warning`, rien sinon (et alors pas d'espace initial).

- [ ] **Step 1: Écrire le test (exécution manuelle avec un `event` fabriqué)**

Un Workflow à déclenchement `alert` se lance aussi à la main : `inputs.event` tient lieu d'`event` (vérifié en 9.4.7). Le test couvre les cas du Review Focus.

```bash
cat > $HARNAIS/test_salon.sh <<'EOF'
#!/bin/bash
H=$(dirname "$0"); WF=${1:-tchap-monitoring-staging}; SALON=${WF#tchap-}
curl -s -u elastic:testpass123 -H kbn-xsrf:true -H Content-Type:application/json localhost:15601/api/workflows/workflow/$WF/run -d @- >/dev/null <<'JSON'
{"inputs":{"event":{
  "rule":{"id":"r1","name":"Règle test","tags":["prod","critical"]},
  "ruleUrl":"http://localhost:15601/app/management/insightsAndAlerting/triggersActions/rule/r1",
  "spaceId":"default",
  "alerts":[
    {"kibana":{"alert":{"evaluation":{"value":"2"},"url":"http://localhost:15601/app/r?l=X&v=1","reason":"inutilisé"}},"message":["app-a : crash (exit \"137\" <OOM>)","app-b : app_restarted & co"]},
    {"kibana":{"alert":{"evaluation":{"value":"1"},"url":"http://localhost:15601/app/r?l=Y"}},"message":"seule ligne"},
    {"kibana":{"alert":{"reason":"Document count is 3 in the last 10m"}}}
  ]}}}
JSON
sleep 15; python3 -I $H/salon.py $SALON -n 3
EOF
chmod +x $HARNAIS/test_salon.sh
```

Attendu, dans l'ordre (3 messages) :
```
🚨 Règle test (2)
• app-a : crash (exit "137" <OOM>)
• app-b : app_restarted & co
http://localhost:15601/app/r?l=X&v=1
HTML: <p>🚨 <strong>Règle test</strong> (2)</p><ul><li>app-a : crash (exit &#34;137&#34; &lt;OOM&gt;)</li><li>app-b : app_restarted &amp; co</li></ul><p><a href="http://localhost:15601/app/r?l=X&v=1">Ouvrir dans Discover</a> · <a href="http://localhost:15601/app/management/insightsAndAlerting/triggersActions/rule/r1">Voir la règle</a></p>
🚨 Règle test (1)
• seule ligne
http://localhost:15601/app/r?l=Y
HTML: <p>🚨 <strong>Règle test</strong> (1)</p><ul><li>seule ligne</li></ul><p><a href="http://localhost:15601/app/r?l=Y">Ouvrir dans Discover</a> · <a href="http://localhost:15601/app/management/insightsAndAlerting/triggersActions/rule/r1">Voir la règle</a></p>
🚨 Règle test
• Document count is 3 in the last 10m
HTML: <p>🚨 <strong>Règle test</strong></p><ul><li>Document count is 3 in the last 10m</li></ul><p><a href="http://localhost:15601/app/management/insightsAndAlerting/triggersActions/rule/r1">Voir la règle</a></p>
```

- [ ] **Step 2: Vérifier que le test échoue**

Run: `$HARNAIS/test_salon.sh`
Expected: les 3 derniers messages du salon ne sont pas ceux attendus (Workflow inexistant : seuls les messages de la Task 3 apparaissent).

- [ ] **Step 3: Écrire `tchap-monitoring-staging.console`**

```
# Workflow du salon Tchap monitoring-staging : à choisir dans l'action
# .workflows d'une règle pour y envoyer ses alertes. Spécification : README.md.
#
# ID du salon : à substituer à <id-salon-monitoring-staging> au moment de
# l'import (Tchap → paramètres du salon → Avancé). Ne parle pas à Matrix :
# construit le message et appelle tchap-client.
# La boucle doit être une étape « type: foreach » : une propriété foreach:
# posée sur l'étape workflow.execute est ignorée sans erreur.
# Mise à jour : PUT kbn:/api/workflows/workflow/tchap-monitoring-staging avec {"yaml": …}.
POST kbn:/api/workflows/workflow
{
  "id": "tchap-monitoring-staging",
  "yaml": """
name: Tchap - monitoring-staging
description: Envoie les alertes de la règle dans le salon Tchap monitoring-staging
enabled: true
triggers:
  - type: alert
consts:
  salon: "<id-salon-monitoring-staging>"
steps:
  - name: chaque-alerte
    type: foreach
    foreach: "{{ event.alerts | json }}"
    steps:
      - name: notifier
        type: workflow.execute
        with:
          workflow-id: tchap-client
          inputs:
            salon: "{{ consts.salon }}"
            texte: "{% if event.rule.tags contains 'critical' %}🚨 {% elsif event.rule.tags contains 'warning' %}⚠️ {% endif %}{{ event.rule.name }}{% if foreach.item.kibana.alert.evaluation.value %} ({{ foreach.item.kibana.alert.evaluation.value }}){% endif %}{% if foreach.item.message %}{% for ligne in foreach.item.message %}\n• {{ ligne }}{% endfor %}{% else %}\n• {{ foreach.item.kibana.alert.reason }}{% endif %}{% if foreach.item.kibana.alert.url %}\n{{ foreach.item.kibana.alert.url }}{% endif %}"
            html: "<p>{% if event.rule.tags contains 'critical' %}🚨 {% elsif event.rule.tags contains 'warning' %}⚠️ {% endif %}<strong>{{ event.rule.name | escape }}</strong>{% if foreach.item.kibana.alert.evaluation.value %} ({{ foreach.item.kibana.alert.evaluation.value }}){% endif %}</p><ul>{% if foreach.item.message %}{% for ligne in foreach.item.message %}<li>{{ ligne | escape }}</li>{% endfor %}{% else %}<li>{{ foreach.item.kibana.alert.reason | escape }}</li>{% endif %}</ul><p>{% if foreach.item.kibana.alert.url %}<a href=\"{{ foreach.item.kibana.alert.url }}\">Ouvrir dans Discover</a> · {% endif %}<a href=\"{{ event.ruleUrl }}\">Voir la règle</a></p>"
"""
}
```

Note : le bloc `"""…"""` de Dev Tools est du texte brut, transmis tel quel : le YAML y voit `\"`, soit un `"` dans sa chaîne entre guillemets doubles, et `\n` un retour à la ligne.

- [ ] **Step 4: Importer et vérifier que le test passe**

Run :
```bash
SALON=$(python3 -c "import json;print(json.load(open('$HARNAIS/salons.json'))['salons']['monitoring-staging'])")
python3 -I $HARNAIS/replay.py supervision/workflows/tchap/tchap-monitoring-staging.console --set "<id-salon-monitoring-staging>=$SALON" --tolerer 409
$HARNAIS/test_salon.sh tchap-monitoring-staging
```
Expected: exactement les 3 messages attendus du Step 1. En cas d'écart de forme, corriger le YAML puis rejouer avec `PUT kbn:/api/workflows/workflow/tchap-monitoring-staging` (`replay.py` ne fait que `POST` : utiliser `curl -XPUT … -d '{"yaml": …}'` ou supprimer puis recréer : `curl -XDELETE -u elastic:testpass123 -H kbn-xsrf:true localhost:15601/api/workflows -H Content-Type:application/json -d '{"ids":["tchap-monitoring-staging"]}'`).

- [ ] **Step 5: Écrire les 3 autres Workflows de salon**

Copier `tchap-monitoring-staging.console` en remplaçant **partout** `monitoring-staging` par le nom du salon :
- `tchap-monitoring-production.console` : id `tchap-monitoring-production`, name `Tchap - monitoring-production`, `<id-salon-monitoring-production>` ;
- `tchap-o11y-production.console` : id `tchap-o11y-production`, name `Tchap - o11y-production`, `<id-salon-o11y-production>` ;
- `tchap-o11y-staging.console` : id `tchap-o11y-staging`, name `Tchap - o11y-staging`, `<id-salon-o11y-staging>`.

```bash
cd docs/observabilite/supervision/workflows/tchap
for s in monitoring-production o11y-production o11y-staging; do sed "s/monitoring-staging/$s/g" tchap-monitoring-staging.console > tchap-$s.console; done
cd -
```

- [ ] **Step 6: Importer et tester les 3 autres**

Run :
```bash
for s in monitoring-production o11y-production o11y-staging; do
  ID=$(python3 -c "import json;print(json.load(open('$HARNAIS/salons.json'))['salons']['$s'])")
  python3 -I $HARNAIS/replay.py supervision/workflows/tchap/tchap-$s.console --set "<id-salon-$s>=$ID" --tolerer 409
  $HARNAIS/test_salon.sh tchap-$s
done
```
Expected: les 3 messages attendus du Step 1, dans chacun des 3 salons.

- [ ] **Step 7: Commit**

```bash
git add docs/observabilite/supervision/workflows/tchap/tchap-*.console
git commit -m "feat(tchap): Workflows de salon monitoring et o11y"
```

---

## Task 5: Règles X1–X5 vers Tchap

**Files:**
- Modify: `docs/observabilite/supervision/rules/3-rules-alertes-externes.console` (tags et `actions` des 5 règles, en-tête)

**Interfaces:**
- Consumes: Workflows de salon (Task 4) ; `message` (Tasks 1-2).
- Produces: chaque règle a 2 actions : l'action Mattermost existante, inchangée, et l'action `.workflows`.

- [ ] **Step 1: Écrire le test de bout en bout**

```bash
cat > $HARNAIS/test_regles.sh <<'EOF'
#!/bin/bash
H=$(dirname "$0"); NOW=$(date -u +%FT%T.%3NZ)
es() { curl -s -u elastic:testpass123 -H Content-Type:application/json "localhost:19200$1" -d "$2"; echo; }
es /logs-alertes-scalingo-staging-default/_doc "{\"id\":\"t1\",\"created_at\":\"$NOW\",\"type\":\"restart\",\"app_id\":\"t\",\"app_name\":\"pass-emploi-api-staging\",\"user\":{\"username\":\"test\"},\"type_data\":{\"scope\":[\"web\"],\"reason\":\"user_restart\"}}"
es /logs-alertes-scalingo-prod-default/_doc "{\"id\":\"t2\",\"created_at\":\"$NOW\",\"type\":\"crash\",\"app_id\":\"t\",\"app_name\":\"pass-emploi-api-prod\",\"user\":{\"username\":\"scalingo-platform\"},\"type_data\":{\"scope\":[\"web\"],\"reason\":\"oom\"}}"
es /logs-alertes-scalingo-staging-default/_doc "{\"id\":\"t3\",\"created_at\":\"$NOW\",\"type\":\"restart\",\"app_id\":\"t\",\"app_name\":\"pass-emploi-api-prod\",\"type_data\":{}}"
es /logs-alertes-github-default/_doc '{"number":1,"repository":"pass-emploi-api","html_url":"https://github.com/France-Travail/pass-emploi-api/security/dependabot/1","dependency":{"package":{"ecosystem":"npm","name":"axios"}},"security_advisory":{"ghsa_id":"GHSA-zzzz","cve_id":"CVE-2026-11111","summary":"Test","severity":"critical"}}'
curl -s -u elastic:testpass123 -XPOST "localhost:19200/logs-alertes-*/_refresh?expand_wildcards=all" >/dev/null
for r in $(grep -o 'kbn:/api/alerting/rule/[0-9a-f-]*' "$1" | cut -d/ -f5); do
  curl -s -u elastic:testpass123 -H kbn-xsrf:true -H x-elastic-internal-origin:kibana -XPOST localhost:15601/internal/alerting/rule/$r/_run_soon >/dev/null; done
sleep 30
for s in monitoring-production monitoring-staging o11y-production; do echo "== $s"; python3 -I $H/salon.py $s -n 3; done
echo "== mattermost-simule"; curl -s -u elastic:testpass123 "localhost:19200/mattermost-simule/_count"; echo
EOF
chmod +x $HARNAIS/test_regles.sh
```

Attendu (l'ordre des messages dans un salon peut varier) :
- `monitoring-staging` : `⚠️ Scalingo - Hors-Prod - Crash, redémarrage, arrêt ou seuil dépassé (1)` / `• pass-emploi-api-staging : app_restarted (user_restart) sur web, par test` ;
- `monitoring-production` : `🚨 Scalingo - Prod - Crash, redémarrage ou arrêt d'une app (1)` / `• pass-emploi-api-prod : app_crashed (oom) sur web, par scalingo-platform`, et `🚨 GitHub - CVE high ou critical ouverte (1)` / `• pass-emploi-api : CVE-2026-11111 — axios (critical) : Test — https://github.com/…/dependabot/1` ;
- `o11y-production` : `⚠️ Alertes externes - Payload rejeté (failure store) (1)` / `• Document count is 1 …` (le document `t3`, app de prod dans le data stream staging, part au failure store) ;
- `mattermost-simule` : `count` ≥ 4 (les actions Mattermost partent toujours).

- [ ] **Step 2: Vérifier que le test échoue**

Run (depuis `docs/observabilite`) : `$HARNAIS/test_regles.sh supervision/rules/3-rules-alertes-externes.console`
Expected: aucun nouveau message dans les salons ; `mattermost-simule` reçoit les documents.

- [ ] **Step 3: Ajouter les tags de sévérité**

Dans `"tags"` de chaque règle, ajouter en premier : `"critical"` pour X1 (`1b97f0e0-…`) et X4 (GitHub) ; `"warning"` pour X2, X3, X5. Exemple X1 :

```json
  "tags": [
    "critical",
    "prod",
    "alertes-externes"
  ],
```

- [ ] **Step 4: Ajouter l'action `.workflows`**

Dans `"actions"` de chaque règle, après l'action Mattermost existante (qui prend une virgule finale), ajouter, avec le `workflowId` de la règle (X1, X2, X4 : `tchap-monitoring-production` ; X3 : `tchap-monitoring-staging` ; X5 : `tchap-o11y-production`) :

```json
    {
      "id": "system-connector-.workflows",
      "params": {
        "subAction": "run",
        "subActionParams": {
          "workflowId": "tchap-monitoring-production",
          "summaryMode": true,
          "alertStates": {
            "new": true,
            "ongoing": true,
            "recovered": false
          }
        }
      }
    }
```

- [ ] **Step 5: Compléter l'en-tête du fichier**

Ajouter à la fin du bloc de commentaires d'en-tête :

```
#
# Chaque règle notifie aussi Tchap : action .workflows vers le Workflow du salon
# (../workflows/tchap/). ongoing: true est nécessaire, une alerte restant active
# tant que des événements arrivent ; recovered: false évite un message à la fin
# de l'alerte. Les actions Mattermost sont retirées le 1er novembre 2026.
```

- [ ] **Step 6: Rejouer et vérifier que le test passe**

Run :
```bash
for id in $(grep -o 'kbn:/api/alerting/rule/[0-9a-f-]*' supervision/rules/3-rules-alertes-externes.console | cut -d/ -f5); do
  curl -s -u elastic:testpass123 -H kbn-xsrf:true -XDELETE localhost:15601/api/alerting/rule/$id; done
python3 -I $HARNAIS/replay.py supervision/rules/3-rules-alertes-externes.console
$HARNAIS/test_regles.sh supervision/rules/3-rules-alertes-externes.console
```
Expected: les messages attendus du Step 1 dans les 3 salons.

- [ ] **Step 7: Deux événements, l'alerte restant active**

Run : réinjecter deux redémarrages staging (`t4`, `t5`, même commande que `t1` avec ces `id`), à 1 minute d'intervalle, chacun suivi d'un `_run_soon` de X3 (`07c9c5d7-e8fe-4964-ac8d-684b1c4c39b8`, même `curl` que dans `test_regles.sh`), puis `python3 -I $HARNAIS/salon.py monitoring-staging -n 3`.
Expected: un message pour `t4`, puis un message pour `t5` seul (le premier n'est pas renvoyé).

- [ ] **Step 8: Commit**

```bash
git add docs/observabilite/supervision/rules/3-rules-alertes-externes.console
git commit -m "feat(alertes-externes): X1 à X5 notifient Tchap via les Workflows de salon"
```

---

## Task 6: Supervision des envois Tchap

**Files:**
- Create: `docs/observabilite/supervision/rules/4-rules-tchap.console`

**Interfaces:**
- Consumes: `.workflows-executions` (`status` et `workflowId` en `keyword`, `finishedAt` en `date`, `error.message` dans `_source`).
- Produces: règle `26888801-090e-41ee-839b-73d2832330a8` « Tchap - Envoi en échec », sans action.

- [ ] **Step 1: Écrire le test**

```bash
cat > $HARNAIS/test_supervision.sh <<'EOF'
#!/bin/bash
curl -s -u elastic:testpass123 -H kbn-xsrf:true -H Content-Type:application/json localhost:15601/api/workflows/workflow/tchap-client/run \
  -d '{"inputs":{"salon":"!inexistant:localhost","texte":"x","html":"x"}}' >/dev/null; sleep 10
curl -s -u elastic:testpass123 -H kbn-xsrf:true -H x-elastic-internal-origin:kibana -XPOST localhost:15601/internal/alerting/rule/26888801-090e-41ee-839b-73d2832330a8/_run_soon >/dev/null; sleep 15
curl -s -u elastic:testpass123 localhost:15601/api/alerting/rule/26888801-090e-41ee-839b-73d2832330a8 | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["execution_status"]["status"], d["last_run"]["alerts_count"], len(d["actions"]))'
EOF
chmod +x $HARNAIS/test_supervision.sh
```

- [ ] **Step 2: Vérifier que le test échoue**

Run: `$HARNAIS/test_supervision.sh`
Expected: erreur `KeyError: 'execution_status'` (règle inexistante).

- [ ] **Step 3: Écrire `4-rules-tchap.console`**

```
# Règle de supervision des notifications Tchap. Spécification :
# ../workflows/tchap/README.md.
#
# Un envoi en échec (jeton expiré, bot sorti d'un salon, salon inconnu) passe
# l'exécution du Workflow en failed, mais la règle d'origine reste « ok » : sans
# cette règle, l'alerte serait perdue sans trace. Pas d'action : Tchap ne peut
# pas signaler sa propre panne, et Mattermost est décommissionné le
# 1er novembre 2026. Elle est consultée par la routine de surveillance.
# Création : POST ci-dessous. Mise à jour : PUT sur la même URL, même corps
# SANS "rule_type_id" ni "consumer".

# Envois Tchap en échec (tchap-client et Workflows de salon)
POST kbn:/api/alerting/rule/26888801-090e-41ee-839b-73d2832330a8
{
  "name": "Tchap - Envoi en échec",
  "tags": [
    "warning",
    "prod",
    "o11y",
    "tchap"
  ],
  "schedule": {
    "interval": "5m"
  },
  "params": {
    "searchType": "esQuery",
    "esQuery": "{\"query\":{\"bool\":{\"filter\":[{\"term\":{\"status\":\"failed\"}},{\"prefix\":{\"workflowId\":\"tchap-\"}}]}}}",
    "index": [".workflows-executions"],
    "timeField": "finishedAt",
    "timeWindowSize": 10,
    "timeWindowUnit": "m",
    "threshold": [
      0
    ],
    "thresholdComparator": ">",
    "size": 20,
    "aggType": "count",
    "groupBy": "all",
    "termSize": 5,
    "excludeHitsFromPreviousRun": true,
    "sourceFields": []
  },
  "actions": [],
  "rule_type_id": ".es-query",
  "consumer": "alerts"
}
```

- [ ] **Step 4: Importer et vérifier que le test passe**

Run :
```bash
python3 -I $HARNAIS/replay.py supervision/rules/4-rules-tchap.console --tolerer 409
$HARNAIS/test_supervision.sh
```
Expected: `ok {'new': 1, …, 'active': 1} 0` (statut `active` ou `new` = 1, aucune action). Dans Kibana (`http://localhost:15601/app/observability/alerts`), l'alerte « Tchap - Envoi en échec » apparaît.

- [ ] **Step 5: Commit**

```bash
git add docs/observabilite/supervision/rules/4-rules-tchap.console
git commit -m "feat(tchap): règle de supervision des envois en échec"
```

---

## Task 7: Documentation et ADR-004

**Files:**
- Create: `docs/observabilite/supervision/workflows/tchap/README.md`
- Create: `docs/decisions/ADR-004-notifications-tchap-kibana-workflows.md`
- Modify: `docs/observabilite/supervision/alertes-externes.md` (statut, chaîne, tableau des règles, mise en service)
- Modify: `docs/observabilite/supervision/objets-kibana.md` (section Requêtes Dev Tools)
- Modify: `docs/observabilite/README.md` (section Décisions d'architecture)
- Modify: `docs/observabilite/routine-surveillance.md` (section Santé de la stack d'observabilité)
- Modify: `docs/superpowers/specs/2026-10-13-alertes-tchap-workflows-design.md` (statut)

- [ ] **Step 1: Écrire `workflows/tchap/README.md`**

```markdown
# Notifications Tchap — Workflows Kibana

Les règles Kibana notifient Tchap par des **Workflows** : une règle choisit son
salon en choisissant le Workflow de ce salon dans son action `.workflows`,
comme elle choisissait un connecteur Mattermost par canal. Décision :
[ADR-004](../../../../decisions/ADR-004-notifications-tchap-kibana-workflows.md).

```
Rule ──action .workflows──► tchap-<salon> ──workflow.execute──► tchap-client ──connecteur .http──► Tchap
                            (met en forme)                     (PUT …/send/m.room.message/{execution.id})
```

| Fichier | Contenu |
|---|---|
| [`connecteur-tchap.console`](connecteur-tchap.console) | connecteur `.http` : URL de Tchap et jeton du bot |
| [`tchap-client.console`](tchap-client.console) | le seul Workflow qui parle à Matrix |
| [`tchap-monitoring-production.console`](tchap-monitoring-production.console), [`tchap-monitoring-staging.console`](tchap-monitoring-staging.console), [`tchap-o11y-production.console`](tchap-o11y-production.console), [`tchap-o11y-staging.console`](tchap-o11y-staging.console) | un Workflow par salon |
| [`../../rules/4-rules-tchap.console`](../../rules/4-rules-tchap.console) | règle « Tchap - Envoi en échec » |

## Le message

Générique, construit à partir de ce que la règle transmet (son id, son nom, ses
tags, ses alertes) :

```
🚨 Scalingo - Prod - Crash, redémarrage ou arrêt d'une app (2)
• pass-emploi-api-prod : app_crashed (oom) sur web, par scalingo-platform
• pass-emploi-web-prod : app_restarted, par alice
Ouvrir dans Discover · Voir la règle
```

- **Sévérité** : tag `critical` (🚨) ou `warning` (⚠️) de la règle.
- **Lignes** : le champ `message` des documents trouvés, écrit par l'ingest
  pipeline ; à défaut, la raison de l'alerte (`kibana.alert.reason`).
- **Liens** : Discover (`kibana.alert.url`) et la page de la règle.

Le Workflow ne reçoit pas les documents trouvés par la règle (`context.hits`) :
ils sont fusionnés champ par champ dans le document d'alerte, sans lien entre
une app et son action, et `event.action` y est écrasé. D'où une ligne toute
faite par document, dans un seul champ.

## Contrat de `tchap-client`

| Entrée | Contenu |
|---|---|
| `salon` | ID du salon, `!…:agent.tchap.gouv.fr` (Tchap → paramètres du salon → Avancé) |
| `texte` | message en texte brut |
| `html` | message en HTML, **déjà échappé** (`\| escape` sur toute donnée) |

Un appel = un message. Le `txnId` de Matrix est l'`execution.id` de l'appel :
il doit changer à chaque message, sinon Matrix croit à une nouvelle tentative
et ne poste rien.

## Brancher une règle

1. Ajouter à la règle le tag `critical` ou `warning`.
2. Ajouter l'action `.workflows` vers le Workflow du salon :
   ```json
   { "id": "system-connector-.workflows",
     "params": { "subAction": "run", "subActionParams": {
       "workflowId": "tchap-o11y-production", "summaryMode": true,
       "alertStates": { "new": true, "ongoing": true, "recovered": false } } } }
   ```
3. Si les documents de la règle ont un champ `message` lisible, ce sont eux
   qui font les lignes ; sinon, la raison de l'alerte.

## Ajouter un salon

1. Créer le salon dans Tchap, y inviter le bot, le faire rejoindre :
   `curl -X POST "https://matrix.agent.tchap.gouv.fr/_matrix/client/v3/rooms/<id encodé>/join" -H "Authorization: Bearer <jeton>"`.
2. Copier un `tchap-<salon>.console` en remplaçant le nom du salon partout,
   l'importer en substituant `<id-salon-…>`.

## Pièges

- La boucle sur les alertes est une **étape** `type: foreach` ; une propriété
  `foreach:` posée sur `workflow.execute` est ignorée sans erreur.
- `kibana.alert.url` est déjà absolue (Kibana a un `server.publicBaseUrl`) : ne
  pas la préfixer.
- Les Workflows exigent la licence **Enterprise**.
- Un envoi en échec laisse la règle d'origine à « ok » : seule la règle
  « Tchap - Envoi en échec » le montre.
```

- [ ] **Step 2: Écrire l'ADR-004**

```markdown
# Notifications d'alertes vers Tchap par les Workflows Kibana

* Statut: accepté
* Décideurs: équipe pass-emploi
* Date: 2026-10-13

## Contexte et Définition du Problème

Mattermost est décommissionné le 1er novembre 2026. Les règles Kibana y
notifient des canaux par des connecteurs Webhook, un par canal. Elles doivent
notifier Tchap, la messagerie de l'État, qui est un serveur Matrix.

Envoyer un message Matrix, c'est `PUT /rooms/{salon}/send/m.room.message/{txnId}`,
avec un `txnId` unique par message : un `txnId` déjà vu est pris pour une
nouvelle tentative et rien n'est posté. Le connecteur Webhook de Kibana a une
URL fixe : il ne peut pas produire ce `txnId`.

## Facteurs de Décision

* Pas de brique intermédiaire à héberger et à maintenir chez nous.
* La règle choisit son salon, comme elle choisissait son canal Mattermost.
* Migrer les autres règles avant le 1er novembre sans écrire de code par règle.

## Solutions Étudiées

* Passerelle slack2tchap (beta.gouv), hébergée chez nous
* Service n8n mutualisé de l'incubateur beta.gouv
* Connecteur Webhook Kibana en `POST` sur l'ancienne route sans `txnId`
* Watcher Elasticsearch (`PUT` avec `{{ctx.id}}`)
* Workflows Kibana, avec un Workflow par règle
* Workflows Kibana, avec un Workflow par salon

## Résultat de la Décision

Solution retenue : « Workflows Kibana, avec un Workflow par salon », **parce que
nous sommes en licence Elastic Cloud Enterprise**, que les Workflows exigent.
Le connecteur `.http` des Workflows accepte des variables dans son chemin :
`txnId = {{ execution.id }}`, conforme à la norme Matrix. La règle déclenche le
Workflow de son salon ; un Workflow commun, `tchap-client`, est le seul à
appeler Tchap. Détail : [`supervision/workflows/tchap/`](../observabilite/supervision/workflows/tchap/README.md).

### Impacts Positifs

* Aucune brique à héberger ; tout est versionné en `.console`.
* Migrer une règle : un tag et une action.
* Échappement HTML des données (`| escape`), impossible avec Mustache.

### Impacts Négatifs

* Dépendance à la licence Enterprise. **Sans elle**, repli sur le connecteur
  Webhook en `POST` sans `txnId` (route tolérée par Synapse, hors norme
  Matrix ; pas d'échappement HTML).
* Message générique : le texte « À vérifier » propre à chaque règle reste dans
  la doc des alertes.
* Les champs des documents n'arrivent pas appariés au Workflow : chaque
  pipeline doit écrire une ligne `message` toute faite.
* Un envoi en échec ne fait pas échouer la règle : il faut une règle dédiée.

## Avantages et Inconvénients des Solutions

### Passerelle slack2tchap

* Bien, car elle accepte le format Slack actuel des messages.
* Mauvais, car c'est une application à héberger, mettre à jour et superviser.
* Mauvais, car elle ne protège pas mieux des doublons : un nouveau `txnId` à
  chaque requête reçue.

### Service n8n mutualisé beta.gouv

* Bien, car rien à héberger.
* Mauvais, car un service tiers, sans engagement, et un routage par PR sur un
  fichier commun.

### Connecteur Webhook en `POST` sans `txnId`

* Bien, car aucun changement d'architecture.
* Mauvais, car hors norme Matrix (route ancienne tolérée par Synapse), pas
  d'échappement HTML.

### Watcher Elasticsearch

* Bien, car `PUT` conforme, licence Gold.
* Mauvais, car un second système d'alerte : requêtes à réécrire, retards
  d'indexation et liens Discover à gérer soi-même.

### Workflow par règle

* Bien, car message sur mesure par règle.
* Mauvais, car un Workflow à écrire par règle, et le salon se change dans le
  Workflow, pas dans la règle.

## Liens

* Spécification : [`docs/superpowers/specs/2026-10-13-alertes-tchap-workflows-design.md`](../superpowers/specs/2026-10-13-alertes-tchap-workflows-design.md)
* [Alertes externes](../observabilite/supervision/alertes-externes.md)
```

- [ ] **Step 3: Mettre à jour `alertes-externes.md`**

- Dans le bloc de statut, remplacer « des **Kibana Rules** notifient Mattermost comme toutes les autres alertes » (intro) par « des **Kibana Rules** les notifient, dans Tchap et, jusqu'au 1er novembre 2026, dans Mattermost » ; ajouter au statut : « Notification Tchap : validée sur la même pile locale avec Synapse le 2026-10-13. »
- Dans le schéma « La chaîne », remplacer `──► Kibana Rules X1 à X4 ──► Mattermost` par `──► Kibana Rules X1 à X4 ──► Tchap (Workflows) + Mattermost`.
- Dans le tableau des fichiers, ajouter la ligne `| [`workflows/tchap/`](workflows/tchap/README.md) | notifications Tchap : connecteur, tchap-client, Workflows de salon |`.
- Dans « Récapitulatif des règles », renommer la colonne `Canal` en `Canal Tchap (Mattermost)` et mettre : X1, X2, X4 `monitoring-production (#monitoring-production)` ; X3 `monitoring-staging (#o11y-staging)` ; X5 `o11y-production (#o11y-production)`.
- Ajouter dans « Champs ECS produits » : « `message` : la ligne de notification de l'événement, en texte brut, lue par les Workflows Tchap (cf. [workflows/tchap](workflows/tchap/README.md#le-message)). »
- Dans « Mise en service », insérer après l'étape 4 (Règles) une étape « **Tchap** : suivre [workflows/tchap/README.md](workflows/tchap/README.md) (bot, 4 salons, connecteur, Workflows), **avant** de rejouer les règles : elles référencent les Workflows de salon. » et déplacer l'étape « Règles » après elle ; à l'étape « Test sans Scalingo », ajouter « … et dans le salon Tchap `monitoring-staging` » ; à l'étape « Bascule », ajouter « Le 1er novembre 2026 : retirer les actions Mattermost de X1 à X5. »

- [ ] **Step 4: Mettre à jour `objets-kibana.md`, `observabilite/README.md`, `routine-surveillance.md`**

- `objets-kibana.md`, tableau « Requêtes Dev Tools », ajouter :
  `| [`workflows/tchap/`](workflows/tchap/README.md) | connecteur Tchap et Workflows de notification (tchap-client, un par salon) |`
  `| [`rules/4-rules-tchap.console`](rules/4-rules-tchap.console) | règle « Tchap - Envoi en échec », sans action |`
- `observabilite/README.md`, section « Décisions d'architecture », ajouter :
  `- [ADR-004 — Notifications d'alertes vers Tchap par les Workflows Kibana](../decisions/ADR-004-notifications-tchap-kibana-workflows.md)`
- `routine-surveillance.md`, section « Santé de la stack d'observabilité », ajouter une ligne au tableau existant (même format que ses lignes) : règle « Tchap - Envoi en échec » dans *Alerts* — une alerte = des notifications perdues ; lire `error.message` dans l'exécution du Workflow (*Workflows → Executions*).

- [ ] **Step 5: Statut de la spec**

Dans la spec, remplacer `**Statut : validé le 2026-10-13, non implémenté.**` par `**Statut : implémenté le <date>.**` et ajouter en fin de fichier une section `## Écarts avec l'implémentation` : « La ligne `message` des événements Scalingo commence par le nom complet de l'app (`scalingo.app_name`, ex. `pass-emploi-api-prod`) et non par `service.name`, qui a perdu son suffixe d'environnement. »

- [ ] **Step 6: Vérifier les liens relatifs**

Run (depuis la racine du repo) :
```bash
python3 -I - <<'EOF'
import os, re
for f in ['docs/observabilite/supervision/workflows/tchap/README.md', 'docs/decisions/ADR-004-notifications-tchap-kibana-workflows.md', 'docs/observabilite/supervision/alertes-externes.md', 'docs/observabilite/supervision/objets-kibana.md', 'docs/observabilite/README.md', 'docs/observabilite/routine-surveillance.md']:
    for link in re.findall(r'\]\(([^)#:]+)', open(f).read()):
        if not os.path.exists(os.path.join(os.path.dirname(f), link)):
            print('cassé:', f, link)
EOF
```
Expected: aucune ligne `cassé:`.

- [ ] **Step 7: Commit**

```bash
git add docs/observabilite/supervision/workflows/tchap/README.md docs/decisions/ADR-004-notifications-tchap-kibana-workflows.md docs/observabilite/supervision/alertes-externes.md docs/observabilite/supervision/objets-kibana.md docs/observabilite/README.md docs/observabilite/routine-surveillance.md docs/superpowers/specs/2026-10-13-alertes-tchap-workflows-design.md
git commit -m "docs(tchap): README des Workflows, ADR-004, mise en service des alertes externes"
```

- [ ] **Step 8: Arrêter la pile**

Run: `$HARNAIS/pile.sh down`
