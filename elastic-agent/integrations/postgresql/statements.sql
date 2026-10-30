with miennes as (
  select * from pg_stat_statements
  where userid = (select oid from pg_roles where rolname = current_user)
),
par_temps as (select queryid from miennes order by total_exec_time desc limit 200),
par_appels as (select queryid from miennes order by calls desc limit 200)
select
  m.queryid::text as queryid,
  left(regexp_replace(m.query, '\s+', ' ', 'g'), 2000) as requete,
  m.calls,
  round(m.total_exec_time::numeric, 3)::float8 as total_exec_time_ms,
  round(m.mean_exec_time::numeric, 3)::float8 as mean_exec_time_ms,
  round(m.stddev_exec_time::numeric, 3)::float8 as stddev_exec_time_ms,
  m.rows,
  m.shared_blks_hit,
  m.shared_blks_read,
  concat_ws(',',
    case when m.queryid in (select queryid from par_temps) then 'temps' end,
    case when m.queryid in (select queryid from par_appels) then 'appels' end) as classement
from miennes m
where m.queryid in (select queryid from par_temps union select queryid from par_appels);
