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