package passemploi.test

import io.gatling.core.Predef._
import io.gatling.core.structure.ScenarioBuilder
import io.gatling.http.Predef._
import io.gatling.http.protocol.HttpProtocolBuilder
import passemploi.helpers.Helpers

import java.time.Instant
import java.time.temporal.ChronoUnit

// Tir de charge sur GET /jeunes/:idJeune/pole-emploi/accueil (page d'accueil
// jeune France Travail). Modèle fermé : montée vers un plafond d'utilisateurs
// concurrents, puis palier. Le flow traversé par chaque requête est décrit
// dans perf/README.md.
//
// Prérequis : le jeune FT existe en base sur l'environnement cible, l'API
// pointe sur perf/api-simulator (cf. son README), et USER_TOKEN est un JWT
// valide et non expiré de ce jeune. Ne JAMAIS cibler la production.
//
// Variables d'environnement :
//   API_URL                   Cible (défaut : http://localhost:5000)
//   USER_ID                   Id pass-emploi du jeune FT (défaut : Alban336)
//   USER_TOKEN                JWT du jeune FT (obligatoire)
//   MAX_USERS                 Plafond d'utilisateurs concurrents (défaut : 10)
//   RAMP_DURATION_IN_SECONDS  Durée de la montée (défaut : 30)
//   HOLD_DURATION_IN_SECONDS  Durée du palier (défaut : 60)
//   P95_THRESHOLD_MS          Seuil p95 (défaut : 5000 — SLO I3 pages critiques,
//                             cf. docs/perf/observabilite.md)
//   FAILED_PERCENT_THRESHOLD  Taux d'échec max en % (défaut : 1.0 — SLO I1 ≥ 99 %)

class AccueilFranceTravailSimulation extends Simulation {
  val apiUrl: String    = Helpers.getProperty("API_URL", "http://localhost:5000")
  val userId: String    = Helpers.getProperty("USER_ID", "ca5014cb-9bb5-4d8e-befb-596ee59c4d7b")
  val userToken: String = Helpers.getProperty("USER_TOKEN", "")

  require(
    userToken.nonEmpty,
    "USER_TOKEN manquant : JWT du jeune FT, signé par le Keycloak dont l'api-simulator sert les clés"
  )

  val maxUsers: Int                  = Helpers.getProperty("MAX_USERS", "10").toInt
  val rampDurationInSeconds: Int     = Helpers.getProperty("RAMP_DURATION_IN_SECONDS", "30").toInt
  val holdDurationInSeconds: Int     = Helpers.getProperty("HOLD_DURATION_IN_SECONDS", "60").toInt
  val p95ThresholdMs: Int            = Helpers.getProperty("P95_THRESHOLD_MS", "5000").toInt
  val failedPercentThreshold: Double = Helpers.getProperty("FAILED_PERCENT_THRESHOLD", "1.0").toDouble

  // ISO 8601 strict exigé par l'API ; Instant = UTC avec suffixe "Z", donc pas
  // de '+' de fuseau à encoder dans l'URL
  private val maintenant = Instant.now().truncatedTo(ChronoUnit.SECONDS)

  val httpProtocol: HttpProtocolBuilder = http
    .baseUrl(apiUrl)
    .authorizationHeader(s"Bearer $userToken")
    .acceptHeader("*/*")
    .acceptEncodingHeader("gzip, deflate")
    .userAgentHeader("Gatling")

  val scn: ScenarioBuilder = scenario("Accueil jeune FT")
    .exec(
      http("GET /jeunes/:id/pole-emploi/accueil")
        .get(s"/jeunes/$userId/pole-emploi/accueil?maintenant=$maintenant")
        .check(status.is(200))
    )

  setUp(
    scn.inject(
      rampConcurrentUsers(1).to(maxUsers).during(rampDurationInSeconds),
      constantConcurrentUsers(maxUsers).during(holdDurationInSeconds)
    )
  ).protocols(httpProtocol)
    .assertions(
      global.responseTime.percentile(95).lt(p95ThresholdMs),
      global.failedRequests.percent.lt(failedPercentThreshold)
    )
}
