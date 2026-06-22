# Conventions logs ECS — transverse

> Socle **partagé api / connect / web**. Chaque repo l'implémente avec sa propre
> instance pino et sa propre liste de `event.action` ; les règles ci-dessous
> sont communes. Taxonomie spécifique d'un repo : voir son fichier dédié
> (api : [couverture-api](./couverture-api.md)).

## Finalités

Trois usages cibles structurent toute la démarche (détail : [kibana](./kibana.md)) :

- **Investigation incident** — reconstituer ce qui s'est passé pour un utilisateur / une requête.
- **Reporting métier** — compter les actions métier par structure / dispositif.
- **Monitoring technique** — détecter les pannes (partenaires, auth).

Principe directeur : **emit = faits, dashboard = interprétation**. La couche
d'émission logue des faits bruts (`status_code`, `url.path`, `error.*`) sans
juger ; c'est le dashboard qui classe bug / pas-bug.

## Taxonomie `event.action`

- **`message` = `event.action`** : verbe au passé, snake_case, low-cardinality,
  agrégeable (`request_completed`, `auth_succeeded`, `external_api_call`…).
- Pas d'interpolation dans `message` — les détails vont dans des champs séparés
  (`http.*`, `url.*`, `error.*`).
- Chaque repo définit sa liste de `event.action` selon ses étapes métier.

## `event.outcome`

`success` / `failure` uniquement → filtre transverse des dashboards. Posé sur
chaque log porteur d'un `event.action`.

## `log.level` — `info` / `error` pour l'opérationnel (`debug` opt-in en plus)

Pour les logs **opérationnels** (ceux qu'on lit en continu), deux niveaux
seulement : `info` / `error` (**pas de `warn`**). En plus de ça, `debug` existe
comme **niveau diagnostic opt-in** (cf. section dédiée plus bas) — il n'entre pas
dans la doctrine orthogonale ci-dessous, qui ne concerne que info/error.

`level` et `outcome` sont **deux axes orthogonaux** :

- **`level`** = « quelque chose a-t-il *cassé* ? » → `info` / `error`
- **`outcome`** = « l'opération a-t-elle *réussi* ? » → `success` / `failure`

| level | outcome | sens |
|---|---|---|
| info | success | nominal |
| info | failure | échec géré/attendu (erreur métier, 4xx partenaire) — pas un bug |
| error | failure | crash — exception non rattrapée, 5xx, erreur réseau |

`level` se dérive de la **nature** de l'erreur (crash vs échec géré), pas du
simple fait qu'il y ait une erreur. `warn` écarté : redondant dès que `outcome`
porte l'axe succès/échec.

### Doctrine : choisir le level (test d'actionabilité)

Critère = **« un humain doit-il regarder CETTE ligne, prise isolément ? »** — pas
le code HTTP. Donc actionabilité + à qui la faute :
- **5xx / panne de transport** → quelqu'un (partenaire ou notre infra) est cassé →
  **error**.
- **4xx (401/404/408…)** → **info**. Un 401 isolé ne prouve rien (token expiré +
  retry, ou conf) ; un 404 est souvent un résultat métier attendu ; un 408 est
  transient. Ce qui est un problème, c'est *un volume soutenu* de 4xx.
- Un per-event `level` **ne peut pas** capturer « soutenu » ni le contexte. La
  nuance 4xx vit donc dans les **alertes/dashboards rate-based** (ex. règle Kibana
  « > X 401/min »), jamais dans le `level` à l'émission.
- Si un jour les 400 « notre requête malformée » (= notre bug) se noient dans les
  401/404, alors seulement envisager `warn` — sur besoin réel, pas par anticipation.

### Panne de transport ≠ « erreur sans status » (raffinement appels sortants)

Sur les appels sortants (`external_api_call`), une panne de transport est une `err`
axios dont le status **n'est pas un refus HTTP volontaire** (`undefined || < 400`) :
body tronqué après des headers `200` (`aborted`, décompression Brotli interrompue),
ECONNRESET. Ces cas ont un `status_code` < 500 mais sont de vraies pannes → **error**.
Cf. `external-api-logger.helpers.ts` : `isCrash = status>=500 || (err && status<400/undefined)`.
Détail dans [couverture-api](./couverture-api.md).

### `debug` — niveau diagnostic opt-in (activable par `LOG_LEVEL`)

`debug` est un niveau **en plus** d'info/error, destiné à instrumenter des
parcours difficiles à reproduire (bugs de déconnexion / connexion remontés par un
utilisateur, où l'on veut un maximum de contexte si le cas se reproduit). Il est
**piloté par la var d'env `LOG_LEVEL`** (défaut `info`) : passer `LOG_LEVEL=debug`
sur un environnement (y compris prod, temporairement) active l'émission de ces
lignes ; tout autre niveau les coupe à la source.

- **Pas dans la doctrine info/error.** Un log `debug` ne porte pas la sémantique
  « quelque chose a cassé » ; il sert au diagnostic. Il peut ne pas porter
  `event.action`/`event.outcome`.
- **Reste soumis à la redaction** (cf. ci-dessous) : un `debug` qui dumpe un
  payload passe par `serializeBodyForLog` → secrets `[Redacted]`.
- **Contrainte de typage ES.** Un `debug` indexé doit respecter les mappings des
  index `logs-*`. En particulier, un champ libre qui dumpe un payload
  hétérogène (objet **ou** string selon les cas) provoque un
  `document_parsing_exception` (rejet 400). Cf. règle ci-dessous + [infra-elasticsearch](./infra-elasticsearch.md).

## Diagnostic libre → `labels.*`

Toute paire clé/valeur **arbitraire** (dump de payload, contexte de debug) va
dans `labels.<clé>`, **jamais** dans un champ générique inventé (`data`,
`payload`, `meta`…).

- ECS mappe `labels.*` en `keyword` de façon **stable** → pas de conflit.
- Un champ générique est mappé **dynamiquement** : son type est figé par le 1er
  document, et tout log de forme différente (string vs objet) est **rejeté**
  (ES 400). C'est un nom de champ qui collisionne par nature.
- Gros blob (> 1 Ko) dans `labels.*` : stocké dans `_source` mais **non indexé**
  (`ignore_above`) → retrouvable via `trace.id`, pas filtrable/agrégeable.

## Redaction & données sensibles

- **Secrets** masqués par `isSensitiveKey` : une clé dont le nom (insensible à
  la casse) **contient** `token` / `secret` / `password` / `authorization` /
  `bearer` / `api_key` / `apikey` / `credential` → valeur `[Redacted]`. Match
  par fragment (couvre `subject_token`, `access_token`, `client_secret`… sans
  énumérer). Volontairement **pas** `code` / `key` : collision avec des champs
  métier.
- **Redaction récursive** dans les payloads de forme arbitraire
  (`serializeBodyForLog`) : le `redact` natif de pino ne couvre que des chemins
  fixes connus, pas la descente récursive — d'où le helper.
- **Bodies de requête** logués sur **échec** (toujours) ; sur **succès**
  seulement si `LOG_LEVEL=debug`. Tronqués à 4 Ko. Binaire/stream →
  `[binary]` / `[stream]`.
- **PII « ordinaire »** (noms, dates, contenus métier) non masquable par clé :
  assumée — d'où le logging des bodies sur échec uniquement (en `info`).
- **Pas d'ID utilisateur dans les payloads applicatifs** —
  `user.{id,type,structure}` est propagé par le mixin pino via le `Context`
  (AsyncLocalStorage).

## Champs ECS

Champs standards : `event.*`, `error.*`, `http.*`, `url.*`, `user.*`,
`service.*` → flatten automatique côté Logstash. Tout nouveau sous-namespace
demande un ajout dans `logstash.conf`.

`error` au format ECS via **`toEcsError(error)`** : helper unique gérant Error
JS, erreur métier (code/message), valeur inconnue → `{type, message, stack_trace}`.

## Pattern d'archi : `rootLogger` + mixin

Chaque repo expose un **`rootLogger`** unique (singleton pino) utilisé partout :

```ts
rootLogger.info({ event: { action: 'xxx_yyy', outcome: 'success' } }, 'xxx_yyy')
```

Garanties :

- **Mixin pino** : injecte `user.*`, `trace.id`, `transaction.id` (depuis
  `Context` / APM) sur chaque log.
- **Redact pino natif** : chemins fixes sensibles (`Authorization`, `cookie`…).
- `pino-http` partage la même instance → même config sur les logs HTTP.

Pas de wrapper, pas de DI.

## Patterns d'instrumentation (transverses)

- **Appels sortants — deux familles, même `external_api_call`** :
  - **Clients axios** → base class `ExternalApiClient` (Template Method) qui émet
    automatiquement (`outcome`, `event.duration`, `http.*`, `url.*`, `error.*`,
    bodies sur échec). Chaque client partenaire en hérite (api).
  - **SDK non-axios** (openid-client, firebase-admin…) → helper explicite
    `logExternalCall(...)` autour de l'appel, **mêmes champs / même format** ECS.
  - Règle : aucun appel partenaire ne sort sans `external_api_call`. Côté api,
    `FirebaseClient` reste une piste (cf [couverture-api](./couverture-api.md)).
- **Corrélation cross-requête par clé métier** : quand un parcours s'étale sur
  plusieurs requêtes HTTP (login OIDC, workflow async) `trace.id` APM ne suffit
  pas (per-requête). Identifier une clé métier stable (connect : `interaction.uid`),
  la propager via le `Context`/`RequestContext` posé par un middleware, l'exposer
  en `labels.<nom>_id` via le mixin. Recherche Kibana : `labels.<nom>_id: "<val>"`.
  Jobs async : même logique avec `labels.job_run_id`.

## Adoption d'une nouvelle app / brique

Le socle est multi-apps (api / connect / web / futures briques). Pour chaque
nouvelle app : porter le socle pino (rootLogger, mixin, helpers de redaction),
le `RequestContext` (AsyncLocalStorage), choisir **un use case déclencheur**
investigable (api : RDV Milo ; connect : login MiLo jeune), définir sa liste finie
de `event.action`, instrumenter auth + handlers + appels sortants, brancher le
drain Scalingo vers le Logstash mutualisé, puis valider dans Kibana. Documenter la
taxonomie du repo dans un `couverture-<repo>.md` dédié.

## Pointeurs code de référence

| Sujet | Repo | Chemin |
|---|---|---|
| `rootLogger`, mixin, helpers | pass-emploi-api | `src/utils/logger.module.ts` |
| `Context` (AsyncLocalStorage) | pass-emploi-api | `src/building-blocks/context.ts` |
| `ExternalApiClient` (base axios) | pass-emploi-api | `src/infrastructure/clients/external-api-client.ts` |
| `logExternalCall` (SDK non-axios) | pass-emploi-connect | `src/utils/monitoring/external-call.logger.ts` |
| Logger + `RequestContext` connect | pass-emploi-connect | `src/utils/monitoring/{logger.module,request-context}.ts` |
| Logstash + templates ES | pass-emploi-tools | `logs/logstash.conf`, `logs/elastic/*.console` |

## Décisions durables (transverses)

- `event.action` = taxonomie unique (notion de « famille » abandonnée).
- `level` dérivé de la nature de l'erreur, pas de sa simple présence.
- Redaction par fragment de clé (`isSensitiveKey`), une liste unique partagée.
- Bodies logués sur échec ; succès → `debug` uniquement.
- Templates ES versionnés (voir [infra-elasticsearch](./infra-elasticsearch.md)).
- Logs router Scalingo reformatés ECS côté Logstash (`request_routed`).
- `apmService.captureError` conservé **en parallèle** des logs ECS (canal distinct).
- `event.action` deux familles d'appels sortants unifiées sous un même schéma.