# Format des logs — ECS

Comment une app Pass Emploi (api, connect, web) **émet** un log : format ECS
structuré en JSON sur `stdout`, via un `rootLogger` pino. C'est la seule étape
qui vit dans le code applicatif ; tout ce qui suit (drain, Logstash, ES) est
mutualisé dans `pass-emploi-tools`.

**Invariant à respecter** : tout nouveau log passe par le `rootLogger` au format
ECS (`event.action` au passé + `event.outcome`). Les logs **opérationnels** sont
`info`/`error` (pas de `warn`) ; `debug` existe en plus comme niveau diagnostic
opt-in piloté par `LOG_LEVEL`. Jamais de `console.log`. Jamais d'exception brute
passée à un logger (`toEcsError(e)` d'abord). Lire
[conventions.md](conventions.md) avant d'ajouter ou modifier un log.

| Fichier | Contenu |
|---|---|
| [conventions.md](conventions.md) | Socle transverse : taxonomie `event.action`, `outcome`/`level`, redaction, archi `rootLogger`, patterns d'instrumentation, décisions durables |
| [couverture-api.md](couverture-api.md) | Spécifique pass-emploi-api : taxonomie, couverture, validation E2E RDV Milo, limites connues |

Contraintes imposées par l'aval : une ligne ne doit pas dépasser **16 Ko**
(troncature du drain, cf. [collecte/logs/drain-scalingo](../../collecte/logs/drain-scalingo.md)) ;
tout champ ECS custom doit être déclaré dans `logs@custom`
(cf. [stockage/logs](../../stockage/logs/README.md)).
