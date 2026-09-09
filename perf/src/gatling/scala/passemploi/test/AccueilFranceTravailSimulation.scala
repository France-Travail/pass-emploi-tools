package passemploi.test

import io.gatling.core.Predef._
import io.gatling.core.structure.ScenarioBuilder
import io.gatling.http.Predef._
import io.gatling.http.protocol.HttpProtocolBuilder
import passemploi.helpers.Helpers

import java.time.Instant
import java.time.temporal.ChronoUnit

// Tir de charge sur GET /jeunes/:idJeune/pole-emploi/accueil (page d'accueil
// jeune France Travail). Modèle ouvert : montée vers un débit d'arrivées, puis
// palier — les arrivants n'attendent pas que les précédents aient fini. Le flow
// traversé par chaque requête est décrit dans perf/README.md.
//
// Prérequis : le jeune FT existe en base sur l'environnement cible, l'API
// pointe sur perf/mock-externes (cf. son README), et USER_TOKEN est un JWT
// valide et non expiré de ce jeune. Ne JAMAIS cibler la production.
//
// Variables d'environnement :
//   API_URL                   Cible (défaut : http://localhost:5000)
//   USER_ID                   Id pass-emploi du jeune FT (défaut : Alban336)
//   USER_TOKEN                JWT du jeune FT (obligatoire)
//   USERS_PER_SEC             Parcours démarrés par seconde au palier (défaut : 10)
//   RAMP_DURATION_IN_SECONDS  Durée de la montée (défaut : 30)
//   HOLD_DURATION_IN_SECONDS  Durée du palier (défaut : 60)
//   P99_THRESHOLD_MS          Seuil p99 par requête (défaut : 500)
//   SUCCESS_PERCENT_THRESHOLD Taux de réussite minimum en % (défaut : 99.5)

class AccueilFranceTravailSimulation extends Simulation {
  val apiUrl: String    = Helpers.getProperty("API_URL", "http://localhost:5000")
  val userId: String    = Helpers.getProperty("USER_ID", "ca5014cb-9bb5-4d8e-befb-596ee59c4d7b")
  val userToken: String = Helpers.getProperty("USER_TOKEN", "")

  require(
    userToken.nonEmpty,
    "USER_TOKEN manquant : JWT du jeune FT émis par connect. Transitoire — le lot 3 remplace cette variable par un login via connect"
  )

  val usersPerSec: Double            = Helpers.getProperty("USERS_PER_SEC", "10").toDouble
  val rampDurationInSeconds: Int     = Helpers.getProperty("RAMP_DURATION_IN_SECONDS", "30").toInt
  val holdDurationInSeconds: Int     = Helpers.getProperty("HOLD_DURATION_IN_SECONDS", "60").toInt
  val p99ThresholdMs: Int             = Helpers.getProperty("P99_THRESHOLD_MS", "500").toInt
  val successPercentThreshold: Double = Helpers.getProperty("SUCCESS_PERCENT_THRESHOLD", "99.5").toDouble

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
      rampUsersPerSec(1).to(usersPerSec).during(rampDurationInSeconds),
      constantUsersPerSec(usersPerSec).during(holdDurationInSeconds)
    )
  ).protocols(httpProtocol)
    // Modèle ouvert : sous saturation, Gatling continue de créer des
    // utilisateurs que le système n'absorbe plus. Sans borne, un tir qui part
    // en vrille monopolise l'environnement et noie l'injecteur.
    .maxDuration(rampDurationInSeconds + holdDurationInSeconds + 60)
    .assertions(
      forAll.responseTime.percentile(99).lt(p99ThresholdMs),
      global.successfulRequests.percent.gt(successPercentThreshold)
    )
}
