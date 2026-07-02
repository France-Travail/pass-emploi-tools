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