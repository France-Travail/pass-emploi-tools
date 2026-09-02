package passemploi.helpers

import java.net.URI

// La chaîne de login traverse oidc-provider, des contrôleurs Nest et l'IDP
// mocké, qui ne s'accordent pas sur la forme de leurs en-têtes Location :
// certains sont absolus, d'autres relatifs à leur hôte. Plutôt que de parier
// étape par étape, on normalise systématiquement.
object Redirections {
  def resoudre(base: String, location: String): String =
    if (location.startsWith("http://") || location.startsWith("https://"))
      location
    else
      URI.create(base).resolve(location).toString

  def code(url: String): Option[String] =
    """[?&]code=([^&]+)""".r.findFirstMatchIn(url).map(_.group(1))
}
