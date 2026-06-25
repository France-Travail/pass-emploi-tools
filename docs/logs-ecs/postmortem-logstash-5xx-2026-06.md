# Post-mortem — 5xx & pics de latence sur le Logstash mutualisé (juin 2026)

> **Type** : explication (Diataxis). Document de compréhension : comment Logstash
> fonctionne, pourquoi l'incident s'est produit, et comment lire les indicateurs
> qu'on a mis en place. Pour la config ES / l'historique des autres incidents,
> voir [infra-elasticsearch.md](./infra-elasticsearch.md).

## TL;DR

Le Logstash mutualisé (`pass-emploi-tools/logs/`, Logstash 9.0.1 sur Scalingo)
renvoyait des **5xx constants aux heures de charge** (8h–18h) et des **pics de
response time** (p99 jusqu'à ~12 s), avec des **crashs/restarts** périodiques.

**Cause racine** : la heap JVM était laissée au **défaut** (25 % de la RAM *vue*
par la JVM). Et sur Scalingo, la JVM **sous-détecte la RAM du conteneur** (cgroup
→ ~2 Go vus) → le défaut tombe à **~512 Mo, y compris sur un conteneur XL (4 Go)**
(mesuré : `Heap Max Capacity: 512M` au boot d'un XL). 512 Mo est trop peu pour
Logstash (≥ 1 Go). Conséquences en cascade :

1. Heap saturée → **`OutOfMemoryError`** → crash → restart (boucle).
2. Sur les petits conteneurs (< 2 CPU), la JVM choisit en plus **SerialGC**
   (mono-thread) → **pauses stop-the-world de plusieurs secondes**.
3. Pendant une pause GC, **Netty (l'input HTTP) est figé** → les POST du
   log-drain partent en timeout → **5xx + pics de latence**.
4. Le RSS du process (~1,3–1,5 Go) dépasse la marge d'un L → **swap**, qui
   ralentit encore le GC (relecture heap depuis le disque).

**Correctif** : **fixer `-Xmx` explicitement (obligatoire)** — le défaut n'est
*jamais* fiable à cause de la sous-détection cgroup. Config cible :
**conteneur XL + `-Xms1g`/`-Xmx1g` + `-XX:+UseG1GC`**. Le XL apporte G1 (bonnes
pauses) et la marge off-heap, mais **ne suffit pas seul** : sans `-Xmx`, la heap
reste à 512 Mo même en XL.

---

## 1. Comment fonctionne Logstash (le modèle mental)

Logstash est un **pipeline de traitement de logs** en 3 étages :

```
   INPUT          →        FILTER         →        OUTPUT
(on reçoit)          (on transforme)          (on envoie)

http (port $PORT)    json, mutate, drop...    elasticsearch (bulk)
```

Chez nous : toutes les apps (api, connect, web) envoient leurs logs via le
**log-drain Scalingo** (des POST HTTP) vers ce Logstash unique, qui parse /
nettoie / route (`logstash.conf`) puis pousse vers Elastic Cloud.

### La techno en dessous : JVM, JRuby, Netty

Point clé pour comprendre l'incident :

- Logstash est une appli **Java** → tourne dans une **JVM**.
- Sa config (`logstash.conf`) est interprétée en **Ruby**, exécuté **dans** la
  JVM via **JRuby**.
- L'input `http` (réception des POST du drain) est géré par **Netty**, la lib
  réseau Java.

```
        ┌─────────────────────────────────────────────┐
        │                  JVM (Java)                  │
        │   Netty  ──►  JRuby (filtres .conf)  ──►      │ ──► Elasticsearch
        │  (réseau)      (transformation)              │
        │   Tout ça vit dans la MÉMOIRE de la JVM      │
        └─────────────────────────────────────────────┘
```

**Tout ce monde partage la mémoire du même process.** D'où l'importance critique
du dimensionnement mémoire.

### La file d'attente (queue) et les workers

Entre l'input et la sortie il y a une **queue en mémoire** (dans la heap) :

- l'input **pousse** les events dans la queue ;
- des **workers** (threads, `pipeline.workers`, défaut = nb de vCPU) les
  **tirent**, appliquent les filtres, puis l'output envoie en **bulk** à ES ;
- capacité « en vol » = `pipeline.workers` × `pipeline.batch.size` (125 par défaut).

**Backpressure (contre-pression)** : si ES ralentit, les workers tirent moins
vite, la queue se remplit, et l'input **se bloque en poussant** → il ne lit plus
les POST → 5xx possibles **aussi**, mais d'origine ES (à distinguer du GC, cf. §3).

---

## 2. La mémoire JVM : heap, off-heap, RSS, GC

### Heap vs off-heap vs RSS

| Zone | Contrôlée par | Contenu |
|---|---|---|
| **Heap** | `-Xms` / `-Xmx` | Objets Java/Ruby : events en traitement, queue, batchs |
| **Off-heap** | *non* contrôlée par `-Xmx` | Buffers Netty, moteur JRuby, metaspace, threads (~300–500 Mo) |
| **RSS** | — (= ce que l'OS voit) | **heap utilisée + off-heap + reste** ≈ 1,3–1,5 Go |

- `-Xmx` = **plafond** de la heap (un mur, pas une réservation). La dépasser =
  `OutOfMemoryError` → crash.
- **Sans `-Xmx`**, la JVM prend par défaut **25 % de la RAM du conteneur**.
  - L (2 Go) → ~512 Mo de heap ← **trop petit, cause du bug**.
  - XL (4 Go) → ~1 Go de heap ← suffisant (on a mesuré un pic réel à 559 Mo).
- **C'est le RSS qui compte pour le conteneur**, pas seulement `-Xmx`. Un RSS de
  ~1,4 Go sur un L (2 Go) laisse peu de marge → **swap**.

### Le Garbage Collector (GC) et les pauses stop-the-world

Java libère la mémoire automatiquement via un **ramasse-miettes**. Pour faire son
ménage, il met parfois **tout le reste en pause** (**pause stop-the-world**).
Pendant cette pause, **Netty ne répond plus** → timeouts → 5xx.

Deux GC en jeu ici :

| GC | Quand la JVM le choisit | Comportement |
|---|---|---|
| **SerialGC** | machine détectée « petite » (< 2 Go **ou** < 2 CPU) | mono-thread, **pauses longues** (jusqu'à plusieurs secondes) |
| **G1GC** | machine « server-class » (≥ 2 Go **et** ≥ 2 CPU) | concurrent, **pauses courtes** (< 50 ms) |

> ⚠️ **Découverte clé de l'incident** : sur les conteneurs **L**, la JVM
> auto-sélectionnait **SerialGC** → pauses multi-secondes. Sur **XL**, elle prend
> **G1** → pauses < 50 ms. `-Xmx` ne contrôle **pas** ce choix ; pour le forcer
> indépendamment de la taille, utiliser `-XX:+UseG1GC`.

### La chaîne causale complète

```
heap par défaut (512 Mo sur L, trop petit)
   → GC sous pression permanente + JVM en SerialGC + swap
   → pauses stop-the-world de plusieurs secondes
   → Netty figé → POST du drain en timeout
   → 5xx constants + pics de response time aux heures de charge
   → à terme OutOfMemoryError → crash → restart
```

---

## 3. Les indicateurs mis en place et comment les lire

Deux instrumentations **temporaires** ont été ajoutées pour le diagnostic
(à retirer après la campagne de mesure) :

### a) Node stats (`ns_*`) via `http_poller`

L'API de stats interne de Logstash (`http://127.0.0.1:9600/_node/stats`) est
interrogée toutes les 10 s par un input `http_poller`, et on en extrait 5 champs
(le doc complet ~30 Ko est tronqué par le drain à 16 Ko → on extrait en pipeline
avant `stdout`). **Ce sont des compteurs cumulés** : ce qui compte est la
**différence entre deux relevés**, pas la valeur absolue.

| Indicateur | Ce que c'est | Comment l'interpréter |
|---|---|---|
| `ns_in` | events **entrés** (cumulé) | pente = débit d'entrée (Δ / 10 s) |
| `ns_out` | events **sortis** vers ES (cumulé) | doit coller à `ns_in` ; s'il décroche → ça s'accumule |
| `ns_filtered` | events ayant traversé les filtres | ≈ `ns_in` (sauf drops, ex. bots) |
| `ns_qpush_ms` | temps total où l'input est **bloqué à pousser** dans la queue (cumulé, ms) | **indicateur de backpressure** : grimpe vite → ES est le goulot ; reste plat → pas de backpressure |
| `ns_dur_ms` | temps total passé **dans les filtres** (cumulé, ms) | coût CPU du filtrage |

**Lecture type (état sain mesuré)** : `ns_out`/`ns_in` ≈ 99,6 % (rien ne
s'accumule, ES suit) et `ns_qpush_ms` ≈ 0,5 % de `ns_dur_ms` (pas de
backpressure). → le tuyau coule, la sortie n'est pas bouchée.

### b) GC logging (`-Xlog`)

Ajouté dans `jvm.options` :

```
-Xlog:gc,safepoint:stderr:utctime,level,tags
```

- `gc` = une ligne par GC avec **la durée de pause** ;
- `safepoint` = toutes les pauses stop-the-world (pas que GC) ;
- `utctime` = pour s'aligner sur les timestamps Logstash.

**Comment lire une ligne GC** :

```
GC(1007) Pause Young (Allocation Failure) 579M->351M(822M) 9.972ms
         └─ type de pause       heap avant→après(committed)  └─ DURÉE de la pause
```

- `579M->351M` : heap utilisée avant → après (ici 228 Mo libérés).
- `(822M)` : heap actuellement réservée (grandit jusqu'à `-Xmx`).
- `9.972ms` : **la valeur à surveiller**. < 50 ms = sain. Plusieurs secondes =
  c'est ce qui fige Netty.

Le **type de pause** est parlant : `Pause Full` = pire cas (collecte toute la
heap, tout est arrêté) ; `Pause Young` = collecte de la jeune génération (normal,
court en G1). Et la **première ligne au boot** (`Using Serial` / `Using G1`)
révèle le GC choisi — déterminant.

### Les 3 causes possibles de 5xx, et comment chacune se voit

1. **GC / mémoire** (notre cas) → pauses GC longues dans `-Xlog`, swap, heap
   pleine, `OutOfMemoryError`. `ns_qpush_ms` reste **plat** (l'input n'est pas
   bloqué par la queue, il est figé par le GC).
2. **ES saturé (backpressure)** → `ns_qpush_ms` **grimpe vite**, `ns_out`
   décroche de `ns_in`, erreurs 429/retry côté ES. *(Éliminé : 0 retry/429.)*
3. **Filtrage trop coûteux** → `ns_dur_ms` explose, CPU à 100 %.
   *(Éliminé : CPU ~40 %.)*

---

## 4. Déroulé du diagnostic (preuves)

> ⚠️ **Subtilité chronologique** : le GC logging n'a été déployé que vers 12:40.
> Le diagnostic du matin reposait donc sur les **`OutOfMemoryError` directs** (pas
> sur des durées de pause, qu'on n'avait pas encore). Les pauses GC chronométrées
> n'ont confirmé le mécanisme qu'en début d'après-midi.

| Fenêtre | État conteneur | GC log ? | Preuve observée |
|---|---|---|---|
| 08h–10h | 1× L, **sans `-Xmx`** (~512 Mo) | ❌ | `OutOfMemoryError: Java heap space` répétés → crash loop |
| 10h–12h | 1× L, `-Xmx1g` | ❌ | plus d'OOM ; spike résiduel 11:22 (inféré GC, non chronométré) |
| 12:22–14:14 | **2× L**, `-Xmx1g`, **SerialGC** | ✅ | **pauses Full 4–6,7 s** + swap des **deux** conteneurs |
| 14:15+ | **1× XL**, `-Xmx1g`, **G1GC** | ✅ | pauses **max ~34 ms**, heap ~559 Mo, aucun OOM → **sain** |

**Exemples de pauses GC longues capturées (fenêtre 2× L, SerialGC)** :

| Heure (CEST) | Conteneur | Ligne de log |
|---|---|---|
| 12:46:53 | web-1 | `Pause Full (CodeCache GC Threshold) 406M->329M(797M) `**`5410 ms`** |
| 13:37:14 | web-2 | `Pause Young (Allocation Failure) 580M->354M(819M) `**`6672 ms`** |
| 13:51:00 | web-2 | `Pause Full (CodeCache GC Threshold) 398M->341M(824M) `**`6279 ms`** |

→ Une pause de **6,7 s** = Netty figé 6,7 s = tous les POST du drain en timeout
pendant ce temps. CQFD pour le lien GC → 5xx.

### Pourquoi le scaling **horizontal** (2× L) ne résout rien

Le scaling horizontal répartit le **débit de requêtes**, mais **pas l'empreinte
mémoire par process**. Chaque JVM Logstash porte son ~1,3–1,5 Go de RSS quel que
soit le volume traité → sur des L, **les deux conteneurs swappent même à
demi-charge**. C'est ce qu'on a observé. **L'incident est un problème de footprint
par process, pas de throughput** → la réponse est **verticale** (XL), pas
horizontale.

```
Problème : swap en prod
├─ Débit trop élevé pour 1 process (faible) ✗ ÉLIMINÉ
│  └─ 2× L à demi-charge swappent quand même → pas le débit
└─ Empreinte mémoire/process > RAM d'un L (HAUTE) ✓ CONFIRMÉ
   ├─ RSS ~1,3–1,5 Go > marge utile d'un L (2 Go) → swap
   └─ XL (4 Go) : RSS tient en RAM, G1, GC < 50 ms → sain
```

---

## 5. Décision & correctif

**Le défaut heap n'est jamais fiable.** On a longtemps cru que « passer en XL
suffirait seul » (en supposant un défaut de 25 % × 4 Go = 1 Go). **C'est faux** :
la JVM **sous-détecte la RAM** du conteneur sur Scalingo (cgroup → ~2 Go vus même
sur un XL de 4 Go), donc le défaut reste **512 Mo quelle que soit la taille**
(mesuré : `Heap Max Capacity: 512M` au boot d'un XL le 25/06). Le XL apporte G1
(via ≥ 2 CPU) et la marge off-heap, mais **pas** une heap plus grande.

→ **Fixer `-Xmx` explicitement devient obligatoire**, pas optionnel.

| Levier | Verdict | Justification |
|---|---|---|
| **Fixer `-Xms1g`/`-Xmx1g`** | ✅ **Obligatoire** | le défaut tombe à 512 Mo même en XL (sous-détection cgroup) → OOM. 1 Go suffit (pic réel ~559 Mo) |
| **Conteneur XL** | ✅ Nécessaire | ≥ 2 CPU → G1 auto ; 4 Go réels → marge off-heap. Mais **insuffisant seul** sans `-Xmx` |
| **`-XX:+UseG1GC`** | ✅ Recommandé | verrouille G1 quelle que soit la taille/le CPU détectés (évite le downgrade Serial) |
| **`-w` (workers)** | ❌ Laisser le défaut | pas une cause racine ; levier de throughput secondaire |
| **Override `LS_JAVA_OPTS`** | 👍 Échappatoire | permet de surcharger `-Xmx` ou d'activer le GC verbeux **sans redéployer** (appendé après `jvm.options`) |

**Config cible figée** : **conteneur XL + `-Xms1g`/`-Xmx1g` + `-XX:+UseG1GC`,
workers au défaut.** Override d'urgence via `LS_JAVA_OPTS`.

### Mesures finales (campagne 24–25/06)

Instrumentation identique sur tous les paliers (`gc+init` au boot + `gc,safepoint`
+ `ns_*`), heap au **défaut** pour observer le comportement brut.

| Palier | GC au boot | Heap max (défaut) | Pause GC max | OOM/crash | Verdict |
|---|---|---|---|---|---|
| **1× L** | **Serial** | 512 Mo | (OOM avant pauses longues) | **7× OOM + crash** (16:58) | ❌ inutilisable |
| **2× L** | **Serial** | 512 Mo | — | les 2 conteneurs en **swap** d'emblée | ❌ horizontal inutile |
| **1× XL** (défaut) | **G1** | **512 Mo** ⚠️ | < 0,5 s | 0 (mais charge faible, fin de journée) | ⚠️ tient à basse charge, **bombe à retardement en pointe** (heap 512 Mo) |
| **1× XL + `-Xmx1g`** (aprèm 24/06) | **G1** | 1 Go | **~34 ms** | 0 | ✅ **sain** (réf.) |

**Lecture clé** : le palier « 1× XL défaut » prouve la sous-détection (G1 mais
heap 512 Mo) ; le palier « 1× XL + `-Xmx1g` » est la seule config saine sous
charge réelle. *(Le « XL sain » reste à reconfirmer sur une journée de pointe
complète avec la config cible.)*

---

## 6. Monitoring & réactivation du diagnostic (doctrine)

**Principe : diagnostic ≠ monitoring.** Les signaux permanents sont des
**métriques** (légères) ; les logs verbeux sont **opt-in** (le temps d'un
incident), jamais en dur.

| Besoin | Outil | Statut |
|---|---|---|
| Santé opérationnelle continue | Métriques **Scalingo** (CPU/RAM/**swap**/5xx/RPM) + autoscaler | ✅ déjà là, sans maintenance — `swap` et `5xx` = meilleurs voyants |
| Empreinte JVM au boot | `-Xlog:gc+init` (heap max + GC) | ✅ gardé en dur (coût négligeable) |
| Pauses GC en incident | `LS_JAVA_OPTS="-Xlog:gc,safepoint:…"` + restart | 🔁 opt-in, à retirer après |
| Internes Logstash en continu (queue, GC time…) | **Metricbeat** / Elastic Agent → index monitoring | 💡 si besoin un jour ; **ne pas** reconstruire le `http_poller` maison |

**Réactiver le GC verbeux en incident** (sans redéployer) : poser la variable
Scalingo `LS_JAVA_OPTS="-Xlog:gc,safepoint:stderr:utctime,level,tags"`, restart,
puis la retirer une fois clos.

## 7. Suites & nettoyage

- [x] Figer la config cible (`jvm.options` : `-Xms1g`/`-Xmx1g`/`-XX:+UseG1GC`).
- [x] Retirer l'instrumentation temporaire (`http_poller` + `nodestats` dans
      `logstash.conf` ; `-Xlog:gc,safepoint` passé en opt-in `LS_JAVA_OPTS`).
- [x] Garder `-Xlog:gc+init` (empreinte de boot permanente).
- [ ] **Reconfirmer le XL+`-Xmx1g` sur une journée de pointe complète.**
- [ ] **Sécurité** : le credential ES (`ELASTICSEARCH_*`, user `logstash`) a fuité
      en clair lors du diagnostic → **à rotationner** sur Elastic Cloud + mettre à
      jour la variable Scalingo.

## 8. Leçons à retenir

1. **Toujours fixer `-Xmx` explicitement** pour une JVM en conteneur. Le défaut
   (25 % de la RAM *vue*) est piégeux : sur Scalingo la JVM **sous-détecte la
   RAM** (cgroup) → 512 Mo même sur un XL de 4 Go. Vérifier au boot avec
   `-Xlog:gc+init` (« Heap Max Capacity »). `scalingo run` n'est **pas**
   représentatif (one-off de taille différente, voit la RAM de l'hôte).
2. **Le choix Serial/G1 dépend du CPU détecté**, pas de `-Xmx` : sur un petit
   conteneur (< 2 CPU), downgrade SerialGC → pauses multi-secondes. Verrouiller
   avec `-XX:+UseG1GC`.
3. **Pour une appli mono-process gourmande en mémoire, scaler verticalement**, pas
   horizontalement : l'horizontal ne réduit pas l'empreinte par process (les 2× L
   swappaient les deux à demi-charge).
4. **Distinguer les origines de 5xx** via les bons indicateurs : `ns_qpush_ms`
   (backpressure ES) vs pauses GC (`-Xlog`) vs CPU (filtrage). Ne pas confondre.
5. **Diagnostic verbeux = opt-in, jamais permanent.** Le piloter par env var
   (`LS_JAVA_OPTS`) pour l'activer en incident sans redéployer.