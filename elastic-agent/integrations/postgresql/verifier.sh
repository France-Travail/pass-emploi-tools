#!/bin/bash
# À lancer dans un conteneur ponctuel de l'app qui porte la base : les conteneurs ont psql, pas le poste local.
set -u
cd "$(dirname "$0")"
echec=0
declare -A attendues=(
  [statements.sql]="queryid requete calls total_exec_time_ms stats_reset requetes_evincees"
  [index_stats.sql]="index idx_scan idx_tup_read idx_tup_fetch taille_octets taille_table_octets contrainte stats_reset"
  [table_stats.sql]="table seq_scan seq_tup_read idx_scan n_live_tup n_dead_tup n_mod_since_analyze last_analyze last_autoanalyze last_vacuum last_autovacuum n_tup_ins n_tup_upd n_tup_del stats_reset"
  [index_hygiene.sql]="table index valide doublon_de index_de_la_table taille_index_octets taille_table_octets taille_index_table_octets"
  [activite.sql]="plus_vieille_transaction_s sessions_idle_in_transaction sessions_en_attente_verrou plus_longue_attente_verrou_s"
)
for f in statements.sql index_stats.sql table_stats.sql index_hygiene.sql activite.sql; do
  if [ ! -f "$f" ]; then echo "$f : ABSENT"; echec=1; continue; fi
  debut=$(date +%s%N)
  sortie=$(psql "$SCALINGO_POSTGRESQL_URL" -X -A -F '|' -v ON_ERROR_STOP=1 -f "$f" 2>&1) || { echo "$f : ERREUR $sortie"; echec=1; continue; }
  ms=$(( ($(date +%s%N) - debut) / 1000000 ))
  lignes=$(( $(printf '%s\n' "$sortie" | wc -l) - 2 ))
  echo "$f : $lignes lignes en $ms ms"
  echo "  colonnes : $(printf '%s\n' "$sortie" | head -1)"
  printf '%s\n' "$sortie" | sed -n '2,4p' | cut -c1-200 | sed 's/^/  /'
  entete="|$(printf '%s\n' "$sortie" | head -1)|"
  for colonne in ${attendues[$f]}; do
    [[ "$entete" == *"|$colonne|"* ]] || { echo "  colonne $colonne absente"; echec=1; }
  done
  if [[ "$entete" == *"|stats_reset|"* ]]; then
    vides=$(printf '%s\n' "$sortie" | sed '1d;$d' | awk -F'|' '$NF == "" { n++ } END { print n + 0 }')
    [ "$vides" = 0 ] || { echo "  stats_reset vide sur $vides lignes"; echec=1; }
  fi
  if [ "$f" = statements.sql ]; then
    doublons=$(printf '%s\n' "$sortie" | sed '1d;$d' | awk -F'|' '{ print $1 }' | sort | uniq -d | wc -l)
    [ "$doublons" = 0 ] || { echo "  $doublons queryid en double"; echec=1; }
    printf '%s\n' "$sortie" | head -1 | grep -q 'requetes_evincees' || { echo "  colonne requetes_evincees absente"; echec=1; }
    printf '%s\n' "$sortie" | sed '1d;$d' | awk -F'|' '{ print $2 }' | grep -Eiq '^ *(copy|set|show|do|call|vacuum|analyze|create|alter|drop|truncate|grant|revoke|begin|commit|rollback|reset|lock|refresh|cluster|reindex|discard|deallocate|prepare|execute|listen|notify|unlisten|checkpoint|explain) ' && { echo "  commande utilitaire présente"; echec=1; }
    longueur=$(printf '%s\n' "$sortie" | sed '1d;$d' | awk -F'|' '{ if (length($2) > m) m = length($2) } END { print m + 0 }')
    echo "  texte le plus long : $longueur caractères"
    [ "$longueur" -le 10000 ] || { echo "  texte au-delà de 10 000 caractères"; echec=1; }
    [ "$lignes" -le 400 ] || { echo "  plus de 400 lignes"; echec=1; }
    printf '%s\n' "$sortie" | grep -q 'insufficient privilege' && { echo "  texte illisible"; echec=1; }
  fi
  [ "$ms" -lt 2000 ] || { echo "  plus de 2 s"; echec=1; }
done
[ $echec = 0 ] && echo VERIFICATION_OK || echo VERIFICATION_KO
