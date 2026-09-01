-- Volumétrie de production — entrées de dimensionnement du harnais de tir.
-- Cf. docs/superpowers/specs/2026-09-01-harnais-tir-perf-design.md (§5.2)
--
-- Lecture seule. Ne renvoie que des agrégats : aucune donnée personnelle.
-- Q6 est gratuite (statistiques du catalogue) : la lancer en premier pour
-- cadrer. Q1-Q5 et Q7 balayent les grosses tables : hors heure de pointe.

-- Q1 — Taille des portefeuilles conseiller.
-- La médiane ne suffit pas : ce sont les gros portefeuilles qui font mal.
SELECT
  COUNT(*)                                                        AS nb_conseillers,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY nb_jeunes)         AS p50,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY nb_jeunes)         AS p90,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY nb_jeunes)         AS p99,
  MAX(nb_jeunes)                                                  AS max
FROM (
  SELECT c.id, COUNT(j.id) AS nb_jeunes
  FROM conseiller c
  LEFT JOIN jeune j ON j.id_conseiller = c.id
  GROUP BY c.id
) portefeuilles;

-- Q2 — Actions par jeune, ventilé par structure.
SELECT
  structure,
  COUNT(*)                                                        AS nb_jeunes,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY nb_actions)        AS p50,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY nb_actions)        AS p90,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY nb_actions)        AS p99,
  MAX(nb_actions)                                                 AS max
FROM (
  SELECT j.id, j.structure, COUNT(a.id) AS nb_actions
  FROM jeune j
  LEFT JOIN action a ON a.id_jeune = j.id
  GROUP BY j.id, j.structure
) actions_par_jeune
GROUP BY structure
ORDER BY nb_jeunes DESC;

-- Q3 — Favoris par jeune (les trois types confondus), ventilé par structure.
WITH favoris AS (
  SELECT id_jeune FROM favori_offre_emploi
  UNION ALL
  SELECT id_jeune FROM favori_offre_engagement
  UNION ALL
  SELECT id_jeune FROM favori_offre_immersion
)
SELECT
  structure,
  COUNT(*)                                                        AS nb_jeunes,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY nb_favoris)        AS p50,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY nb_favoris)        AS p90,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY nb_favoris)        AS p99,
  MAX(nb_favoris)                                                 AS max
FROM (
  SELECT j.id, j.structure, COUNT(f.id_jeune) AS nb_favoris
  FROM jeune j
  LEFT JOIN favoris f ON f.id_jeune = j.id
  GROUP BY j.id, j.structure
) favoris_par_jeune
GROUP BY structure
ORDER BY nb_jeunes DESC;

-- Q4 — Alertes (recherches sauvegardées) par jeune, ventilé par structure.
SELECT
  structure,
  COUNT(*)                                                        AS nb_jeunes,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY nb_alertes)        AS p50,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY nb_alertes)        AS p90,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY nb_alertes)        AS p99,
  MAX(nb_alertes)                                                 AS max
FROM (
  SELECT j.id, j.structure, COUNT(r.id) AS nb_alertes
  FROM jeune j
  LEFT JOIN recherche r ON r.id_jeune = j.id
  GROUP BY j.id, j.structure
) alertes_par_jeune
GROUP BY structure
ORDER BY nb_jeunes DESC;

-- Q5 — Rendez-vous par jeune, ventilé par structure.
SELECT
  structure,
  COUNT(*)                                                        AS nb_jeunes,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY nb_rdv)            AS p50,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY nb_rdv)            AS p90,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY nb_rdv)            AS p99,
  MAX(nb_rdv)                                                     AS max
FROM (
  SELECT j.id, j.structure, COUNT(rvja.id) AS nb_rdv
  FROM jeune j
  LEFT JOIN rendez_vous_jeune_association rvja ON rvja.id_jeune = j.id
  GROUP BY j.id, j.structure
) rdv_par_jeune
GROUP BY structure
ORDER BY nb_jeunes DESC;

-- Q6 — Volumétrie et poids des tables. Lit les statistiques du catalogue,
-- ne balaye rien : sans coût, à lancer en premier.
-- n_live_tup est une estimation, suffisante pour dimensionner.
SELECT
  relname                                                         AS table_name,
  n_live_tup                                                      AS lignes_estimees,
  pg_size_pretty(pg_total_relation_size(relid))                   AS poids_total
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC
LIMIT 25;

-- Q7 — Répartition par structure, et part de jeunes actifs.
-- Un jeune dormant occupe la base sans peser sur le trafic : la part
-- d'actifs sépare le fond de charge du volume réellement sollicité.
SELECT
  structure,
  COUNT(*)                                                        AS total,
  COUNT(*) FILTER (
    WHERE date_derniere_activite > NOW() - INTERVAL '7 days'
  )                                                               AS actifs_7j,
  COUNT(*) FILTER (
    WHERE date_derniere_activite > NOW() - INTERVAL '30 days'
  )                                                               AS actifs_30j,
  COUNT(*) FILTER (
    WHERE date_premiere_connexion IS NULL
  )                                                               AS jamais_connectes
FROM jeune
GROUP BY structure
ORDER BY total DESC;
