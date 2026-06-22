# Logs ECS — pass-emploi-api

> Spécifique au repo **pass-emploi-api**. Conventions transverses :
> [conventions](./conventions.md). Refonte mergée (PR #228), en prod (v9.37.x).

## Taxonomie `event.action` (api)

| `event.action` | `log.logger` | site d'émission |
|---|---|---|
| `request_completed` / `request_failed` | _absent_ | requête HTTP entrante (pino-http) |
| `auth_succeeded` / `auth_failed` | `OidcAuthGuard` | validation JWT |
| `handler_executed` | `<X>{Command,Query,Job}Handler` | exécution handler CQRS |
| `external_api_call` | `MiloClient`, `PoleEmploiClient`, `PoleEmploiPartenaireClient`, `OidcClient`, `BrevoClient`, `MatomoClient`, `AntivirusClient`, `DiagorienteClient`, `ImmersionClient`, `ServiceCiviqueClient` | appel HTTP sortant |
| `request_routed` | _absent, `tags: router`_ | router Scalingo (émis par Logstash) |
| `accueil_sessions_milo_recuperees` (`failure`) | `GetAccueilJeuneMiloQueryHandler` | mode dégradé accueil : le `try/catch` autour des sessions Milo a avalé une exception → l'accueil répond 200 **sans sessions**. Seule trace de cette dégradation silencieuse (le `request_completed` voit un succès). Émis via `rootLogger.error` + `toEcsError`. |

## Couverture

HTTP entrant, auth OIDC, handlers CQRS, worker Bull, 10 clients HTTP externes,
logs router. `trace.id` corrélation bout en bout.

Spécificités api :

- **`handler_executed`** émis par les base classes CQRS (`logHandlerExecuted`).
  Discriminant crash / échec géré : `error instanceof Error` (les `DomainError`
  sont des `implements`, pas des `extends Error`).
- **`external_api_call`** via Template Method `ExternalApiClient` +
  `ExternalApiLoggerService`.
- **Bodies** : `http.request.body.content` (entrant via pino-http, sortant via
  `external_api_call`) sur échec, et sur succès si `LOG_LEVEL=debug` ;
  `http.response.body.content` côté partenaire. Voir [conventions](./conventions.md) (redaction).
- **Headers de diagnostic sur échec sortant** : un 401 partenaire ne dit rien
  dans le body, la cause OAuth est dans `WWW-Authenticate` (RFC 6750). Allowlist
  `DIAGNOSTIC_RESPONSE_HEADERS = ['www-authenticate','retry-after']` capturée
  **uniquement sur échec**, extraction case-insensitive, set-cookie exclu.
  ⚠️ Posée en **feuilles plates** `http.response.{www_authenticate,retry_after}`,
  **pas** `http.response.headers.*` : le template APM mappe `http.response.headers`
  en non-objet → tenter un objet donne `can't merge a non object mapping`, 400.
  Chaîne 3 repos : api (`external-api-logger.helpers.ts`) → tools (renames logstash
  `[msg][http][response][...]` + `logs@custom` keyword). Générique tous clients.

## Cas de validation end-to-end : RDV Milo

Périmètre choisi comme exemple bout-en-bout : création/màj/suppression de RDV
conseiller + inscriptions de jeunes aux sessions Milo.

Trace attendue pour un `POST /rendez-vous` (filtrer sur `trace.id`) :

1. `auth_succeeded` (`OidcAuthGuard`)
2. `request_completed` `POST /rendez-vous` (201)
3. `handler_executed` `CreateRendezVousCommandHandler` (success)
4. `external_api_call` `MiloClient` (si sync Milo)
5. `external_api_call` `BrevoClient` (si email invitation ICS)

Tous corrélés par le même `trace.id`, portant `user.{id,type,structure}` du conseiller.

Alertes RDV Milo : `external_api_call` `MiloClient` `failure` rate élevé →
Slack #ops ; échecs `CreateRendezVousCommandHandler` → Slack #dev.

## Limites connues & pistes

- **FirebaseClient** non instrumenté (firebase-admin SDK, pas Axios).
- **Worker** : `trace.id` / `transaction.id` absents dans le contexte async des
  jobs ; `labels.job_run_id` couvre en attendant.
- **Corrélation chaînes de jobs Milo** (`SUIVRE_FILE_EVENEMENTS_MILO` →
  `TRAITER_EVENEMENT_MILO`) : ajouter `milo.event_id` au payload si besoin.
- **PII** : la log factory `MiloClient` leak un email.
- **Retry 401 transient Milo (page 2)** : depuis le fix pagination (la page 2
  échouée n'est plus avalée → renvoie `failure`), un 401 transient fait échouer
  la requête conseiller. Piste : retry page 2 sur 401 (1 essai + re-exchange).
  Contexte : token i-milo échangé 1×/requête (`exchangeTokenConseillerMilo`,
  Keycloak token-exchange), même idpToken réutilisé page 1 & page 2 ; cas réel vu
  page 1 200 en 4,92 s puis page 2 401 en 13 ms → branche probable = i-milo sous charge.
- **`expires_in` jeté** (`oidc-client.db.ts`, parsé dans `TokenExchangeResponse`
  mais seul `access_token` est renvoyé) : (a) le loguer = diagnostic TTL ;
  (b) pré-refresh si proche expiration = prévention 401. Ordre : (a) d'abord.
- **Pagination plafonnée à 2 pages (~300 résultats)** : si >300 sessions (vu 471),
  le reste n'est jamais récupéré même en succès total. À challenger si besoin produit.
- **`validation_failed` (ValidationPipe, `src/main.ts`)** : `message =
  JSON.stringify(validationErrors)` déverse `target` (payload complet) + `value`
  (doublon) → fuite PII potentielle (contourne la redaction pino) + bloat. Fix :
  ne logger que `{property, constraints}` ; le `BadRequestException` renvoyé au
  client garde le détail complet (voulu).
