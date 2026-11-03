#!/usr/bin/env bash
# Exécute start.sh dans un conteneur jetable, avec un faux elastic-agent.
# Lancer depuis la racine du repo : bash elastic-agent/tests/test_start.sh
set -u
racine="$(cd "$(dirname "$0")/.." && pwd)"
ca="$(printf -- '-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n')"
echecs=0

lancer() {
  docker run --rm -e HOSTNAME=test-worker-1 "$@" -v "$racine:/src:ro" python:3.12-slim bash -c '
    mkdir -p /app/bin && printf "#!/bin/sh\necho AGENT_LANCE\n" > /app/bin/elastic-agent && chmod +x /app/bin/elastic-agent
    bash /src/start.sh && cat /app/certs/postgresql-ca.pem 2>/dev/null'
}

verifier() {
  if [[ "$2" == *"$3"* ]]; then echo "ok   $1"; else echo "ECHEC $1 : attendu « $3 », obtenu « $2 »"; echecs=$((echecs + 1)); fi
}

sortie="$(lancer -e POSTGRESQL_CA_CERT_BASE64="$(printf '%s\n' "$ca" | base64 -w0)")"
verifier "le certificat est écrit dans /app/certs/postgresql-ca.pem" "$sortie" "$ca"
verifier "l'agent démarre avec le certificat" "$sortie" AGENT_LANCE

sortie="$(lancer)"
verifier "l'agent démarre sans certificat" "$sortie" AGENT_LANCE

sortie="$(lancer -e POSTGRESQL_CA_CERT_BASE64="pas du base64 !")"
verifier "l'agent démarre avec un certificat invalide" "$sortie" AGENT_LANCE

[ $echecs = 0 ] && echo "4/4 OK" || { echo "$echecs échec(s)"; exit 1; }
