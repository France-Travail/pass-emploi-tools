with index_de_l_app as (
  select
    n.nspname as schema,
    t.relname as "table",
    c.relname as index,
    i.indexrelid,
    i.indrelid,
    i.indisvalid and i.indisready as valide,
    i.indkey::text as colonnes,
    coalesce(pg_get_expr(i.indpred, i.indrelid), '') as predicat,
    coalesce(pg_get_expr(i.indexprs, i.indrelid), '') as expressions
  from pg_index i
  join pg_class c on c.oid = i.indexrelid
  join pg_class t on t.oid = i.indrelid
  join pg_namespace n on n.oid = t.relnamespace
  where n.nspname not in ('pg_catalog', 'information_schema', 'pg_toast', 'tiger', 'tiger_data', 'topology')
)
select
  a.schema,
  a."table",
  a.index,
  a.valide,
  coalesce((
    select string_agg(b.index, ',' order by b.index)
    from index_de_l_app b
    where b.indrelid = a.indrelid and b.indexrelid <> a.indexrelid
      and b.predicat = a.predicat and b.expressions = a.expressions
      and (b.colonnes = a.colonnes or b.colonnes like a.colonnes || ' %')
  ), '') as doublon_de,
  (select count(*) from index_de_l_app b where b.indrelid = a.indrelid) as index_de_la_table,
  pg_relation_size(a.indexrelid) as taille_index_octets,
  pg_table_size(a.indrelid) as taille_table_octets,
  pg_indexes_size(a.indrelid) as taille_index_table_octets
from index_de_l_app a;
