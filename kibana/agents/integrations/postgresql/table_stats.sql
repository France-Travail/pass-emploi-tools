select
  s.schemaname as schema,
  s.relname as "table",
  s.seq_scan,
  s.seq_tup_read,
  s.idx_scan,
  s.n_live_tup,
  s.n_dead_tup,
  s.n_mod_since_analyze,
  s.n_tup_ins,
  s.n_tup_upd,
  s.n_tup_del,
  coalesce(s.last_analyze::text, 'jamais') as last_analyze,
  coalesce(s.last_autoanalyze::text, 'jamais') as last_autoanalyze,
  coalesce(s.last_vacuum::text, 'jamais') as last_vacuum,
  coalesce(s.last_autovacuum::text, 'jamais') as last_autovacuum,
  pg_total_relation_size(s.relid) as taille_octets,
  coalesce(t.n_live_tup, 0) as toast_n_live_tup,
  coalesce(t.n_dead_tup, 0) as toast_n_dead_tup,
  coalesce(t.last_autovacuum::text, 'jamais') as toast_last_autovacuum,
  coalesce(pg_relation_size(t.relid), 0) as toast_taille_octets,
  coalesce((select stats_reset from pg_stat_database where datname = current_database())::text, 'jamais') as stats_reset
from pg_stat_user_tables s
join pg_class c on c.oid = s.relid
-- pg_stat_user_tables exclut le schéma pg_toast : les lignes mortes d'un gros JSON réécrit n'apparaissent que par cette jointure
left join pg_stat_all_tables t on t.relid = c.reltoastrelid
where s.schemaname not in ('tiger', 'tiger_data', 'topology');
