# Notifications d'alertes vers Tchap via Kibana Workflows — design

> **Statut : implémenté le 2026-10-13** (validé sur pile locale, pas encore déployé sur Elastic Cloud). Premier lot : les règles
> X1 à X5 des [alertes externes](../../observabilite/supervision/alertes-externes.md).
>
> Artefact de travail : il guide l'implémentation, il n'a pas vocation à rester
> à jour au-delà. La doc de référence sera le `README.md` de
> `observabilite/supervision/workflows/tchap/` et l'ADR-004.

## 1. Problème

Mattermost est **décommissionné le 1ᵉʳ novembre 2026**. Les 34 règles Kibana
notifient aujourd'hui des canaux Mattermost par des connecteurs Webhook (un par
canal). Elles doivent notifier **Tchap**, sans brique intermédiaire à héberger
chez nous (ni slack2tchap, ni n8n).

Tchap est un serveur Matrix (Synapse). Envoyer un message, c'est
`PUT /_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}`, où le
`txnId` doit être **unique à chaque message** : un `txnId` déjà vu est pris
pour une nouvelle tentative et le message n'est pas posté (vérifié en local).
Le connecteur Webhook de Kibana a une URL fixe (seul le body est templaté,
code v9.4.7) : il ne peut pas produire ce `txnId`.

## 2. Décisions structurantes

| #  | Décision                                                                                                                     | Raison                                                                                                                                                                                                                                                                                |
|----|------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| D1 | Les règles déclenchent des **Kibana Workflows** (action système `.workflows`), qui appellent Tchap par le connecteur `.http` | Le `path` du connecteur `.http` est templaté : `txnId = {{ execution.id }}`, conforme à la norme Matrix. Possible **parce que nous sommes en licence Elastic Cloud Enterprise** (requise par les Workflows) → ADR-004                                                                 |
| D2 | **Un Workflow par salon** (`tchap-<salon>`), choisi dans l'action de la règle                                                | Même geste qu'avec un connecteur Mattermost par canal : c'est la règle qui choisit sa destination. Migrer une règle = ajouter une action                                                                                                                                              |
| D3 | **Un seul Workflow parle à Matrix** : `tchap-client`                                                                         | Le bloc HTTP n'existe qu'une fois ; changer l'appel à Tchap = un fichier                                                                                                                                                                                                              |
| D4 | **Message générique** : sévérité (tag), nom de la règle, lignes, liens                                                       | Le Workflow ne reçoit de la règle que son id, son nom, ses tags et ses alertes (`buildAlertEvent`, v9.4.7)                                                                                                                                                                            |
| D5 | Une **ligne `message` par événement**, écrite par l'ingest pipeline                                                          | Le Workflow ne reçoit pas `context.hits` : les champs des documents sont fusionnés champ par champ dans le document d'alerte (`service.name: [a, b]`), sans appariement, et `event.action` y est écrasé (`open`). Un champ unique par document garde l'appariement (vérifié en local) |
| D6 | Pendant la transition, X1–X5 notifient **Tchap et Mattermost**                                                               | Comparaison des deux canaux jusqu'au 1ᵉʳ novembre                                                                                                                                                                                                                                     |
| D7 | Les échecs d'envoi sont visibles dans une règle **sans action**                                                              | Mattermost disparaît ; Tchap ne peut pas signaler sa propre panne                                                                                                                                                                                                                     |

## 3. Architecture

```
Ingest pipelines Scalingo / GitHub ──► champ message (1 ligne par événement)
                                              │
Rules X1–X5 ──┬─► action webhook Mattermost (jusqu'au 1ᵉʳ novembre)
              └─► action .workflows ──► tchap-<salon>         (salon choisi par la règle)
                                          foreach alerte → texte + html
                                              │ workflow.execute
                                              ▼
                                        tchap-client
                                          PUT /rooms/{salon}/send/m.room.message/{execution.id}
                                              │ connecteur .http « Tchap » (URL + jeton en en-tête secret)
                                              ▼
                                            Tchap

.workflows-executions (status: failed) ──► règle « Tchap - Envoi en échec » (sans action)
```

### Fichiers

```
docs/observabilite/supervision/workflows/tchap/
  connecteur-tchap.console              connecteur .http, jeton remplacé par <jeton-du-bot>
  tchap-client.console                  seul appel à Matrix
  tchap-monitoring-production.console   X1, X2, X4
  tchap-monitoring-staging.console      X3
  tchap-o11y-production.console         X5
  tchap-o11y-staging.console            aucune règle pour l'instant (règles de la stack, lot suivant)
  README.md                             contrat de tchap-client, ajouter une règle ou un salon, pièges
docs/decisions/ADR-004-notifications-tchap-kibana-workflows.md
```

Les Workflows se versionnent en `.console` comme le reste de `supervision/` :
`POST kbn:/api/workflows/workflow` avec `{"id": "...", "yaml": """..."""}`, et
`PUT kbn:/api/workflows/workflow/<id>` avec `{"yaml": ...}` pour une mise à jour.

## 4. Composants

### 4.1 Connecteur `.http` « Tchap »

```json
{
  "name": "Tchap",
  "connector_type_id": ".http",
  "config": { "url": "https://matrix.agent.tchap.gouv.fr", "hasAuth": false, "authType": null },
  "secrets": { "secretHeaders": { "Authorization": "Bearer <jeton-du-bot>" } }
}
```

`authType: null` est obligatoire avec `hasAuth: false` (sinon erreur de
validation). Le jeton n'est relu ni par l'API, ni dans les exécutions, ni dans
les index `.workflows-*` (vérifié en local).

### 4.2 `tchap-client`

Contrat d'entrée : `salon` (ID du salon, `!…:agent.tchap.gouv.fr`), `texte`
(texte brut), `html` (HTML déjà échappé).

```yaml
name: Tchap - Client
triggers:
  - type: manual
inputs:
  - { name: salon, type: string, required: true }
  - { name: texte, type: string, required: true }
  - { name: html,  type: string, required: true }
steps:
  - name: envoyer
    type: http
    connector-id: <id du connecteur Tchap>
    with:
      method: PUT
      path: /_matrix/client/v3/rooms/{{ inputs.salon | url_encode }}/send/m.room.message/{{ execution.id }}
      body:
        msgtype: m.text
        body: "{{ inputs.texte }}"
        format: org.matrix.custom.html
        formatted_body: "{{ inputs.html }}"
```

### 4.3 Workflows de salon `tchap-<salon>`

Ne contiennent que l'ID du salon et la mise en forme. Gabarit :

```yaml
name: Tchap - monitoring-production
triggers:
  - type: alert
consts:
  salon: "<ID du salon>"
steps:
  - name: chaque-alerte
    type: foreach                     # une étape foreach, pas une propriété foreach: (ignorée sur workflow.execute)
    foreach: "{{ event.alerts | json }}"
    steps:
      - name: notifier
        type: workflow.execute
        with:
          workflow-id: tchap-client
          inputs:
            salon: "{{ consts.salon }}"
            texte: "<sévérité> {{ event.rule.name }} (<nombre>)<lignes>\n<lien Discover>"
            html: "<p><sévérité> <strong>{{ event.rule.name | escape }}</strong> (<nombre>)</p><ul><lignes></ul><p><a href=\"<lien Discover>\">Ouvrir dans Discover</a> · <a href=\"<lien règle>\">Voir la règle</a></p>"
```

| Élément       | Source                                                                                                                                                  |
|---------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| Sévérité      | tag de la règle : `critical` → 🚨, `warning` → ⚠️ (`event.rule.tags contains …`)                                                                       |
| Nombre        | `foreach.item.kibana.alert.evaluation.value`                                                                                                            |
| Lignes        | `foreach.item.message` (liste, une entrée par document) ; à défaut `foreach.item.kibana.alert.reason` ; chaque ligne passe par `\| escape` dans le HTML |
| Lien Discover | `foreach.item.kibana.alert.url`, **déjà absolue** quand `server.publicBaseUrl` est défini (cas d'Elastic Cloud) : ne pas la préfixer par `kibanaUrl`    |
| Lien règle    | `event.ruleUrl` (à vérifier à l'implémentation)                                                                                                         |

Le texte « À vérifier » ne figure plus dans le message : il reste dans
`alertes-externes.md`.

### 4.4 Ligne `message` (ingest pipelines)

Une ligne par **type d'événement**, pas par règle (X1 et X3 lisent les mêmes
types). Texte brut, sans markdown (le HTML l'échapperait tel quel). Reprend le
contenu des lignes Mattermost actuelles :

| Pipeline                        | Événement                                                                  | `message`                                                                                                                                   |
|---------------------------------|----------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `ingest-alertes-scalingo`       | `crash`, `repeated_crash`, `restart`, `stop`, `start`, `deployment`, autre | `<service.name> : <event.action>[ (<event.reason>)][ sur <labels.scope>][, par <user.name>]`                                                |
| `ingest-alertes-scalingo`       | `alert`                                                                    | `<service.name> : <labels.metric> à <labels.value_text> (seuil <labels.limit_text>)[ sur <service.node.name>]`                              |
| `ingest-alertes-scalingo`       | `scale`                                                                    | `<service.name> : app_scaled <labels.formation_before> → <labels.formation>`                                                                |
| `ingest-alertes-github-default` | une CVE                                                                    | `<service.name> : <vulnerability.id> — <package.name> (<vulnerability.severity>) : <vulnerability.description> — <vulnerability.reference>` |

Le champ `message` est déjà mappé (`match_only_text`, via
`pass-emploi-logs@mappings`) : pas de changement de template. Les `_simulate`
de chaque pipeline vérifient la ligne produite sur les captures réelles.

X5 lit le failure store : ses documents ne passent pas par le pipeline, ils
n'ont pas de `message` → ligne `kibana.alert.reason`.

### 4.5 Règles X1–X5

Dans `rules/3-rules-alertes-externes.console` :

- ajout du tag de sévérité (`critical` pour X1 et X4, `warning` pour X2, X3, X5) ;
- ajout d'une 2ᵉ action, l'action Mattermost restant inchangée :

```json
{
  "id": "system-connector-.workflows",
  "params": {
    "subAction": "run",
    "subActionParams": {
      "workflowId": "tchap-monitoring-production",
      "summaryMode": true,
      "alertStates": { "new": true, "ongoing": true, "recovered": false }
    }
  }
}
```

| Règle      | Workflow                      | Mattermost (jusqu'au 1ᵉʳ novembre) |
|------------|-------------------------------|------------------------------------|
| X1, X2, X4 | `tchap-monitoring-production` | `#monitoring-production`           |
| X3         | `tchap-monitoring-staging`    | `#o11y-staging`                    |
| X5         | `tchap-o11y-production`       | `#o11y-production`                 |

`ongoing: true` est nécessaire : avec `excludeHitsFromPreviousRun`, un 2ᵉ
événement arrivé pendant que l'alerte est active doit être notifié (vérifié en
local : 2 événements = 2 messages, sans renvoi). `recovered: false` évite un
message à la fin de l'alerte.

### 4.6 Supervision des envois

Règle « Tchap - Envoi en échec » dans un fichier `rules/` : requête sur
`.workflows-executions`, `status: failed`, champ de temps `finishedAt`,
**sans action**. Un échec y apparaît avec l'erreur Matrix (`error.message`,
ex. `[403] Forbidden: User … not in room …`) ; l'enfant **et** le parent
passent en `failed`, la règle d'origine reste `ok`. Ajoutée à la
[routine de surveillance](../../observabilite/routine-surveillance.md).
À vérifier à l'implémentation : lecture de `.workflows-executions` (index
caché) par une règle.

## 5. Mise en service

1. **Tchap** : compte bot sur une boîte fonctionnelle de l'équipe ; 4 salons
   `monitoring-production`, `monitoring-staging`, `o11y-production`,
   `o11y-staging`, non chiffrés si Tchap le permet ; inviter le bot,
   `curl …/join`, récupérer le jeton (`curl …/login`), le ranger dans le coffre.
   Test : `curl PUT …/send/m.room.message/<txnId>` dans chaque salon.
2. **Pipelines** : rejouer `ingest-alertes-scalingo` puis
   `ingest-alertes-github-default` ; leurs `_simulate` donnent les lignes attendues.
3. **Kibana** : connecteur Tchap, `tchap-client`, les 4 Workflows de salon.
   Test : exécution manuelle de `tchap-client` vers chaque salon.
4. **Règles** : rejouer X1–X5, puis la règle de supervision.
5. **Bout en bout** : le `curl` d'injection de `alertes-externes.md` → message
   dans `#o11y-staging` (Mattermost) **et** `monitoring-staging` (Tchap).
6. **Échec** : faux salon dans `tchap-monitoring-staging`, une injection, la
   règle de supervision passe en alerte ; remettre le bon salon.
7. **1ᵉʳ novembre** : retirer les actions Mattermost de X1–X5, supprimer les
   connecteurs `Mattermost-*`.

## 6. Documentation

- `observabilite/supervision/workflows/tchap/README.md` (nouveau).
- `docs/decisions/ADR-004-notifications-tchap-kibana-workflows.md` (nouveau) :
  décision fondée sur la licence Elastic Cloud Enterprise ; solutions écartées
  (slack2tchap, n8n mutualisé beta.gouv, connecteur Webhook en `POST` sans
  `txnId`, Watcher, un Workflow par règle, salon porté par un tag de la règle)
  et repli sans Enterprise (Webhook en `POST`).
- `alertes-externes.md` : chaîne, canaux, mise en service.
- `objets-kibana.md` et `observabilite/README.md` : Workflows et ADR-004.

## 7. Risques

| Risque                                                          | Conséquence                                                                           | Parade                                             |
|-----------------------------------------------------------------|---------------------------------------------------------------------------------------|----------------------------------------------------|
| Expiration du jeton ou désactivation du bot par Tchap (inconnu) | Tous les envois en `401`                                                              | Règle de supervision, consultée par la routine     |
| Salons Tchap forcément chiffrés                                 | Messages en clair dans un salon chiffré : acceptés par Synapse, affichage non vérifié | Vérifier l'affichage à l'étape 1                   |
| Workflows récents (9.x), API susceptible d'évoluer              | Fichiers `.console` à adapter à une montée de version                                 | Tests de l'étape 3 rejoués après montée de version |

## 8. Hors périmètre

- Les **29 autres règles** (applicatives, stack, SLO) : lot suivant, **avant le
  1ᵉʳ novembre** (elles ne notifient que Mattermost). Avec D2, chacune se migre
  en ajoutant un tag de sévérité et une action vers un Workflow de salon.
  **Sauf** pour les règles sur les logs applicatifs (`logs-<env>-default`) : leur
  `message` est la ligne de log brute, que les Workflows de salon listeraient
  telle quelle. À trancher en début de lot : Workflow de salon limité à
  `kibana.alert.reason`, ou champ de notification dédié.
- Les alertes qui postent dans Mattermost **hors Kibana** : 11 et 12 (AutoOps)
  passent à un connecteur Webhook AutoOps en `POST` direct vers Tchap (ADR-004,
  section « Alertes émises hors Kibana ») ; 6 (webhook Scalingo de Logstash)
  est retirée, couverte par X1 et X3. À faire avant le 1er novembre.
- La bascule des notifiers Scalingo directs et de `security-alerts.yml`
  (étapes 6 à 8 de la mise en service de `alertes-externes.md`).

## 9. Écarts avec l'implémentation

- La ligne `message` des événements Scalingo commence par le nom complet de
  l'app (`scalingo.app_name`, ex. `pass-emploi-api-prod`) et non par
  `service.name`, qui a perdu son suffixe d'environnement.
- Le README de `workflows/tchap/` porte la mise en service Tchap (bot, salons,
  imports, test), à laquelle renvoie `alertes-externes.md`.
