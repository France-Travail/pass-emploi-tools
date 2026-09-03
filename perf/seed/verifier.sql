-- Vérifie que le seed a produit le pool et la répartition attendus.
-- Échoue avec un code de sortie non nul si ce n'est pas le cas.
--
-- Les paramètres transitent par des GUC plutôt que par interpolation psql :
-- psql ne substitue pas ses variables à l'intérieur d'un bloc dollar-quoté.

\if :{?pool_size}
\else
  \set pool_size 50
\endif
\if :{?pool_prefix}
\else
  \set pool_prefix 'perf-ft-'
\endif

SET perf.pool_prefix = :'pool_prefix';
SET perf.pool_size   = :'pool_size';

DO $$
DECLARE
  prefixe           text := current_setting('perf.pool_prefix');
  taille            int  := current_setting('perf.pool_size')::int;
  nb_jeunes         int;
  nb_favoris        int;
  nb_alertes        int;
  favoris_attendus  int;
  alertes_attendues int;
BEGIN
  SELECT count(*) INTO nb_jeunes
  FROM jeune WHERE id_authentification LIKE prefixe || '%';

  IF nb_jeunes <> taille THEN
    RAISE EXCEPTION 'Pool : % jeunes en base, % attendus', nb_jeunes, taille;
  END IF;

  SELECT count(*) INTO nb_favoris
  FROM favori_offre_emploi f
  JOIN jeune j ON j.id = f.id_jeune
  WHERE j.id_authentification LIKE prefixe || '%';

  SELECT sum(CASE WHEN i % 20 = 19 THEN 15 WHEN i % 20 >= 14 THEN 2 ELSE 0 END)
  INTO favoris_attendus FROM generate_series(0, taille - 1) i;

  IF nb_favoris <> favoris_attendus THEN
    RAISE EXCEPTION 'Favoris : % en base, % attendus', nb_favoris, favoris_attendus;
  END IF;

  SELECT count(*) INTO nb_alertes
  FROM recherche r
  JOIN jeune j ON j.id = r.id_jeune
  WHERE j.id_authentification LIKE prefixe || '%';

  SELECT sum(CASE WHEN i % 20 = 19 THEN 5 WHEN i % 20 >= 14 THEN 1 ELSE 0 END)
  INTO alertes_attendues FROM generate_series(0, taille - 1) i;

  IF nb_alertes <> alertes_attendues THEN
    RAISE EXCEPTION 'Alertes : % en base, % attendues', nb_alertes, alertes_attendues;
  END IF;

  RAISE NOTICE 'OK — % jeunes, % favoris, % alertes', nb_jeunes, nb_favoris, nb_alertes;
END $$;
