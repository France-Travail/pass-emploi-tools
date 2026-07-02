# Conventions & garde-fous — ingestion des logs (drain → Logstash → ES)

> **Type** : référence (Diataxis). Les invariants durables de la chaîne d'ingestion
> de logs mutualisée : signatures de panne, garde-fous JVM/Scalingo, playbook de
> diagnostic. Sert aussi de **contexte de reprise** pour une session outillée.
>
> Récit de l'incident qui a produit ces règles : [postmortem-2026-07.md](./postmortem-2026-07.md).
> Conventions ECS du logging applicatif (autre sujet) :
> [../logs-ecs/](../logs-ecs/README.md).

## La chaîne (modèle mental)

```
apps (api / web / connect)  ──drain HTTP Scalingo──►  Logstash mutualisé  ──bulk──►  Elastic Cloud
   stdout                    (POST, par app)          (4× XL, logstash.conf)          (index logs-*)
```

- Infra : `pass-emploi-tools/logs/` — app Scalingo `pass-emploi-logstash-prod`,
  région `osc-secnum-fr1`, buildpack `Scalingo/logstash-buildpack`.
- Chaque app source a **son propre drain** (indépendant) vers l'app logstash ; le
  **router Scalingo** répartit sur les instances logstash.

## Les 2 modes de panne — signatures

| | **Mode A — blackout TOTAL** | **Mode B — trou d'UNE app** |
|---|---|---|
| Portée | toutes les apps ensemble | une seule (la plus grosse : api) |
| Cause | contre-pression **output ES** | **quarantaine du drain Scalingo** |
| Où | dans Logstash (output bloqué) | **en amont** de Logstash (drain) |
| Signature | **0 % CPU sur TOUS les conteneurs**, mémoire plate, 429 sur toutes les apps | une app à **0 pendant ~5 min pile**, autres continues, bouffée de **499** avant |
| Fix | **persistent queue** + scaling | découpler recevoir/traiter (cf. x10) ; atténué par + d'instances |

## Garde-fous durables (ne pas se faire avoir)

1. **Conteneur XL Scalingo = 2 Go** (pas 4). Donc **`-Xmx` ≤ ~1-1,2 Go** : Logstash
   consomme ~0,8-1 Go **hors heap** (Netty/direct memory, JRuby, metaspace, threads)
   + l'OS. **`-Xmx2g` sur XL 2 Go = 100 % du conteneur → OOM-kill → restart →
   blackout.**
2. **Heap piloté UNIQUEMENT par la var d'env Scalingo `JAVA_OPTS`**, jamais
   `LS_JAVA_OPTS`. Le wrapper du buildpack (`bin/logstash`) fait :
   ```
   if JAVA_OPTS contient "-Xms" : LS_JAVA_OPTS="$JAVA_OPTS"        (pas de -Xms128m)
   sinon                        : LS_JAVA_OPTS="-Xms128m $JAVA_OPTS"
   puis: unset JAVA_OPTS
   ```
   → une var `LS_JAVA_OPTS` posée en env est **toujours écrasée** ; le `-Xms` de
   `jvm.options` est **inerte** (le buildpack force `-Xms128m` sauf si `JAVA_OPTS`
   contient `-Xms`). Heap fixe → `JAVA_OPTS="-Xms1g -Xmx1g"`.
3. **Quarantaine du drain Scalingo** = **10 lignes consécutives** refusées → drain
   quarantiné **5 min** (aucun log envoyé), escalade **10/15/20 min**. Frappe la
   **plus grosse** app en premier (api ≈ 59 % du volume, ~5-6× web/connect) : elle
   atteint 10 refus consécutifs le plus vite. Un hoquet Logstash d'1 s = blackout de
   5 min pour api. *(Amplification énorme — c'est le mode B.)*
4. **Persistent queue** (`queue.type: persisted`) = buffer **disque** (pas RAM),
   sous `/app` (writable, éphémère). `queue.max_bytes` = plafond avant contre-pression
   (~64 Mo au repos). C'est le **filet du mode A**. ⚠️ Éphémère : survit aux blips ES,
   pas à un restart ; le fsync peut rallonger l'ACK → à surveiller vs les 499.
5. **`scalingo run` = one-off isolé** : ne voit **pas** le `localhost:9600` de l'app
   web (réseau séparé), voit une autre RAM. Non représentatif pour mesurer heap/API.

## Playbook de diagnostic {#playbook-de-diagnostic}

1. **Travailler sur la donnée du MOMENT T du trou**, pas une fenêtre saine (source
   n°1 de temps perdu dans cet incident).
2. **Router logs = l'arme principale** : le path contient `appname=<source>`.
   Ventiler par app :
   - `grep -oE 'appname=[a-z0-9-]+' F | sort | uniq -c` → volume par app.
   - idem filtré `status=429` / `status=499` → qui est puni.
   - **200/min par app** autour du trou → **quelle app tombe à 0** (une seule = mode B).
   - trous de secondes sans requête → durée réelle du blackout.
3. **GC vs ES** (pics de response time) : activer `JAVA_OPTS="-Xms1g -Xmx1g
   -Xlog:gc,safepoint:stderr:utctime,level,tags"`, lire les logs **de l'app logstash** :
   pic **avec** `Pause … ms` = GC ; pic **sans** = ES (corréler au monitoring Elastic
   Cloud). **Retirer après** (verbeux).
4. **Codes** : **429** = input plein (backpressure) ; **499** = le drain a coupé
   (Logstash trop lent à répondre) ; **0 requête** d'une app = son drain en quarantaine.

## Fausses pistes (écartées — ne pas y retourner sans raison nouvelle)

GC actuel (0 % CPU pendant les trous), OOM (mémoire plate ~1,3 Go), coût de
traitement d'api (durées égales aux autres apps), saturation de volume (le trou api
arrive à bas régime), fsync PQ (pics présents avec ET sans PQ).

## Direction pour tenir à x10 (le vrai chantier)

Le scaling horizontal ne règle **ni le drain ni ES**. Cause structurelle : les
**filtres lourds tournent sur le chemin d'ACK** de l'input HTTP → ACK lent → 499 →
quarantaine. **Découpler recevoir de traiter** :

- **Option A (natif Logstash, à faire en premier)** : 2 pipelines — `ingest`
  (`http → PQ`, zéro filtre, ACK rapide) + `process` (`PQ → filtres → ES`). Supprime
  la quarantaine à la racine et rend la PQ structurelle.
- **Option B (gros volume)** : broker Kafka/Redis entre apps et Logstash.
- **En parallèle** : scaler ES (data streams/ILM/ingest nodes) ; déporter du parsing
  vers les **ingest pipelines ES** (réduire le coût **par event**, pas le volume).
- **À mesurer** : plafond d'**une** instance (req/min avant 429/499) → marge linéaire
  + seuil de bascule vers l'option A puis B.

Détail et justification : [postmortem-2026-07.md § 7](./postmortem-2026-07.md#7-next-steps--tenir-à-x10).

## État déployé — VOLATILE, vérifier avant d'agir

> ⚠️ Cette section date (≠ invariant). Vérifier l'état réel sur Scalingo avant toute
> action. Au **2026-07-02** :

- **4× XL** (2 Go), heap **`-Xms1g -Xmx1g`** via `JAVA_OPTS`.
- **PQ retirée** temporairement (test GC-vs-ES) ; `-Xlog:gc,safepoint` activé
  temporairement via `JAVA_OPTS`.
- Plus de perte observée, response time plat au pic (~35k req/min).
- Décisions ouvertes : remettre la PQ (filet mode A), retirer le GC verbeux après
  test, statuer heap `jvm.options` vs `JAVA_OPTS`. Cf. postmortem § 6.
