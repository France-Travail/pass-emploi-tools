package passemploi.helpers

import java.nio.charset.StandardCharsets
import java.util.Base64

// Lecture du payload d'un JWT, sans vérification de signature : le tir n'a pas
// à valider le token, seulement à y lire l'identité que connect lui a attribuée.
// L'API lit ce même claim `userId` (oidc.auth-guard.ts) pour autoriser l'appel.
object Jwt {
  def claim(token: String, nom: String): Option[String] = {
    token.split('.') match {
      case Array(_, payload, _*) => extraire(decoder(payload), nom)
      case _                     => None
    }
  }

  private def decoder(segment: String): String = {
    val rembourrage = "=" * ((4 - segment.length % 4) % 4)
    new String(
      Base64.getUrlDecoder.decode(segment + rembourrage),
      StandardCharsets.UTF_8
    )
  }

  // Extraction sans dépendance JSON : le payload est plat et on ne cherche
  // qu'une chaîne. Ajouter une bibliothèque pour ça serait disproportionné.
  private def extraire(json: String, nom: String): Option[String] = {
    val motif = s""""$nom"\\s*:\\s*"([^"]*)"""".r
    motif.findFirstMatchIn(json).map(_.group(1))
  }
}
