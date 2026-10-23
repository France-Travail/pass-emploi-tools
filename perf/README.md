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

> **Un run local ([`local-run/`](./local-run/README.md)) valide le parcours,
> jamais la tenue en charge** : machine locale, mock en local, pas d'APM. Les
> SLO se jugent sur les environnements Scalingo dédiés.

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

> ⚠️ **`pool_size ≥ nombre d'arrivées du tir`** côté seed
> (`perf/seed/README.md`) : à pool plus petit, les mêmes bénéficiaires sont
> relus pendant toute la fenêtre, restent chauds en cache PostgreSQL, et le tir
> mesure le cache plutôt que l'application. En palier, les arrivées valent
> `(1 + USERS_PER_SEC) × ramp / 2 + USERS_PER_SEC × hold`. Le workflow calcule
> le seuil et refuse de tirer en dessous, en affichant la valeur à poser.

Le système de fichiers d'un one-off est éphémère : ce qui compte pour un tir
manuel est le résumé écrit sur la console pendant l'exécution (requêtes, p95,
taux d'erreur). Pour récupérer le rapport HTML malgré tout, voir
`RAPPORT_STDOUT` plus bas.

## Tirer depuis la CI

`Actions → Perf - Tir API → Run workflow`. Le workflow réveille les apps,
déploie l'injecteur depuis la branche courante, sème le pool, tire et archive.

| Input | Défaut | Ce qu'il change |
|---|---|---|
| `simulation` | `LoginEtAccueilFranceTravailSimulation` | Simulation Gatling jouée |
| `users_per_sec` | `10` | Débit du profil `palier` — refusé si le pool ne couvre pas les arrivées |
| `fond_size` | `0` | Bénéficiaires hors pool, en plus de lui — cf. « Fond de charge » ci-dessous |
| `taille_connect` / `taille_api` / `taille_mock` | `M` chacune | Taille de chaque app pendant le tir (sans effet sur `logstash-perf`) — viser la taille de prod pour un tir représentatif |
| `p99_threshold_ms` / `success_percent_threshold` | `500` / `99.5` | Les deux SLO assertés (profil `palier` uniquement) |
| `arret_apres_tir` | `false` | Rescale les apps à 0 en fin de tir |

**Chercher le point de rupture** : `profil: escalier` (input du workflow ou
`PROFIL=escalier` en local) fait monter le débit par paliers
(`palier_debut`, `palier_pas`, `nb_paliers`, `duree_palier_en_secondes`) au
lieu d'un débit fixe, **sans assertion** — un p99 agrégeant des paliers à des
débits différents ne jugerait rien. Le step *Verdict* le sait et ne cherche pas
d'assertion à lire pour ce profil. La lecture se fait sur le rapport HTML, par
seconde : c'est là qu'on voit à quel palier la latence décroche. Voir l'en-tête
de [`LoginEtAccueilFranceTravailSimulation.scala`](./src/gatling/scala/passemploi/test/LoginEtAccueilFranceTravailSimulation.scala).

**Fond de charge** : sans lui, la table `jeune` fait la taille du pool
(quelques centaines de lignes) au lieu de la taille de prod (≈48 500
bénéficiaires `POLE_EMPLOI` — [`docs/perf/volumetrie-prod.md`](../docs/perf/volumetrie-prod.md)),
et l'index scan, la pression sur le cache buffer et le plan de requête n'ont
alors aucune raison de ressembler à la prod. `fond_size` sème des bénéficiaires
supplémentaires — hors du pool, jamais tirés par `mock-externes` — aux mêmes
distributions par profil (favoris/alertes) que le pool. Ce n'est **pas** un
restore d'un vrai snapshot de prod (mécanique non tranchée, cf.
[`docs/perf/harnais.md`](../docs/perf/harnais.md)) : c'est une approximation de
volume et de pression sur les index, qui coûte quelques secondes à semer.
Détail dans [`perf/seed/fond-de-charge.sql`](./seed/fond-de-charge.sql).

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

> **La taille des apps est pilotée par le tir**, app par app (`taille_connect`,
> `taille_api`, `taille_mock`, défaut `M` chacune) : le workflow réveille
> chaque app avec `scale web:1:<taille>`, donc chaque tir fixe explicitement
> sur quoi il mesure — plus de dépendance au dernier réglage laissé par
> quelqu'un. Une variable par app plutôt qu'une taille commune : rien
> n'oblige `connect` et `api` à partager la même taille en prod, et viser
> l'iso-prod suppose de pouvoir les régler séparément. `mock-externes` n'a pas
> d'équivalent en prod (il remplace l'IdP/API France Travail) ; `logstash-perf`
> est exclu de ce pilotage, sa taille répond à son propre test de charge
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

## Scénario job : archivage de migration

`Actions → Perf - Job archivage de migration → Run workflow`. Le workflow
réveille les apps et le **worker** de l'api, sème le pool puis la population de
migration ([`seed/README.md`](./seed/README.md)), lance l'archivage, attend sa
ligne `suivi_job`, lance le nettoyage, attend la sienne, puis rend un verdict
([`job/verdict_job.py`](./job/verdict_job.py)). Le worker est éteint en fin de
tir, quoi qu'il arrive.

### Avant le tir : semer le Redis de connect, depuis un poste

Le workflow ne sème pas le Redis de `pass-emploi-connect-perf` : il vérifie
seulement que les `2 × taille_population` clés de la population y sont, et
refuse sinon. Le seed écrit un fond de clés `oidc:` au `DBSIZE` de prod
(974 199), plus deux tokens par jeune de la population, avec un TTL de 3 jours :
le semer moins de 3 jours avant le tir. `ioredis` est pris dans un checkout de
`pass-emploi-connect`, d'où le répertoire courant.

Par tunnel (deux terminaux) :

```sh
scalingo --region osc-secnum-fr1 --app pass-emploi-connect-perf db-tunnel SCALINGO_REDIS_URL

cd ../pass-emploi-connect
URL="$(scalingo --region osc-secnum-fr1 --app pass-emploi-connect-perf env-get SCALINGO_REDIS_URL \
       | sed -E 's#@[^/@]+$#@127.0.0.1:10000#')"
node ../pass-emploi-tools/perf/job/redis-connect.cjs semer --url "$URL" \
     --fond 1000000 --longueur 60 --prefixe perf-migr- --taille 2000 --ttl 259200
```

Ou par un one-off, qui lit `REDIS_URL` sur l'app (depuis la racine de ce repo) :

```sh
scalingo --region osc-secnum-fr1 --app pass-emploi-connect-perf run --file perf/job/redis-connect.cjs \
  "node /tmp/uploads/redis-connect.cjs semer --fond 1000000 --longueur 60 --prefixe perf-migr- --taille 2000 --ttl 259200"
```

La commande rend `{"dbsize": …}`. `bilan --prefixe perf-migr-` rend `DBSIZE`,
les clés de la population restantes et le résumé des `KEYS` lus dans le
`SLOWLOG` (128 dernières entrées). Le plan Redis de connect-perf doit tenir
~250 Mo (≥ 512 Mo), et viser celui de la prod pour un coût de `KEYS` fidèle.

**Limite connue** : la longueur des clés de fond (60 caractères) est supposée,
faute de mesure en prod. Le coût du `KEYS` mesuré est donc un ordre de grandeur.

### Config manuelle de `pass-emploi-api-perf`

Le workflow la vérifie et refuse de tirer si elle manque. Il ne la pose jamais.

| Variable | Valeur |
|---|---|
| `SENDINBLUE_API_URL` | `https://mock-externes-perf.osc-secnum-fr1.scalingo.io/brevo` (sinon : vrais mails via Brevo) |
| `CHAT_MOCK_URL` | `https://mock-externes-perf.osc-secnum-fr1.scalingo.io/chat` (sinon : vrai Firestore) |
| `OIDC_ISSUER_API_URL`, `OIDC_API_KEY` | `pass-emploi-connect-perf` et sa clé : c'est lui qui révoque les accès |
| `MATTERMOST_JOBS_WEBHOOK_URL` | absente, sinon les échecs injectés y sont notifiés (avertissement seulement) |

Le process `worker` du Procfile de l'api doit exister : c'est lui qui exécute
les deux chaînes.

### Inputs

| Input | Défaut | Ce qu'il change |
|---|---|---|
| `taille_population` | `2000` | Jeunes archivés, puis nettoyés. Le Redis doit avoir été semé avec la même taille |
| `inactifs_tous_les` / `echec_mail_tous_les` / `echec_chat_tous_les` | `5` / `100` / `100` | Part d'inactifs et d'échecs injectés, portés par les données semées |
| `seuil_archivage_minutes` | `15` | Durée maximale de l'archivage (attente : 3 × le seuil) |
| `timeout_nettoyage_minutes` | `90` | Attente maximale du nettoyage, rapporté sans seuil |
| `bilan_redis` | `true` | Lecture du Redis de connect par un one-off, avant et après le nettoyage |
| `taille_worker` / `nb_worker` | `M` / `1` | Conteneurs worker de l'api |
| `taille_connect` / `nb_connect` / `taille_api` / `taille_mock` | `M` / `1` / `M` / `M` | Comme pour le tir API |
| `arret_apres_tir` | `false` | Rescale les apps web à 0 en fin de tir |

Les latences du mock (`LATENCE_MAIL_MS`, `LATENCE_CHAT_MS`, `MESSAGES_PAR_CHAT`)
se lisent sur `mock-externes-perf`, comme `POOL_SIZE`.

### Lire le résultat

Le résumé du run donne deux tableaux de constats. Archivage : `termine`,
`nbTraites` = population, `nbEchecs` = 0, `nbEchecsMail` = échecs injectés,
durée ≤ seuil, jeunes supprimés, témoins intacts, une archive par jeune.
Nettoyage : `termine`, `nbTraites` = population − échecs chat,
`nbTraites + nbEchecs` = population, `nbEchecsIdp` = 0, `nbEchecsChat` = échecs
injectés, plus aucune clé de la population dans Redis. Suivent la durée des deux
chaînes, le `DBSIZE` et les `KEYS`. L'artefact `job-archivage-<run_id>` garde
les JSON et `metadonnees.json`.

**Durées par lot et latence IdP** : si les secrets `ES_URL` et `ES_API_KEY`
(clé en lecture seule sur `logs-perf-*`) sont posés dans l'environnement
GitHub « Performance », le résumé ajoute les lots par chaîne (nombre, en échec,
p50/p95/max), la latence des `DELETE /accounts` vers connect et les erreurs par
étape, lus par [`job/lire_logs.py`](./job/lire_logs.py). Sans eux, le résumé
donne les trois requêtes ES|QL remplies, à coller dans Kibana.

Le tir ne mesure **ni Firestore ni Brevo** : tous deux sont mockés. La durée du
nettoyage est donc rapportée sans seuil.

| Symptôme | Cause probable |
|---|---|
| `nbEchecsIdp` = population | `OIDC_ISSUER_API_URL` ou `OIDC_API_KEY` faux sur api-perf |
| `nbEchecsIdp` > 0 sans être la population | Timeout de 5 s de l'api dépassé par un `KEYS` lent : regarder les `KEYS` du bilan |
| `nbEchecsMail` = 0 alors que des échecs sont injectés | Le mail avale ses erreurs HTTP côté api |
| `ligne suivi_job` absente | Worker éteint, chaîne plantée, ou chaîne déjà en cours (`chaine deja en cours`) |
| Refus « clés de la population dans le Redis » | Redis non semé, semé avec une autre taille, ou TTL expiré |

## Run with docker

### Build

```sh
docker build -t gatling .
```

### Run a simulation

```sh
docker run gatling passemploi.test.AccueilFranceTravailSimulation
```
