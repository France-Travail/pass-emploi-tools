# Alertes de sécurité

Les alertes sur les **vulnérabilités des dépendances** de nos repos (les CVE
remontées par Dependabot, que le workflow GitHub Actions
[`security-alerts.yml`](../../../.github/workflows/security-alerts.yml) envoie
dans `logs-alertes-github-default`) et sur une **suspicion d'attaque par déni
de service**, lue dans les alertes de métriques Scalingo (cf.
[collecte par webhook](../collecte/webhooks/README.md)). Aucune ne dépend des
logs des apps.

## Récapitulatif

| #  | Signal                    | Data stream                   | Condition                                 | Fréquence | Throttle | Sévérité    |
|----|---------------------------|-------------------------------|-------------------------------------------|-----------|----------|-------------|
| V1 | CVE high/critical ouverte | `logs-alertes-github-default` | `vulnerability.severity` high ou critical | 5 min     | —        | 🚨 Critical |
| S2a | Suspicion d'attaque DDoS, prod | `logs-alertes-scalingo-prod-default` | alertes `rpm` et `5XX` de la même app à moins de 10 min, non revenues à la normale | 1 min | — | 🚨 Critical |
| S2b | Suspicion d'attaque DDoS, staging / perf | `logs-alertes-scalingo-staging-default`, `-perf-default` | idem | 1 min | — | 🚨 Critical |

**Création** : rejouer [`rules/generated/1-rules-securite.console`](rules/generated/1-rules-securite.console)
dans Dev Tools, après les sessions Discover de
[`discovers/webhooks/`](discovers/webhooks/).

## V1 — CVE high ou critical ouverte (Critical)

**Objectif** : qu'aucune CVE high ou critical ne reste ouverte sans être vue.

`security-alerts.yml` renvoie **à chaque passage** toutes les CVE encore
ouvertes : V1 les notifie donc à chaque passage, une ligne par CVE (repo, CVE,
paquet, sévérité, résumé, lien vers l'alerte Dependabot ; le nom du repo mène à
la page de ses alertes, `labels.dependabot_url` posé par le pipeline), comme le faisait
l'envoi direct vers Mattermost. Chaque exécution ne compte que les documents
arrivés depuis la précédente (`excludeHitsFromPreviousRun`) : un passage = une
notification.

| Paramètre               | Valeur |
|-------------------------|--------|
| **Rule name**           | `GitHub - CVE high ou critical ouverte` |
| **Type**                | Elasticsearch query rule (KQL), data view `logs-alertes-github-default` |
| **Requête**             | `vulnerability.severity : ("high" or "critical")` |
| **Fenêtre / fréquence** | 10 min / 5 min |
| **Actions**             | Tchap via le Workflow `tchap-monitoring-securite` : à l'écart des pannes de `monitoring-production` |
| **Dashboards**          | les pages d'alertes Dependabot des 3 repos (liens externes, hors Related dashboards) |

**À vérifier** :
1. Le Discover **[Pass Emploi] Alertes externes - CVE Dependabot** : les CVE
   ouvertes par repo, avec leur score.
2. Les alertes Dependabot du repo concerné, à traiter selon leur sévérité :
   [[GitHub] Alertes Dependabot - pass-emploi-api](https://github.com/France-Travail/pass-emploi-api/security/dependabot),
   [[GitHub] Alertes Dependabot - pass-emploi-web](https://github.com/France-Travail/pass-emploi-web/security/dependabot),
   [[GitHub] Alertes Dependabot - pass-emploi-connect](https://github.com/France-Travail/pass-emploi-connect/security/dependabot).
   Dans le message, ces 3 liens fixes sont remplacés par celui du repo de chaque
   CVE, sur son nom : une règle ne sait pas choisir les liens selon les CVE
   qu'elle liste ; l'Investigation guide, qui ne voit pas les CVE, garde les 3.

## S2a / S2b — Suspicion d'attaque DDoS (Critical)

**Objectif** : désigner l'app attaquée dès les premières minutes, même quand le
log drain et Logstash ont décroché. Le 23/10/2026, 3 IP ont envoyé à connect
27 400 requêtes par minute et 9 800 erreurs 5xx en 5 min, et les logs ont
disparu pendant 25 h ; le même scénario, d'une seule IP, était passé inaperçu le
21/10.

Une règle ES|QL sur les [alertes de métriques Scalingo](alertes-applicatives.md#alertes-de-métriques-scalingo--la-surcharge-sans-les-logs) :
pour chaque app, le dernier événement de ses alertes `Requests per Minute` et
`5xx Errors` ; elle sonne si les deux sont des dépassements, à moins de 10 min
d'intervalle. Fenêtre de 45 min : au-delà du rappel de 30 min des alertes, une
alerte toujours dépassée y garde un événement. Le RPM seul (un pic légitime qui
passe) ne la déclenche pas ; rejouée sur les 30 jours d'octobre 2026 avec les
seuils retenus, elle n'aurait sonné que les 21 et 23/10, sur connect.

| Paramètre               | Valeur |
|-------------------------|--------|
| **Rule name**           | `Scalingo - Prod - Suspicion d'attaque DDoS` (S2a), `Scalingo - Hors-Prod - Suspicion d'attaque DDoS` (S2b) |
| **Type**                | Elasticsearch query rule (ES\|QL), `groupBy: all` |
| **Fenêtre / fréquence** | 45 min / 1 min |
| **Actions**             | Tchap via le Workflow `tchap-monitoring-securite` (S2a) ou `tchap-monitoring-staging` (S2b) |
| **Message**             | une ligne par app : nom, requêtes par minute et 5xx relevés par Scalingo, heure du premier dépassement |

**À vérifier** :
1. Quelle app, depuis quand, et le trafic continue-t-il de monter : ses
   métriques (onglet Metrics) dans le **[Scalingo] Dashboard des apps**.
2. Un événement légitime l'explique-t-il : mise en service, notification de
   masse, campagne de communication.
3. D'où vient le trafic : si les logs du routeur arrivent encore (règle 3b au
   repos), le Discover **[Pass Emploi] Logs de Prod - Trafic du routeur par IP** ;
   sinon, les logs du routeur lus chez Scalingo, sans drain ni Logstash
   (cf. [runbook](../runbooks/investigation-incident.md#suspicion-de-ddos-ou-surcharge-de-linfra)),
   puis le support Scalingo.

**Création** : nouvelles règles, à créer avec `POST` (cf. l'en-tête de leur
bloc dans [`rules/generated/1-rules-securite.console`](rules/generated/1-rules-securite.console)),
après la session Discover
[`discover-session-prod-trafic-routeur-par-ip.ndjson`](discovers/applicatives/discover-session-prod-trafic-routeur-par-ip.ndjson)
et le Workflow [`tchap-monitoring-securite`](workflows/tchap/generated/tchap-monitoring-securite.console).
