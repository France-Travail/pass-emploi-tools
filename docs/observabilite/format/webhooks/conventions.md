# Conventions ECS des webhooks : correspondance avec les champs ECS

Comment chaque ingest pipeline transforme le payload d'une source externe
(notifier Scalingo, alerte Dependabot) en document ECS, ou vérifie celui que
l'émetteur a déjà écrit (rapport de versions) : quel champ source donne
quel champ ECS, avec quelle règle, et comment se construit la ligne `message`
que les règles et Tchap affichent. C'est l'équivalent, pour ces sources, des
[conventions des logs ECS](../logs/conventions.md) pour les logs des apps.

Cette matrice redit volontairement ce que font les pipelines, **par exception**
à la règle « un fait, un endroit » : ECS et l'organisation des configurations
Elastic du repo sont peu familiers à l'équipe, qui a besoin de lire la
correspondance sans lire le Painless des pipelines, comme pour les logs.

Ce fichier décrit **ce que font les pipelines** de [`supervision/pipelines/webhooks/`](../../supervision/pipelines/webhooks/README.md) :
toute modification d'un pipeline se reporte ici dans la même PR, et inversement.
La chaîne, les accès et la mise en service : [collecte par webhook](../../collecte/webhooks/README.md).

## Principes communs à toutes les sources

| Principe | Règle |
|---|---|
| Un data stream par source | `logs-alertes-<source>-<env>-default` (Scalingo, un par environnement) ou `logs-alertes-<source>-default` (GitHub, versions). Le pipeline est le `default_pipeline` du data stream : l'émetteur n'a rien à préciser. |
| Payload brut gardé | Tout le payload est déplacé sous `<source>.*` (`scalingo.*`, `github.*`), en `dynamic: false` : lisible dans le document, **non indexé** (on ne cherche pas dedans). Seule exception : l'email de l'auteur Scalingo, supprimé. |
| Champs ECS indexés | Uniquement ceux des tableaux ci-dessous. Mappings : `logs-alertes@mappings` (`event.id`, `.kind`, `.provider`, `.reason`) et `logs-alertes-<source>@mappings`, dans [`stockage/logs/2-component-templates.console`](../../stockage/logs/2-component-templates.console) ; le reste suit `ecs@mappings` (`labels.*` en keyword). |
| `event.provider` | Le nom de la source : `scalingo`, `github` ; pour le rapport de versions, celui de l'émetteur (`inventaire-versions`). |
| `event.action` | Verbe au passé, snake_case, comme pour les logs (cf. [taxonomie](../logs/conventions.md#taxonomie-eventaction)). Un type inconnu de la source n'est pas rejeté : il sort en `<source>_<type>`. |
| `message` | **La ligne de notification** de l'événement, en texte brut, construite par le pipeline. Les règles et les Workflows Tchap l'affichent telle quelle, une ligne par document (tag `tchap-lignes`). C'est la seule différence assumée avec les logs ECS des apps, où `message` = `event.action` : ici, un document = une notification. |
| Rejet | Un document qui n'a pas la forme attendue de sa source est **rejeté** (processeur `fail` ou erreur d'un processeur) et part dans le failure store de son data stream (`<data stream>::failures`), que lit la règle 14. Il n'est jamais indexé à moitié. |
| Données personnelles | Ni email ni valeur de variable d'environnement : `user.name` porte l'identifiant de l'auteur, `labels.details` les **noms** des variables. |

## Scalingo (`logs-alertes-scalingo-<env>-default`)

Pipelines, dans l'ordre d'exécution :

1. `ingest-alertes-scalingo-<env>-default` : pipeline par défaut du data stream.
   Appelle `ingest-alertes-scalingo-format-slack` si le payload est au format
   Slack, vérifie l'enveloppe, appelle `ingest-alertes-scalingo`, puis vérifie
   l'environnement.
2. `ingest-alertes-scalingo-format-slack` : ramène un payload au format Slack à
   l'enveloppe habituelle (cf. [ci-dessous](#format-slack)).
3. `ingest-alertes-scalingo` : la transformation en champs ECS.

### Payload attendu

Enveloppe des notifiers webhook, vérifiée sur des captures réelles :

```json
{"id": "…", "created_at": "2026-09-23T14:02:11.000Z", "type": "restart",
 "app_id": "…", "app_name": "pass-emploi-logstash-perf",
 "user": {"username": "…", "email": "…"},
 "type_data": {…}}
```

`type_data` change de forme selon `type` ; seuls les champs lus sont listés
dans la matrice.

### Matrice

| Champ ECS | Source | Règle de transformation | Si absent |
|---|---|---|---|
| `@timestamp` | `created_at` | date ISO 8601 | rejet (erreur du processeur `date`) |
| `event.provider` | — | `scalingo` | — |
| `event.id` | `id` | copie | champ absent |
| `event.kind` | `type` | `alert` si `type` = `alert`, sinon `event` | — |
| `event.action` | `type` (+ `type_data.activated`) | cf. [table des actions](#table-des-actions) | — |
| `event.outcome` | `type` (+ `type_data.activated`) | cf. [table des actions](#table-des-actions) ; absent pour les autres types | — |
| `event.reason` | `type_data.reason` | copie (`user_restart`, `oom`…) | champ absent |
| `service.name` | `app_name` | sans son suffixe `-prod`, `-staging` ou `-perf` (même règle que Logstash) : `pass-emploi-api-prod` → `pass-emploi-api` | rejet (`app_name` obligatoire) |
| `service.environment` | `app_name` | le suffixe : `prod`, `staging`, `perf` | rejet : le pipeline de l'environnement exige le sien |
| `service.node.name` | `type_data.sender_name` | copie, pour `type` = `alert` seulement (`web-1`) | champ absent |
| `user.name` | `user.username` | copie ; `scalingo-platform` pour un événement automatique. **`user.email` n'est pas conservé**, ni dans `user`, ni sous `scalingo.*` | champ absent |
| `labels.scalingo_type` | `type` | copie de la valeur brute : à lire pour un type inconnu | — |
| `labels.metric`, `labels.value_text`, `labels.limit_text` | `type_data.metric`, `.value_text`, `.limit_text` | copie en texte, pour `type` = `alert` seulement (`RAM`, `96.96 %`, `≥ 90.0 %`) | champ absent |
| `labels.formation` | `type_data.containers` | `<conteneur>=<taille>` par conteneur, triés par nom, séparés par une espace : `web=0:L worker=0:L` | champ absent |
| `labels.formation_before` | `type_data.previous_containers` | même format | champ absent |
| `labels.scaled_to_zero` | `type_data.containers` | `"true"` si toutes les tailles commencent par `0`, sinon `"false"` | champ absent |
| `labels.scope` | `type_data.scope` (liste) | valeurs jointes par `,` : `web` | champ absent |
| `labels.details` | `type_data.details` | copie si non vide ; posé par le [format Slack](#format-slack) | champ absent |
| `labels.categorie` | `event.action`, `service.environment` | `incident` ou `infra`, cf. [catégorie et émoji](#catégorie-et-émoji) | — |
| `message` | tout ce qui précède | cf. [gabarit](#gabarit-du-message) | — |
| `scalingo.*` | tout le payload, sauf `user` | copie brute, non indexée (`app_id`, `type_data` complet…) | — |

### Table des actions

| `type` | `event.action` | `event.outcome` | Constaté |
|---|---|---|---|
| `alert`, `type_data.activated: true` | `resource_threshold_exceeded` | `failure` | ✅ |
| `alert`, sinon | `resource_threshold_recovered` | `success` | ✅ |
| `restart` | `app_restarted` | — | ✅ |
| `scale` | `app_scaled` | — | ✅ |
| `crash` | `app_crashed` | `failure` | — |
| `repeated_crash` | `app_crashed_repeatedly` | `failure` | — |
| `stop` | `app_stopped` | — | — |
| `start` | `app_started` | — | — |
| `deployment` | `app_deployed` | — | — |
| autre (dont le [format Slack](#format-slack)) | `scalingo_<type>` | — | ✅ (`scalingo_variables_bulk_edited`, `scalingo_variable_removed`) |

✅ = observé sur un événement réel. Les autres noms viennent du catalogue
Scalingo, sans avoir été observés : un crash qui arrive sous un autre `type`
sort en `scalingo_<type>` et en `infra`, donc sans 🚨. Dans ce cas, ajouter ce
`type` à la table `actions` du pipeline `ingest-alertes-scalingo` (et à
`failures` si c'est un échec, à `arrets` si c'est un incident), puis ici.

### Catégorie et émoji

| `event.action` | `labels.categorie` | Émoji en prod | Émoji en staging et perf |
|---|---|---|---|
| `app_crashed`, `app_crashed_repeatedly`, `app_restarted` (quelle que soit `event.reason`), `app_stopped` | `incident` | 🚨 | ⚠️ |
| `resource_threshold_exceeded` | `incident` | ⚠️ | ⚠️ |
| toutes les autres (`app_deployed`, `app_scaled`, `app_started`, `resource_threshold_recovered`, `scalingo_<type>`) | `infra` | ℹ️ | ℹ️ |

La catégorie se déduit de l'émoji : `infra` si ℹ️, sinon `incident`. Elle
permet de filtrer l'infra hors des salons de monitoring (cf.
[alertes applicatives](../../supervision/alertes-applicatives.md)).

### Gabarit du message

`<app_name>` est le nom complet de l'app, suffixe compris. Entre crochets : la
partie n'est écrite que si le champ existe.

Pour `type` = `alert` :

```
<émoji> <app_name> : <labels.metric ou « ressource »>[ à <labels.value_text>] (seuil <labels.limit_text ou « inconnu »>)[ sur <service.node.name>]
```

« à » devient « revenue à » pour `resource_threshold_recovered`.

Pour les autres types :

```
<émoji> <app_name> : <event.action>[ <labels.formation_before> → <labels.formation>][ (<event.reason>)][ (<labels.details>)][ sur <labels.scope>][, par <user.name>]
```

Exemples (tests des pipelines) :

| Événement | `message` |
|---|---|
| seuil de RAM dépassé, perf | `⚠️ pass-emploi-logstash-perf : RAM à 96.96 % (seuil ≥ 90.0 %) sur web-1` |
| scaling à zéro | `ℹ️ pass-emploi-logstash-perf : app_scaled web=1:L worker=0:L → web=0:L worker=0:L, par prenom.nom` |
| redémarrage manuel, perf | `⚠️ pass-emploi-logstash-perf : app_restarted (user_restart) sur web, par prenom.nom` |
| crash, prod | `🚨 pass-emploi-api-prod : app_crashed (oom) sur web, par scalingo-platform` |
| variable ajoutée (format Slack) | `ℹ️ pass-emploi-logstash-perf : scalingo_variables_bulk_edited (New vars : TEST_NOTIFIER_ELASTIC), par prenom.nom` |

### Format Slack

Le même notifier webhook envoie certains événements au format qu'il poste dans
Mattermost : c'est le cas des modifications de variables, alors
que les redémarrages, scalings et alertes arrivent au format habituel.

```json
{"username": "Scalingo",
 "attachments": [{"title": "[pass-emploi-logstash-perf] Variables bulk edited",
                  "fields": [{"title": "New vars", "value": "• `TEST_NOTIFIER_ELASTIC`"}],
                  "footer": "By prenom.nom", "ts": 1792427008}]}
```

Reconnu quand `app_name` est absent et `attachments` est une liste non vide.
`ingest-alertes-scalingo-format-slack` écrit alors l'enveloppe habituelle, qui
suit ensuite la [matrice](#matrice) :

| Champ de l'enveloppe | Source (`attachments[0]`) | Règle |
|---|---|---|
| `app_name` | `title` | le texte entre `[` et `]` |
| `type` | `title` | le libellé après `]`, en minuscules, chaque caractère qui n'est ni lettre ni chiffre remplacé par `_` : `variables_bulk_edited` → `event.action` `scalingo_variables_bulk_edited` |
| `type_data.details` | `fields` | `<title> : <nom>, <nom>` par champ, champs séparés par ` ; `. Les noms sont les lignes de `value`, sans `•` ni `` ` `` : **des noms de variables, jamais leurs valeurs** |
| `user.username` | `footer` | le texte après `By ` |
| `created_at` | `ts` | secondes epoch → ISO 8601 |
| `id` | `title`, `ts` | `<app_name>-<ts>` |

Un titre qui ne commence pas par `[<app>]` est laissé tel quel : sans
`app_name`, le document est rejeté.

### Rejets

| Cause | Message d'erreur (failure store) |
|---|---|
| `app_name`, `type` ou `type_data` absent (après le format Slack) | `Pas un événement de notifier Scalingo : app_name, type ou type_data absent` |
| suffixe de l'app différent de l'environnement du data stream | `App <app_name> envoyée vers logs-alertes-scalingo-<env>-default : corriger l'URL de son notifier` |
| `created_at` absent ou illisible | erreur du processeur `date` |

## Dependabot (`logs-alertes-github-default`)

Pipeline : `ingest-alertes-github-default`, pipeline par défaut du data stream.

### Payload attendu

Un document par alerte, envoyé par
[`security-alerts.yml`](../../../../.github/workflows/security-alerts.yml) dans
un `_bulk` : l'objet renvoyé par `GET /repos/{owner}/{repo}/dependabot/alerts`
de l'API REST GitHub, plus `repository` (nom court du repo), ajouté par le
workflow.

```json
{"number": 42, "state": "open", "repository": "pass-emploi-api",
 "html_url": "https://github.com/France-Travail/pass-emploi-api/security/dependabot/42",
 "dependency": {"package": {"ecosystem": "npm", "name": "axios"}},
 "security_advisory": {"ghsa_id": "GHSA-…", "cve_id": "CVE-…", "summary": "…", "severity": "high",
                       "cvss_severities": {"cvss_v3": {"score": 7.5}}}}
```

### Matrice

| Champ ECS | Source | Règle de transformation | Si absent |
|---|---|---|---|
| `@timestamp` | — | **heure d'ingestion** (`_ingest.timestamp`), pas la date de création de l'alerte GitHub : le workflow renvoie à chaque passage toutes les CVE ouvertes, que V1 compte à chaque passage | — |
| `event.provider` | — | `github` | — |
| `event.kind` | — | `alert` | — |
| `event.action` | — | `dependency_vulnerability_detected` | — |
| `event.id` | `repository`, `number` | `<repo>#<number>` : `pass-emploi-api#42` | — |
| `service.name` | `repository` | copie ; à défaut, 5ᵉ segment de `html_url` (le nom du repo) | `null` si les deux manquent |
| `vulnerability.id` | `security_advisory.cve_id` | copie ; à défaut, `security_advisory.ghsa_id` | — |
| `vulnerability.severity` | `security_advisory.severity` | copie (`low`, `medium`, `high`, `critical`) | champ absent |
| `vulnerability.description` | `security_advisory.summary` | copie | champ absent |
| `vulnerability.reference` | `html_url` | copie : la page de l'alerte | champ absent |
| `vulnerability.score.base` | `security_advisory.cvss_severities.cvss_v3.score` | copie ; si absent ou `0`, `security_advisory.cvss.score` | champ absent |
| `vulnerability.scanner.vendor` | — | `GitHub Dependabot` | — |
| `package.name` | `dependency.package.name` | copie | champ absent |
| `labels.ecosystem` | `dependency.package.ecosystem` | copie (`npm`…) | champ absent |
| `labels.ghsa_id` | `security_advisory.ghsa_id` | copie | — |
| `labels.dependabot_url` | `html_url` | la page des alertes du repo : `html_url` coupée après `/security/dependabot` | `https://github.com/France-Travail/<repo>/security/dependabot` |
| `message` | tout ce qui précède | cf. [gabarit](#gabarit-du-message-1) | — |
| `github.*` | tout le payload | copie brute, non indexée | — |

Pas d'`event.outcome`, de `service.environment` ni de `labels.categorie` : une
CVE ne dépend pas d'un environnement, et la gravité est portée par
`vulnerability.severity` (V1 filtre `high` et `critical`).

### Gabarit du message

```
<service.name> : <vulnerability.id>[ — <package.name>] (<vulnerability.severity>) : <vulnerability.description>
```

Exemple : `pass-emploi-api : CVE-2026-00000 — axios (high) : Exemple de vulnérabilité`.

### Rejets

| Cause | Message d'erreur (failure store) |
|---|---|
| `security_advisory` absent | `Pas une alerte Dependabot : security_advisory absent` |

## Rapport de versions (`logs-alertes-versions-default`)

Pipeline : `ingest-alertes-versions-default`, pipeline par défaut du data stream.

Différence assumée avec les autres sources : l'émetteur est à nous et écrit des
documents **déjà ECS**, `message` compris. Le pipeline ne transforme rien, il
fait respecter le contrat ci-dessous et rejette le reste. Il n'y a donc pas de
payload brut : les détails de l'émetteur vont sous `versions.*`.

### Payload attendu

Un document par ligne du rapport, envoyé dans un `_bulk` par
`inventaire/inventaire-versions.sh --envoyer` (mode d'emploi :
[`inventaire/README.md`](../../../../inventaire/README.md)). Un autre émetteur
(le passage hebdomadaire des dépendances) écrit ses propres lignes avec le même
contrat et son propre `event.provider`.

```json
{"@timestamp": "2026-11-02T17:40:04Z",
 "event": {"provider": "inventaire-versions", "kind": "alert", "action": "end_of_life_detected",
           "id": "inventaire-versions-20261102T174004Z/fin-de-vie/api/postgresql/14"},
 "service": {"name": "api"},
 "message": "⏰ api : postgresql 14 en fin de vie le 2026-11-12, dans 10 j — ci 14, local 14",
 "labels": {"run_id": "inventaire-versions-20261102T174004Z", "categorie": "fin_de_vie", "echeance": "moins_de_30_j", …},
 "versions": {"jours_restants": 10, "ou": […]}}
```

### Matrice

| Champ ECS | Posé par | Règle | Si absent |
|---|---|---|---|
| `@timestamp` | émetteur | heure de l'envoi, la même pour tous les documents d'un envoi | heure d'ingestion |
| `event.provider` | émetteur | nom de l'émetteur : `inventaire-versions` | rejet |
| `event.kind` | émetteur | `alert` (notifié tout de suite par MV1) ou `event` (rapport hebdomadaire seulement), cf. [catégories](#catégories) | rejet ; toute autre valeur aussi |
| `event.action` | émetteur | verbe au passé, cf. [catégories](#catégories) | rejet |
| `event.id` | émetteur | `<labels.run_id>/<catégorie>/<composant>/…` : unique dans un envoi | rejet |
| `event.outcome` | émetteur | récapitulatif seulement : `failure` s'il y a des erreurs de collecte, sinon `success` | champ absent |
| `event.ingested` | pipeline | heure d'ingestion | — |
| `service.name` | émetteur | composant de l'inventaire (`api`, `keycloak`, `logstash-process`…) ; `inventaire-versions` pour le récapitulatif | rejet |
| `service.environment` | émetteur | `prod`, `staging` ou `perf`, pour la stack Elastic seulement | champ absent |
| `message` | émetteur | cf. [gabarit](#gabarit-du-message-2) : une seule ligne, 500 caractères au plus | rejet |
| `labels.run_id` | émetteur | identifiant de l'envoi, `inventaire-versions-<AAAAMMJJTHHMMSSZ>` : le rapport hebdomadaire lit les documents du dernier | — |
| `labels.categorie` | émetteur | `ecart`, `stack_elastic_violation`, `stack_elastic_retard`, `fin_de_vie`, `recapitulatif` | — |
| `labels.brique`, `.version`, `.app`, `.source`, `.cluster_version` | émetteur | la ligne de l'inventaire : brique, version trouvée, app Scalingo, source (`déployé`, `variable LOGSTASH_VERSION`…), version du cluster | champ absent |
| `labels.produit`, `.cycle`, `.eol`, `.echeance`, `.derniere_version` | émetteur | fin de vie : produit et cycle endoflife.date, date de fin de vie, `depassee` / `moins_de_30_j` / `moins_de_6_mois`, dernière version du cycle | champ absent |
| `labels.inventaire_genere_le`, `.erreurs_collecte` | émetteur | récapitulatif : date de collecte de l'inventaire (différente de l'envoi avec `--depuis`), appels en échec | champ absent |
| `versions.jours_restants` | émetteur | fin de vie : jours avant la date, négatif si dépassée (`long`) | champ absent |
| `versions.compteurs.*` | émetteur | récapitulatif : `ecarts`, `violations`, `retards`, `fins_de_vie_depassees`, `fins_de_vie_moins_de_30_j`, `fins_de_vie_moins_de_6_mois`, `erreurs_collecte` (`long`) | champ absent |
| `versions.*` (le reste) | émetteur | détail lisible, non indexé : `cellules` d'un écart, `ou` d'une fin de vie | — |

### Catégories

| `labels.categorie` | `event.action` | `event.kind` | Émoji |
|---|---|---|---|
| `stack_elastic_violation` : brique Elastic au-dessus du cluster | `elastic_stack_version_ahead_detected` | `alert` | 🚨 |
| `fin_de_vie`, dépassée | `end_of_life_detected` | `alert` | ⛔ |
| `fin_de_vie`, dans moins de 30 jours | `end_of_life_detected` | `alert` | ⏰ |
| `fin_de_vie`, dans moins de 6 mois | `end_of_life_detected` | `event` | ⏳ |
| `stack_elastic_retard` : brique Elastic sous le cluster | `elastic_stack_version_behind_detected` | `event` | 🐢 |
| `ecart` : valeurs incompatibles entre environnements | `version_mismatch_detected` | `event` | 🔀 |
| `recapitulatif` : un par envoi | `inventory_completed` | `event` | 📋, ⚠️ si collecte incomplète ou cluster non lu |

### Gabarit du message

```
🔀 <composant> : <brique> en écart — <colonne> <valeurs>, …
🚨 <app> : <brique> <version> au-dessus du cluster Elastic <version du cluster> (<source>)
🐢 <app> : <brique> <version> en retard sur le cluster Elastic <version du cluster> (<source>)
⛔ <composant> : <brique> <cycle>[ (<produit>)] en fin de vie depuis le <date> — <contexte> <version>, …
⏰ <composant> : <brique> <cycle>[ (<produit>)] en fin de vie le <date>, dans <n> j — <contexte> <version>, …
⏳ (même gabarit que ⏰)
📋 Inventaire des versions : <n> écart(s), <n> violation(s) et <n> retard(s) de la stack Elastic, <n> fin(s) de vie à moins de 6 mois dont <n> dépassée(s), <n> erreur(s) de collecte[ : <3 premiers appels en échec>…]
```

Le produit n'est écrit que pour `java` (`azul-zulu` sur Scalingo, `eclipse-temurin`
en CI et dans les images) et `stack` (`ubuntu`). Exemples (inventaire réel du
2026-11-02, tests du pipeline) :

| Ligne | `message` |
|---|---|
| écart | `🔀 api : postgresql en écart — prod 15.13.0, staging 16.9.0, perf 17.11.0, ci 14, local 14` |
| retard Elastic | `🐢 pass-emploi-heartbeat-prod : heartbeat 9.4.7 en retard sur le cluster Elastic 9.4.8 (déployé)` |
| fin de vie dépassée | `⛔ keycloak : keycloak 24.0 en fin de vie depuis le 2024-06-10 — prod 24.0.5, staging 24.0.5` |
| fin de vie à 30 jours | `⏰ api : postgresql 14 en fin de vie le 2026-11-12, dans 10 j — ci 14, local 14` |
| récapitulatif | `📋 Inventaire des versions : 17 écart(s), 0 violation(s) et 5 retard(s) de la stack Elastic, 11 fin(s) de vie à moins de 6 mois dont 4 dépassée(s), 0 erreur(s) de collecte` |

### Rejets

Un message par document, les causes séparées par ` ; ` :

| Cause | Message d'erreur (failure store) |
|---|---|
| `event`, `event.provider`, `.kind`, `.action`, `.id`, `service.name` ou `message` absent | `Pas une ligne du rapport de versions : <champ> absent` |
| `event.kind` ni `alert` ni `event` | `… : event.kind <valeur> au lieu de alert ou event` |
| `message` sur plusieurs lignes, ou de plus de 500 caractères | `… : message sur plusieurs lignes`, `… : message de plus de 500 caractères` |
| champ racine hors `@timestamp`, `event`, `service`, `message`, `labels`, `versions` | `… : champ racine non prévu (<champs>) : détails sous versions.*, dimensions sous labels.*` |

## Qui lit quels champs

| Règle | Data streams | Champs lus |
|---|---|---|
| A4a, A4b | `logs-alertes-scalingo-prod-default` ; `-staging-` et `-perf-default` | `service.name` (hors apps de la stack), `message` |
| 6a, 6b | mêmes data streams | `service.name` (apps de la stack : Logstash, Elastic Agent, Heartbeat), `message` |
| V1 | `logs-alertes-github-default` | `vulnerability.severity` (`high`, `critical`), `message` |
| MV1 | `logs-alertes-versions-default` | `event.kind` (`alert`), `message` |
| rapport hebdomadaire des versions (Workflow) | `logs-alertes-versions-default` | `event.action` (`inventory_completed`), `labels.run_id`, `labels.categorie`, `event.kind`, `versions.jours_restants`, `message` |
| 14 | les 5 failure stores | le document rejeté et son erreur |

## Ajouter une source

1. Choisir le data stream (`logs-alertes-<source>[-<env>]-default`), puis
   créer ses templates et son failure store
   ([`stockage/logs/`](../../stockage/logs/README.md)).
2. Écrire son pipeline dans [`supervision/pipelines/webhooks/`](../../supervision/pipelines/webhooks/README.md), avec ses `_simulate` sur
   des captures réelles. Il doit poser au moins `@timestamp`, `event.provider`,
   `event.kind`, `event.action`, `event.id`, `service.name` et `message`, et
   ranger le payload brut sous `<source>.*` en `dynamic: false`.
3. Ajouter sa section ici : payload attendu, matrice, gabarit du message, rejets.
4. Créer son accès en écriture seule
   ([`acces-webhooks.console`](../../supervision/pipelines/webhooks/acces-webhooks.console))
   et sa règle, puis ajouter son failure store à la règle 14.
