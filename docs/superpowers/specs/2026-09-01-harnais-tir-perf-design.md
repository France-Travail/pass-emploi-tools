# Harnais de tir de performance — design

> **Statut : design validé, non implémenté.** Rédigé le 2026-09-01.
> Sous-chantier « Harnais de tir (env, jeu de données, outillage) » du chantier
> [Performances](../../perf/README.md).
>
> Artefact de travail : il guide l'implémentation et n'a pas vocation à durer.
> Le livrable d'équipe est `docs/perf/harnais.md` (lot 5).

## 1. Problème

Le harnais actuel (`perf/`) ne permet pas de rejouer un tir. Trois blocages :

1. **Le tir exige un JWT collé à la main.** `perf/api-simulator/app.py` embarque
   en dur les clés publiques d'un environnement réel ; le `USER_TOKEN` doit être
   un JWT non expiré émis par cet environnement. Chaque tir commence donc par une
   manipulation humaine, et le token meurt en quelques minutes.
2. **Le tir est mono-utilisateur.** Tous les utilisateurs virtuels partagent une
   identité : même ligne PostgreSQL chaude, mêmes caches. Le chemin mesuré est
   anormalement favorable.
3. **Le mock a mangé `pass-emploi-connect`.** En se substituant à
   `OIDC_ISSUER_URL`, le simulateur sort `connect` du périmètre mesuré — alors
   que le login est le scénario le plus risqué du jour J (SLO I2).

Objectif : un tir **rejouable sans intervention humaine**, sur un environnement
**réinitialisable**, mesurant `connect` et `api` réels.

## 2. Décisions structurantes

| # | Décision | Raison |
|---|---|---|
| D1 | Environnement de perf **dédié** sur Scalingo (`api-perf`, `connect-perf`, PostgreSQL, Redis), plus pipeline de logs et APM dédiés | Autorise le reset destructif, isole la mesure |
| D2 | Le mock ne couvre **que ce qui est hors de notre contrôle** : IdP France Travail et APIs partenaires | `connect` et `api` doivent rester réels ; cette frontière ne bouge pas quand le code change |
| D3 | Jeu de données **hybride** : image de base figée + seed idempotent des acteurs du tir | Le `pg_restore` gouverne la vitesse d'itération ; le seed est rapide |
| D4 | Volumétrie **calibrée sur des agrégats de production** (via Metabase) | Un seed sous-dimensionné donne des tirs verts et une MES rouge |
| D5 | Le **mock choisit l'identité**, tirée au hasard dans un pool de taille N | `connect` ne passe aucun paramètre client à l'IdP (cf. §5.3) |
| D6 | GitHub Actions **orchestre** ; l'injecteur est au choix runner hébergé ou one-off Scalingo | Un runner mutualisé ajoute du jitter sur le p95, qui est ce qu'on asserte |
| D7 | Scénario v1 : **login FT + accueil FT**, chemin complet | C'est le parcours métier qui charge réellement la base |

## 3. Architecture

```
   GitHub Actions (orchestrateur unique)
   │
   ├─ 1. garde-fou anti-prod
   ├─ 2. restore image de base ──┐
   ├─ 3. seed du tir ────────────┤
   ├─ 4. tir  ──► injecteur ─────┤     (runner hébergé OU one-off Scalingo)
   ├─ 5. verdict vs SLO          │
   └─ 6. archivage du rapport    │
                                 ▼
            ┌──────────── projet Scalingo « perf » ────────────┐
            │                                                  │
   Gatling ─┼─► connect-perf ──► mock-externes  (4 endpoints IdP FT)
            │       │                  ▲
            │       ▼                  │
            └──► api-perf ─────────────┘  (APIs partenaires FT)
                    │
                    ├─► PostgreSQL-perf   ← image de base + seed
                    ├─► Redis-perf
                    └─► logstash-perf ──► ES (index perf) + APM-perf
```

| Composant | Responsabilité | État |
|---|---|---|
| `mock-externes` | IdP FT (4 endpoints) + APIs partenaires FT | Existe sous le nom `api-simulator`, à recentrer et renommer |
| Jeu de données | Image de base versionnée + seed idempotent | À créer |
| Simulation Gatling | Login via `connect` puis accueil FT, N identités | À reprendre |
| Workflow | Enchaîne les 6 étapes, porte garde-fou et verdict | À créer |

## 4. `mock-externes`

### 4.1 Contrat IdP

`connect` ne fait **aucun discovery** sur ses IdP : il construit la configuration
du client à partir d'URLs plates fournies par l'environnement
(`pass-emploi-connect/src/idp/service/helpers.ts`, `createIdpIssuerConfig`).
Le contrat se réduit à quatre endpoints :

| Variable `connect` | Comportement attendu |
|---|---|
| `IDP_FT_JEUNE_AUTHORIZATION_URL` | Redirige vers `redirectUri` avec `?code=…&state=…`, sans page de login |
| `IDP_FT_JEUNE_TOKEN_URL` | `access_token` + `id_token` signé + `refresh_token` ; grants `authorization_code` et `refresh_token`, auth `client_secret_post` |
| `IDP_FT_JEUNE_JWKS` | Clés publiques validant l'`id_token` |
| `IDP_FT_JEUNE_USERINFO` | Les claims dont `connect` fabrique l'utilisateur — dont `sub` |

Aucune ligne de code à modifier dans `connect` ni dans `api` : uniquement de la
configuration.

### 4.2 Signature et clés

Le mock **génère sa propre paire de clés au démarrage** et publie la clé publique
sur son endpoint `jwks`. C'est lui qui signe l'`id_token`, que `openid-client`
vérifie côté `connect`.

Conséquence directe : les clés d'un environnement réel codées en dur disparaissent,
et avec elles le JWT à renouveler à la main. C'est ce qui débloque la rejouabilité.

### 4.3 APIs partenaires

Conservées telles quelles (démarches, prestations, rendez-vous agenda). À
instruire : `FrancetravailBeneficiaireService.resoudreStructureNonAccompagne`
appelle `francetravailapi.getStatut(accessToken)` — appel externe supplémentaire
dans le chemin de login, à servir par le mock s'il est déclenché dans notre cas.

### 4.4 Remise en place de `connect`

`OIDC_ISSUER_URL` de `api-perf` repointe sur `connect-perf`, qui expose déjà
`/protocol/openid-connect/certs` et `/protocol/openid-connect/token`
(`pass-emploi-connect/src/oidc-provider/oidc.service.ts:131-137`) — les deux
routes que le mock usurpait.

## 5. Jeu de données et identités

### 5.1 Deux couches

| Couche | Contenu | Rythme |
|---|---|---|
| Image de base | Fond de charge : volumétrie et distributions des grosses tables | Entre deux campagnes |
| Seed du tir | Les N jeunes du pool, leurs conseillers, actions, favoris, RDV | Avant chaque tir, idempotent |

Règle : **restore d'image = début de campagne ; seed = début de tir.** Un
`pg_restore` se compte en minutes et tuerait la boucle « tir → mitigation → re-tir ».

### 5.2 Calibration (lot 0)

Livrable : `docs/perf/volumetrie-prod.md`, **daté**, ne contenant que des agrégats
— percentiles de taille de portefeuille, d'actions / démarches / favoris / RDV par
jeune, volumétrie des grosses tables, part d'actifs, répartition par structure.
Aucune ligne de données, donc aucun sujet RGPD.

Source : **Metabase** (`stats.pass-emploi.beta.gouv.fr`). `pass-emploi-analytics`
ne convient pas — il calcule des taux de pénétration à partir de sources externes
et ne touche pas les données applicatives.

### 5.3 Pool d'identités

`connect` n'envoie à l'IdP que `nonce`, `scope`, `state` et éventuellement `realm`
(`idp.service.ts:100-110`). **Ni `login_hint`, ni passe-plat des paramètres
client** : Gatling ne peut donc pas désigner l'identité sans modifier `connect`,
ce qu'on refuse. C'est le mock qui choisit.

Trois pièces reliées par une **convention**, pas par un fichier partagé :

1. Un pool de `N` identités déterministes, dérivées d'un motif stable.
2. Le **seed** crée les jeunes correspondants, avec `idAuthentification` égal au
   `sub` du pool.
3. Le **mock** tire une identité au hasard dans le pool à chaque autorisation et
   la porte jusqu'au `userinfo`.

Le tirage aléatoire plutôt qu'un round-robin est délibéré : le mock tourne en
plusieurs workers, un compteur partagé serait un point de synchronisation. Sans
état, donc worker-safe — et une distribution inégale est plus réaliste qu'une
rotation parfaite.

Seuls `N` et le motif sont partagés, par variable d'environnement.

### 5.4 Le seed est un prérequis dur

Pour un bénéficiaire FT
(`pass-emploi-api/src/application/commands/update-utilisateur.command.handler.ts:417-443`) :

```
getJeuneByIdAuthentification(sub) ──trouvé──► login OK
        │ non trouvé
getJeuneByEmail(email)            ──trouvé──► login OK
        │ non trouvé
NonTraitableError(UTILISATEUR_INEXISTANT)     login refusé
```

**Aucune auto-création.** Un jeune absent de la base fait échouer le login : le
seed conditionne le tir.

Le parcours **non accompagné** (`FT_DEMANDEUR_D_EMPLOI`, `FT_ESPACE_CANDIDAT`)
emprunte une autre branche, avec sa propre logique de création. Hors v1.

### 5.5 Idempotence et garde-fou

Le seed doit pouvoir tourner deux fois sans diverger : périmètre identifiable
(entités du pool, préfixées), suppression puis recréation, jamais d'`INSERT`
accumulatif.

Étant destructeur, il porte le **garde-fou anti-prod** : refus de démarrer si
l'URL de base ne porte pas le marqueur d'environnement de perf.

## 6. Simulation Gatling

Scénario v1, chemin complet :

1. Login via `connect-perf` (redirection vers `mock-externes`, callback, JWT).
2. `GET /jeunes/:idJeune/pole-emploi/accueil?maintenant=<ISO8601>` avec ce JWT.

Modèle fermé : montée vers `MAX_USERS` puis palier. Assertions conservées de
l'existant : p95 < `P95_THRESHOLD_MS` (SLO I3) et échecs < `FAILED_PERCENT_THRESHOLD`
(SLO I1), cf. `docs/perf/observabilite.md`.

L'`idJeune` n'est plus une constante : il provient du JWT obtenu au login, donc de
l'identité tirée par le mock.

## 7. Orchestration et verdict

### 7.1 Un workflow, deux régimes

`perf-api.yml`, en `workflow_dispatch`, avec un paramètre `injecteur` valant
`runner` ou `scalingo`. Même code, même seed, même verdict — seul l'endroit
d'exécution change. Deux chemins distincts divergeraient, et celui qu'on utilise
le moins pourrirait.

Paramètres : profil de charge, seuils SLO, taille du pool, `injecteur`,
`restore-image`.

Déclencheurs : `workflow_dispatch` pour le tir. Sur PR touchant `perf/**`,
**pas de tir** (destructeur, monopolise l'environnement) mais `make compile`, pour
ne pas découvrir une simulation cassée le jour où on en a besoin.

L'image de l'injecteur réutilise `perf/Dockerfile` et `perf/entrypoint.sh`.

### 7.2 Corrélation avec l'observabilité

Pas de `run_id` applicatif. L'environnement étant dédié, **tout le trafic sur
`api-perf` pendant la fenêtre du tir est le tir** : le workflow enregistre
`debut`/`fin`, ce qui suffit à isoler dans les logs et l'APM. C'est le motif déjà
employé par `logstash-perf.yml`, et il ne coûte aucune ligne de code applicatif.

Limite assumée : deux scénarios tirés en parallèle sur le même environnement ne
seraient plus séparables. Problème à traiter quand il se posera.

### 7.3 Métadonnées archivées

Rapport Gatling et métadonnées en **artefacts GitHub**.

| Métadonnée | Pourquoi |
|---|---|
| Profil de charge et seuils | Deux tirs à profils différents ne se comparent pas |
| Version d'image de base et de seed | Un gain peut venir des données |
| SHA `api` / `connect` déployés | Ce qu'on mesure réellement |
| Plans Scalingo des apps et addons | Le gain le plus facile à confondre avec une optimisation |
| Fenêtre temporelle | Point d'entrée dans logs et APM |
| Verdict et p95 mesuré | La ligne à comparer |

Les artefacts GitHub **expirent** (90 jours par défaut). Suffisant en campagne
active ; insuffisant pour comparer la MES à une baseline ancienne. Piste ouverte,
ajoutable sans redécoupage : un journal versionné `docs/perf/journal-des-tirs.md`,
une ligne par tir.

## 8. Lots

```
Lot 0  Volumétrie prod (agrégats Metabase, note datée)
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
Lot 1  mock-externes   Lot 2  Données
       • renommage            • image de base
       • 4 endpoints IdP      • seed idempotent
       • clés au boot         • garde-fou anti-prod
       • tirage dans le pool
        └─────────┬─────────┘
                  ▼
Lot 3  Simulation login + accueil FT via connect
                  ▼
Lot 4  Workflow d'orchestration (2 régimes)
                  ▼
Lot 5  docs/perf/harnais.md
```

Le lot 0 conditionne le lot 2 : écrire le seed sans les distributions, c'est
fabriquer des chiffres à refaire. Les lots 1 et 2 sont parallélisables ensuite.

**Premier jalon de valeur : la fin du lot 3** — un tir manuel, complet,
reproductible. Le lot 4 automatise quelque chose qui marche déjà ; l'inverse
oblige à déboguer le workflow et le scénario en même temps.

## 9. Prérequis hors harnais

- **Apps et addons Scalingo** — préalable à tout tir.
- **Dimensionnement de `logstash-perf`** — à vérifier avant le premier tir
  sérieux : le débit de logs d'une API sous charge n'a rien à voir avec les
  200 logs/s du test de non-régression Logstash, et un blackout du drain
  (cf. `docs/blackout-logs/`) donne un tir aveugle. Vérification, pas développement.
- **APM dédiée** — à provisionner avec les apps.

## 10. Points à lever à l'implémentation

1. `getStatut` est-il déclenché dans le parcours accompagné ? Si oui, le mock doit
   le servir (§4.3).
2. Motif exact des `sub` du pool et colonne cible côté seed.
3. Mécanique de restore retenue sur Scalingo, et durée mesurée d'un `pg_restore`
   de l'image de base — elle fixe le rythme des campagnes.
4. Marqueur d'environnement retenu pour le garde-fou anti-prod.

## 11. Hors périmètre v1

Web conseiller, jobs et crons, notification push massive, IdP MILO et Conseil
Départemental, parcours FT non accompagné, mode invité. Tous sont de vrais
scénarios de charge ; l'architecture les accueille sans redécoupage.

## 12. Références

- `docs/perf/README.md` — démarche du chantier, principes
- `docs/perf/observabilite.md` — SLI/SLO I1-I5
- `docs/blackout-logs/` — garde-fous d'ingestion
- `.github/workflows/logstash-perf.yml` — motif d'orchestration réutilisé
