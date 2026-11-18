with miennes as (
  select * from pg_stat_statements
  where userid = (select oid from pg_roles where rolname = current_user)
    and dbid = (select oid from pg_database where datname = current_database())
    and toplevel
    -- Avant PostgreSQL 16, les commandes utilitaires gardent leurs valeurs en clair dans le texte.
    and query !~* '^\s*(copy|set|show|do|call|vacuum|analyze|create|alter|drop|truncate|grant|revoke|begin|start|commit|rollback|savepoint|release|reset|lock|refresh|cluster|reindex|discard|deallocate|prepare|execute|listen|notify|unlisten|checkpoint|explain|comment|security|declare|fetch|close|move|load)\M'
),
par_temps as (select queryid from miennes order by total_exec_time desc limit 200),
par_appels as (select queryid from miennes order by calls desc limit 200)
select
  m.queryid::text as queryid,
  left(regexp_replace(m.query, '\s+', ' ', 'g'), 10000) as requete,
  m.calls,
  round(m.total_exec_time::numeric, 3)::float8 as total_exec_time_ms,
  round(m.mean_exec_time::numeric, 3)::float8 as mean_exec_time_ms,
  round(m.stddev_exec_time::numeric, 3)::float8 as stddev_exec_time_ms,
  m.rows,
  m.shared_blks_hit,
  m.shared_blks_read,
  concat_ws(',',
    case when m.queryid in (select queryid from par_temps) then 'temps' end,
    case when m.queryid in (select queryid from par_appels) then 'appels' end) as classement,
  (select stats_reset from pg_stat_statements_info)::text as stats_reset,
  (select dealloc from pg_stat_statements_info) as requetes_evincees
from miennes m
where m.queryid in (select queryid from par_temps union select queryid from par_appels);
