with sessions as (
  select pid, query_id, state, wait_event_type, wait_event, application_name, xact_start, state_change
  from pg_stat_activity
  where datname = current_database()
    and usename = current_user
    and pid <> pg_backend_pid()
),
attentes as (
  select s.*, unnest(pg_blocking_pids(s.pid)) as bloqueur
  from sessions s
  where s.wait_event_type = 'Lock'
),
modeles as (
  select queryid,
    case
      -- Avant PostgreSQL 16, les commandes utilitaires gardent leurs valeurs en clair dans le texte.
      when bool_or(query ~* '^\s*(copy|set|show|do|call|vacuum|analyze|create|alter|drop|truncate|grant|revoke|begin|start|commit|rollback|savepoint|release|reset|lock|refresh|cluster|reindex|discard|deallocate|prepare|execute|listen|notify|unlisten|checkpoint|explain|comment|security|declare|fetch|close|move|load)\M')
        then upper(substring(min(query) from '^\s*(\w+)')) || ' (texte masqué)'
      else left(regexp_replace(min(query), '\s+', ' ', 'g'), 2000)
    end as modele
  from pg_stat_statements
  where userid = (select oid from pg_roles where rolname = current_user)
    and dbid = (select oid from pg_database where datname = current_database())
  group by queryid
)
select
  a.pid::text as bloque_pid,
  a.bloqueur::text as bloqueur_pid,
  b.pid is not null as bloqueur_visible,
  coalesce(round(extract(epoch from now() - a.state_change)), 0)::bigint as attente_s,
  a.wait_event as type_verrou,
  a.application_name as bloque_application,
  a.query_id::text as bloque_requete_id,
  mb.modele as bloque_modele,
  b.state as bloqueur_etat,
  b.application_name as bloqueur_application,
  coalesce(round(extract(epoch from now() - b.xact_start)), 0)::bigint as bloqueur_transaction_s,
  b.query_id::text as bloqueur_requete_id,
  mk.modele as bloqueur_modele
from attentes a
left join sessions b on b.pid = a.bloqueur
left join modeles mb on mb.queryid = a.query_id
left join modeles mk on mk.queryid = b.query_id;
