package passemploi.test

import io.gatling.core.Predef._
import io.gatling.core.structure.ScenarioBuilder
import io.gatling.http.Predef._
import io.gatling.http.protocol.HttpProtocolBuilder
import passemploi.helpers.{Helpers, Jwt, Redirections}

import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.Base64

// Tir de bout en bout : login réel via pass-emploi-connect, puis accueil jeune
// France Travail. Seul l'IDP France Travail est mocké (perf/mock-externes) ;
// connect et api sont réels, ce sont eux qu'on mesure.
//
// La chaîne de redirections est suivie à la main, étape par étape, plutôt que
// via followRedirect. Deux raisons : la dernière redirection pointe vers un
// schéma d'URL mobile que Gatling ne sait pas suivre, et le découpage donne un
// temps de réponse par étape — ce qui est exactement ce qu'on veut pour
// instruire le SLO I2 (capacité de connexion).
//
// Prérequis : mock-externes lancé, connect branché dessus, et le pool semé en
// base avec le même POOL_PREFIX / POOL_SIZE (cf. perf/seed/README.md).
// Ne JAMAIS cibler la production.
//
// Variables d'environnement :
//   CONNECT_URL               Base de pass-emploi-connect
//   API_URL                   Base de pass-emploi-api
//   CLIENT_ID / CLIENT_SECRET Client OIDC déclaré dans connect (obligatoires)
//   REDIRECT_URI              Callback du client (obligatoire)
//   KC_IDP_HINT               Porte d'entrée (défaut : pe-jeune → structure POLE_EMPLOI)
//   MAX_USERS, RAMP_DURATION_IN_SECONDS, HOLD_DURATION_IN_SECONDS
//   P95_THRESHOLD_MS          Seuil p95 (défaut : 5000 — SLO I3)
//   FAILED_PERCENT_THRESHOLD  Taux d'échec max en % (défaut : 1.0 — SLO I1)

class LoginEtAccueilFranceTravailSimulation extends Simulation {
  val connectUrl: String   = Helpers.getProperty("CONNECT_URL", "http://localhost:8081")
  val apiUrl: String       = Helpers.getProperty("API_URL", "http://localhost:5000")
  // Aucune valeur par défaut : les clients OIDC de connect sont entièrement
  // pilotés par variables d'environnement (CLIENT_APP_ID/SECRET/CALLBACKS),
  // donc rien n'est devinable depuis le code.
  val clientId: String     = Helpers.getProperty("CLIENT_ID", "")
  val clientSecret: String = Helpers.getProperty("CLIENT_SECRET", "")
  val redirectUri: String  = Helpers.getProperty("REDIRECT_URI", "")
  val idpHint: String      = Helpers.getProperty("KC_IDP_HINT", "pe-jeune")

  require(clientId.nonEmpty, "CLIENT_ID manquant : cf. CLIENT_APP_ID de connect")
  require(
    clientSecret.nonEmpty,
    "CLIENT_SECRET manquant : cf. CLIENT_APP_SECRET de connect"
  )
  require(
    redirectUri.nonEmpty,
    "REDIRECT_URI manquant : doit figurer dans les callbacks du client"
  )

  val maxUsers: Int                  = Helpers.getProperty("MAX_USERS", "10").toInt
  val rampDurationInSeconds: Int     = Helpers.getProperty("RAMP_DURATION_IN_SECONDS", "30").toInt
  val holdDurationInSeconds: Int     = Helpers.getProperty("HOLD_DURATION_IN_SECONDS", "60").toInt
  val p95ThresholdMs: Int            = Helpers.getProperty("P95_THRESHOLD_MS", "5000").toInt
  val failedPercentThreshold: Double = Helpers.getProperty("FAILED_PERCENT_THRESHOLD", "1.0").toDouble

  private val authentificationClient =
    "Basic " + Base64.getEncoder.encodeToString(
      s"$clientId:$clientSecret".getBytes("UTF-8")
    )

  val httpProtocol: HttpProtocolBuilder = http
    .acceptHeader("*/*")
    .acceptEncodingHeader("gzip, deflate")
    .userAgentHeader("Gatling")
    .disableFollowRedirect

  // Chaque utilisateur virtuel a ses propres state et nonce : les réutiliser
  // ferait collisionner les interactions côté connect sous charge.
  private val alea = exec { session =>
    val jeton = java.util.UUID.randomUUID().toString
    session.set("state", jeton).set("nonce", jeton)
  }

  // Chaque saut normalise son Location : oidc-provider, les contrôleurs Nest et
  // le mock ne s'accordent pas sur relatif vs absolu.
  private def suivre(nom: String, urlSource: String, urlCible: String) =
    exec(
      http(nom)
        .get(s"#{$urlSource}")
        .check(status.in(302, 303, 307))
        .check(header("location").saveAs("location"))
    ).exec { session =>
      session.set(
        urlCible,
        Redirections.resoudre(
          session(urlSource).as[String],
          session("location").as[String]
        )
      )
    }

  private val login = exec(
    http("01 authorize (connect)")
      .get(s"$connectUrl/protocol/openid-connect/auth")
      .queryParam("client_id", clientId)
      .queryParam("redirect_uri", redirectUri)
      .queryParam("response_type", "code")
      .queryParam("scope", "openid profile email")
      .queryParam("state", "#{state}")
      .queryParam("nonce", "#{nonce}")
      .queryParam("kc_idp_hint", idpHint)
      .check(status.in(302, 303))
      .check(header("location").saveAs("location"))
  ).exec { session =>
      session.set(
        "urlInteraction",
        Redirections.resoudre(connectUrl, session("location").as[String])
      )
    }
    .exec(suivre("02 interaction (connect)", "urlInteraction", "urlIdp"))
    .exec(suivre("03 authorize (mock IDP)", "urlIdp", "urlCallbackIdp"))
    // Étape la plus coûteuse du login : connect y fait le token exchange auprès
    // du mock, le userinfo, les coordonnées, puis le PUT /auth/users vers
    // l'API. C'est elle qui échoue si le pool n'est pas semé.
    .exec(suivre("04 callback IDP (connect)", "urlCallbackIdp", "urlReprise"))
    .exec(suivre("05 reprise interaction (connect)", "urlReprise", "urlFinale"))
    .exec { session =>
      // La redirection finale vise le schéma du client mobile : on ne la suit
      // pas, on en extrait le code d'autorisation.
      session.set(
        "code",
        Redirections.code(session("urlFinale").as[String]).getOrElse("")
      )
    }
    .exec(
      http("06 token (connect)")
        .post(s"$connectUrl/protocol/openid-connect/token")
        .header("Authorization", authentificationClient)
        .formParam("grant_type", "authorization_code")
        .formParam("code", "#{code}")
        .formParam("redirect_uri", redirectUri)
        .check(status.is(200))
        .check(jsonPath("$.access_token").saveAs("accessToken"))
    )
    .exec { session =>
      // L'identité du jeune n'est pas choisie par Gatling : le mock l'a tirée
      // au sort. On la lit dans le token, là où l'API la lira aussi.
      Jwt.claim(session("accessToken").as[String], "userId") match {
        case Some(identifiant) => session.set("idJeune", identifiant)
        case None              => session.markAsFailed
      }
    }
    .exitHereIfFailed

  private val accueil = exec { session =>
    session.set(
      "maintenant",
      Instant.now().truncatedTo(ChronoUnit.SECONDS).toString
    )
  }.exec(
    http("07 accueil FT (api)")
      .get(s"$apiUrl/jeunes/#{idJeune}/pole-emploi/accueil")
      .queryParam("maintenant", "#{maintenant}")
      .header("Authorization", "Bearer #{accessToken}")
      .check(status.is(200))
  )

  val scn: ScenarioBuilder =
    scenario("Login FT puis accueil").exec(alea).exec(login).exec(accueil)

  setUp(
    scn.inject(
      rampConcurrentUsers(1).to(maxUsers).during(rampDurationInSeconds),
      constantConcurrentUsers(maxUsers).during(holdDurationInSeconds)
    )
  ).protocols(httpProtocol)
    .assertions(
      details("07 accueil FT (api)").responseTime.percentile(95).lt(p95ThresholdMs),
      global.failedRequests.percent.lt(failedPercentThreshold)
    )
}
