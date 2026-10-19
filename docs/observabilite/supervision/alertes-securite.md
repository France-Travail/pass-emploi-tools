# Alertes de sécurité

Les alertes sur les **vulnérabilités des dépendances** de nos repos : les CVE
remontées par Dependabot, que le workflow GitHub Actions
[`security-alerts.yml`](../../../.github/workflows/security-alerts.yml) envoie
dans `logs-alertes-github-default` (cf.
[collecte des événements externes](../collecte/evenements-externes/README.md)).
Elles signalent un risque à traiter, pas une panne.

## Récapitulatif

| #  | Signal                    | Data stream                   | Condition                                 | Fréquence | Throttle | Sévérité    |
|----|---------------------------|-------------------------------|-------------------------------------------|-----------|----------|-------------|
| V1 | CVE high/critical ouverte | `logs-alertes-github-default` | `vulnerability.severity` high ou critical | 5 min     | —        | 🚨 Critical |

**Création** : rejouer [`rules/3-rules-securite.console`](rules/3-rules-securite.console)
dans Dev Tools, après les sessions Discover de
[`discovers/evenements-externes/`](discovers/evenements-externes/).

## V1 — CVE high ou critical ouverte (Critical)

**Objectif** : qu'aucune CVE high ou critical ne reste ouverte sans être vue.

`security-alerts.yml` renvoie **à chaque passage** toutes les CVE encore
ouvertes : V1 les notifie donc à chaque passage, une ligne par CVE (repo, CVE,
paquet, sévérité, résumé, lien vers l'alerte Dependabot), comme le faisait
l'envoi direct vers Mattermost. Chaque exécution ne compte que les documents
arrivés depuis la précédente (`excludeHitsFromPreviousRun`) : un passage = une
notification.

| Paramètre               | Valeur |
|-------------------------|--------|
| **Rule name**           | `GitHub - CVE high ou critical ouverte` |
| **Type**                | Elasticsearch query rule (KQL), data view `logs-alertes-github-default` |
| **Requête**             | `vulnerability.severity : ("high" or "critical")` |
| **Fenêtre / fréquence** | 10 min / 5 min |
| **Actions**             | Mattermost-monitoring-production ; Tchap via le Workflow `tchap-monitoring-production` |
| **Dashboards**          | les pages d'alertes Dependabot des 3 repos (liens externes, hors Related dashboards) |

**À vérifier** :
1. Le Discover **[Pass Emploi] Alertes externes - CVE Dependabot** : les CVE
   ouvertes par repo, avec leur score.
2. Les alertes Dependabot du repo concerné, à traiter selon leur sévérité :
   [[GitHub] Alertes Dependabot - pass-emploi-api](https://github.com/France-Travail/pass-emploi-api/security/dependabot),
   [[GitHub] Alertes Dependabot - pass-emploi-web](https://github.com/France-Travail/pass-emploi-web/security/dependabot),
   [[GitHub] Alertes Dependabot - pass-emploi-connect](https://github.com/France-Travail/pass-emploi-connect/security/dependabot).
   Dans le message, chaque CVE renvoie en plus à sa propre alerte.

> **Pendant la migration** : `security-alerts.yml` garde son envoi direct vers
> Mattermost tant que son envoi vers Elasticsearch n'est pas en place (cf.
> [mise en service](../collecte/evenements-externes/README.md#mise-en-service),
> étape GitHub Actions).
