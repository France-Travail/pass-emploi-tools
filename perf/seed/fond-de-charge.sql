-- Sème un fond de charge : des bénéficiaires France Travail supplémentaires,
-- hors du pool, jamais tirés par mock-externes (préfixe distinct de
-- POOL_PREFIX). Sans lui, le tir mesure une table `jeune` de la taille du
-- pool (quelques centaines de lignes) au lieu de la taille de prod (≈48 500
-- bénéficiaires POLE_EMPLOI) : plan de requête, pression sur le cache buffer
-- et coût des index n'ont alors aucune raison de ressembler à la prod.
--
-- Fichier séparé de seed.sql, volontairement : le fond de charge est un choix
-- de fidélité (gros volume, lent à semer), le pool est un prérequis dur
-- (login échoue sans lui). Ne pas les coupler évite qu'une modification de
-- l'un ne redimensionne l'autre par accident.
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--        -v fond_size=48000 -v fond_prefix=perf-fond- -f fond-de-charge.sql
--
-- fond_prefix sans guillemets, comme pool_prefix (cf. seed.sql) : l'interpolation
-- :'fond_prefix' quote déjà la valeur.
--
-- DESTRUCTEUR sur son propre périmètre (fond_prefix) : supprime et recrée les
-- conseillers de fond, jamais le pool. Le garde-fou anti-prod de seed.sql
-- s'applique ici aussi.
--
-- Distribution calée sur docs/perf/volumetrie-prod.md, ligne POLE_EMPLOI :
-- mêmes profils favoris/alertes par jeune que seed.sql (70 % vides, 25 %
-- courants, 5 % tail), portefeuilles par conseiller proches de la p90 mesurée
-- (47 jeunes) plutôt qu'un unique conseiller géant qui fausserait toute
-- requête filtrant par id_conseiller.
--
-- Ni action ni rendez_vous : vides côté France Travail (cf. seed.sql).

\if :{?fond_size}
\else
  \set fond_size 0
\endif
\if :{?fond_prefix}
\else
  \set fond_prefix 'perf-fond-'
\endif

\ir garde-fou.sql

\set portefeuille 47

BEGIN;

-- Idempotence : les FK cascadent depuis conseiller (cf. seed.sql), donc
-- supprimer les conseillers de fond efface leurs jeunes, favoris et alertes.
DELETE FROM conseiller WHERE id LIKE :'fond_prefix' || 'conseiller-%';

INSERT INTO conseiller (
  id, nom, prenom, email, username, structure, id_authentification, date_creation
)
SELECT
  :'fond_prefix' || 'conseiller-' || c,
  'Perf',
  'ConseillerFond',
  :'fond_prefix' || 'conseiller-' || c || '@perf.local',
  :'fond_prefix' || 'conseiller-' || c,
  'POLE_EMPLOI',
  :'fond_prefix' || 'conseiller-' || c,
  now()
FROM generate_series(0, ((:fond_size - 1) / :portefeuille)) AS c;

INSERT INTO jeune (
  id, nom, prenom, id_conseiller, id_conseiller_initial, date_creation,
  email, structure, id_authentification, dispositif,
  date_derniere_activite, date_premiere_connexion, date_derniere_connexion
)
SELECT
  :'fond_prefix' || i,
  'Perf',
  :'fond_prefix' || i,
  :'fond_prefix' || 'conseiller-' || (i / :portefeuille),
  :'fond_prefix' || 'conseiller-' || (i / :portefeuille),
  now(),
  :'fond_prefix' || i || '@perf.local',
  'POLE_EMPLOI',
  :'fond_prefix' || i,
  'CEJ',
  now(), now(), now()
FROM generate_series(0, :fond_size - 1) AS i;

-- Même distribution par profil que le pool (cf. seed.sql) : 70 % vides,
-- 25 % courants, 5 % tail, calée sur les percentiles POLE_EMPLOI du lot 0.
INSERT INTO favori_offre_emploi (
  id_jeune, id_offre, titre, type_contrat, date_creation,
  nom_entreprise, is_alternance, localisation_nom
)
SELECT
  :'fond_prefix' || i,
  'offre-fond-' || i || '-' || n,
  'Offre de perf ' || n,
  'CDI',
  now(),
  'Entreprise de perf',
  false,
  'Paris'
FROM generate_series(0, :fond_size - 1) AS i
CROSS JOIN LATERAL generate_series(
  1,
  CASE WHEN i % 20 = 19 THEN 15 WHEN i % 20 >= 14 THEN 2 ELSE 0 END
) AS n;

INSERT INTO recherche (
  id, id_jeune, type, titre, metier, localisation, criteres
)
SELECT
  gen_random_uuid(),
  :'fond_prefix' || i,
  'OFFRES_EMPLOI',
  'Alerte de perf ' || n,
  'Boulanger',
  'Paris',
  '{"commune":"75056"}'::jsonb
FROM generate_series(0, :fond_size - 1) AS i
CROSS JOIN LATERAL generate_series(
  1,
  CASE WHEN i % 20 = 19 THEN 5 WHEN i % 20 >= 14 THEN 1 ELSE 0 END
) AS n;

COMMIT;
