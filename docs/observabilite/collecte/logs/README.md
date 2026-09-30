# Collecte des logs — vue d'ensemble

Comment un log quitte le `stdout` d'une app Scalingo et arrive dans le buffer
Redis, prêt à être traité. La suite (Redis → filtres → ES) est dans
[`../../process/logs/`](../../process/logs/README.md) ; le format émis par les
apps dans [`../../format/logs/`](../../format/logs/README.md).

## La chaîne (modèle mental)

```
apps (api / web / connect)  ──drain HTTP Scalingo──►  Logstash INGEST  ──►  Redis  ──►  Logstash PROCESS  ──►  Elastic Cloud
   stdout                    (POST, par app)          (ACK rapide)         (buffer)     (filtres + bulk)       (logs-*)
```

- Chaque app source a **son propre drain** (indépendant) vers l'app
  `pass-emploi-logstash-<env>` ; le **router Scalingo** répartit sur ses instances.
- Le pipeline `ingest` n'a qu'un rôle : **acquitter le drain au plus vite** et
  écrire dans la liste Redis `logstash:ingest`.
- Inventaire des apps, dimensionnement et garde-fous JVM :
  [`../../infrastructure.md`](../../infrastructure.md).

## Les 2 modes de panne — signatures

| | **Mode A — blackout TOTAL** | **Mode B — trou d'UNE app** |
|---|---|---|
| Portée | toutes les apps ensemble | une seule (la plus grosse : api) |
| Cause | contre-pression **output ES** | **quarantaine du drain Scalingo** |
| Où | dans Logstash (output bloqué) | **en amont** de Logstash (drain) |
| Signature | **0 % CPU sur TOUS les conteneurs**, mémoire plate, 429 sur toutes les apps | une app à **0 pendant ~5 min pile**, autres continues, bouffée de **499** avant |
| Fix | buffer découplé (Redis) + scaling | découpler recevoir/traiter (pipeline ingest) ; atténué par + d'instances |

Diagnostic pas-à-pas : [playbook du runbook Logstash](../../runbooks/runbook-logstash.md#playbook-de-diagnostic-de-lingestion).

## Pour aller plus loin

| Fichier | Contenu |
|---|---|
| [drain-scalingo.md](drain-scalingo.md) | Le maillon qu'on ne maîtrise pas : quarantaine, troncature 16 Ko, plafonds, décision ADR-003 |
| [pipeline.md](pipeline.md) | Pipeline `ingest` : réception HTTP, zéro filtre, écriture Redis |
