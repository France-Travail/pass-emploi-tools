-- Ligne finale d'une chaîne de job lancée après t0, en une ligne JSON (rien si
-- elle n'est pas encore écrite). Seule la dernière ligne d'une chaîne est
-- sauvée : elle porte termine, ou chaineDejaEnCours si la route a refusé de
-- lancer une deuxième chaîne. Le filtre t0 écarte les lignes des tirs précédents.
--
--   psql "$DATABASE_URL" -At -v job_type=NETTOYER_ARCHIVES_JEUNES \
--        -v t0=2026-10-23T10:00:00Z -f suivi-job.sql

SELECT row_to_json(ligne)
FROM (
  SELECT
    id, job_run_id, succes, nb_erreurs, temps_execution, date_execution, resultat,
    EXTRACT(EPOCH FROM
      date_execution + temps_execution * interval '1 millisecond' - :'t0'::timestamptz
    )::float AS duree_totale_s
  FROM suivi_job
  WHERE job_type = :'job_type'
    AND date_execution >= :'t0'::timestamptz
    AND (resultat ? 'termine' OR resultat ? 'chaineDejaEnCours')
  ORDER BY id
  LIMIT 1
) AS ligne;
