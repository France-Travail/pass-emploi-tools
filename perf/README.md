# Tests de performance

Harnais Gatling du chantier perf (démarche et SLO : [`docs/perf/`](../docs/perf/README.md)).

## Simulations

| Simulation                               | Cible                   | Description                                                       |
| ---------------------------------------- | ----------------------- | ----------------------------------------------------------------- |
| `LoginEtAccueilFranceTravailSimulation`  | connect + pass-emploi-api | **Bout en bout** : login FT réel puis page d'accueil jeune      |
| `AccueilFranceTravailSimulation`         | pass-emploi-api         | Page d'accueil jeune seule, avec un JWT fourni à la main          |
| `LogstashIngestSimulation`               | Logstash                | Non-régression du pipeline d'ingestion (CI : `logstash-perf.yml`) |

## Le workflow accueil FT, étape par étape

Seules les dépendances **hors de notre contrôle** sont mockées. `connect` et
`api` sont réels : ce sont eux qu'on mesure.

```
Gatling ──► connect-perf ──► mock-externes   (IdP France Travail)
         └► api-perf ──────► mock-externes   (APIs partenaires FT)
                          ├► connect-perf    (validation du JWT — le vrai)
                          └► PostgreSQL      (vraies données)
```

1. **Login** — Gatling passe par `connect`, qui délègue à l'IdP mocké et
   récupère un `sub` tiré dans le pool. `connect` prend nom/prénom/email via
   `/peconnect-coordonnees` (pas via le `userinfo`), puis enregistre
   l'utilisateur auprès de l'API et émet le JWT.
2. **Validation du JWT** — l'API vérifie la signature contre le JWKS de
   `connect`, découvert via `OIDC_ISSUER_URL` et mis en cache après le 1er appel.
3. **Autorisation** — le jeune `idJeune` doit exister en **base** : aucune
   auto-création pour un bénéficiaire FT, un jeune inconnu fait échouer le login.
4. **Token exchange** — l'API échange le JWT du jeune contre un token IDP
   France Travail auprès de `connect`.
5. **Fan-out parallèle** — 3 appels France Travail mockés (démarches,
   prestations, rendez-vous agenda) + 3 lectures en base réelles (alertes,
   favoris, campagne).
6. **Agrégation** — compteurs de la semaine, prochain rendez-vous, réponse JSON.

## Prérequis pour tirer

1. **Un environnement cible dédié** — ne JAMAIS tirer sur la production.
2. **`mock-externes` lancé**, avec `connect` et l'API branchés dessus : voir
   [`mock-externes/README.md`](./mock-externes/README.md) pour les variables des
   deux côtés.
3. **Les jeunes du pool semés en base** : voir [`seed/README.md`](./seed/README.md).
   Le marqueur d'environnement se pose une fois, à la main ; le seed se rejoue
   avant chaque tir. `pool_prefix` et `pool_size` doivent valoir exactement
   `POOL_PREFIX` et `POOL_SIZE` du mock.

> **Pas d'environnement Scalingo dédié pour l'instant ?** `make start` fait
> tourner tout ce qui précède en local (`connect`/`api` natifs contre
> `mock-externes`) — voir [`local-run/README.md`](./local-run/README.md).
> Valide le parcours, pas les SLO.

## Le login, étape par étape

`LoginEtAccueilFranceTravailSimulation` suit la chaîne de redirections **à la
main**, sans `followRedirect`. Deux raisons : la redirection finale vise le
schéma d'URL du client mobile, que Gatling ne sait pas suivre ; et le découpage
donne un **temps de réponse par étape**, qui est la matière du SLO I2.

| Étape | Qui répond | Ce qui s'y passe |
|---|---|---|
| 01 authorize | connect | `kc_idp_hint=pe-jeune` → structure `POLE_EMPLOI` |
| 02 interaction | connect | `/francetravail-jeune/connect/{uid}?type=cej` |
| 03 authorize | mock IDP | le mock **tire une identité** dans le pool |
| 04 callback IDP | connect | token exchange, userinfo, coordonnées, `PUT /auth/users` |
| 05 reprise interaction | connect | reprise de l'interaction oidc-provider |
| 06 token | connect | échange du code contre le JWT |
| 07 accueil FT | api | la page mesurée |

L'étape 04 est la plus coûteuse, et **c'est elle qui échoue si le pool n'est pas
semé** : l'API ne crée aucun bénéficiaire France Travail inconnu.

Gatling ne choisit pas l'identité du jeune — le mock l'a tirée au sort. Il la lit
dans le claim `userId` du token, celui-là même que l'API lit pour autoriser
l'appel.

> **État d'avancement.** Lots 1 à 3 en place et **joués de bout en bout** le
> 2026-09-03, contre un `connect` et une `api` réels en local
> ([`local-run/`](./local-run/README.md)) : les 7 étapes passent, 0 % d'échec.
> La chaîne fait bien **7 sauts**, comme la spec le supposait — aucun écart sur
> le nombre de redirections.
>
> Ce que ce tir **ne** valide **pas** : les SLO. Machine locale, mock en local,
> pas d'APM — les temps mesurés (p95 de l'accueil à 136 ms à 1 utilisateur) ne
> disent rien de la tenue en charge. Il faut les environnements Scalingo dédiés
> (spec §9). Voir
> [`docs/superpowers/specs/2026-09-01-harnais-tir-perf-design.md`](../docs/superpowers/specs/2026-09-01-harnais-tir-perf-design.md).

## Setup

> JDK version 11+
> Scala version 2.13

## Run locally

```sh
make loginFT        # tir de bout en bout : login FT réel puis accueil
make accueilFT      # accueil seul, avec un JWT fourni à la main
make report         # sert le dernier rapport HTML sur http://localhost:8123
```

Le Makefile source `.env` à chaque lancement — pas de `source .env` à faire
(ni à oublier) : modifier le fichier suffit. Le premier lancement crée `.env`
depuis `.env.template` ; le renseigner puis relancer.

Autres cibles :

```sh
make run SIMULATION=passemploi.test.AccueilFranceTravailSimulation   # une autre simulation
make compile                                               # compilation seule
```

## Tirer depuis Scalingo

`gatling-perf` héberge l'injecteur : les tirs y sont des conteneurs one-off
(`scalingo run`), pas un process permanent — voir `Procfile` pour pourquoi le
type `web` déclaré ne sert qu'à satisfaire le boot initial de Scalingo.

```sh
make deployer                               # ⚠️ après toute modification de perf/
make tir                                    # login FT réel puis accueil, USERS_PER_SEC=10
make tir USERS_PER_SEC=20 RAMP_DURATION_IN_SECONDS=120
make tir TIR_SIMULATION=passemploi.test.AccueilFranceTravailSimulation
```

> ⚠️ **L'injecteur tourne sur son slug déployé, pas sur tes fichiers locaux**,
> et le déploiement automatique est désactivé sur l'app. Sans `make deployer`,
> un tir mesure la simulation du dernier déploiement — silencieusement, sans
> aucune erreur. Le workflow CI, lui, déploie la branche courante avant chaque
> tir.

> ⚠️ **`pool_size ≥ 5 × USERS_PER_SEC`** côté seed (`perf/seed/README.md`) : à
> pool trop petit devant la charge, les mêmes bénéficiaires restent chauds en
> cache PostgreSQL et le tir mesure le cache plutôt que l'application. Avec le
> pool par défaut (`pool_size=200`), rester sous `USERS_PER_SEC=40`.
>
> Le facteur 5 se comptait en utilisateurs *concurrents*, qui ne sont plus un
> paramètre en modèle ouvert : on les majore par le débit, ce qui suppose un
> parcours d'au plus une seconde. Si le parcours s'allonge, recalculer sur la
> concurrence observée au tir précédent.

Le système de fichiers d'un one-off est éphémère : ce qui compte pour un tir
manuel est le résumé écrit sur la console pendant l'exécution (requêtes, p95,
taux d'erreur). Pour récupérer le rapport HTML malgré tout, voir
`RAPPORT_STDOUT` plus bas.

## Tirer depuis la CI

`Actions → Perf - Tir API → Run workflow`. Le workflow réveille les apps,
déploie l'injecteur depuis la branche courante, sème le pool, tire et archive.

| Input | Défaut | Ce qu'il change |
|---|---|---|
| `users_per_sec` | `10` | Refusé si `POOL_SIZE < 5 × users_per_sec` |
| `taille_apps` | `M` | Taille de `connect`/`api`/`mock-externes` pendant le tir (sans effet sur `logstash-perf`) |
| `p99_threshold_ms` / `success_percent_threshold` | `500` / `99.5` | Les deux SLO assertés |
| `arret_apres_tir` | `false` | Rescale les apps à 0 en fin de tir |

**Pourquoi dimensionner l'injecteur** (`TAILLE_INJECTEUR`, `XL` par défaut,
distinct de `taille_apps`) : Gatling consomme lui-même du CPU/RAM en générant
la charge — connexions HTTP ouvertes, parsing des réponses, calcul des stats.
Un injecteur sous-dimensionné devient le facteur limitant du tir : on croit
mesurer l'API, on mesure en fait la JVM de l'injecteur qui sature avant elle.
En modèle ouvert, ce risque est plus concret qu'en fermé : sous saturation de
la cible, Gatling continue de créer des utilisateurs en attente au lieu de
ralentir de lui-même, ce qui grossit sa propre mémoire (d'où le `maxDuration`
posé dans les simulations).

**Le tir est résumé dans l'onglet Actions**, en haut de la page du run
(`$GITHUB_STEP_SUMMARY`) : paramètres, verdict, p95 de la requête assertée,
étape la plus lente, étapes en KO, détail par étape et taille des conteneurs —
pas besoin de télécharger quoi que ce soit pour lire un résultat. Le rendu est
fait par [`resume-tir.py`](./resume-tir.py), rejouable sur un artefact
téléchargé :

```sh
python3 resume-tir.py metadonnees.json sortie-tir.txt perf/build/reports/gatling
```

`metadonnees.json` est le **fichier structuré du tir**, et le seul candidat à un
journal versionné : outre les paramètres, il porte le contexte d'infra que le
workflow ne pilote pas — taille et statut des conteneurs, SHA déployé de chaque
app, plans des addons, taille de l'injecteur — extraits de la sortie brute du
CLI Scalingo par [`infra_tir.py`](./infra_tir.py). Sans eux, un résultat archivé
n'est pas comparable à un autre.

> **La taille des apps est pilotée par le tir** (input `taille_apps`, défaut
> `M`) : le workflow réveille `connect`/`api`/`mock-externes` avec
> `scale web:1:<taille>`, donc chaque tir fixe explicitement sur quoi il mesure
> — plus de dépendance au dernier réglage laissé par quelqu'un. `logstash-perf`
> est volontairement exclu : sa taille répond à son propre test de charge
> (`logstash-perf.yml`), pas au SLO applicatif mesuré ici. Le `--size` du
> `make tir`, lui, ne concerne que le conteneur one-off de l'**injecteur** —
> voir « Pourquoi dimensionner l'injecteur » ci-dessous.
 Pour le détail (console complète, état des apps
Scalingo, métadonnées), l'artefact `tir-<run_id>` (conservé 90 jours) contient
trois fichiers texte bruts, à ouvrir avec n'importe quel éditeur — ce ne sont
pas des rapports formatés, juste la sortie des commandes.

**Rapport HTML Gatling** (graphiques interactifs, détail par requête) : présent
dans l'artefact. Décompresser le zip, puis ouvrir
`perf/build/reports/gatling/<horodatage>/index.html` — c'est un rapport avec
ses dossiers `style/` et `js/` à côté, pas un fichier autonome.

Il traverse **stdout du conteneur one-off** en base64
(`tir-et-rapport.sh` + `scalingo run --silent`), parce qu'un one-off n'est ni
routé en HTTP ni persistant : sa sortie standard est le seul canal. Le
workflow le rétablit en arborescence après le tir. Un tir manuel n'émet rien
par défaut (`RAPPORT_STDOUT=0`), pour garder un terminal lisible :

```sh
make tir RAPPORT_STDOUT=1 > tir.b64        # rapatrier le rapport à la main
sed -n '/---RAPPORT-GATLING-DEBUT---/,/---RAPPORT-GATLING-FIN---/p' tir.b64 \
  | sed '1d;$d' | base64 -d | tar xz -C build/reports
```

> Le workflow **ne restaure aucune image de base** : la base ne contient que le
> pool semé. Les chiffres valident la chaîne, pas un p95 de production.

## Run with docker

### Build

```sh
docker build -t gatling .
```

### Run a simulation

```sh
docker run gatling passemploi.test.AccueilFranceTravailSimulation
```
