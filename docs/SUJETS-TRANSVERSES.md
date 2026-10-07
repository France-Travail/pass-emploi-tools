# Index des sujets transverses

> **Routeur** des gros sujets transverses durables de Pass Emploi. Toujours chargé
> (importé par `CONTEXTE-TRANSVERSE.md`) pour qu'on **sache** quels sujets existent
> et où est leur doc, sans charger tout le détail.
>
> Chaque entrée = **ouvrir quand** (déclencheur de lecture) + **invariant**
> (garde-fou avant d'agir) + **référence stable** (doc versionnée). Ne lister ici
> que du **versionné** — pas de pointeur vers des notes personnelles. Une entrée
> tient en 10 lignes hors liste de références, suit les règles « Documentation »
> de `CONTEXTE-TRANSVERSE.md`, et ne cite ni variable ni valeur de configuration :
> elle renvoie au mode d'emploi qui les porte.
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

## Logs ECS

- **Ouvrir quand** : on parle de logs, de champs ECS, d'un dashboard Kibana, ou
  qu'on cherche à savoir si un événement est déjà tracé.
- **Invariant** : tout log passe par le `rootLogger` au format ECS (`event.action`
  au passé + `event.outcome`). Logs opérationnels en `level` info|error (pas de
  `warn`) ; `debug` en plus, en opt-in. Jamais de `console.log`.
  **Jamais d'exception brute passée à un logger** : `toEcsError(e)` d'abord
  (sinon `err.config`/`err.response` axios → fuite d'identifiants + ligne > 16 Ko
  tronquée par le drain → log perdu). Charger le détail **avant** d'ajouter ou
  modifier un log.
- **Référence stable** : [`pass-emploi-tools/docs/observabilite/logs-ecs/`](./observabilite/logs-ecs/README.md)
  — `conventions.md` (format, nommage, redaction, « ne jamais logger une exception
  brute »), `infra-elasticsearch.md` (data streams, templates, ILM),
  `kibana.md` (use cases), `couverture-api.md` (ce qui est tracé côté api).

## Ingestion des logs · résilience & scaling (blackouts, drain)

- **Ouvrir quand** : des logs manquent ou arrivent en retard, le drain Scalingo ou
  Logstash est suspecté, ou on redimensionne un maillon de la chaîne d'ingestion.
- **Invariant** : le log-drain Scalingo **quarantine une app 5 min** dès **10 lignes
  consécutives** refusées (escalade 10/15/20 min) → un hoquet Logstash = blackout de
  la plus grosse app (`pass-emploi-api`). Conteneur XL Scalingo = **2 Go** → heap
  ≤ ~1 Go (Logstash consomme presque autant hors heap). Charger la référence
  **avant** de scaler ou retoucher la chaîne d'ingestion.
- **Référence stable** : [`pass-emploi-tools/docs/observabilite/ingestion-logs/`](./observabilite/ingestion-logs/README.md)
  — `runbook-astreinte-logstash.md` (5 scénarios de panne : backpressure ES, gel GC,
  DLQ, crash conteneur, backlog Redis),
  `conventions.md` (garde-fous JVM/Scalingo, playbook de diagnostic).
  Post-mortems associés dans `../post-mortems/` :
  `postmortem-2026-06-logstash-5xx.md` (fonctionnement JVM/Netty/GC, correctif XL),
  `postmortem-2026-07-blackout-logs.md` (les 2 modes de panne observés),
  `postmortem-2026-09-unenrolled-elastic-agent.md` (Elastic Agent bloqué UNENROLLED
  après recréation d'app Scalingo).

## App Jeune

- **Ouvrir quand** : **toute** question touchant l'app jeune — publics,
  authentification, invité, droits, plan d'action.
- **Invariant** : ne pas confondre public, mode d'authentification et
  représentation dans l'API ; les droits se déduisent de la présence d'un
  conseiller chez nous, d'un dossier France Travail ou d'un rattachement Mission
  Locale, jamais du mode d'authentification. Une fonctionnalité ne s'ouvre à
  l'invité qu'explicitement, et le mécanisme d'autorisation ne le garantit pas
  seul. Un identifiant venu du générateur de plan n'est jamais une clé chez nous.
- **Référence stable** : [`pass-emploi-tools/docs/app-jeune/README.md`](./app-jeune/README.md).

## Performances

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
