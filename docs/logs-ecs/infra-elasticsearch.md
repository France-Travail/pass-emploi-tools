# Infra Elasticsearch — logs

Staging et prod partagent **le même cluster ES** ; ils ne diffèrent que par le
nom des data streams. Le Logstash mutualisé (`pass-emploi-tools/logs/`, archi
**2 pipelines** depuis 2026-07 : `pipeline-ingest.conf` → `pipeline-process.conf`,
cf. [blackout-logs/conventions](../blackout-logs/conventions.md)) reçoit les drains
de toutes les apps Scalingo (api, connect, web) et route par `appname` vers
`logs-<env>-default` (app) et `logs-router-<env>-default` (router).

## Data streams

| Data stream | Index template | Contenu |
|---|---|---|
| `logs-{prod,staging,perf}-default` | `logs-<env>@template-custom` | logs applicatifs |
| `logs-router-*-default` | `logs-router` | logs du router Scalingo (`request_routed`) |
| `logs-logstash-errors-*-default` | `logs-logstash-errors@template-custom` | events en erreur de **traitement** Logstash (`_jsonparsefailure`, `_mutate_error`, `_rubyexception`…) |
| `logs-logstash-dlq-*-default` | `logs-logstash-dlq@template-custom` | events **rejetés par ES** (conflit de mapping), relus depuis la Dead Letter Queue |

Les deux derniers sont les index de diagnostic de la chaîne elle-même : leur
exploitation (alertes, KQL, actions correctives) est dans le
[runbook d'astreinte](./runbook-astreinte-logstash.md).

## Templates versionnés — `pass-emploi-tools/logs/elastic/`

Toute la config ES est versionnée dans `pass-emploi-tools/logs/elastic/` :
trois fichiers `.console` (`1-ilm-policies`, `2-component-templates`,
`3-index-templates`) importés dans **Kibana → Dev Tools → Import requests**,
dans l'ordre. Le `README.md` du dossier sert de runbook (application, rollover,
vérification). Plus de script — application manuelle assumée (config qui change
rarement).

**Brique de factorisation** : `logs@custom` (component template) définit les
champs ECS custom (`event.action`, `event.outcome`, `log.logger`, `error.*`)
**une seule fois**, composé par les templates applicatifs **et** le template
router.

## Logstash — post-traitement mutualisé

`pipeline-process.conf` fait le post-traitement commun aux trois repos : parsing
des logs router (logfmt → ECS `request_routed`), renames/flatten ECS, détection
d'env, **drops** de bruit (healthchecks Scalingo, bootstrap NestJS
`RouterExplorer` & co, lignes non-JSON du conteneur `postdeploy`).
`pipeline-ingest.conf` ne fait, lui, **aucun filtre** — c'est un invariant, il
n'existe que pour acquitter le drain au plus vite.

Ce qui doit rester **in-app** (pino) et ne peut pas descendre dans Logstash :
émission ECS structurée, **redaction des secrets** (un secret ne doit jamais
sortir du process), propagation `trace.id` / `user.*`. Logstash = post-traitement
générique mutualisé ; l'app = émission + redaction.

## Settings critiques

- `index.mode: logsdb`
- `index.mapping.total_fields.ignore_dynamic_beyond_limit: true` → nouveaux
  champs dynamiques silencieusement `_ignored` au-delà de `total_fields.limit`.
- `logs-router@mappings` en `dynamic: false`.

## Historique incidents

**App prod — `_ignored` (2026-05-19)** : après la refonte ECS, champs `event.*`
en `_ignored` malgré présence dans `_source`. Cause : datastream en génération
45, mapping pollué par des années de logs freeform → saturation
`total_fields.limit`. Fix : `POST logs-prod-default/_rollover`.

**Router — `event.action` non cherchables (mai 2026)** : cause **différente**
(pas de saturation) — le template `logs-router` ne composait pas `logs@custom`,
et son `logs-router@mappings` hand-rollé en `dynamic: false` ne déclarait pas
`event.action` / `outcome`. Fix : `logs-router` compose désormais `logs@custom`,
puis rollover.

**Logstash — 5xx & pics de latence (juin 2026)** : 5xx constants aux heures de
charge + crashs. Cause : heap JVM au défaut (~512 Mo sur conteneur L) → OOM +
SerialGC à pauses multi-secondes figeant l'input Netty. Fix : conteneur **XL**
(heap défaut ~1 Go + G1 auto) + `-Xmx1g`. Détail complet (fonctionnement
JVM/Netty/GC, indicateurs, diagnostic) :
[postmortem-logstash-5xx-2026-06.md](./postmortem-logstash-5xx-2026-06.md).

À retenir : après tout changement de schéma d'ingestion, surveiller `_ignored`
et prévoir un `_rollover` (non destructif).

## Commandes utiles (Dev Tools)

```
GET _data_stream/logs-*-default
GET _component_template/<nom>     # pas de liste séparée par virgules sur les templates
GET _index_template/<nom>
GET _ilm/policy/logs-prod-retention
POST <datastream>/_rollover       # non destructif
```