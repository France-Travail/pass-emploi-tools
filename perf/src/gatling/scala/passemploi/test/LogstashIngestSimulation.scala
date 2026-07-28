package passemploi.test

import io.gatling.core.Predef._
import io.gatling.core.structure.ScenarioBuilder
import io.gatling.http.Predef._
import io.gatling.http.protocol.HttpProtocolBuilder
import io.netty.handler.codec.http.HttpHeaderValues
import passemploi.helpers.Helpers

import java.util.UUID
import java.util.concurrent.atomic.AtomicLong

// Simulation de charge sur le pipeline-ingest Logstash.
//
// Objectif : valider que l'architecture 2 pipelines + Persistent Queue
// résout la quarantaine du drain Scalingo (cf. docs/blackout-logs/).
//
// Scénario : montée en charge progressive 1 → USERS_PER_SEC logs/s.
// Chaque utilisateur virtuel envoie un log JSON applicatif (format pino-http)
// en POST HTTP Basic Auth, comme le ferait le drain Scalingo.
//
// Le body est généré depuis logs/log-applicatif.template.json (PebbleFileBody).
// Les champs varient à chaque requête : timestamp, trace.id, req.id, statut.
//
// Variables d'environnement :
//   LOGSTASH_URL        URL du Logstash à tester (défaut : http://localhost:5044)
//   LOGSTASH_USER       Identifiant Basic Auth (défaut : user)
//   LOGSTASH_PASSWORD   Mot de passe Basic Auth (défaut : password)
//   USERS_PER_SEC       Débit cible en logs/s (défaut : 200)
//   DURATION_IN_SECONDS Durée de la montée en charge (défaut : 120)

class LogstashIngestSimulation extends Simulation {

  private val logstashUrl: String  = Helpers.getProperty("LOGSTASH_URL", "http://localhost:5044")
  private val logstashUser: String = Helpers.getProperty("LOGSTASH_USER", "user")
  private val logstashPass: String = Helpers.getProperty("LOGSTASH_PASSWORD", "password")

  val usersPerSec: Double    = Helpers.getProperty("USERS_PER_SEC", "200").toDouble
  val durationInSeconds: Int = Helpers.getProperty("DURATION_IN_SECONDS", "120").toInt

  // Compteur partagé entre tous les utilisateurs virtuels.
  // Utilisé pour req.id et user.id — garantit l'unicité sans collision.
  private val counter = new AtomicLong(0)

  // Cas cohérents : (statusCode, httpMethod, url, responseTime, eventAction, eventOutcome, msg).
  // Distribution réaliste : 3 succès pour 1 erreur.
  // format: off
  private val logCases = Seq(
    (200, "GET",  "/api/v1/conseillers/1/jeunes",                 42,  "request_completed", "success", "request_completed"),
    (200, "GET",  "/api/v1/jeunes/hermione",                      18,  "request_completed", "success", "request_completed"),
    (200, "POST", "/api/v1/conseillers/1/jeunes/hermione/action", 95,  "request_completed", "success", "request_completed"),
    (401, "GET",  "/api/v1/conseillers/1/jeunes",                 12,  "request_completed", "failure", "request_completed"),
    (403, "GET",  "/api/v1/jeunes/hermione",                      8,   "request_completed", "failure", "request_completed"),
    (404, "GET",  "/api/v1/actions/unknown-id",                   6,   "request_completed", "failure", "request_completed"),
    (500, "POST", "/api/v1/conseillers/1/jeunes/hermione/action", 230, "request_failed",    "failure", "request_failed"),
  )
  // format: on

  // Identité de l'application simulée — correspond à ce que le drain Scalingo enverrait.
  private val appName: String  = "pass-emploi-api-perf"
  private val hostname: String = "web-1"

  val httpProtocol: HttpProtocolBuilder = http
    .baseUrl(logstashUrl)
    .basicAuth(logstashUser, logstashPass)
    .acceptHeader("*/*")
    .contentTypeHeader(HttpHeaderValues.APPLICATION_JSON.toString)

  val scn: ScenarioBuilder = scenario("Ingest log via drain HTTP")
    .exec { session =>
      val id      = counter.incrementAndGet()
      val caseIdx = (id % logCases.size).toInt
      val (statusCode, httpMethod, url, responseTime, eventAction, eventOutcome, msg) = logCases(caseIdx)

      // trace.id : 32 hex chars (format elastic-apm-node)
      val traceId       = UUID.randomUUID().toString.replace("-", "")
      // transaction.id : 16 hex chars (8 premiers bytes d'un UUID)
      val transactionId = UUID.randomUUID().toString.replace("-", "").take(16)

      session
        .set("currentTimeMs",  System.currentTimeMillis())
        .set("traceId",        traceId)
        .set("transactionId",  transactionId)
        .set("reqId",          id)
        .set("httpMethod",     httpMethod)
        .set("url",            url)
        .set("statusCode",     statusCode)
        .set("responseTime",   responseTime)
        .set("eventAction",    eventAction)
        .set("eventOutcome",   eventOutcome)
        .set("msg",            msg)
    }
    .exec(
      http("POST log applicatif")
        .post(s"/?appname=$appName&hostname=$hostname")
        .body(PebbleFileBody("logs/log-applicatif.template.json"))
        .check(status.in(200, 201))
      
    )

  // Seuil p95 adapté au débit cible :
  //   ≤ 1000 logs/s → 600ms  : latence de base réseau GitHub Actions (Azure) → Scalingo (AWS) ~440ms
  //                            marge de 160ms pour absorber la variabilité réseau + le JVM cold start de Gatling
  //                            (outliers en début de ramp-up)
  //   > 1000 logs/s → 2000ms : large marge avant le timeout drain Scalingo (~5s)
  private val p95ThresholdMs: Int = if (usersPerSec <= 1000) 600 else 2000

  setUp(
    scn.inject(
      rampUsersPerSec(1).to(usersPerSec).during(durationInSeconds)
    )
  ).protocols(httpProtocol)
    .assertions(
      global.responseTime.percentile(95).lt(p95ThresholdMs),
      // Taux d'erreur < 0,1% : 10 timeouts consécutifs → quarantaine Scalingo 5 min.
      global.failedRequests.percent.lt(0.1)
    )
}
