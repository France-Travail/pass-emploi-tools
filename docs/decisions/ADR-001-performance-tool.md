# Choix de l'outil de tests de performance

* Statut: accepté
* Décideurs: équipe pass-emploi
* Date: 2026-07-28

## Contexte et Définition du Problème

Le projet a besoin d'un outil de tests de performance pour valider que la tenue en charge de l'architecture.
Quel outil choisir parmi les solutions du marché, sachant que Gatling est déjà présent dans le projet et que la DNUM des 
ministères sociaux recommande K6 ?

## Facteurs de Décision

* **Intégration existante** — Gatling est déjà configuré (Gradle, Dockerfile, CI GitHub Actions) ; migrer a un coût
* **Non-bloquant** — l'outil doit supporter les hauts débits sans modèle thread-based
* **Cohérence base de code** — TypeScript/JavaScript est la stack principale du projet (NestJS)
* **Scénarios complexes** — montée en charge progressive, variété de cas (7 types de logs), assertions p99
* **Intégration CI/CD GitHub Actions** — assertions exploitables en pipeline, pas de serveur externe requis
* **Coût** — outil open-source, sans licence commerciale ni infrastructure dédiée
* **Auditabilité** — code source ouvert, pas de boîte noire
* **Expertise disponible** — autres Octos OCTO Technology ayant utilisé l'outil en mission

## Solutions Étudiées

* Gatling
* K6
* Locust
* autocannon
* Artillery
* JMeter

## Résultat de la Décision

Solution retenue: **Gatling**, car c'est la seule solution déjà intégrée dans le projet (Gradle, Dockerfile, CI), avec
une expertise OCTO disponible, et qui valide tous les facteurs de décision techniques
(non-bloquant, scénarios complexes, assertions CI/CD, open-source gratuit).

### Tableau Comparatif

| Critère                             | Gatling  | K6  | Locust  | autocannon | Artillery  | JMeter  |
|-------------------------------------|----------|-----|---------|------------|------------|---------|
| Déjà dans le projet                 | ✅        | ❌   | ❌       | ❌          | ❌          | ❌       |
| Non-bloquant (haute perf)           | ✅        | ✅   | ✅       | ✅          | ⚠️          | ❌       |
| Cohérent base de code (TS/JS)       | ⚠️        | ✅   | ❌       | ✅          | ✅          | ❌       |
| Scénarios complexes                 | ✅        | ✅   | ✅       | ❌          | ✅          | ✅       |
| Intégration CI/CD GitHub Actions    | ✅        | ✅   | ⚠️       | ❌          | ✅          | ⚠️       |
| Rapports HTML intégrés              | ✅        | ⚠️   | ✅       | ❌          | ⚠️          | ✅       |
| Coût (open-source, sans licence)    | ✅        | ✅   | ✅       | ✅          | ✅          | ✅       |
| Auditabilité (open-source)          | ✅        | ✅   | ✅       | ✅          | ✅          | ✅       |
| Expertise OCTO disponible           | ✅        | ❌   | ✅       | ✅          | ❌          | ⚠️       |
| Recommandé DNUM                     | ❌        | ✅   | ❌       | ❌          | ❌          | ❌       |
| Expérience développeur              | ✅        | ✅   | ✅       | ✅          | ✅          | ❌       |

### Impacts Positifs

* Zéro coût de migration — le pipeline CI et le Dockerfile existants sont réutilisés
* Rapports HTML détaillés générés automatiquement (percentiles, graphes temporels)
* Assertions intégrées (p99, taux d'erreur) exploitables directement en GitHub Actions
* Open-source Apache 2.0 — auditabilité complète, pas de licence commerciale
* Expertise OCTO disponible pour la montée en compétence

### Impacts Négatifs

* Scala — déroutant pour des développeurs TypeScript/JavaScript ; courbe d'apprentissage initiale
* Non recommandé par la DNUM des ministères sociaux (qui recommande K6)

## Avantages et Inconvénients des Solutions

### Gatling

[https://gatling.io](https://gatling.io) — open-source Apache 2.0, Scala/Java, Akka/Netty

* Bien, car déjà intégré dans le projet (Gradle, Dockerfile, CI GitHub Actions)
* Bien, car non-bloquant (Akka/Netty) — supporte les très hauts débits
* Bien, car rapports HTML riches générés automatiquement
* Bien, car assertions CI/CD intégrées (p99, taux d'erreur)
* Bien, car open-source gratuit, pas de licence commerciale
* Bien, car expertise OCTO Technology disponible
* Mauvais, car Scala — pas cohérent avec la stack TypeScript du projet
* Mauvais, car non recommandé par la DNUM

### K6

[https://k6.io](https://k6.io) — open-source AGPL-3.0, JavaScript/TypeScript, Go

* Bien, car recommandé par la DNUM des ministères sociaux
* Bien, car TypeScript — cohérent avec la base de code NestJS
* Bien, car non-bloquant (Go) — haute performance
* Bien, car open-source gratuit (version OSS), pas de licence commerciale
* Bien, car intégration GitHub Actions native
* Mauvais, car non présent dans le projet — migration nécessaire (Dockerfile, CI, Gradle → npm)
* Mauvais, car rapports HTML moins riches sans configuration supplémentaire (Grafana/InfluxDB)
* Mauvais, car pas d'expertise OCTO identifiée sur ce projet

### Locust

[https://locust.io](https://locust.io) — open-source MIT, Python, gevent

* Bien, car open-source gratuit
* Bien, car interface web temps réel intégrée
* Mauvais, car Python — pas cohérent avec la base de code TypeScript/Scala
* Mauvais, car performance inférieure à Gatling et K6 pour les très hauts débits
* Mauvais, car pas d'expertise équipe

### autocannon

[https://github.com/mcollina/autocannon](https://github.com/mcollina/autocannon) — open-source MIT, Node.js/TypeScript, libuv

* Bien, car TypeScript — cohérent avec la base de code
* Bien, car open-source gratuit, très léger
* Bien, car non-bloquant (libuv)
* Mauvais, car outil de **benchmark brut**, pas de test de charge scénarisé
* Mauvais, car pas de DSL pour les scénarios complexes (montée en charge progressive, assertions)
* Mauvais, car pas de rapports HTML — sortie JSON uniquement
* Mauvais, car inadapté pour simuler des comportements variés (7 types de logs différents)

### Artillery

[https://www.artillery.io](https://www.artillery.io) — open-source MPL-2.0, YAML + JavaScript/TypeScript, Node.js

* Bien, car TypeScript — cohérent avec la base de code
* Bien, car scénarios YAML lisibles par des non-développeurs
* Bien, car open-source gratuit (version OSS)
* Mauvais, car performance limitée par Node.js pour les très hauts débits (> 1000 req/s difficile sur une seule machine)
* Mauvais, car YAML + JS = deux langages à maintenir
* Mauvais, car pas d'expertise équipe

### JMeter

[https://jmeter.apache.org](https://jmeter.apache.org) — open-source Apache 2.0, XML + Groovy/Java, threads Java

* Bien, car open-source gratuit
* Bien, car très répandu, documentation abondante
* Mauvais, car configuration XML verbeuse et difficile à versionner/relire
* Mauvais, car modèle thread-based : 1 thread = 1 utilisateur virtuel → RAM élevée pour les hauts débits
* Mauvais, car expérience développeur médiocre (consensus équipe et retours OCTO)
* Mauvais, car inadapté pour une intégration CI/CD moderne

## Liens

* [Recommandation DNUM — Tests de performance](https://dnum-ministeres-sociaux.gitbook.io/ressources/developper/tests-et-strategies/tests-de-performance#outils-sur-le-marche)
* [Simulation Gatling existante](../../perf/src/gatling/scala/passemploi/test/LogstashIngestSimulation.scala)
* [Pipeline CI GitHub Actions](../../.github/workflows/logstash-perf.yml)
