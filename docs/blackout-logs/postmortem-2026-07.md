# Post-mortem — Blackouts & perte de logs sur le Logstash mutualisé (juin–juillet 2026)

> **Type** : explication (Diataxis). Comment l'incident s'est produit, les **deux
> modes de panne distincts** qu'on a démêlés, et **comment la chaîne d'ingestion
> tiendra (ou pas) à x10 utilisateurs**.
>
> Garde-fous durables + playbook de diagnostic : [conventions.md](./conventions.md).
> Incident **distinct** du précédent (5xx/GC de juin, heap sous-dimensionnée) :
> [../logs-ecs/postmortem-logstash-5xx-2026-06.md](../logs-ecs/postmortem-logstash-5xx-2026-06.md).
> Celui-ci part **après** le correctif `-Xmx1g` de cette campagne-là.

## TL;DR

Aux **pics d'usage**, le Logstash mutualisé (`pass-emploi-tools/logs/`, 4× conteneurs
XL sur Scalingo) cessait d'indexer certains logs dans Elastic → **trous réels dans
l'index** (perte, pas juste retard). Deux causes **différentes**, découvertes l'une
après l'autre :

| Mode | Portée | Cause racine | Correctif |
|---|---|---|---|
| **A — Blackout total** | **toutes** les apps en même temps | Contre-pression **output Elasticsearch** : Logstash bloqué en attente d'ES (0 % CPU partout), file **en mémoire** sans buffer → l'input jette les logs reçus | **Persistent queue** (`queue.type: persisted`) + **scaling horizontal** (→ 3-4× XL) |
| **B — Trou sur `pass-emploi-api` seul** | **une seule** app (la plus volumineuse) | **Quarantaine du log-drain Scalingo** : 10 lignes consécutives refusées → drain mis en quarantaine 5 min (aucun log envoyé), escalade 10/15/20 min | **Atténué** par 4× XL (moins de hoquets → moins de déclenchements). **Pas éliminé** — enjeu de l'archi x10 |

**État au 2026-07-02** : à **4× XL**, plus de perte observée, response time **plat
même au pic du matin** (~35k req/min). Mais le mode B est **latent** et redevient
critique avec la montée en charge → cf. [§7 Next steps x10](#7-next-steps--tenir-à-x10).

---

## 1. Le symptôme

- « Logstash reçoit mais n'envoie plus les logs à Elastic », par **rafales aux
  pics** (ex. matin ~9h, ou bascules de charge).
- Confirmé côté **Kibana** : trous nets dans l'index `logs-*` (ex. `pass-emploi-api-prod`
  vide de ~14:43 à ~14:45, puis de 17:37 à 17:41 le 2026-07-01). → **perte réelle**.
- Côté **métriques Scalingo** : chutes verticales à 0 du « requests/min » de l'app
  logstash, et pics de response time (p99 jusqu'à ~9 s).

> ⚠️ Ne pas confondre : l'**ondulation** du requests/min (5k↔40k) est **normale**
> (elle suit le volume de logs réel des apps). Seules les **chutes à 0** sont des
> blackouts.

---

## 2. Mode A — Blackout total (contre-pression Elasticsearch)

**Ce qu'on a vu** (2026-06-30) : toutes les apps trouent **ensemble**, **0 % CPU
sur tous les conteneurs simultanément**, mémoire **plate** (~1,3 Go), et des 429
répartis sur **toutes** les apps proportionnellement à leur volume.

**Mécanique** :

```
ES ralentit / décroche (ConnectTimeout Elastic Cloud au pic)
   → les workers Logstash bloquent sur l'output (attente I/O = 0 % CPU)
   → la file EN MÉMOIRE se remplit (pas de buffer disque)
   → l'input HTTP se bloque → renvoie 429 → le drain jette les logs
   → trou d'indexation sur TOUTES les apps
```

Le **0 % CPU sur tous les conteneurs à la fois** est la signature : ils sont
**bloqués en attente du même ES partagé**, pas en train de calculer (⇒ ni GC ni OOM).

**Correctif** :
1. **`queue.type: persisted`** (persistent queue) : buffer **disque** entre l'input
   et l'output. Un décrochage ES court est encaissé sur disque et rejoué, au lieu
   de remonter en contre-pression et de jeter les logs. Un trou ES de ~44 s
   ≈ ~11 Mo de backlog → tient dans une PQ de 256 Mo → **zéro perte**.
2. **Scaling horizontal** (3 puis 4× XL) : plus de capacité d'ingestion, moins de
   décrochages.

→ Mode A **résolu**. (⚠️ La PQ est le filet de ce mode ; elle a été **retirée
temporairement** pour un test GC/ES en cours — voir [§6](#6-état-actuel--décisions-ouvertes).)

---

## 3. Mode B — Trou sur `pass-emploi-api` seul (quarantaine du drain)

Une fois le mode A traité, il restait des trous **uniquement sur `pass-emploi-api`**,
**web et connect continus** pendant ce temps.

### 3.1 La preuve (2026-07-01, à BAS volume, fin de journée)

Requêtes **200/min** par app source (extrait des router logs, champ `appname=`) :

```
min      api    web  connect
17:35   5108    639   1221
17:36   3423   1105   1221     ← rafale de 429/499 sur api
17:37      0    864   1320     ← api = 0
17:38      0   1237   1281     ← api = 0
17:39      0   1335   1244     ← api = 0
17:40      0    828   1368     ← api = 0
17:41   1794   1149   1589     ← api repart
```

- **api tombe à ZÉRO ~4-5 min ; web/connect ne bougent pas.**
- Juste avant (17:36) : bouffée de **429** (rejet) + **499** (le client — le drain —
  coupe car Logstash répond trop lentement). Les **200 réponses `499` sont TOUTES à
  17:36**.
- Répartition : api = **73 %** des 429 et **71 %** des 499.
- **Durées de traitement identiques entre apps** (api ~25 ms, web ~28, connect ~30)
  → api n'est **pas** plus coûteux à traiter.
- **C'est arrivé à BAS volume** → ce n'est **pas** une saturation de débit.

### 3.2 La cause racine : la quarantaine du log-drain Scalingo

[Doc Scalingo — log drain](https://doc.scalingo.com/platform/app/log-drain) :

> If a log drain target fails to accept **10 consecutive log lines**, it is placed
> in **quarantine for 5 minutes**. During that time, no log lines are sent to it.
> If it still fails after quarantine, the duration increases: **10, 15, 20 min…**

Ça matche à la minute : 17:36 → 10 échecs consécutifs → **~5 min de quarantaine
sèche** (17:37-17:40) → reprise 17:41.

> **Amplification brutale** : Logstash bronche **~1 seconde**, et Scalingo punit
> l'app de **5 minutes** de logs jetés. Un micro-hoquet devient un blackout.

### 3.3 Pourquoi api et pas web/connect (même mécanisme !)

Le drain est **identique** pour les 3 apps. La différence est le **débit** :

| App | req/min vers le drain | régime |
|---|---|---|
| **api** | **~6 000-8 000** (59 % du volume total) | proche saturation |
| web | ~1 000-1 300 | large marge |
| connect | ~1 200-1 600 | large marge |

api pousse **5-6× plus**. Le mot-clé de la doc est « **CONSÉCUTIVES** » :

- **api ≈ 100-130 req/s** → un hoquet Logstash d'**1 s** = des dizaines de lignes
  qui échouent **à la suite** → seuil de **10 consécutives franchi instantanément**
  → quarantaine.
- **web/connect ≈ 20-25 req/s** → pendant le même hoquet, trop peu de lignes en vol
  pour enchaîner 10 échecs avant que le hoquet passe → **pas de quarantaine**.

C'est exactement ce que montrent les compteurs de 17:36 : web/connect ont **senti**
le même hoquet (quelques 429/499 épars) mais n'ont **jamais** basculé.

> **Analogie** : 3 éviers, **même tuyau d'évacuation**, mais le robinet d'api est
> ouvert 6× plus grand. Un bouchon momentané ne fait déborder que l'évier dont
> l'arrivée dépasse l'évacuation ralentie.

**Correctif actuel** : 4× XL réduit la fréquence des hoquets → moins de
déclenchements → plus de perte observée. Mais c'est une **atténuation** : un seul
hoquet suffit toujours à quarantiner api, et le seuil devient **plus facile à
atteindre à mesure qu'api grossit**. → cf. Next steps.

---

## 4. Déroulé du diagnostic & fausses pistes écartées

Le diagnostic a été **sinueux** ; consigner les impasses évite de les refaire.

| Hypothèse | Verdict | Preuve qui l'élimine |
|---|---|---|
| GC death-spiral (comme juin) | ⚠️ Réel en juin, **pas** la cause ici | Blackout total à **0 % CPU** — un GC consomme du CPU |
| **OOM** (suite à un `-Xmx2g` posé par erreur) | ❌ Éliminé | Mémoire **plate ~1,3 Go**, jamais proche des 2 Go. *(Et `-Xmx2g` sur XL 2 Go = piège, cf. conventions.)* |
| ES saturé (backpressure) | ✅ **Cause du mode A** | 0 % CPU sur **tous** les conteneurs, 429 répartis sur toutes les apps, trou index global |
| Coût de traitement des events api | ❌ Éliminé | Durées **identiques** entre apps (api la plus basse) |
| Saturation de volume au pic | ❌ Éliminé (pour le mode B) | Le trou api arrive à **bas volume** |
| fsync de la PQ | ❌ Éliminé (comme cause des pics) | Les pics de latence existaient **avec ET sans** PQ |
| **Quarantaine drain (api)** | ✅ **Cause du mode B** | api → 0 pendant 5 min pile, web/connect continus, doc Scalingo, 499 groupés |

**Outil de diagnostic clé** : les **router logs** contiennent l'app source dans le
path (`?appname=pass-emploi-api-prod`) → on peut ventiler volume, 429, 499 et trous
**par app**. C'est ce qui a isolé le mode B. Détail dans [conventions.md](./conventions.md#playbook-de-diagnostic).

---

## 5. Garde-fous appris à la dure

Résumé — détail complet dans [conventions.md](./conventions.md) :

- **XL Scalingo = 2 Go** (pas 4) → **`-Xmx` ≤ ~1 Go**. `-Xmx2g` = OOM-kill.
- **Heap piloté via `JAVA_OPTS`**, jamais `LS_JAVA_OPTS` (écrasé par le buildpack).
- **Signatures** : 0 % CPU global = backpressure ES (mode A) ; trou d'une seule app
  = quarantaine drain (mode B) ; latence bimodale = pause stop-the-world (GC).

---

## 6. État actuel & décisions ouvertes

Config déployée au 2026-07-02 :

- **4× XL** (2 Go), heap **`-Xms1g -Xmx1g`** (posé via `JAVA_OPTS`).
- **PQ retirée** (du repo et du déployé) — **temporairement**, pour un test
  GC-vs-ES en cours (`JAVA_OPTS="… -Xlog:gc,safepoint:…"`).
- Plus de perte observée ; response time plat au pic.

Décisions à trancher :

- [ ] **Remettre la PQ** ? C'est le **filet du mode A** (backpressure ES). Retirée
      pour isoler le fsync pendant le test ; à réintégrer une fois le test clos,
      sauf si on adopte l'archi découplée (§7) qui la rend structurelle.
- [ ] **Retirer `-Xlog:gc,safepoint`** de `JAVA_OPTS` après le test (verbeux :
      pollue le drain + stockage ES). Garder `-Xlog:gc+init` (boot only).
- [ ] Statuer sur la config heap durable dans `jvm.options` vs `JAVA_OPTS`
      (aujourd'hui le heap réel vient de `JAVA_OPTS`).

---

## 7. Next steps — tenir à x10 {#7-next-steps--tenir-à-x10}

**Le scaling horizontal est une piste, pas une architecture.** À x10 (~350k req/min),
Logstash n'est pas ce qui casse — ce sont **le drain et ES**. ~40 instances XL en
linéaire serait cher **et** ne réglerait pas les deux plafonds :

1. **Drain HTTP Scalingo** : la quarantaine se déclenche sur 10 échecs
   **consécutifs**. Plus api grossit, plus le moindre hoquet atteint 10 consécutifs
   → quarantaines **plus fréquentes et qui escaladent** (5→10→15 min). Ajouter des
   instances réduit les hoquets mais **ne supprime pas** ce mode.
2. **Elasticsearch** : à x10 d'ingestion, si le cluster ne suit pas, Logstash bloque
   quel que soit le nombre d'instances (goulot **partagé**).

### Cause structurelle à casser

Aujourd'hui, le **pipeline lourd** (regex/kv/json/ruby de `logstash.conf`) tourne
**sur le chemin d'ACK de l'input HTTP**. Donc un batch lent = ACK lent = le drain
timeout (`499`) = quarantaine. **Il faut découpler *recevoir* de *traiter*.**

### Option A — natif Logstash (à faire en premier, proportionné)

Deux pipelines (pipeline-to-pipeline) :

- **`ingest`** : `http input → persisted queue`, **zéro filtre** → ACK **rapide et
  constant** → le drain ne timeout plus → **plus de quarantaine**.
- **`process`** : lit la queue → filtres lourds → ES, **à son rythme**, découplé de
  l'ACK et d'ES.

Meilleur rapport effort/gain : supprime la cause racine de la quarantaine sans
changer d'infra, et rend la PQ structurelle (mode A couvert aussi).

### Option B — broker (si on vise vraiment gros)

`apps → Kafka/Redis → consumers Logstash → ES`. Découplage total, absorbe les
bursts, **rejouable**, aucune quarantaine. Archi standard des pipelines de logs à
haut volume. Plus lourde à opérer → quand l'option A ne suffit plus.

### Leviers complémentaires

- **Scaler ES en parallèle** : data streams + ILM + sharding correct + capacité
  d'ingestion (nœuds dédiés au besoin). Incontournable à x10.
- **Réduire le coût PAR ÉVÉNEMENT** (≠ réduire le volume, qu'on veut garder) :
  déporter du parsing vers les **ingest pipelines ES**, alléger les regex, `drop`
  au plus tôt. Chaque instance encaisse alors davantage.

### Le chiffre qui manque pour planifier

Mesurer le **plafond d'UNE instance** : à quel req/min une seule commence à faire
des 429/499 ? → donne (a) la marge linéaire réelle et (b) **le volume auquel on tape
le plafond drain/ES**, donc quand basculer sur l'option A puis B.

---

## 8. Leçons à retenir

1. **Un blackout de logs n'est pas forcément Logstash.** Ici la cause finale
   (mode B) est **en amont** : la quarantaine du drain Scalingo. Toujours vérifier
   **où** le trou naît (drain ? input ? output ? ES ?) via les router logs par app.
2. **Même mécanisme ≠ même comportement.** Le drain est identique pour les 3 apps ;
   seule api bascule, parce qu'elle tourne près du plafond (ρ→1). Raisonner en
   **taux d'utilisation**, pas en « ça marche pour les autres ».
3. **10 échecs *consécutifs* = piège des flux à haut débit.** Un seuil « consécutif »
   se franchit d'autant plus vite que le débit est élevé → punit toujours la plus
   grosse app en premier.
4. **XL Scalingo = 2 Go** → `-Xmx` plafonné à ~1 Go ; heap piloté via `JAVA_OPTS`
   (pas `LS_JAVA_OPTS`). Vérifier au boot avec `-Xlog:gc+init`.
5. **Diagnostiquer sur la donnée du moment T, pas sur une fenêtre saine.** Une grande
   part du temps perdu venait de fenêtres de logs qui **ne couvraient pas** le trou.
6. **Scaler horizontalement gagne du temps, pas une architecture.** Pour x10,
   découpler *recevoir* (ACK rapide) de *traiter* (filtres + ES).
