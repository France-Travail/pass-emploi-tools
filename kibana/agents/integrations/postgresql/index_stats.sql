select
  s.schemaname as schema,
  s.relname as "table",
  s.indexrelname as index,
  s.idx_scan,
  s.idx_tup_read,
  s.idx_tup_fetch,
  pg_relation_size(s.indexrelid) as taille_octets,
  pg_table_size(s.relid) as taille_table_octets,
  (select t.n_live_tup from pg_stat_user_tables t where t.relid = s.relid) as lignes_table,
  (i.indisprimary or i.indisunique
    or exists (select 1 from pg_constraint c where c.conindid = s.indexrelid)) as contrainte,
  coalesce((select stats_reset from pg_stat_database where datname = current_database())::text, 'jamais') as stats_reset
from pg_stat_user_indexes s
join pg_index i on i.indexrelid = s.indexrelid
where s.schemaname not in ('tiger', 'tiger_data', 'topology');
