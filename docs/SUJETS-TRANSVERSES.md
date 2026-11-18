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

## Logs, SLO et alertes applicatives

- **Ouvrir quand** : on parle de logs, de champs ECS, d'`outcome` ou de `level`,
  du code HTTP renvoyé par l'api, d'un SLO, d'une alerte ou d'un salon Tchap, ou
  qu'on cherche à savoir si un événement est déjà tracé.
- **Invariant** : tout log passe par le `rootLogger` au format ECS, une exception
  par `toEcsError` (sinon fuite d'identifiants, ligne perdue). `outcome` = le fait
  de la ligne ; `level: error` = une ligne par incident, celle de la cause. Le code
  HTTP décrit l'appelant et nous : un échec partenaire dû à notre appel sort en
  5xx. Un SLO se lit sur le status de la requête, jamais sur le level. Charger le
  détail **avant** de toucher un log, une règle ou un SLO.
- **Référence stable** : [`observabilite/README.md`](./observabilite/README.md) (index) —
  [`logs.md`](./observabilite/logs.md) (familles de lignes, `outcome`, `level`, codes HTTP, champs, redaction),
  [`slo.md`](./observabilite/slo.md) (promesses, burn rate, angles morts),
  [`alertes.md`](./observabilite/alertes.md) (catalogue, critères, gravités),
  [`fonctionnement.md`](./observabilite/fonctionnement.md) (chemin jusqu'à Tchap, salons),
  [`routine-surveillance.md`](./observabilite/routine-surveillance.md) (dashboards, reporting),
  [`runbooks/investigation-incident.md`](./observabilite/runbooks/investigation-incident.md) (KQL d'enquête),
  [`kibana/README.md`](../kibana/README.md) (objets Kibana à déployer et leur mode d'emploi).

## Ingestion des logs · résilience & scaling (blackouts, drain)

- **Ouvrir quand** : des logs manquent ou arrivent en retard, le drain Scalingo ou
  Logstash est suspecté, ou on redimensionne un maillon de la chaîne d'ingestion.
- **Invariant** : le log-drain Scalingo **quarantine une app 5 min** dès **10 lignes
  consécutives** refusées (escalade 10/15/20 min) → un hoquet Logstash = blackout de
  la plus grosse app (`pass-emploi-api`). Conteneur XL Scalingo = **2 Go** → heap figé à
  `-Xmx256m` (mémoire totale ~1,7 Go, ne pas monter), piloté via `LS_JAVA_OPTS`
  (`JAVA_OPTS` est ignoré par Logstash).
  Charger la référence **avant** de scaler ou retoucher la chaîne d'ingestion.
- **Référence stable** : [`infra/collecte/logs/`](./observabilite/infra/collecte/logs/README.md)
  — `drain-scalingo.md` (quarantaine, troncature, décision ADR-003), `pipeline.md` (ingest) ;
  [`infra/process/logs/`](./observabilite/infra/process/logs/README.md) — `pipeline.md` (process, routage, DLQ),
  `performances.md` (tirs, trajectoire x10) ;
  [`infra/infrastructure.md`](./observabilite/infra/infrastructure.md) (inventaire, garde-fous JVM/Scalingo, dimensionnement) ;
  [`infra/pilotage.md`](./observabilite/infra/pilotage.md) (Fleet, agents) ;
  [`infra/stockage/logs/README.md`](./observabilite/infra/stockage/logs/README.md) (data streams, templates, ILM) ;
  [`infra/format/webhooks/conventions.md`](./observabilite/infra/format/webhooks/conventions.md) (champs ECS des événements reçus par webhook) ;
  [`infra/alertes-stack-observabilite.md`](./observabilite/infra/alertes-stack-observabilite.md).
  Procédures pas-à-pas de diagnostic : [`pass-emploi-tools/docs/observabilite/runbooks/runbook-logstash.md`](./observabilite/runbooks/runbook-logstash.md)
  (5 scénarios de panne : backpressure ES, gel GC, DLQ, crash conteneur, backlog Redis).
  Rattrapage des logs restés en DLQ (jamais la vider avant) : [`pass-emploi-tools/logs/rattrapage/README.md`](../logs/rattrapage/README.md).
  Post-mortems associés dans `observabilite/post-mortems/` :
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
