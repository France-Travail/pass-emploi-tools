#!/usr/bin/env bash

set -e

export PATH="/app/bin:$PATH"

mkdir -p /app/data/elastic-agent-state

# Génère un ELASTIC_AGENT_ID unique et stable par instance à partir du HOSTNAME Scalingo
# (ex: pass-emploi-elastic-agent-perf-worker-1 → UUID déterministe).
# Cela évite l'erreur ErrAgentIdentity quand plusieurs instances tournent en parallèle.
export ELASTIC_AGENT_ID=$(python3 -c "import uuid; print(uuid.uuid5(uuid.NAMESPACE_DNS, '${HOSTNAME}'))")

# GOMEMLIMIT : soft limit Go GC (analogue à LS_JAVA_OPTS pour Logstash).
# Valeur par défaut : 512 MiB.
# À ajuster via la variable d'env Scalingo ELASTIC_AGENT_GO_OPTS après mesure réelle.
STATE_PATH="/app/data/elastic-agent-state" \
  env ${ELASTIC_AGENT_GO_OPTS:-GOMEMLIMIT=512MiB} \
  elastic-agent container
