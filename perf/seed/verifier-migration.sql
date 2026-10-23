-- Vérifie que migration.sql a produit une population que l'archivage ciblera.
-- Échoue avec un code de sortie non nul si ce n'est pas le cas.
--
-- Paramètres en GUC, comme verifier.sql : psql ne substitue pas ses variables
-- dans un bloc dollar-quoté.

\if :{?taille}
\else
  \set taille 2000
\endif
\if :{?prefixe}
\else
  \set prefixe 'perf-migr-'
\endif
\if :{?population}
\else
  \set population 'perf-migration'
\endif
\if :{?temoins}
\else
  \set temoins 47
\endif

SET perf.prefixe    = :'prefixe';
SET perf.population = :'population';
SET perf.taille     = :'taille';
SET perf.temoins    = :'temoins';

DO $$
DECLARE
  prefixe          text := current_setting('perf.prefixe');
  population_cible text := current_setting('perf.population');
  taille           int  := current_setting('perf.taille')::int;
  temoins          int  := current_setting('perf.temoins')::int;
  nb_cibles        int;
  nb_temoins       int;
  nb_deploiements  int;
  nb_archives      int;
  nb_id_distinct   int;
BEGIN
  -- Branche agence de sqlJeuneDansPopulation (api, sql-helpers.ts), appelée
  -- par MigrationSqlRepository.getBeneficiairesAMigrerParProfilOuConseillerCite.
  -- C'est la requête de l'api qui fait foi : à réaligner si elle change.
  SELECT count(*) INTO nb_cibles
  FROM jeune j
  JOIN conseiller c ON c.id = COALESCE(j.id_conseiller_initial, j.id_conseiller)
  WHERE EXISTS (
    SELECT 1 FROM population_agence_ft pa
    WHERE pa.id_population = population_cible
      AND pa.id_agence = c.id_agence
      AND (pa.dispositifs IS NULL OR c.dispositif = ANY (pa.dispositifs))
  );

  IF nb_cibles <> taille THEN
    RAISE EXCEPTION 'Population : % jeunes ciblés, % attendus', nb_cibles, taille;
  END IF;

  SELECT count(*) INTO nb_temoins
  FROM jeune j
  JOIN conseiller c ON c.id = COALESCE(j.id_conseiller_initial, j.id_conseiller)
  WHERE j.id LIKE prefixe || 'temoin-%'
    AND NOT EXISTS (
      SELECT 1 FROM population_agence_ft pa
      WHERE pa.id_population = population_cible AND pa.id_agence = c.id_agence
    );

  IF nb_temoins <> temoins THEN
    RAISE EXCEPTION 'Témoins : % jeunes hors population, % attendus', nb_temoins, temoins;
  END IF;

  SELECT count(*) INTO nb_deploiements
  FROM deploiement d
  WHERE d.id_population = population_cible AND d.nature = 'MIGRATION';

  IF nb_deploiements <> 1 THEN
    RAISE EXCEPTION 'Déploiement MIGRATION : % pour la population, 1 attendu', nb_deploiements;
  END IF;

  SELECT count(*) INTO nb_archives
  FROM archive_jeune a WHERE a.id_population = population_cible;

  IF nb_archives <> 0 THEN
    RAISE EXCEPTION 'Archives : % déjà présentes pour la population, 0 attendue', nb_archives;
  END IF;

  -- Le nettoyage doit révoquer avec le sub archivé, pas avec l'id du jeune :
  -- sans jeune dont les deux diffèrent, le tir ne le prouverait pas.
  SELECT count(*) INTO nb_id_distinct
  FROM jeune j
  WHERE j.id LIKE prefixe || '%'
    AND j.id NOT LIKE prefixe || 'temoin-%'
    AND j.id <> j.id_authentification;

  IF nb_id_distinct = 0 THEN
    RAISE EXCEPTION 'Aucun jeune dont l''id diffère du sub : le tir ne prouverait pas que le nettoyage lit le sub archivé';
  END IF;

  RAISE NOTICE 'OK — % jeunes ciblés, % témoins, % jeunes dont l''id diffère du sub',
    nb_cibles, nb_temoins, nb_id_distinct;
END $$;
