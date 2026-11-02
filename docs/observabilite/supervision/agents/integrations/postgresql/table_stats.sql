select
  schemaname as schema,
  relname as "table",
  seq_scan,
  seq_tup_read,
  idx_scan,
  n_live_tup,
  n_dead_tup,
  n_mod_since_analyze,
  n_tup_ins,
  n_tup_upd,
  n_tup_del,
  coalesce(last_analyze::text, 'jamais') as last_analyze,
  coalesce(last_autoanalyze::text, 'jamais') as last_autoanalyze,
  coalesce(last_vacuum::text, 'jamais') as last_vacuum,
  coalesce(last_autovacuum::text, 'jamais') as last_autovacuum,
  pg_total_relation_size(relid) as taille_octets,
  coalesce((select stats_reset from pg_stat_database where datname = current_database())::text, 'jamais') as stats_reset
from pg_stat_user_tables
where schemaname not in ('tiger', 'tiger_data', 'topology');
