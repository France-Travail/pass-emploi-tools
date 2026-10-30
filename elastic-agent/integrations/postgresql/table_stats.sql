select
  schemaname as schema,
  relname as "table",
  seq_scan,
  seq_tup_read,
  idx_scan,
  n_live_tup,
  pg_total_relation_size(relid) as taille_octets,
  coalesce((select stats_reset from pg_stat_database where datname = current_database())::text, 'jamais') as stats_reset
from pg_stat_user_tables
where schemaname not in ('tiger', 'tiger_data', 'topology');
