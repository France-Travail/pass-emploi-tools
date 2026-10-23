#!/usr/bin/env bash
# Attend la ligne finale d'une chaîne de job (suivi-job.sql), au plus timeout_s.
#
#   attendre-suivi-job.sh <database_url> <job_type> <t0> <timeout_s>
#
# Imprime la ligne JSON, ou rien au timeout : le verdict dit alors « ligne
# absente » plutôt que de laisser le step échouer sans constat.
set -uo pipefail

url="$1" job_type="$2" t0="$3" timeout_s="$4"
ici="$(dirname "$0")"
fin=$(( $(date +%s) + timeout_s ))

while :; do
  ligne="$(psql "$url" -At -v ON_ERROR_STOP=1 -v job_type="$job_type" -v t0="$t0" \
                -f "$ici/suivi-job.sql")" || { echo "Lecture de suivi_job en échec, nouvel essai" >&2; ligne=""; }
  if [ -n "$ligne" ]; then
    echo "$ligne"
    exit 0
  fi
  if [ "$(date +%s)" -ge "$fin" ]; then
    echo "Aucune ligne $job_type après ${timeout_s}s" >&2
    exit 0
  fi
  sleep 15
done
