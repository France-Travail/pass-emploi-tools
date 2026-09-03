# Index des sujets transverses

> **Routeur** des gros sujets transverses durables de Pass Emploi. Toujours chargé
> (importé par `CONTEXTE-TRANSVERSE.md`) pour qu'on **sache** quels sujets existent
> et où est leur doc, sans charger tout le détail.
>
> Chaque entrée = **ouvrir quand** (déclencheur de lecture) + **invariant**
> (garde-fou avant d'agir) + **référence stable** (doc versionnée). Ne lister ici
> que du **versionné** — pas de pointeur vers des notes personnelles.
> Tenue à jour : voir [CONVENTIONS-DOC.md](./CONVENTIONS-DOC.md).

## Règle de chargement

1. **Un sujet évoqué suffit.** Ouvrir sa référence dès qu'il est mentionné — une
   **question** *sur* un sujet déclenche la lecture, pas seulement l'intention de
   modifier du code. Les invariants ci-dessous sont formulés « avant d'agir » :
   c'est un plancher, pas la condition unique.
2. **Descendre jusqu'au fichier.** Les références sont des **routeurs** : le
   `README.md` d'un sujet est un index, pas une destination. Aller au fichier
   nommé dans l'entrée.
3. **Sujet absent de cet index = pas de doc d'équipe.** Le dire explicitement
   plutôt que de supposer qu'elle existe ailleurs.

## Logs ECS · durable, en prod (v9.37.x)

- **Ouvrir quand** : on parle de logs, de champs ECS, d'un dashboard Kibana, ou
  qu'on cherche à savoir si un événement est déjà tracé.
- **Invariant** : tout log passe par le `rootLogger` au format ECS (`event.action`
  au passé + `event.outcome`). Logs opérationnels en `level` info|error (pas de
  `warn`) ; `debug` en plus, opt-in via `LOG_LEVEL`. Jamais de `console.log`.
  Charger le détail **avant** d'ajouter ou modifier un log.
- **Référence stable** : [`pass-emploi-tools/docs/logs-ecs/`](./logs-ecs/README.md)
  — `conventions.md` (format et nommage), `infra-elasticsearch.md` (templates, ILM),
  `kibana.md` (use cases), `couverture-api.md` (ce qui est tracé côté api),
  `postmortem-logstash-5xx-2026-06.md`.

## Ingestion des logs · résilience & scaling (blackouts, drain) · 2026-07

- **Ouvrir quand** : des logs manquent ou arrivent en retard, le drain Scalingo ou
  Logstash est suspecté, ou on redimensionne un maillon de la chaîne d'ingestion.
- **Invariant** : le log-drain Scalingo **quarantine une app 5 min** dès **10 lignes
  consécutives** refusées (escalade 10/15/20 min) → un hoquet Logstash = blackout de
  la plus grosse app (`pass-emploi-api`). Conteneur XL Scalingo = **2 Go** → `-Xmx`
  ≤ ~1 Go, piloté via `JAVA_OPTS` (jamais `LS_JAVA_OPTS`, écrasé par le buildpack).
  Charger la référence **avant** de scaler ou retoucher la chaîne d'ingestion.
- **Référence stable** : [`pass-emploi-tools/docs/blackout-logs/`](./blackout-logs/README.md)
  — `conventions.md` (garde-fous JVM/Scalingo, playbook de diagnostic),
  `postmortem-2026-07.md` (les 2 modes de panne observés).

## App Jeune · WIP, ouvert le 2026-07-02

- **Ouvrir quand** : **toute** question touchant la nouvelle app jeune — publics,
  authentification, mode invité, onboarding, plan d'action — y compris les
  questions d'organisation, de planning et de livraison.
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
  — `utilisateurs-authentification.md` (publics, modes d'authent, mode invité livré),
  `parcours-fonctionnalites.md` (parcours d'entrée, pages, matrice profils→accès),
  `plan-action.md` (archi proxy vers le POC).

## Performances · WIP, ouvert le 2026-07-06

- **Ouvrir quand** : on parle de charge, de pic de trafic, de MES, de SLO, de
  temps de réponse, ou de dimensionnement Scalingo.
- **Invariant** : aucune fonctionnalité exposée à un pic prévisible (MES,
  communication massive, notification push de masse) sans **SLO défini** et
  **scénario de charge identifié**. Les tirs de perf se jugent contre ces SLO
  et une baseline mesurée — jamais « au feeling ».
- **Référence stable** : [`pass-emploi-tools/docs/perf/`](./perf/README.md)
  — `README.md` (démarche en 6 phases, principes, sous-chantiers : SLO/trafic,
  partenaires, harnais de tir, mode dégradé/runbooks, plan Scalingo),
  `observabilite.md`, `harnais.md` (ce qui est mocké et pourquoi, invariants du
  harnais), `volumetrie-prod.md`.
