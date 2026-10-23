-- Contrôles SQL après l'archivage, en une ligne JSON.
--
--   psql "$DATABASE_URL" -At -v prefixe=perf-migr- -v population=perf-migration \
--        -f controles-archivage.sql

SELECT json_build_object(
  'jeunes_population_restants',
    (SELECT count(*) FROM jeune
     WHERE id LIKE :'prefixe' || '%' AND id NOT LIKE :'prefixe' || 'temoin-%'),
  'temoins_restants',
    (SELECT count(*) FROM jeune WHERE id LIKE :'prefixe' || 'temoin-%'),
  'archives',
    (SELECT count(*) FROM archive_jeune WHERE id_population = :'population')
);
