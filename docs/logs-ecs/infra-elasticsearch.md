# Infra Elasticsearch — logs

Staging et prod partagent **le même cluster ES** ; ils ne diffèrent que par le
nom des data streams. Le Logstash (`pass-emploi-tools/logs/logstash.conf`) reçoit
les drains de toutes les apps Scalingo (api, connect, web) et route par
`appname` vers `logs-<env>-default` (app) et `logs-router-<env>-default` (router).

## Data streams

| Data stream | Index template | ILM |
|---|---|---|
| `logs-prod-default` | `logs-prod@template-custom` | `logs-prod-retention` |
| `logs-staging-default` | `logs-staging@template-custom` | `logs-staging-retention` |
| `logs-router-{prod,staging}-default` | `logs-router` | `logs-prod-retention` |

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

`logstash.conf` fait le post-traitement commun aux trois repos : parsing des
logs router (logfmt → ECS `request_routed`), renames/flatten ECS, détection
d'env, **drops** de bruit (healthchecks Scalingo, bootstrap NestJS
`RouterExplorer` & co, lignes non-JSON du conteneur `postdeploy`).

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