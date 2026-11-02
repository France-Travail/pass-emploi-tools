select
  coalesce(round(extract(epoch from max(now() - xact_start)))::bigint, 0) as plus_vieille_transaction_s,
  count(*) filter (where state like 'idle in transaction%') as sessions_idle_in_transaction,
  count(*) filter (where wait_event_type = 'Lock') as sessions_en_attente_verrou,
  coalesce(round(extract(epoch from max(now() - state_change) filter (where wait_event_type = 'Lock')))::bigint, 0) as plus_longue_attente_verrou_s
from pg_stat_activity
where datname = current_database()
  and usename = current_user
  and pid <> pg_backend_pid();
