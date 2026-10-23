-- Attendus du verdict, comptés dans la base semée plutôt que recalculés par
-- formule : une ligne JSON, à lancer en -At juste après migration.sql.

\if :{?prefixe}
\else
  \set prefixe 'perf-migr-'
\endif
\if :{?population}
\else
  \set population 'perf-migration'
\endif

WITH semes AS (
  SELECT
    j.id,
    j.email,
    j.id LIKE :'prefixe' || 'temoin-%' AS temoin,
    j.date_derniere_activite IS NOT NULL AND j.date_derniere_connexion IS NOT NULL AS actif
  FROM jeune j
  WHERE j.id LIKE :'prefixe' || '%'
)
SELECT json_build_object(
  'id_population', :'population',
  'population', count(*) FILTER (WHERE NOT temoin),
  'actifs', count(*) FILTER (WHERE NOT temoin AND actif),
  'echecs_mail', count(*) FILTER (WHERE NOT temoin AND actif AND email LIKE '%echec-mail%'),
  'echecs_chat', count(*) FILTER (WHERE NOT temoin AND id LIKE '%echec-chat%'),
  'temoins', count(*) FILTER (WHERE temoin)
)
FROM semes;
