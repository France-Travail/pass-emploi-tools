# Collecte par webhook (Scalingo, GitHub)

Les événements émis hors des apps qui arrivent **par webhook** : un appel HTTP
direct de l'émetteur à l'API Elasticsearch, sans agent ni Logstash. Les sources :
les notifiers des apps Scalingo (crash, redémarrage, arrêt, déploiement, seuils
RAM/CPU…) et les CVE remontées par Dependabot via
[`security-alerts.yml`](../../../../../.github/workflows/security-alerts.yml).
Ils sont écrits dans un data stream par source, transformés en champs ECS par un
ingest pipeline ([`kibana/pipelines/webhooks/`](../../../../../kibana/pipelines/webhooks/README.md)),
et lus par des Kibana Rules rangées par périmètre :

| Données                                                                       | Alertes                                                                                 |
|-------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| Événements Scalingo des apps applicatives                                     | A4a à A4d dans les [alertes applicatives](../../../alertes.md)    |
| Événements Scalingo des apps de la stack (Logstash, Elastic Agent, Heartbeat) | M6a, M6b dans les [alertes de la stack](../../alertes-stack-observabilite.md) |
| CVE Dependabot                                                                | S1 dans les [alertes de sécurité](../../../alertes-securite.md)                |
| Événements rejetés (failure store)                                            | 14 dans les [alertes de la stack](../../alertes-stack-observabilite.md)     |

## La chaîne

```mermaid
flowchart LR
  subgraph emetteurs["Émetteurs"]
    direction TB
    SC["Notifiers webhook Scalingo<br/>(Basic Auth dans l'URL)"]
    GH["security-alerts.yml (curl)<br/>(clé API)"]
  end

  subgraph elasticsearch["Elasticsearch"]
    direction TB
    PS["pipeline ingest-alertes-scalingo-&lt;env&gt;-default"]
    PG["pipeline ingest-alertes-github-default"]
    DS["logs-alertes-scalingo-&lt;env&gt;-default"]
    DG["logs-alertes-github-default"]
    FS["&lt;data stream&gt;::failures"]
  end

  subgraph regles["Règles Kibana"]
    direction TB
    R["A4a à A4d, M6a / M6b, S1"]
    R14["14 (rejets)"]
  end

  SC --> PS --> DS --> R
  GH --> PG --> DG --> R
  PS -- "document rejeté" --> FS
  PG -- "document rejeté" --> FS
  FS --> R14
```

Un data stream par source, et par environnement pour Scalingo, comme
`logs-<env>-default` : chaque flux a la rétention des logs de son environnement,
et chaque émetteur n'écrit que dans les siens.

Aucun agent à héberger : les émetteurs appellent l'API Elasticsearch, la
transformation en champs ECS se fait dans un **ingest pipeline**.

| Fichier                                                                                                        | Contenu                                                                                                                                                                                                    |
|----------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`stockage/logs/`](../../stockage/logs/README.md) `2-component-templates.console`, `3-index-templates.console` | mapping et templates des 4 data streams (logsdb, `default_pipeline`, failure store), création à l'avance des data streams ; rétention : les briques `logs-<env>-retention-custom` existantes               |
| [`kibana/pipelines/webhooks/`](../../../../../kibana/pipelines/webhooks/README.md)                            | les ingest pipelines (transformation en champs ECS) et l'accès en écriture des émetteurs ; ce que font les pipelines : [format/webhooks/conventions.md](../../format/webhooks/conventions.md) |
| [`kibana/discovers/webhooks/`](../../../../../kibana/discovers/webhooks/)                                     | sessions Discover des événements, des CVE et des rejets                                                                                                                                                    |

**Un événement = une ligne de notification.** Les règles ne comptent que les
documents arrivés depuis leur exécution précédente (`excludeHitsFromPreviousRun`)
et listent chacun sur une ligne. Elles ne sont **pas** groupées par app : avec
un `groupBy`, Kibana ignore `excludeHitsFromPreviousRun` et renotifie le même
événement à chaque exécution tant qu'il reste dans la fenêtre (constaté en
test). `security-alerts.yml` renvoie à chaque passage toutes les CVE encore
ouvertes : S1 les notifie donc à chaque passage.

## Champs ECS produits

La correspondance champ par champ (payload de la source → champ ECS → règle de
transformation), le gabarit de la ligne `message`, les catégories et émojis, et
les causes de rejet : **[format/webhooks/conventions.md](../../format/webhooks/conventions.md)**.

En résumé : chaque pipeline pose `event.provider` (`scalingo` | `github`),
`event.kind`, `event.action`, `event.id`, `service.name` et `message`, la ligne
de notification de l'événement en texte brut, que les règles et les Workflows
Tchap listent telle quelle. Le payload brut est gardé sous `scalingo.*` ou
`github.*`, lisible dans le document mais **non indexé**.

## Mise en service

À faire dans l'ordre : chaque étape dépend de la précédente.

1. **Stockage** : dans [`stockage/logs/`](../../stockage/logs/README.md), rejouer
   les blocs `logs-alertes*` de `2-component-templates.console`, puis de
   `3-index-templates.console`, **y compris la création des 4 data streams et
   de leur failure store** qui suit les templates : sans elle, les règles
   tombent en erreur tant qu'aucun document n'est arrivé.
2. **Pipelines** : rejouer [`ingest-alertes-scalingo.console`](../../../../../kibana/pipelines/webhooks/ingest-alertes-scalingo.console)
   et [`ingest-alertes-scalingo-format-slack.console`](../../../../../kibana/pipelines/webhooks/ingest-alertes-scalingo-format-slack.console)
   en premier, puis les trois `ingest-alertes-scalingo-<env>-default.console` et
   `ingest-alertes-github-default.console`. Les `_simulate` en fin de fichier
   doivent donner les résultats annoncés en commentaire.
3. **Accès** : rejouer [`acces-webhooks.console`](../../../../../kibana/pipelines/webhooks/acces-webhooks.console)
   en remplaçant `<mot-de-passe-généré>` par un mot de passe alphanumérique,
   rangé dans le coffre de l'équipe. Copier le champ `encoded` de l'API Key.
4. **Sessions Discover** : importer les `.ndjson` de
   [`kibana/discovers/webhooks/`](../../../../../kibana/discovers/webhooks/)
   (cf. [importer](../../../../../kibana/objets-kibana.md#importer)), **avant** les
   règles : leurs liens pointent vers ces sessions par leur id.
5. **Règles** : A4a, A4b ([`2-rules-applicatives.console`](../../../../../kibana/rules/generated/2-rules-applicatives.console)),
   M6a, M6b, M13 ([`3-rules-stack-observabilite.console`](../../../../../kibana/rules/generated/3-rules-stack-observabilite.console)),
   S1 ([`1-rules-securite.console`](../../../../../kibana/rules/generated/1-rules-securite.console)).
   Elles reprennent les IDs des anciennes X1 à X5 : `PUT` les met à jour, sauf
   **M6b**, nouvelle, à créer avec `POST` (cf. l'en-tête de son bloc).
6. **Test sans Scalingo** :
   ```bash
   printf 'Mot de passe : '; read -rs MDP; echo
   curl -sS -w '\nHTTP %{http_code}\n' -X POST "https://alertes-scalingo:${MDP}@<endpoint-es>/logs-alertes-scalingo-staging-default/_doc" -H 'Content-Type: application/json' -d '{"id":"test","created_at":"'"$(date -u +%FT%TZ)"'","type":"restart","app_id":"test","app_name":"pass-emploi-api-staging","user":{"username":"test"},"type_data":{"scope":["web"],"reason":"user_restart"}}'
   ```
   La réponse doit contenir `"result":"created"` **sans** `"failure_store":"used"`.
   Sous 5 min, A4b le notifie (un redémarrage est un incident). L'endpoint Elasticsearch est indiqué sur la page
   du déploiement Elastic Cloud (`….es.…`, pas l'adresse de Kibana).
7. **Notifiers Scalingo** : sur chaque app suivie, **un seul** notifier
   **Webhook** (deux écriraient deux fois les mêmes événements) vers
   `https://alertes-scalingo:<mdp>@<endpoint-es>/logs-alertes-scalingo-<env>-default/_doc`
   (`<env>` = suffixe de l'app), nommé d'après son salon :

   | Apps (région)                                                                                 | Notifier                             | Événements                                               |
   |-----------------------------------------------------------------------------------------------|--------------------------------------|----------------------------------------------------------|
   | `api`, `connect`, `metabase`, `web` de prod (`osc-secnum-fr1`)                                 | `Elastic monitoring production`      | tous, ou presque : déploiements, crashs, variables, addons, collaborateurs, domaines |
   | `logstash`, `logstash-process`, `heartbeat`, `elastic-agent` de prod (`osc-secnum-fr1`)        | `Elastic monitoring o11y production` | `app_crashed_repeated`, `app_restarted`, `app_stopped`   |
   | `logstash`, `logstash-process` de perf (`osc-secnum-fr1`)                                      | `Elastic monitoring o11y staging`    | `app_crashed_repeated`, `app_restarted`                  |
   | `api`, `connect`, `web` de staging (`osc-fr1`), `keycloak-staging` (`osc-secnum-fr1`)          | `Elastic monitoring staging`         | déploiements, crashs et redémarrages selon l'app         |

   Rattacher aussi les alertes de métriques Scalingo de l'app à ce notifier.
   Une app ajoutée ou retirée l'est aussi dans `APPS` de
   [`verifier-parite.py`](../../../../../kibana/pipelines/webhooks/verifier-parite.py).
   Les apps de la stack sont celles que filtrent M6a et M6b (`service.name`) :
   une app de la stack ajoutée ici l'est aussi dans ces deux règles, sinon ses
   événements partent dans les salons applicatifs (A4a à A4d). Non suivies : outils
   de tir et mocks de perf, apps de perf applicatives, `elastic-agent-perf`,
   `tfstate`, `nginx-rp`, `tchap-webhooks`.
8. **GitHub Actions** : [`security-alerts.yml`](../../../../../.github/workflows/security-alerts.yml)
   envoie les CVE vers `logs-alertes-github-default` (un `_bulk`, une CVE par
   document, plus `repository`) quand le repo appelant lui passe, tous deux
   optionnels, l'entrée `elastic-url` (sa variable `ELASTIC_URL`, l'endpoint
   Elasticsearch) et le secret `ELASTIC_ALERTES_GITHUB_API_KEY` (champ `encoded`
   de l'API Key de l'étape 3). Repos appelants :
   `pass-emploi-api`, `pass-emploi-web`, `pass-emploi-connect` ; dans chacun,
   créer la variable et le secret puis, dans son `security-alerts.yml`,
   épingler le nouveau commit et les transmettre. Un rejet par Elasticsearch
   fait échouer l'étape. Ne partent que les CVE high/critical dont l'avis
   n'est pas retiré (`withdrawn_at` vide : un avis retiré garde son alerte
   ouverte jusqu'à ce que GitHub la ferme) et qui touchent une dépendance de
   production selon `yarn npm audit --environment production`. Le scope de
   GitHub ne suffit pas : il classe `runtime` toute dépendance transitive lue
   dans un `yarn.lock`, dev comprise. Si l'audit Yarn échoue, le workflow
   retombe sur ce scope GitHub, avec un warning dans son journal.

   **L'envoi se coupe sans PR** : variable `CVE_ENVOI_ELASTICSEARCH` du repo
   appelant à `false` (*Settings* → *Secrets and variables* → *Actions* →
   *Variables*), transmise en entrée `envoi-elasticsearch`. Absente, les CVE
   partent si `ELASTIC_URL` et `ELASTIC_ALERTES_GITHUB_API_KEY` existent ; à
   `false`, le workflow ne fait que lister les CVE dans son journal.

Contrôle de complétude :
[`verifier-parite.py`](../../../../../kibana/pipelines/webhooks/verifier-parite.py) compare, app par app, l'historique
Scalingo (`scalingo timeline`, limité aux événements sélectionnés dans le
notifier Elastic) aux documents reçus depuis une date, et liste le failure
store. Lecture seule ; code de sortie non nul au moindre écart.

```bash
# ES_URL : l'endpoint Elasticsearch ; ES_API_KEY : une clé API qui peut lire les data streams logs-alertes-*
python3 -I kibana/pipelines/webhooks/verifier-parite.py --depuis <date ISO 8601, par exemple 2026-10-19T17:00:00Z>
```

## Limites connues

- **Noms des `type` de crash et de déploiement** : jamais observés sur un
  événement réel, repris du catalogue Scalingo (cf. [table des actions](../../format/webhooks/conventions.md#table-des-actions)).
- **Événements au format Slack** : seules les modifications de variables ont été
  observées. Un autre type dans ce format passe par le même pipeline et sort en
  ℹ️ `scalingo_<libellé>` ; un format encore différent part au failure store
  (règle M13).
- **Identifiants dans l'URL du notifier** : visibles de tous les collaborateurs
  de l'app Scalingo. Acceptable parce que l'utilisateur ne peut qu'ajouter des
  documents aux 3 data streams Scalingo (`create_doc` + `auto_configure`). Pour
  révoquer : changer son mot de passe et mettre à jour les notifiers.
