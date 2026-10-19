# Collecte des événements externes (Scalingo, GitHub)

Les événements **émis hors d'Elastic** : les notifiers des apps Scalingo
(crash, redémarrage, arrêt, déploiement, seuils RAM/CPU…) et les CVE remontées
par Dependabot via [`security-alerts.yml`](../../../../.github/workflows/security-alerts.yml).
Ils sont écrits dans un data stream par source, transformés en champs ECS par un
ingest pipeline, et lus par des Kibana Rules rangées par périmètre :

| Données | Alertes |
|---|---|
| Événements Scalingo des apps applicatives | A4a, A4b dans les [alertes applicatives](../../supervision/alertes-applicatives.md) |
| Événements Scalingo des apps de la stack (Logstash, Elastic Agent, Heartbeat) | 6a, 6b dans les [alertes de la stack](../../supervision/alertes-stack-observabilite.md) |
| CVE Dependabot | V1 dans les [alertes de sécurité](../../supervision/alertes-securite.md) |
| Événements rejetés (failure store) | 14 dans les [alertes de la stack](../../supervision/alertes-stack-observabilite.md) |

> **Statut** : validé de bout en bout sur une pile Elasticsearch + Kibana 9.4.7
> locale (pipelines, droits, failure store, règles, messages rendus). Stockage,
> pipelines et accès déployés sur Elastic Cloud le 2026-10-14 ; notifiers
> Scalingo et envoi de `security-alerts.yml` : en cours (cf.
> [mise en service](#mise-en-service)).

## La chaîne

```
Notifier webhook Scalingo ──► logs-alertes-scalingo-<env>-default ──┐
  (Basic Auth dans l'URL)       pipeline ingest-alertes-scalingo-<env>-default
                                                                     ├──► Kibana Rules (A4a/A4b, 6a/6b, V1)
security-alerts.yml (curl) ──► logs-alertes-github-default ─────────┘
  (API Key)                     pipeline ingest-alertes-github-default

document rejeté par son pipeline ──► <data stream>::failures ──► règle 14
```

Un data stream par source, et par environnement pour Scalingo, comme
`logs-<env>-default` : chaque flux a la rétention des logs de son environnement,
et chaque émetteur n'écrit que dans les siens.

Aucun agent à héberger : les émetteurs appellent l'API Elasticsearch, la
transformation en champs ECS se fait dans un **ingest pipeline**.

| Fichier | Contenu |
|---|---|
| [`stockage/logs/`](../../stockage/logs/README.md) `2-component-templates.console`, `3-index-templates.console` | mapping et templates des 4 data streams (logsdb, `default_pipeline`, failure store), création à l'avance des data streams ; rétention : les briques `logs-<env>-retention-custom` existantes |
| [`pipelines/ingest-alertes-scalingo.console`](pipelines/ingest-alertes-scalingo.console) | transformation commune des événements Scalingo, et ses `_simulate` sur les captures réelles |
| [`pipelines/ingest-alertes-scalingo-format-slack.console`](pipelines/ingest-alertes-scalingo-format-slack.console) | remet au format habituel un événement envoyé au format Slack (cf. [Scalingo](#scalingo)) |
| [`pipelines/ingest-alertes-scalingo-<env>-default.console`](pipelines/) | pipeline par défaut de chaque data stream Scalingo : vérifie l'enveloppe et l'environnement, puis appelle le pipeline commun |
| [`pipelines/ingest-alertes-github-default.console`](pipelines/ingest-alertes-github-default.console) | transformation des alertes Dependabot |
| [`security/acces-alertes-externes.console`](security/acces-alertes-externes.console) | rôle et utilisateur Scalingo, API Key GitHub |
| [`supervision/discovers/evenements-externes/`](../../supervision/discovers/evenements-externes/) | sessions Discover des événements, des CVE et des rejets |

**Un événement = une ligne de notification.** Les règles ne comptent que les
documents arrivés depuis leur exécution précédente (`excludeHitsFromPreviousRun`)
et listent chacun sur une ligne. Elles ne sont **pas** groupées par app : avec
un `groupBy`, Kibana ignore `excludeHitsFromPreviousRun` et renotifie le même
événement à chaque exécution tant qu'il reste dans la fenêtre (constaté en
test). `security-alerts.yml` renvoie à chaque passage toutes les CVE encore
ouvertes : V1 les notifie donc à chaque passage.

## Champs ECS produits

Commun aux deux sources : `event.provider` (`scalingo` | `github`),
`event.kind`, `event.action`, `event.id`, `service.name`, et `message`, la ligne
de notification de l'événement en texte brut, que les règles et les Workflows
Tchap (cf. [workflows/tchap](../../supervision/workflows/tchap/README.md#le-message))
listent telle quelle. Le payload brut est gardé sous `scalingo.*` ou `github.*`,
lisible dans le document mais **non indexé** (`dynamic: false`) : on ne cherche
pas dedans, on s'en sert pour enquêter ou faire évoluer le mapping.

### Scalingo

Enveloppe commune, vérifiée sur 3 captures réelles le 2026-09-23 :
`{id, created_at, type, app_id, app_name, user, type_data}`. `type_data` change
de forme selon `type`.

| `type` Scalingo                 | `event.action`                                                                     | `event.outcome`       | Autres champs                                                                                       |
|---------------------------------|------------------------------------------------------------------------------------|-----------------------|-----------------------------------------------------------------------------------------------------|
| `alert` ✅                      | `resource_threshold_exceeded` (`activated: true`) / `resource_threshold_recovered` | `failure` / `success` | `event.kind: alert`, `labels.metric`, `labels.value_text`, `labels.limit_text`, `service.node.name` |
| `scale` ✅                      | `app_scaled`                                                                       | —                     | `labels.formation`, `labels.formation_before`, `labels.scaled_to_zero`                              |
| `restart` ✅                    | `app_restarted`                                                                    | —                     | `event.reason` (`user_restart`…), `labels.scope`                                                    |
| `crash`                         | `app_crashed`                                                                      | `failure`             | `event.reason`                                                                                      |
| `repeated_crash`                | `app_crashed_repeatedly`                                                           | `failure`             | `event.reason`                                                                                      |
| `stop` / `start` / `deployment` | `app_stopped` / `app_started` / `app_deployed`                                     | —                     |                                                                                                     |
| autre                           | `scalingo_<type>`                                                                  | —                     | indexé quand même, visible dans Discover                                                            |

**Deux formats.** Le même notifier webhook envoie certains événements au format
Slack, celui qu'il poste dans Mattermost : constaté le 2026-10-19 pour les
modifications de variables (`{username: "Scalingo", attachments: [{title:
"[<app>] Variables bulk edited", fields, footer: "By <auteur>", ts}]}`), alors
que les redémarrages, scalings et alertes arrivent au format ci-dessus.
`ingest-alertes-scalingo-format-slack` les remet dans l'enveloppe habituelle :
`type` = le libellé en snake_case (`scalingo_variables_bulk_edited`, classé
`infra`), `labels.details` = les champs (noms des variables, jamais leurs
valeurs). Exemple : `ℹ️ pass-emploi-logstash-perf : scalingo_variables_bulk_edited (New vars : TEST_NOTIFIER_ELASTIC), par alexandre.tingaud-octo`.

✅ = capturé. Les autres noms de `type` viennent du catalogue Scalingo, **à
confirmer à la première occurrence réelle** : `labels.scalingo_type` garde la
valeur brute. Si un crash arrive sous un autre nom, il tombe en `scalingo_<type>`
et est classé `infra` : l'ajouter à la table `actions` du pipeline
`ingest-alertes-scalingo`, et à `critiques` si c'est un incident.

**Catégorie et émoji** : le pipeline classe chaque événement dans
`labels.categorie` et préfixe `message` d'un émoji, depuis une seule table :

| `labels.categorie` | Événements | Émoji en prod | Émoji en staging / perf |
|---|---|---|---|
| `incident` | `app_crashed`, `app_crashed_repeatedly`, `app_restarted` (quelle que soit la raison), `app_stopped` | 🚨 | ⚠️ |
| `incident` | `resource_threshold_exceeded` | ⚠️ | ⚠️ |
| `infra` | tout le reste, par défaut : `app_deployed`, `app_scaled`, variables, `resource_threshold_recovered`, `scalingo_<type>` | ℹ️ | ℹ️ |

Les niveaux reprennent ceux des anciennes règles X1 (🚨 en prod), X2 et X3 (⚠️) ;
tout événement qu'elles ne notifiaient pas est en ℹ️.

Exemple : `🚨 pass-emploi-api-prod : app_crashed (oom) sur web, par scalingo-platform`.
Les règles filtrent `labels.categorie` si l'on veut un jour sortir l'infra des
salons de monitoring (cf. [alertes applicatives](../../supervision/alertes-applicatives.md)).

`service.name` et `service.environment` suivent la même règle que Logstash
(suffixe `-prod`, `-staging`, `-perf` de l'app). Une app dont le suffixe ne
correspond pas au data stream visé est rejetée : son notifier pointe vers le
mauvais environnement (règle 14). `user.name` est l'auteur
(`scalingo-platform` pour un événement automatique) ; **l'email n'est pas
conservé**.

### Dependabot

Un document par alerte, au format de l'API REST GitHub
(`GET /repos/{owner}/{repo}/dependabot/alerts`), plus `repository` (nom court
du repo). `@timestamp` est l'heure d'envoi par le workflow.

| Champ                                                                 | Source                                                    |
|-----------------------------------------------------------------------|-----------------------------------------------------------|
| `service.name`                                                        | `repository` (à défaut, extrait de `html_url`)            |
| `event.action`                                                        | `dependency_vulnerability_detected` (`event.kind: alert`) |
| `event.id`                                                            | `<repo>#<numéro de l'alerte>`                             |
| `vulnerability.id`                                                    | `security_advisory.cve_id`, à défaut `ghsa_id`            |
| `vulnerability.severity`, `.description`, `.reference`, `.score.base` | `severity`, `summary`, `html_url`, score CVSS v3          |
| `package.name`, `labels.ecosystem`, `labels.ghsa_id`                  | `dependency.package.*`, `ghsa_id`                         |

## Mise en service

À faire dans l'ordre : chaque étape dépend de la précédente.

1. **Stockage** : dans [`stockage/logs/`](../../stockage/logs/README.md), rejouer
   les blocs `logs-alertes*` de `2-component-templates.console`, puis de
   `3-index-templates.console`, **y compris la création des 4 data streams et
   de leur failure store** qui suit les templates : sans elle, les règles
   tombent en erreur tant qu'aucun document n'est arrivé.
2. **Pipelines** : rejouer [`pipelines/ingest-alertes-scalingo.console`](pipelines/ingest-alertes-scalingo.console)
   et [`pipelines/ingest-alertes-scalingo-format-slack.console`](pipelines/ingest-alertes-scalingo-format-slack.console)
   en premier, puis les trois `ingest-alertes-scalingo-<env>-default.console` et
   `ingest-alertes-github-default.console`. Les `_simulate` en fin de fichier
   doivent donner les résultats annoncés en commentaire.
3. **Accès** : rejouer [`security/acces-alertes-externes.console`](security/acces-alertes-externes.console)
   en remplaçant `<mot-de-passe-généré>` par un mot de passe alphanumérique,
   rangé dans le coffre de l'équipe. Copier le champ `encoded` de l'API Key.
4. **Sessions Discover** : importer les `.ndjson` de
   [`supervision/discovers/evenements-externes/`](../../supervision/discovers/evenements-externes/)
   (cf. [importer](../../supervision/objets-kibana.md#importer)), **avant** les
   règles : leurs liens pointent vers ces sessions par leur id.
5. **Règles** : A4a, A4b ([`1-rules-applicatives.console`](../../supervision/rules/1-rules-applicatives.console)),
   6a, 6b, 14 ([`2-rules-stack-observabilite.console`](../../supervision/rules/2-rules-stack-observabilite.console)),
   V1 ([`3-rules-securite.console`](../../supervision/rules/3-rules-securite.console)).
   Elles reprennent les IDs des anciennes X1 à X5 : `PUT` les met à jour, sauf
   **6b**, nouvelle, à créer avec `POST` (cf. l'en-tête de son bloc).
6. **Test sans Scalingo** :
   ```bash
   printf 'Mot de passe : '; read -rs MDP; echo
   curl -sS -w '\nHTTP %{http_code}\n' -X POST "https://alertes-scalingo:${MDP}@<endpoint-es>/logs-alertes-scalingo-staging-default/_doc" -H 'Content-Type: application/json' -d '{"id":"test","created_at":"'"$(date -u +%FT%TZ)"'","type":"restart","app_id":"test","app_name":"pass-emploi-api-staging","user":{"username":"test"},"type_data":{"scope":["web"],"reason":"user_restart"}}'
   ```
   La réponse doit contenir `"result":"created"` **sans** `"failure_store":"used"`.
   Sous 5 min, A4b le notifie. L'endpoint Elasticsearch est indiqué sur la page
   du déploiement Elastic Cloud (`….es.…`, pas l'adresse de Kibana).
7. **Notifiers Scalingo** : pour chaque app qui a un notifier `Mattermost*`, un
   notifier **Webhook** vers
   `https://alertes-scalingo:<mdp>@<endpoint-es>/logs-alertes-scalingo-<env>-default/_doc`
   (`<env>` = suffixe de l'app), avec **la même sélection d'événements** que le
   notifier `Mattermost*`, et le même nom au préfixe près (`Mattermost
   monitoring production` → `Elastic monitoring production`). Une app qui a deux
   notifiers `Mattermost*` n'a qu'un notifier Elastic, avec l'union de leurs
   événements : deux notifiers écriraient deux fois les événements communs.
   Rattacher aussi les alertes de métriques Scalingo de l'app à ce notifier.
   Commencer par une app non critique (`pass-emploi-logstash-perf`).
8. **GitHub Actions** : [`security-alerts.yml`](../../../../.github/workflows/security-alerts.yml)
   envoie les CVE vers `logs-alertes-github-default` (un `_bulk`, une CVE par
   document, plus `repository`) quand le repo appelant lui passe deux secrets,
   optionnels : `ELASTIC_URL` (endpoint Elasticsearch) et
   `ELASTIC_ALERTES_GITHUB_API_KEY` (champ `encoded` de l'API Key de l'étape 3).
   Sans eux, seul l'envoi Mattermost part, comme avant. Repos appelants :
   `pass-emploi-api`, `pass-emploi-web`, `pass-emploi-connect` ; dans chacun,
   créer les deux secrets puis, dans son `security-alerts.yml`, épingler le
   nouveau commit et transmettre les deux secrets. Un rejet par Elasticsearch
   fait échouer l'étape, après l'envoi Mattermost.

Pendant la migration vers Tchap, les notifiers `Mattermost*` sont
**désactivés, jamais supprimés**, une fois la parité constatée :
[`verifier-parite.py`](verifier-parite.py) compare, app par app, l'historique
Scalingo (`scalingo timeline`, limité aux événements sélectionnés dans le
notifier Elastic) aux documents reçus depuis une date, et liste le failure
store. Lecture seule ; code de sortie non nul au moindre écart.

```bash
set -a; . ~/.config/pass-emploi/elastic-claude.env; set +a   # ES_URL, ES_API_KEY
python3 -I verifier-parite.py --depuis 2026-10-19T17:00:00Z
```

## Points ouverts

- **Noms des `type` de crash et de déploiement** : non capturés (cf. [Scalingo](#scalingo)).
- **Événements au format Slack** : seules les variables sont constatées. Un
  autre type dans ce format passe par le même pipeline et sort en ℹ️
  `scalingo_<libellé>` ; un format encore différent part au failure store
  (règle 14).
- **Identifiants dans l'URL du notifier** : visibles de tous les collaborateurs
  de l'app Scalingo. Acceptable parce que l'utilisateur ne peut qu'ajouter des
  documents aux 3 data streams Scalingo (`create_doc` + `auto_configure`). Pour
  révoquer : changer son mot de passe et mettre à jour les notifiers.
