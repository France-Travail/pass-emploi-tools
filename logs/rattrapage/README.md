# Rattrapage des logs de la DLQ

Un log refusé par Elasticsearch (conflit de mapping, document malformé, index en lecture
seule ou cluster rouge) n'est pas perdu : le pipeline `dead_letter_queue` le range dans
`logs-logstash-dlq-<env>-default`, avec le document d'origine dans `event.original`.
`rattraper-dlq.py` le réindexe dans le data stream où le pipeline `process` l'aurait écrit
(`logs-router-<env>-default` pour un log du routeur, `logs-<env>-default` sinon), avec son
`@timestamp` d'origine. Il ne fait qu'appeler l'API d'Elasticsearch : rien n'est créé dans
Elastic, Logstash n'est pas sollicité.

**Ne jamais supprimer la DLQ avant de l'avoir rattrapée** : ce sont les logs manquants.

## Rattraper

1. Corriger d'abord la cause du refus (`logstash.dlq.reason` dans la DLQ) : mapping, place
   disque, cluster rouge. Sinon les documents sont refusés à nouveau.
2. Simuler : combien de logs, vers quels data streams.
   ```bash
   ES_URL=… ES_API_KEY=… python3 -I logs/rattrapage/rattraper-dlq.py --env prod --depuis 2026-11-16T21:00:00Z --simuler
   ```
3. Rattraper, puis retirer de la DLQ ce qui est rattrapé :
   ```bash
   … python3 -I logs/rattrapage/rattraper-dlq.py --env prod --depuis 2026-11-16T21:00:00Z --supprimer
   ```

`--depuis` et `--jusqu-a` bornent la période sur `@timestamp` (la date du log) ; sans eux, toute
la DLQ de l'environnement. La clé API doit pouvoir lire et supprimer dans
`logs-logstash-dlq-<env>-default`, et lire et créer dans `logs-<env>-default` et
`logs-router-<env>-default`.

Relancer le script est sans risque : un log déjà présent dans son data stream n'est pas réécrit
(« déjà présents »), et, avec `--supprimer`, il est retiré de la DLQ. Un log refusé reste dans la
DLQ, avec le type d'erreur affiché ; le code de sortie vaut alors 1.

Tests : `python3 -I -m unittest discover -s logs/rattrapage`, dont la concordance du routage
avec le bloc `output` de `../pipeline-process.conf`.
