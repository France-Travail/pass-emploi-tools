#!/bin/bash
# Lance les requêtes du package SQL contre la base de l'app ; à exécuter dans un conteneur ponctuel Scalingo.
set -u
cd "$(dirname "$0")"
echec=0
for f in statements.sql index_stats.sql table_stats.sql; do
  if [ ! -f "$f" ]; then echo "$f : ABSENT"; echec=1; continue; fi
  debut=$(date +%s%N)
  sortie=$(psql "$SCALINGO_POSTGRESQL_URL" -X -A -F '|' -v ON_ERROR_STOP=1 -f "$f" 2>&1) || { echo "$f : ERREUR $sortie"; echec=1; continue; }
  ms=$(( ($(date +%s%N) - debut) / 1000000 ))
  lignes=$(( $(printf '%s\n' "$sortie" | wc -l) - 2 ))
  echo "$f : $lignes lignes en $ms ms"
  echo "  colonnes : $(printf '%s\n' "$sortie" | head -1)"
  printf '%s\n' "$sortie" | sed -n '2,4p' | cut -c1-200 | sed 's/^/  /'
  if [ "$f" = statements.sql ]; then
    printf '%s\n' "$sortie" | head -1 | grep -q 'stats_reset' || { echo "  colonne stats_reset absente"; echec=1; }
    [ "$lignes" -le 400 ] || { echo "  plus de 400 lignes"; echec=1; }
    printf '%s\n' "$sortie" | grep -q 'insufficient privilege' && { echo "  texte illisible"; echec=1; }
  fi
  [ "$ms" -lt 2000 ] || { echo "  plus de 2 s"; echec=1; }
done
[ $echec = 0 ] && echo VERIFICATION_OK || echo VERIFICATION_KO
