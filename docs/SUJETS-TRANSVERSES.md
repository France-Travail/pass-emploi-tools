# Index des sujets transverses

> **Routeur** des gros sujets transverses durables de Pass Emploi. Toujours chargé
> (importé par `CONTEXTE-TRANSVERSE.md`) pour qu'on **sache** quels sujets existent
> et où est leur doc, sans charger tout le détail. On n'ouvre la référence d'un
> sujet que lorsqu'il devient actif (ou que son invariant l'exige).
>
> Chaque entrée = **invariant** (garde-fou minimal) + **référence stable** (doc
> versionnée). Ne lister ici que du **versionné** — pas de pointeur vers des notes
> personnelles. Tenue à jour : voir [CONVENTIONS-DOC.md](./CONVENTIONS-DOC.md).

## Logs ECS · durable, en prod (v9.37.x)

- **Invariant** : tout log passe par le `rootLogger` au format ECS (`event.action`
  au passé + `event.outcome`). Logs opérationnels en `level` info|error (pas de
  `warn`) ; `debug` en plus, opt-in via `LOG_LEVEL`. Jamais de `console.log`.
  Charger le détail **avant** d'ajouter ou modifier un log.
- **Référence stable** : [`pass-emploi-tools/docs/logs-ecs/`](./logs-ecs/README.md)
  (conventions, infra ES, use cases Kibana, couverture api).

## Ingestion des logs · résilience & scaling (blackouts, drain) · 2026-07

- **Invariant** : le log-drain Scalingo **quarantine une app 5 min** dès **10 lignes
  consécutives** refusées (escalade 10/15/20 min) → un hoquet Logstash = blackout de
  la plus grosse app (`pass-emploi-api`). Conteneur XL Scalingo = **2 Go** → `-Xmx`
  ≤ ~1 Go, piloté via `JAVA_OPTS` (jamais `LS_JAVA_OPTS`, écrasé par le buildpack).
  Charger la référence **avant** de scaler ou retoucher la chaîne d'ingestion.
- **Référence stable** : [`pass-emploi-tools/docs/blackout-logs/`](./blackout-logs/README.md)
  (2 modes de panne, garde-fous JVM/Scalingo, playbook de diagnostic, next steps x10).

## App Jeune · WIP, ouvert le 2026-07-02

- **Invariant** : raisonner l'élargissement des publics de la future app jeune
  sur **3 couches distinctes** — public fonctionnel / mode d'authentification /
  représentation API — sans les confondre (piège historique de `Core.Structure`).
  Rappel structurant : côté FT, le mode d'authent est **unique** (FT Connect), la
  structure est décidée par la **porte d'entrée** au login, pas par l'IDP.
- **Invariant invité** : l'invité est un utilisateur **authentifié à identité
  pseudonyme** (JWT, structure `INVITE`, table `jeune_invite`), pas un appelant
  anonyme. Son accès est **fermé par défaut** : l'autorisation « jeune »
  standard le rejette, chaque route doit être ouverte explicitement. Charger la
  référence **avant** d'exposer une fonctionnalité à l'invité.
- **Invariant plan d'action** : le plan de fin d'onboarding est produit par un
  **service externe au stade POC**, hors SLA, exposé via un **proxy** dans
  `pass-emploi-api` — dont la raison d'être est d'absorber les évolutions du
  POC **sans livraison mobile**. Rien n'est persisté côté API.
- **Référence stable** : [`pass-emploi-tools/docs/app-jeune/`](./app-jeune/README.md)
  (routeur + cadre 3 couches ; sous-chantiers utilisateurs/authentification —
  mode invité livré —, parcours & fonctionnalités, et plan d'action).

## Performances · WIP, ouvert le 2026-07-06

- **Invariant** : aucune fonctionnalité exposée à un pic prévisible (MES,
  communication massive, notification push de masse) sans **SLO défini** et
  **scénario de charge identifié**. Les tirs de perf se jugent contre ces SLO
  et une baseline mesurée — jamais « au feeling ».
- **Référence stable** : [`pass-emploi-tools/docs/perf/`](./perf/README.md)
  (démarche en 6 phases, principes structurants, sous-chantiers : SLO/trafic,
  partenaires, harnais de tir, mode dégradé/runbooks, plan Scalingo).
