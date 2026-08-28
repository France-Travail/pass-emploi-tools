#!/usr/bin/env bash

set -e

export PATH="/app/bin:$PATH"

mkdir -p /app/data/elastic-agent-state

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
