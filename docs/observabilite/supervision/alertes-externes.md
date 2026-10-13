# Alertes externes — centralisées dans Kibana

Les alertes **émises hors d'Elastic** : les notifiers des apps Scalingo
(crash, redémarrage, arrêt, seuils RAM/CPU) et les CVE remontées par
Dependabot via [`security-alerts.yml`](../../../.github/workflows/security-alerts.yml).
Elles postaient directement dans Mattermost, sans trace dans Kibana. Elles sont
désormais écrites dans un data stream par source, d'où des **Kibana Rules** notifient
Mattermost comme toutes les autres alertes : un seul endroit pour les retrouver,
les corréler avec les logs et les compter.

> **Statut** : validé de bout en bout le 2026-10-12 sur une pile Elasticsearch +
> Kibana 9.4.7 locale (pipelines, droits, failure store, règles, messages
> Mattermost rendus). **Pas encore déployé** sur Elastic Cloud : suivre la
> [mise en service](#mise-en-service).

## La chaîne

```
Notifier webhook Scalingo ──► logs-alertes-scalingo-<env>-default ──┐
  (Basic Auth dans l'URL)       pipeline ingest-alertes-scalingo-<env>-default
                                                                     ├──► Kibana Rules X1 à X4 ──► Mattermost
security-alerts.yml (curl) ──► logs-alertes-github-default ─────────┘
  (API Key)                     pipeline ingest-alertes-github-default

document rejeté par son pipeline ──► <data stream>::failures ──► règle X5
```

Un data stream par source, et par environnement pour Scalingo, comme
`logs-<env>-default` : chaque flux a la rétention des logs de son environnement,
et chaque émetteur n'écrit que dans les siens.

Aucun agent à héberger : les émetteurs appellent l'API Elasticsearch, la
transformation en champs ECS se fait dans un **ingest pipeline**.

| Fichier | Contenu |
|---|---|
| [`stockage/logs/`](../stockage/logs/README.md) `2-component-templates.console`, `3-index-templates.console` | mapping et templates des 4 data streams (logsdb, `default_pipeline`, failure store) ; rétention : les briques `logs-<env>-retention-custom` existantes |
| [`pipelines/ingest-alertes-scalingo.console`](pipelines/ingest-alertes-scalingo.console) | transformation commune des événements Scalingo, et ses `_simulate` sur les captures réelles |
| [`pipelines/ingest-alertes-scalingo-<env>-default.console`](pipelines/) | pipeline par défaut de chaque data stream Scalingo : vérifie l'enveloppe et l'environnement, puis appelle le pipeline commun |
| [`pipelines/ingest-alertes-github-default.console`](pipelines/ingest-alertes-github-default.console) | transformation des alertes Dependabot |
| [`security/acces-alertes-externes.console`](security/acces-alertes-externes.console) | rôle et utilisateur Scalingo, API Key GitHub |
| [`rules/3-rules-alertes-externes.console`](rules/3-rules-alertes-externes.console) | règles X1 à X5 |

## Récapitulatif des règles

| #  | Signal                                       | Data stream                                   | Condition                                                               | Fréquence  | Canal                    | Sévérité    |
|----|----------------------------------------------|-----------------------------------------------|-------------------------------------------------------------------------|------------|--------------------------|-------------|
| X1 | Crash, redémarrage ou arrêt d'une app — prod | `logs-alertes-scalingo-prod-default`          | `app_crashed`, `app_crashed_repeatedly`, `app_restarted`, `app_stopped` | 1 min      | `#monitoring-production` | 🚨 Critical |
| X2 | Seuil de ressource Scalingo dépassé — prod   | `logs-alertes-scalingo-prod-default`          | `resource_threshold_exceeded`                                           | 1 min      | `#monitoring-production` | ⚠ Warning  |
| X3 | X1 + X2 — staging/perf                       | `logs-alertes-scalingo-{staging,perf}-default` | idem X1 + X2                                                            | 5 min      | `#o11y-staging`          | ⚠ Warning  |
| X4 | CVE high/critical ouverte                    | `logs-alertes-github-default`                 | `vulnerability.severity` high ou critical                               | 5 min      | `#monitoring-production` | 🚨 Critical |
| X5 | Alerte externe rejetée                       | les 4, sélecteur `::failures`                 | tout document                                                           | 5 min      | `#o11y-production`       | ⚠ Warning  |

**Un événement = une notification.** Chaque exécution ne compte que les
documents arrivés depuis la précédente (`excludeHitsFromPreviousRun`) et
notifie s'il y en a (`onActiveAlert`), en les listant tous, une ligne par app ou
par repo. Pas de throttle : on garde le comportement du notifier direct.
Les règles ne sont **pas** groupées par app : avec un `groupBy`, Kibana ignore
`excludeHitsFromPreviousRun` et renotifie le même événement à chaque exécution
tant qu'il reste dans la fenêtre (constaté en test).

**CVE (X4)** : `security-alerts.yml` renvoie à chaque passage toutes les CVE
encore ouvertes, X4 les notifie donc à chaque passage, comme aujourd'hui.

## Champs ECS produits

Commun aux deux sources : `event.provider` (`scalingo` | `github`),
`event.kind`, `event.action`, `event.id`, `service.name`. Le payload brut est
gardé sous `scalingo.*` ou `github.*`, lisible dans le document mais **non
indexé** (`dynamic: false`) : on ne cherche pas dedans, on s'en sert pour
enquêter ou faire évoluer le mapping.

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

✅ = capturé. Les autres noms de `type` viennent du catalogue Scalingo, **à
confirmer à la première occurrence réelle** : `labels.scalingo_type` garde la
valeur brute. Si un crash arrive sous un autre nom, il tombe en `scalingo_<type>`,
n'est **pas** alerté par X1, et il faut l'ajouter à la table `actions` du
pipeline `ingest-alertes-scalingo`.

`service.name` et `service.environment` suivent la même règle que Logstash
(suffixe `-prod`, `-staging`, `-perf` de l'app). Une app dont le suffixe ne
correspond pas au data stream visé est rejetée : son notifier pointe vers le
mauvais environnement (règle X5). `user.name` est l'auteur
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

1. **Stockage** : dans [`stockage/logs/`](../stockage/logs/README.md), rejouer
   les blocs `logs-alertes*` de `2-component-templates.console`, puis de
   `3-index-templates.console`. Ils s'appuient sur des briques déjà présentes
   sur le cluster (`pass-emploi-logs@mappings`, `logs-<env>-retention-custom`).
2. **Pipelines** : rejouer [`pipelines/ingest-alertes-scalingo.console`](pipelines/ingest-alertes-scalingo.console)
   en premier, puis les trois `ingest-alertes-scalingo-<env>-default.console` et
   `ingest-alertes-github-default.console`. Les `_simulate` en fin de fichier
   doivent donner les résultats annoncés en commentaire.
3. **Accès** : rejouer [`security/acces-alertes-externes.console`](security/acces-alertes-externes.console)
   en remplaçant `<mot-de-passe-généré>` par un mot de passe alphanumérique,
   rangé dans le coffre de l'équipe. Copier le champ `encoded` de l'API Key.
4. **Règles** : rejouer [`rules/3-rules-alertes-externes.console`](rules/3-rules-alertes-externes.console).
5. **Test sans Scalingo** :
   ```bash
   curl -X POST "https://alertes-scalingo:<mdp>@<endpoint-es>/logs-alertes-scalingo-staging-default/_doc" \
     -H 'Content-Type: application/json' \
     -d '{"id":"test","created_at":"'"$(date -u +%FT%TZ)"'","type":"restart","app_id":"test","app_name":"pass-emploi-api-staging","user":{"username":"test"},"type_data":{"scope":["web"],"reason":"user_restart"}}'
   ```
   La réponse doit contenir `"result":"created"` **sans** `"failure_store":"used"`.
   Sous 5 min, X3 poste dans `#o11y-staging`. L'endpoint Elasticsearch est
   indiqué sur la page du déploiement Elastic Cloud.
6. **Scalingo** : sur une app non critique d'abord (`pass-emploi-logstash-perf`),
   **Settings → Notifications → Add notification**, type **Webhook**, URL
   `https://alertes-scalingo:<mdp>@<endpoint-es>/logs-alertes-scalingo-<env>-default/_doc`
   (`<env>` = suffixe de l'app),
   événements `app_crashed_repeated`, `app_restarted`, `app_stopped` et les
   alertes de métriques. Redémarrer l'app et vérifier X3. Puis étendre aux apps de
   prod.
7. **GitHub Actions** : ajouter à `security-alerts.yml` un envoi par CVE vers
   `logs-alertes-github-default` (header `Authorization: ApiKey <encoded>`,
   secret `ELASTIC_ALERTES_GITHUB_API_KEY`), en gardant l'envoi Mattermost
   actuel pendant la période de test. *Pas encore fait.*
8. **Bascule** : une fois X1 à X4 constatés en réel, supprimer les notifiers
   Scalingo vers Mattermost et l'envoi direct de `security-alerts.yml`, puis
   mettre à jour l'[alerte 6](alertes-stack-observabilite.md#alerte-6--restart-du-conteneur-logstash-scalingo-webhook).

## Points ouverts

- **Noms des `type` de crash** : non capturés (cf. [Scalingo](#scalingo)).
- **Canal des apps de la stack** : X1 notifie `#monitoring-production` pour
  toutes les apps de prod, Logstash compris, alors que l'alerte 6 envoyait les
  apps Logstash dans `#o11y-production`. Les séparer = dupliquer X1 avec un
  filtre sur `service.name`.
- **Lien Discover** des messages : relatif si Kibana n'a pas de
  `server.publicBaseUrl` (le cas en test local). À vérifier sur Elastic Cloud au
  premier message réel.
- **Identifiants dans l'URL du notifier** : visibles de tous les collaborateurs
  de l'app Scalingo. Acceptable parce que l'utilisateur ne peut qu'ajouter des
  documents aux 3 data streams Scalingo (`create_doc` + `auto_configure`). Pour
  révoquer : changer son mot de passe et mettre à jour les notifiers.
