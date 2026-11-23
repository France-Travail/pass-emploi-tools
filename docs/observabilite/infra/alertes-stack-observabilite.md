# Alertes de la stack d'observabilité

Les alertes sur **notre infra de télémétrie** (Logstash, Redis, agents Fleet, Elasticsearch) :
elles signalent que la chaîne de logs et de métriques est en panne ou aveugle,
pas que les utilisateurs sont touchés. Les pannes visibles des utilisateurs sont
dans [alertes applicatives](../alertes.md). Liste, gravités, sources et salons :
[catalogue des alertes](../catalogue-alertes.md) ; cette page en donne le
pourquoi et le calibrage. Hors M11 et M12 (AutoOps), ce sont des règles Kibana,
versionnées dans [`kibana/rules/`](../../../kibana/rules/README.md).

> Les Kibana Rules notifient Tchap par les [Workflows Tchap](../../../kibana/workflows/tchap/README.md). Les
> alertes émises hors Kibana, **M11 et M12 (AutoOps)**, préviennent l'équipe par
> e-mail et postent directement dans Tchap, par un connecteur Webhook AutoOps en
> `POST` (cf. leur section,
> [ADR-004](../../decisions/ADR-004-notifications-tchap-kibana-workflows.md#alertes-émises-hors-kibana-autoops)).
> Elles ne passent surtout pas par Elasticsearch : elles doivent alerter quand le
> cluster va mal.

> **Contexte** : les scénarios de panne et leurs indicateurs sont documentés dans
> [`runbooks/runbook-logstash.md`](../runbooks/runbook-logstash.md). Dashboards
> associés : [routine-surveillance](../routine-surveillance.md).

---

## Alerte M1 — Dead Letter Queue non vide

**Objectif** : signaler des **logs non indexés pour une cause que Logstash n'a pas
détectée**. Un log applicatif qui n'arrive pas dans les logs consultables
(`logs-prod-default`…) est mis de côté dans un index de diagnostic. Ici, Logstash
l'a traité sans erreur, mais son enregistrement a échoué en fin de pipeline, le
plus souvent refusé par Elasticsearch (par exemple un conflit de mapping). La cause
exacte est dans `logstash.dlq.reason`. Les erreurs que Logstash détecte lui-même
relèvent de l'[alerte M2](#alerte-m2--index-erreurs-de-traitement-non-vide).

Session Discover : onglet « Logs non indexés : Échec de process Logstash indéterminé ».

> **Note** : la taille de la DLQ (`queue_size_in_bytes`) n'est **pas** exposée dans
> les data streams de métriques Elastic Agent (`metrics-logstash.*`). L'alerte se
> base donc directement sur la présence de documents dans l'index `logs-logstash-dlq-*`,
> alimenté par le pipeline `dead_letter_queue` de Logstash.
>
> ⚠️ **L'index `logs-logstash-dlq-*` n'existe que si au moins un event a été rejeté
> en DLQ** (Logstash crée le data stream à la première écriture). L'alerte Kibana
> `COUNT(*) > 0` fonctionne même si l'index n'existe pas encore : Kibana retourne 0
> → pas d'alerte. Elle se déclenche dès que l'index est créé avec des documents.
> En revanche, la **data view** de diagnostic ne peut être créée qu'une fois le data
> stream existant. Pour l'anticiper, créer les data streams vides via Dev Tools
> (le nom `logs-logstash-dlq-*` matche le template `logs` qui impose l'API data stream) :
> ```
> PUT _data_stream/logs-logstash-dlq-prod-default
> PUT _data_stream/logs-logstash-dlq-staging-default
> PUT _data_stream/logs-logstash-dlq-perf-default
> ```

Champs clés : `logstash.dlq.reason` (cause du rejet ES), `event.original` (payload
complet de l'event fautif en JSON stringifié).

---

## Alerte M2 — Index erreurs de traitement non vide

**Objectif** : signaler des **logs non indexés à cause d'une erreur de transformation
que Logstash a détectée**. Un log applicatif qui n'arrive pas dans les logs
consultables est mis de côté dans un index de diagnostic. Ici, Logstash n'a pas
réussi à le mettre au bon format : il l'a rangé dans `logs-logstash-errors-*`
([routage en sortie](process/logs/pipeline.md#routage-en-sortie)).
Une hausse signale une régression du pipeline de transformation.

Session Discover : onglet « Logs non indexés : Erreur de transformation Logstash ».

**Prod sur 24 h** : une erreur de transformation perd un log, pas la chaîne, et
se traite dans la journée, pas à chaud. La règle tourne toutes les heures sur les
24 dernières heures : un message quand l'alerte apparaît, aucun tant qu'il reste
des erreurs dans la fenêtre. Pas de bilan à heure fixe : l'action `.workflows`
ignore les plages horaires (cf. [brancher une règle](../../../kibana/workflows/tchap/README.md#brancher-une-règle)).

---

## Alerte M3 — Absence de logs (quarantaine drain ou crash Logstash)

**Objectif** : détecter une quarantaine du drain Scalingo ou un crash Logstash.
L'absence de logs dans les index applicatifs et router pendant > 5 min est le signal
d'un arrêt complet de l'ingestion (scénario 4 du runbook).

> **Corrélation** : si les deux alertes (M3a+M3b ou M3c+M3d) se déclenchent simultanément,
> c'est un crash Logstash ou un arrêt de l'app Scalingo. Si seulement l'alerte
> applicatifs se déclenche (router continue), c'est une quarantaine du drain applicatif.

---

## Alerte M4 — Backpressure (inputs bloqués sur la queue)

**Objectif** : détecter un pipeline qui n'absorbe plus son entrée **avant** que des
logs ne se perdent. `queue_backpressure.current` mesure le temps que les **inputs**
passent bloqués à pousser dans la queue mémoire du pipeline, faute de workers
disponibles. La valeur **se cumule sur les threads d'input** : elle va de 0 au nombre
de threads, soit 4 sur `ingest` (`LOGSTASH_INGEST_THREADS`) et 1 sur `process`
(un seul input Redis). Il monte dès que l'aval ralentit (ES pour `process`, Redis
pour `ingest`).

**Seul `ingest` est alerté** : c'est son input HTTP qui répond au drain Scalingo, et
un drain qui attend finit en quarantaine. Sur `process`, l'input Redis bloqué est
attendu : Redis absorbe, et un backlog qui ne se vide pas relève de l'alerte M7.

> **Champ surveillé** : `logstash.pipeline.total.flow.queue_backpressure.current`
> dans le data stream `metrics-logstash.pipeline-default`.
>
> **Calcul par nœud** (`Grouped over` `logstash.pipeline.host.name`) : sans
> regroupement, la règle prend un seul minimum sur tous les conteneurs `ingest`,
> et un conteneur bloqué passe inaperçu tant qu'un autre ne l'est pas.
>
> **Seuil : minimum ≥ 1 sur 15 min** (mesuré sur la prod, 30 jours au 02/10/2026).
> Par tranche de 5 min, le maximum ne distingue rien : sur `ingest`, p95 3,28, p99 et
> max à 4, avec 18 % des tranches au-dessus de 0.5. Ce sont des à-coups de quelques
> secondes. Le minimum sur 15 min, lui, est bimodal : p99 à 0,009, et les seules
> tranches au-dessus de 1 (22 sur 2 805) sont aussi à 4, soit les 4 threads bloqués
> en continu. Le seuil de 1, un thread bloqué en permanence, ne retient que ces cas.
>
> Ces 22 tranches tombent toutes sur des incidents : les après-midi des 03/09, 07/09
> et 08/09, puis la nuit du 14 au 15/09 (de 20 h 45 à 8 h 30), après le crash de Redis.
> Aucun faux positif sur la période.
>
> Les rejets du drain (429/499) ne sont pas observables dans Kibana : les router logs
> des apps Logstash ne sont pas drainés vers ES. Pour les voir, passer par les logs
> Scalingo de l'app (cf. [runbook](../runbooks/runbook-logstash.md#playbook-de-diagnostic-de-lingestion)).
>
> **Indicateur de diagnostic complémentaire** (non alerté) :
> `logstash.pipeline.total.queues.events` — nombre d'events en attente dans la queue.
> À consulter dans le dashboard `[Metrics Logstash] Pipelines Overview` pour
> confirmer l'accumulation une fois l'alerte déclenchée.

---

## Alerte M5 — Heap JVM élevé (risque GC agressif)

**Objectif** : détecter un heap JVM Logstash que le GC n'arrive plus à libérer, signe
de pauses stop-the-world (scénario 2 du runbook) puis d'un `OutOfMemoryError`. La
mémoire totale du conteneur, qui déclenche l'OOM-kill Scalingo, n'est pas couverte
ici : c'est l'[alerte M9](#alerte-m9--mémoire-du-conteneur-logstash-oom-kill-scalingo).

> **Champ surveillé** : `logstash.node.stats.jvm.mem.heap_used_percent`
> dans le data stream `metrics-logstash.node-default`.
>
> **Seuil : minimum ≥ 90 % sur 15 min** (mesuré sur la prod, 30 jours au 02/10/2026).
> Avec `-Xmx256m`, le heap monte à 93 % avant chaque GC (médiane du maximum par
> tranche de 15 min), sur `ingest` comme sur `process` : un seuil sur le maximum
> sonnerait en permanence. Le minimum, c'est-à-dire ce qui reste après le GC, ne
> dépasse jamais 84 % (p99 83 % sur `process`, 82 % sur `ingest`). À 90 %, le GC
> ne libère plus que 10 % d'un heap de 256 Mo.
>
> **Calcul par nœud** (`Grouped over` `host.name`) : sans regroupement, la règle
> prend un seul minimum sur tous les nœuds prod, `ingest` et `process`
> confondus ; un nœud saturé passe inaperçu tant qu'un autre respire.
> Vérifié nœud par nœud sur 7 jours au 05/10/2026 : aucune tranche de 15 min
> au-dessus de 90 %, mais le minimum de `process-prod-worker-2` est monté à
> 89 %. Marge mince, à surveiller.

---

## Alerte M6 — Événements Scalingo des apps de la stack

**Objectif** : savoir ce qui arrive aux apps de la stack d'observabilité
(`pass-emploi-logstash`, `pass-emploi-logstash-process`,
`pass-emploi-elastic-agent`, `pass-emploi-heartbeat`) : crash, arrêt,
redémarrage (OOM-kill…), seuil de ressource, mais aussi déploiements et
opérations d'infra.

Des **Elasticsearch query rules (KQL)** sur les événements des notifiers
Scalingo, collectés dans `logs-alertes-scalingo-<env>-default` (cf.
[collecte par webhook](collecte/webhooks/README.md),
dont la [mise en service](collecte/webhooks/README.md#mise-en-service)
des notifiers). Une règle par environnement, qui liste chaque événement sur une
ligne, préfixée de sa gravité : en prod, 🚨
crash, redémarrage ou arrêt, ⚠️ seuil dépassé ; en staging / perf, ⚠️ pour
les deux ; ℹ️ le reste. Les
apps applicatives vont aux règles A4a à A4d des
[alertes applicatives](../alertes.md).

Chaque exécution ne compte que les documents arrivés depuis la précédente
(`excludeHitsFromPreviousRun`) : un événement = une notification, sans
throttle. Scalingo n'envoie `app_crashed` qu'aux 2ᵉ, 5ᵉ et 12ᵉ crashs, et
`app_crashed_repeatedly` à chaque crash : le notifier doit sélectionner les deux.

> **Alternative** : utiliser l'alerte M3 (absence de logs) comme proxy indirect du
> crash — un crash Logstash se traduit immédiatement par un silence dans
> `logs-prod-default`. Les deux alertes sont complémentaires : l'alerte M6
> donne la **cause** (OOM), l'alerte M3 donne l'**effet** (silence logs).

---

## Alerte M7 — Backlog Redis `logstash:ingest` (pipeline PROCESS découplé)

**Objectif** : détecter une accumulation anormale d'événements dans la liste Redis
`logstash:ingest`, buffer inter-services entre le pipeline `ingest` et le pipeline
`process`. En régime normal, le pipeline `process` consomme la liste en temps réel
et la liste se vide en quelques minutes, même après les pics de :00 et :30 (cf.
seuil ci-dessous). Un backlog durable signale que le pipeline `process` ne consomme plus Redis : redémarrage ou blocage
de `pass-emploi-logstash-process-prod`, coupure réseau Redis, ou backpressure ES
sévère côté `process`.

> **Incident de référence — 14/09/2026** : `pass-emploi-logstash-process-prod` a
> subi plusieurs redémarrages inexpliqués dans la soirée, provoquant l'accumulation
> de ~180 000 événements jusqu'à saturer les 256 Mo de Redis → crash du cluster Redis
> à 20:37 (HAProxy DOWN). **Cause racine inconnue** — logs archivés Scalingo
> inaccessibles à date. Le lendemain matin, l'app s'est rétablie et a vidé le
> backlog — aucun log perdu, mais indexation tardive (~13h de retard).
>
> **Source** : data stream `metrics-redis.key-default` (intégration Redis Elastic
> Agent, collectée par `pass-emploi-elastic-agent-prod`). Champ : `redis.key.length`.
>
> **Seuil : minimum > 1 000 sur 15 min** (mesuré sur la prod du 14/09 au
> 30/09/2026, par tranche de 5 min). En nominal, la liste fait le yo-yo : p50 77,
> p95 1 875, p99 11 606. Les pics tombent les jours ouvrés, de 8 h 30 à 17 h,
> presque tous à :00 ou :30, avec une médiane de 5 259 et un p90 de 14 095, et
> se vident dans la tranche de 5 min. Un `Max` déclenche donc chaque demi-heure.
> Le `Min` ne retient que la liste qui ne redescend pas : sur la période, seul
> l'incident du 14/09 (90 min, jusqu'à 180 799) et le 21/09 à 10 h 50 (15 min,
> 11 500) y passent. L'alerte part 15 à 17 min après le début de la coupure ;
> le 14/09, la saturation est arrivée ~1 h 20 après.

---

## Alerte M8 — Elastic Agent en défaut

**Objectif** : détecter qu'un Elastic Agent a décroché, quelle qu'en soit la
forme. Un agent en défaut, c'est une **supervision aveugle** : les alertes M4, M5
et M7 lisent ses métriques et ne peuvent plus se déclencher — le silence d'un
agent ressemble à une infra saine. Contexte :
[pilotage.md](pilotage.md#savoir-quun-agent-a-décroché).

| Défaut détecté                                                                                                                 | Signal                                 | Source                                     |
|--------------------------------------------------------------------------------------------------------------------------------|----------------------------------------|--------------------------------------------|
| **offline** — ne contacte plus Fleet Server depuis 5 min (seuil fixe Fleet)                                                    | `health_status == "offline"`           | `logs-elastic_agent.status_change-default` |
| **unenrolled** — retiré de Fleet ([post-mortem du 11/09/2026](../post-mortems/postmortem-2026-09-unenrolled-elastic-agent.md)) | `health_status == "unenrolled"`        | idem                                       |
| **unhealthy** — tourne, mais un composant est en erreur ou dégradé                                                             | `health_status == "unhealthy"`         | idem                                       |
| **erreurs d'output** — tourne, mais ses écritures vers ES échouent (peut rester `Healthy`)                                     | > 25 erreurs d'écriture sur la fenêtre | `metrics-elastic_agent.*beat-*`            |

> **Règle maison, reprise des règles natives Fleet.** Elle regroupe en une
> requête les modèles `[Elastic Agent] Offline status`, `Unenrolled status`,
> `Unhealthy status` et `Output errors` livrés depuis la 9.2
> ([doc Elastic](https://www.elastic.co/docs/reference/fleet/alert-templates)) —
> deux règles au lieu de huit, le filtre d'environnement écrit une seule fois.
> Le seuil reprend celui du modèle : > 5 erreurs d'output/min (soit 25 sur la
> fenêtre). Le modèle `Restarts` n'est pas repris : il compte le message
> `Starting…elastic-agent…`, de niveau INFO, que nos agents (logging level
> WARNING) n'envoient pas. Les exclusions `agentless` des
> modèles sont inutiles ici : le filtre d'environnement les écarte déjà.
> **Requête testée le 2026-09-30** sur perf (filtre `"*-perf-*"`, 30 j) : les 8
> agents perf remontent en `offline` / `unhealthy` / `unenrolled`. La branche
> erreurs d'output n'a pu être vérifiée qu'à vide (0 erreur sur la période).
>
> **Filtre d'environnement obligatoire** : les agents perf sont **volontairement
> désactivés** (réduction des coûts d'infra) mais restent enrôlés — sans filtre,
> chaque arrêt de perf déclenche l'alerte. Perf n'a **pas** de règle. Le
> discriminant est le hostname Scalingo, dérivé du nom de l'app
> (`pass-emploi-{logstash,logstash-process,elastic-agent}-<env>-{web,worker}-<n>`),
> porté par `hostname` dans le journal de statut et par `agent.name` dans les
> métriques d'agent — d'où le `COALESCE` (vérifié le 2026-09-30). L'ordre compte : le journal de statut porte aussi un `host.name`,
> qui ne désigne pas forcément l'agent — `hostname` doit rester en tête.
> Toute nouvelle app agent doit respecter
> ce nommage `…-<env>-…`, sinon elle échappe à l'alerte.
>
> **Deux `STATS`** : le compteur `output.write.errors` est cumulatif **par
> composant** ; le delta max − min se calcule par composant avant d'être agrégé
> par agent, sinon on soustrairait les compteurs de deux composants différents.
> Un redémarrage remet le compteur à 0 : si l'agent avait des erreurs avant, le
> delta peut déclencher une fois.
>
> **Transition, pas état** : les statuts viennent du **journal des changements
> de statut** (un document par agent et par transition). La règle se déclenche
> sur la transition puis passe `Recovered` au bout de la fenêtre, **même si
> l'agent est toujours en défaut** — d'où l'absence de message de résolution.
> L'état courant se lit dans Kibana → Fleet → Agents.

---

## Alerte M9 — Mémoire du conteneur Logstash (OOM-kill Scalingo)

**Objectif** : prévenir avant que Scalingo ne tue un conteneur Logstash qui atteint
sa limite mémoire. L'OOM-kill provoque les redémarrages en série (alerte M6, qui
arrive après coup) et, sur `ingest`, la quarantaine du drain. L'alerte M5 ne voit
que le heap : le reste de la mémoire du process (Netty, JRuby, metaspace, threads)
et l'Elastic Agent co-localisé lui échappent (cf.
[garde-fous JVM / Scalingo](infrastructure.md#garde-fous-jvm--scalingo)).

> **Source** : data stream `logs-scalingo.container_stats-default`, alimenté
> chaque minute par l'API Scalingo (intégration Custom API de l'agent dédié, cf.
> [collecte](collecte/metriques/stack-observabilite.md)). Champ :
> `scalingo.memory.pct` (utilisation / limite, de 0 à 1).
>
> **Seuil : maximum ≥ 95 % sur 5 min, par conteneur**. Mesuré du 02/10/2026
> à 19 h (début de la collecte) au 05/10/2026, par tranche de 5 min : `ingest`
> plafonne à 78 % (p99 77,9 %) ; `process` monte plus haut, p99 89,6 % et
> maximum 92,8 % sur `worker-2`. À 95 %, il reste ~100 Mo sur 2 Go avant le kill.
> Le `Max` et non le `Min` : la mémoire d'un conteneur Logstash est quasi plate,
> et un pic suffit à le tuer. **Seuil à recaler sur 30 jours de données**
> (début novembre 2026).

---

## Alerte M10 — ILM en échec ou policy sans suppression

**Objectif** : signaler un index de nos flux qui n'applique pas sa rétention. Soit
sa dernière étape ILM est en échec (index bloqué), soit l'index est sur une policy par défaut
d'Elastic, sans phase `delete` : il grossit sans jamais être supprimé. Cas vécu :
les métriques Fleet et les logs Elastic Agent sur `metrics@lifecycle` /
`logs@lifecycle` jusqu'au 2026-10-05, faute des briques `@custom`.

> **Source** : l'historique ILM (data stream caché `ilm-history-7`), une ligne par
> étape exécutée : `index`, `policy`, `success`. ES|QL ne voit ce data stream
> caché que par ses index : `FROM .ds-ilm-history-7-*`. Un index est bloqué si son
> dernier échec est postérieur à sa dernière étape réussie : une erreur que l'ILM
> relance seul ne sonne pas. L'historique garde le nom de l'index au moment de
> l'étape, même après son passage en `partial-…`.
>
> **Calibrage** (30 jours au 2026-10-06) : 0 étape en échec ; 112 étapes sur
> `metrics@lifecycle` et 17 sur `logs@lifecycle`, toutes antérieures à la
> correction du 2026-10-05. L'alerte aurait sonné dès le premier jour.
>
> **Calibrage du dernier état** (30 jours au 2026-11-23) : 3 étapes en échec
> (`forcemerge` et `searchable_snapshot` vers frozen, le 08/11, le 15/11 et le
> 23/11), toutes relancées avec succès par l'ILM : 0 index bloqué.
> L'ancienne règle, qui comptait tout échec des 24 h, a sonné pour chacune.
>
> **Limites** : un index rattaché à une policy qui n'existe pas n'écrit rien dans
> l'historique et échappe à l'alerte (cf. [runbook ILM, scénario 3](../runbooks/runbook-ilm.md#scénario-3--policy-inexistante-non-alerté)).
> Un index bloqué sur une erreur que l'ILM ne relance pas n'écrit plus rien et sort
> de l'alerte au bout des 7 jours de la fenêtre.
>
> **Sur 7 jours** : rien d'urgent, l'index grossit ou attend. Un seul message pour
> tous les index concernés, comme la prod de
> l'[alerte M2](#alerte-m2--index-erreurs-de-traitement-non-vide).

---

## Alerte M11 — Disque des nœuds Elasticsearch (AutoOps)

**Objectif** : prévenir avant qu'un nœud Elasticsearch plein ne bloque l'écriture,
et donc l'ingestion de tous les logs. Elasticsearch durcit son comportement en
trois paliers de remplissage (*watermarks*) : 85 % (plus de nouveaux shards),
90 % (des shards quittent le nœud), 95 % (écriture bloquée). Le détail de chaque
palier et quoi faire : [runbook disque](../runbooks/runbook-disque-elasticsearch.md).

> **Pourquoi AutoOps** : il collecte d'office l'état disque des nœuds d'un
> déploiement Elastic Cloud et fournit un événement par palier. Une règle Kibana
> demanderait d'abord de collecter ces métriques : la supervision de la stack
> (`.monitoring-*`) ne tourne pas.
>
> **Saisie à la main** (console Elastic Cloud → AutoOps → *Notifications
> settings*, sans API), comme l'alerte M6 : à refaire sur un nouveau déploiement.
> Connecteurs et filtres versionnés dans [`connecteurs/autoops/`](../../../kibana/connecteurs/autoops/) ;
> les réglages des événements, ci-dessous.
> Le cluster est unique et porte tous les environnements : connecteurs et filtres
> ne sont pas nommés par environnement.
>
> **Nœud frozen** : disque à ~90 % en permanence (cache des searchable snapshots),
> soumis à des seuils à part. Il ne doit pas déclencher ces événements ; à
> vérifier au premier événement reçu (champ « Nœuds concernés »).

### M11 — Configuration dans AutoOps

**Événements** : ces 5 événements du déploiement `Pass Emploi`, rangés dans les filtres par
sévérité des [notifications AutoOps](#notifications-autoops-m11-et-m12). Un événement garde ses
réglages par défaut tant qu'on ne lui crée pas de réglage personnalisé (*custom
event settings*) : seul le statut red en a un.

| Événement AutoOps                                 | Réglage personnalisé                                                                                                                                                                                                                  | Déclenchement                             |
|---------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------|
| The disk capacity is about to reach low watermark | aucun (défaut : 10 points sous le palier)                                                                                                                                                                                             | 75 %, préavis                             |
| The low disk watermark has been exceeded          | aucun                                                                                                                                                                                                                                 | 85 %                                      |
| The high disk watermark has been exceeded         | aucun                                                                                                                                                                                                                                 | 90 %                                      |
| The flood stage disk watermark has been exceeded  | aucun                                                                                                                                                                                                                                 | 95 %                                      |
| The cluster status is red                         | `Minimum duration of the red status` = **300** s (ignore les passages en rouge des maintenances Elastic Cloud) ; exclusions par défaut `partial-*`, `restored-*` conservées (index frozen et restaurés, brièvement rouges au montage) | shard principal indisponible depuis 5 min |

Écartés : *The cluster status is yellow* (une copie de secours manque, à chaque
maintenance Elastic Cloud ; la perte réelle est couverte par le statut red) et
*Your cluster version is outdated* (sans urgence, répété jusqu'à la montée de
version).

> ⚠️ Le réglage « … percent before … watermark » est une **marge en points sous le
> palier**, pas un seuil absolu : 85 sur l'événement flood stage le déclencherait
> à 10 %, en permanence.

---

## Alerte M12 — Saturation de l'indexation Elasticsearch (AutoOps)

**Objectif** : voir Elasticsearch ralentir **avant** que Logstash ne se bloque.
Quand les files internes d'Elasticsearch saturent, l'indexation ralentit, les
workers `process` de Logstash attendent, puis `ingest` se bloque et le drain
Scalingo part en quarantaine (cause racine de l'incident de juillet 2026, cf.
[runbook Logstash, scénario 1](../runbooks/runbook-logstash.md#scénario-1--backpressure-elasticsearch)).
Cette alerte précède l'[alerte M4](#alerte-m4--backpressure-inputs-bloqués-sur-la-queue).

> **Saisie à la main**, comme l'[alerte M11](#alerte-m11--disque-des-nœuds-elasticsearch-autoops) :
> console Elastic Cloud → AutoOps → *Notifications settings*.
>
> **Écartés** : *Slow search detected* (personne d'autre que l'équipe et nos
> règles n'interroge Elasticsearch, et les recherches sur le frozen sont lentes
> par nature) et *Long running index task* (déclenché par les fusions et
> snapshots d'ILM à chaque passage en frozen).

### M12 — Configuration dans AutoOps

**Événements** : ces 2 événements du déploiement `Pass Emploi`, rangés dans les filtres par
sévérité des [notifications AutoOps](#notifications-autoops-m11-et-m12).

| Événement AutoOps                 | Réglages (par défaut, sans réglage personnalisé)                                      | Ce qu'il signale                                                   |
|-----------------------------------|---------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| The management queue is high      | `High management queue activity threshold` = 5 ; `How many successive samplings…` = 3 | la file des opérations internes (rollovers, fusions, ILM) sature   |
| The write queue is high           | `Write queue threshold` = 30 ; `How many successive samplings…` = 3                   | la file des écritures d'un nœud n'absorbe plus le flux de Logstash |

Les 3 mesures successives au-dessus du seuil ignorent les montées brèves de ces
files aux pics de logs (:00 et :30). En cas de bruit, augmenter d'abord ce nombre
de mesures (réglage personnalisé), avant de toucher aux seuils.

## Notifications AutoOps (M11 et M12)

Saisies à la main dans la console (AutoOps n'a pas d'API), versionnées dans
[`connecteurs/autoops/`](../../../kibana/connecteurs/autoops/), un fichier par objet de la console :
`connectors/` (*Connector settings*) et `filters/` (*Filter settings*). AutoOps ne sait ni
filtrer par sévérité, ni varier le message selon elle : un filtre par sévérité, avec les seuls
événements de cette sévérité (celle qu'affiche AutoOps), et un connecteur Tchap par sévérité.

| Sévérité | Dans Tchap (`o11y-production`) | Message | Délai |
|---|---|---|---|
| Critical | 🚨 en rouge | complet, avec le runbook du disque | aucun |
| High | ⚠️ en orange | complet, avec le runbook du disque | aucun |
| Medium | en gris | allégé : l'événement et son lien | aucun |
| Low | en gris | allégé | 30 min |

Le délai d'un filtre retarde ses notifications, e-mail compris, et les supprime si l'événement
se referme avant : la file de gestion monte pendant les snapshots d'Elastic Cloud (toutes les
30 min), puis retombe en quelques minutes.

`tests/test_messages_tchap.py` vérifie qu'un événement n'est que dans un filtre, que chaque
filtre a l'e-mail et son seul connecteur Tchap, le délai de Low, et que chaque corps passe le
pare-feu devant Tchap.

**Connecteur Email** (`connectors/email.json`), sur tous les filtres : AutoOps rédige lui-même
le message ; destinataires de l'équipe saisis dans la console, non versionnés. C'est le canal
de secours, indépendant de Tchap.

**Connecteurs Tchap** (`connectors/tchap-<sévérité>.json`) : type **Webhook** ; méthode, URL et
en-têtes, puis, en dernière clé, `corps` : l'objet à coller tel quel dans le champ *Body*. Remplacer `<jeton du bot Tchap>` par le jeton du
bot des [Workflows Tchap](../../../kibana/workflows/tchap/README.md), secret, jamais versionné. Le salon est l'un
de ceux de [`salons.json`](../../../kibana/workflows/tchap/salons.json) : pour en changer, modifier `salon` et
`url` ensemble. Tester avec **Run to test** : le message doit arriver dans le salon, variables
non remplies.

> **Pourquoi `POST` sans `txnId`** : AutoOps n'a ni variable unique par
> événement ni variable dans l'URL, il ne peut pas produire le `txnId` de
> l'envoi normalisé (`PUT …/{txnId}`). La route `POST` sans `txnId` est
> ancienne, hors norme Matrix, mais acceptée par Synapse (le serveur de Tchap).
> Concession : un envoi rejoué après une coupure réseau peut doubler le message.
> Si une montée de version de Tchap supprimait cette route, les notifications
> cesseraient : l'e-mail reste le secours.

> **Constaté sur un événement réel** (management queue) : toutes les variables sont
> remplies. AutoOps envoie un message à l'ouverture (`OPENED`, `${END_TIME}` vaut alors
> `N/A`) puis un à la clôture (`RESOLVED`). Les heures sont en UTC (`+0000`). `${MESSAGE}`
> contient des `<br />`, affichés comme des retours à la ligne dans le HTML, et il était
> identique à `${DESCRIPTION}`, que les corps omettent.

---

## Alerte M13 — Événement externe rejeté

**Objectif** : ne pas perdre en silence une notification Scalingo ou GitHub.
Un document rejeté par son ingest pipeline (ou par Elasticsearch) part au
failure store de son data stream, et son émetteur reçoit **quand même un
succès** : sans cette règle, un changement de format chez Scalingo ou GitHub,
ou un notifier qui vise le mauvais environnement, passerait inaperçu, et
l'alerte que portait le document ne serait pas levée.

---

## Philosophie des alertes

> **Principe directeur : anticiper, pas réagir.**
>
> Une alerte doit se déclencher **avant** que le problème soit avéré et visible par
> les utilisateurs. Une alerte qui se déclenche au moment où les logs sont déjà perdus
> ou les 429 déjà renvoyés est une alerte de réaction — elle est trop tardive pour
> éviter l'impact.
>
> **Chaîne causale type (backpressure ES) :**
> ```
> ES ralentit / heap monte           → Alerte M5a       ← intervenir ici
>   → queue process se remplit       → Logstash process rejette les events
>     → backlog Redis croît          → Alerte M7a          ← filet inter-services
>       → ingest ne peut plus écrire → Alerte M4a (ingest bloqué)
>         → 429 sur les apps         → (signal de réaction — pas alerté)
>           → drain en quarantaine   → Alertes M3a/M3b (filet de sécurité final)
>             → silence total        → trop tard, perte avérée
> ```
>
> **Chaîne causale type (redémarrage/blocage de `process` ou coupure réseau Redis) :**
> ```
> process tombe ou perd Redis       → pipeline process ne consomme plus
>   → backlog Redis croît           → Alerte M7a          ← intervenir ici
>     → pipeline ingest continue    → (pas de 429, drain OK — invisible sans alerte M7)
>       → saturation Redis possible → crash Redis si le backlog dépasse 256 Mo
> ```
> L'incident du 14/09/2026 illustre ce scénario : ~180 000 événements accumulés
> pendant ~13h, saturation Redis → crash à 20:37. Cause racine inconnue (logs
> archivés). Sans l'alerte M7, l'incident serait passé inaperçu jusqu'au lendemain.
>
> **Règles pour toute nouvelle alerte :**
>
> 1. **Préférer les indicateurs internes Logstash** (métriques Fleet) aux indicateurs
>    externes (codes HTTP, logs applicatifs) — les métriques internes reflètent l'état
>    du système avant que l'impact ne soit visible côté client.
> 2. **Éviter les compteurs cumulatifs** (`bulk_requests.with_errors`,
>    `collection_time_in_millis`, `events.out`…) — ils ne redescendent jamais à 0 et
>    ne sont pas alertables directement. Les utiliser uniquement comme indicateurs de
>    diagnostic dans les dashboards et le runbook.
> 3. **Préférer les indicateurs de niveau** (`queue.events_count`,
>    `heap_used_percent`…) — ils reflètent l'état courant du système et permettent
>    de définir un seuil d'alerte clair.
> 4. **Calibrer le seuil pour laisser une marge d'intervention** : l'alerte doit se
>    déclencher assez tôt pour qu'une action corrective soit possible avant que la
>    situation ne devienne critique (ex : un heap qui ne redescend plus sous 90 % laisse
>    le temps d'agir avant l'`OutOfMemoryError`).
> 5. **Les alertes de silence** (alerte M3) sont des filets de sécurité de dernier
>    recours — elles signalent que tous les mécanismes d'anticipation ont échoué.
>    Leur déclenchement doit être traité comme une urgence maximale.
