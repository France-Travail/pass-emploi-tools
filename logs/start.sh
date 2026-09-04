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

# Génère un ELASTIC_AGENT_ID unique et stable par instance à partir du HOSTNAME Scalingo
# (ex: pass-emploi-logstash-perf-web-1 → UUID déterministe).
# Cela évite l'erreur ErrAgentIdentity quand plusieurs instances tournent en parallèle.
export ELASTIC_AGENT_ID=$(python3 -c "import uuid; print(uuid.uuid5(uuid.NAMESPACE_DNS, '${HOSTNAME}'))")

# ELASTIC_AGENT_GO_OPTS : options Go runtime injectées dans l'environnement d'Elastic Agent.
# Analogue à LS_JAVA_OPTS pour Logstash.
# Exemple : ELASTIC_AGENT_GO_OPTS="GOMEMLIMIT=512MiB" pour ajuster la limite mémoire Go.
# GOMEMLIMIT est un soft limit : le GC Go s'active plus agressivement pour rester
# en dessous, sans crasher le processus si la limite est dépassée.
# Valeur par défaut : 256 MiB — conservatrice pour cohabiter avec Logstash dans 2 Go.
# À ajuster via la variable d'env Scalingo ELASTIC_AGENT_GO_OPTS après mesure réelle.
STATE_PATH="/app/data/elastic-agent-state" \
  env ${ELASTIC_AGENT_GO_OPTS:-GOMEMLIMIT=256MiB} \
  elastic-agent container &

exec logstash \
  --config.reload.automatic \
  --path.settings /app/config
