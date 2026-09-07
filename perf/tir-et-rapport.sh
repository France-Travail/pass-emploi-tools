#!/bin/bash
# Joue une simulation, puis émet le rapport HTML sur stdout si on le demande.
#
# Raison d'être : le système de fichiers d'un one-off Scalingo meurt avec le
# conteneur. Le rapport doit donc sortir *pendant* l'exécution, et stdout est
# le seul canal disponible (un one-off n'est pas routé par le routeur Scalingo,
# donc pas joignable en HTTP).
#
# `simulation.log` est exclu : c'est la trace brute, plusieurs Mo, que le
# rapport HTML a déjà agrégée.

set -u

SIMULATION="$1"

# --no-daemon : le daemon Gradle n'a aucun intérêt dans un conteneur one-off
# jetable — il accélère les builds *suivants*, qu'il n'y aura pas.
# --console=plain -q : la barre de progression ANSI de Gradle est illisible une
# fois relayée par `scalingo run` ; -q coupe le bruit de cycle de vie de Gradle
# sans toucher à la sortie du process forké (résumé Gatling).
./gradlew --no-daemon --console=plain -q gatlingRun --simulation "$SIMULATION"
code=$?

# Opt-in : sans ça, un `make tir` lancé à la main déverserait 300 Ko de base64
# dans le terminal.
if [ "${RAPPORT_STDOUT:-0}" = "1" ]; then
  echo "---RAPPORT-GATLING-DEBUT---"
  tar czf - --exclude='simulation.log' -C build/reports gatling | base64
  echo "---RAPPORT-GATLING-FIN---"
fi

# Le code de sortie de Gatling est le verdict SLO : il doit survivre à
# l'émission du rapport.
exit $code
