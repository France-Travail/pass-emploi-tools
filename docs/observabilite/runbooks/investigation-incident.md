# Runbook — investiguer un incident applicatif

« Pourquoi cet utilisateur a un problème, là, maintenant ? » Point de départ :
un `user.id`, un identifiant de requête ou un timestamp. Data view
`logs-*-default-*` (app + router, cf.
[routine-surveillance § Pré-requis](../routine-surveillance.md#pré-requis)).
Pour une panne de la chaîne de logs elle-même : [runbook-logstash](runbook-logstash.md).

Champs pivots : `user.id`, `trace.id`, `http.request.id`, `log.level: error`.

## Requêtes

| Action                        | KQL                                                                                                |
|-------------------------------|----------------------------------------------------------------------------------------------------|
| Tous ses logs récents         | `user.id: "<id>"`                                                                                  |
| Uniquement les erreurs        | `user.id: "<id>" AND log.level: error`                                                             |
| Une requête HTTP (edge + app) | `http.request.id: "<id>"`                                                                          |
| Bout en bout d'une session    | `trace.id: "<id>"` (même pivot dans l'APM, cf. [collecte/traces](../collecte/traces/README.md))    |
| Échecs handler                | `event.action: handler_executed AND event.outcome: failure`                                        |
| Latence réseau vs code        | comparer `event.duration` de `request_routed` vs `request_completed` sur le même `http.request.id` |

## Limite : les flux non authentifiés

Un flux **non authentifié** (login) n'a ni `user.id` ni `trace.id` qui le
traverse → pivoter sur `client.ip` + fenêtre temporelle, ou **reproduire en
live** en tailant les logs. Pour le login, le funnel `login_*` de
`pass-emploi-connect` (`login_initiated` → `login_redirected` →
`login_completed` / `login_failed`, mode d'authentification dans `labels.idp`)
localise l'échec, et `error.type` sa cause. `login.step` est vide en prod : se
fier à `error.type`.

| `error.type`                | Cause                                                                                   | Imputable à |
|-----------------------------|-----------------------------------------------------------------------------------------|-------------|
| `UTILISATEUR_NON_TRAITABLE` | refus voulu : l'utilisateur n'a pas droit à l'app                                       | métier      |
| `OPError`, `RPError`        | l'IDP renvoie une erreur OIDC                                                           | partenaire  |
| `SessionNotFound`           | connect perd l'interaction OIDC au retour de l'IDP (cookie purgé par webview ou ITP iOS) | nous        |
| `ReplyError`, `TypeError`…  | Redis, bug                                                                              | nous        |

## Suspicion de DDoS ou surcharge de l'infra

Déclencheurs : la règle 🚨 « Suspicion d'attaque DDoS » (S2a), une alerte de
métriques Scalingo ⚠️ (requêtes par minute, 5xx, temps de réponse) relayée par
A4a, ou des apps qui ne répondent plus (heartbeat). Une surcharge fait souvent
décrocher le log drain et Logstash : ne pas compter sur nos logs.

1. **Quelle app, depuis quand** : ses métriques dans le dashboard Scalingo de
   l'app (onglet Metrics : requêtes par minute, 5xx, temps de réponse,
   conteneurs). Elles ne passent pas par nos logs. Un événement légitime
   (mise en service, notification de masse, campagne) l'explique-t-il ?
2. **Nos logs arrivent-ils encore** : règle M3b (absence d'ingestion des logs du
   routeur) au repos. Si oui, le Discover **[Pass Emploi] Logs de Prod - Trafic
   du routeur par IP** donne les requêtes et les 5xx par IP, chemin et user agent
   (les IP `10.x` sont des appels internes à Scalingo).
3. **Sinon, les IP en cause sans notre chaîne de logs** : les logs du routeur
   lus directement chez Scalingo, l'IP du client dans `from=` :

   ```bash
   scalingo --region osc-secnum-fr1 --app pass-emploi-connect-prod logs --lines 5000 \
     | grep ' router ' | grep -o 'from="\?[0-9.]*' | sort | uniq -c | sort -rn | head
   ```

   Puis le chemin le plus demandé par l'IP en tête :
   `… | grep '<ip>' | grep -o 'path="[^"]*' | sort | uniq -c | sort -rn | head`.
   Si rien ne ressort, le support Scalingo, qui voit le trafic en amont.
4. **Bloquer** : sur connect, la variable `BLOCKED_IPS` de l'app, une liste JSON
   d'adresses (`["1.2.3.4", "5.6.7.8"]`) dont les requêtes sont refusées en 403.
   Ajouter l'IP à la liste existante, sans l'écraser, puis redémarrer l'app pour
   l'appliquer. Une IP bloquée reste visible dans les logs du routeur (403).

## Dashboard « Investigation utilisateur »

Data view `logs-*-default-*`, filtre global `user.id` : timeline `event.action`,
compteurs par `event.action`, latences `external_api_call`, corrélation
router ↔ app par `http.request.id`.
