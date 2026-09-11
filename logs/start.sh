#!/usr/bin/env bash

set -e

export PATH="/app/bin:$PATH"

mkdir -p /app/data/elastic-agent-state

# Génération de /app/config/pipelines.yml à chaque démarrage.
# Par défaut (INGEST_ENABLED et PROCESS_ENABLED non définies) : tous les pipelines sont actifs.
# Avec INGEST_ENABLED=true seul : seul le pipeline ingest tourne (HTTP → Redis).
# Avec PROCESS_ENABLED=true seul : seuls les pipelines process + dead_letter_queue tournent (Redis → ES).
PIPELINES_GENERATED_CONF_FILE="/app/config/pipelines.yml"

rm -f "$PIPELINES_GENERATED_CONF_FILE"

if [ -z "$INGEST_ENABLED" ] && [ -z "$PROCESS_ENABLED" ]; then
  ACTIVATION_NON_PARAMETREE=true
else
  ACTIVATION_NON_PARAMETREE=false
fi

if [ "$ACTIVATION_NON_PARAMETREE" = "true" ] || [ "${INGEST_ENABLED}" = "true" ]; then
  cat /app/config/pipelines-ingest.yml >> "$PIPELINES_GENERATED_CONF_FILE"
fi

if [ "$ACTIVATION_NON_PARAMETREE" = "true" ] || [ "${PROCESS_ENABLED}" = "true" ]; then
  cat /app/config/pipelines-process.yml >> "$PIPELINES_GENERATED_CONF_FILE"
fi

# Génère un ELASTIC_AGENT_ID unique et stable par instance à partir du HOSTNAME Scalingo.
# (ex: pass-emploi-logstash-perf-web-1 → UUID déterministe).
# ELASTIC_AGENT_ID_SUFFIX permet de forcer ponctuellement une nouvelle identité Fleet
# sans impacter les autres applications.
AGENT_ID_SOURCE="${HOSTNAME}${ELASTIC_AGENT_ID_SUFFIX:+:${ELASTIC_AGENT_ID_SUFFIX}}"

export ELASTIC_AGENT_ID=$(
  python3 -c "import uuid; print(uuid.uuid5(uuid.NAMESPACE_DNS, '${AGENT_ID_SOURCE}'))"
)

# ELASTIC_AGENT_GO_OPTS : options Go runtime injectées dans l'environnement d'Elastic Agent.
# Analogue à LS_JAVA_OPTS pour Logstash.
# Exemple : ELASTIC_AGENT_GO_OPTS="GOMEMLIMIT=512MiB" pour ajuster la limite mémoire Go.
# GOMEMLIMIT est un soft limit : le GC Go s'active plus agressivement pour rester
# en dessous, sans crasher le processus si la limite est dépassée.
# Valeur par défaut : 256 MiB — conservatrice pour cohabiter avec Logstash dans 2 Go.
# À ajuster via la variable d'env Scalingo ELASTIC_AGENT_GO_OPTS après mesure réelle.
#
# Elastic Agent ne démarre que si FLEET_ENROLL=1.
# Sur les containers avec peu de RAM (ex: S/512 Mo), ne pas définir FLEET_ENROLL
# permet de réserver toute la mémoire à Logstash.
if [ "${FLEET_ENROLL}" = "1" ]; then
  # Démarrer l'Elastic Agent seulement après que Logstash répond.
  # Cela évite que l'agent consomme de la mémoire/CPU pendant la phase critique
  # d'initialisation de la JVM Logstash, qui doit répondre dans le délai Scalingo (~60s).
  (
    until curl -sf "http://127.0.0.1:9600/" >/dev/null 2>&1; do
      sleep 2
    done

    echo "Starting Elastic Agent: id=${ELASTIC_AGENT_ID}"

    STATE_PATH="/app/data/elastic-agent-state" \
      env ${ELASTIC_AGENT_GO_OPTS:-GOMEMLIMIT=256MiB} \
      elastic-agent container

    rc=$?
    echo "Elastic Agent exited with code ${rc}" >&2
  ) &
fi

# Décode le CA cert Redis depuis la variable d'env (base64) vers un fichier temporaire.
# Le cert n'est jamais stocké dans le repo — uniquement dans les variables Scalingo.
if [ -n "$REDIS_CA_CERT_BASE64" ]; then
  mkdir -p /app/certs
  echo "$REDIS_CA_CERT_BASE64" | base64 -d > /app/certs/redis-ca.pem
fi

exec logstash \
  --config.reload.automatic \
  --path.settings /app/config

printf '%s' 'ZThJRU9LQUJnczk2RmhRemxYQWo6VUNkRGhBVEZGWm5KNmxRallCb0RsQQ==' | sha256sum