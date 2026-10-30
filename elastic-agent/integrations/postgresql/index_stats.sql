select
  s.schemaname as schema,
  s.relname as "table",
  s.indexrelname as index,
  s.idx_scan,
  pg_relation_size(s.indexrelid) as taille_octets,
  (i.indisprimary or i.indisunique
    or exists (select 1 from pg_constraint c where c.conindid = s.indexrelid)) as contrainte
from pg_stat_user_indexes s
join pg_index i on i.indexrelid = s.indexrelid
where s.schemaname not in ('tiger', 'tiger_data', 'topology');
