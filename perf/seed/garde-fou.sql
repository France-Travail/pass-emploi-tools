-- Refuse toute exécution sur une base qui ne porte pas le marqueur de perf.
--
-- Le test ne porte pas sur le nom de la base : les bases Scalingo ont des noms
-- générés, et une heuristique de nommage serait à la fois faillible et
-- satisfaite par accident. Le marqueur, lui, ne peut être posé qu'à la main.

DO $$
BEGIN
  IF to_regclass('public.perf_marqueur') IS NULL
     OR NOT EXISTS (SELECT 1 FROM perf_marqueur) THEN
    RAISE EXCEPTION
      'GARDE-FOU : la base "%" ne porte pas le marqueur de perf. Le seed est destructeur et refuse de s''exécuter. Poser le marqueur avec marquer-environnement.sql si, et seulement si, cette base est bien un environnement de tir.',
      current_database();
  END IF;
END $$;
