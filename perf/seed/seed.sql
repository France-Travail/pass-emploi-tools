-- Sème le pool de bénéficiaires que mock-externes tire au sort.
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--        -v pool_size=200 -v pool_prefix="'perf-ft-'" -f seed.sql
--
-- DESTRUCTEUR : supprime et recrée tout le périmètre du pool. Le garde-fou
-- refuse de s'exécuter sur une base non marquée (cf. garde-fou.sql).
--
-- pool_prefix et pool_size doivent valoir exactement POOL_PREFIX et POOL_SIZE
-- de mock-externes : le sub qu'il rend doit correspondre à un
-- id_authentification en base, faute de quoi l'API refuse le login
-- (UTILISATEUR_INEXISTANT — aucune auto-création pour un bénéficiaire FT).
--
-- Ni action ni rendez_vous ne sont semées : vides en production côté France
-- Travail, et hors du chemin de lecture de l'accueil (cf. volumetrie-prod.md).

\if :{?pool_size}
\else
  \set pool_size 50
\endif
\if :{?pool_prefix}
\else
  \set pool_prefix 'perf-ft-'
\endif

\ir garde-fou.sql

BEGIN;

-- Idempotence : les FK cascadent depuis conseiller, donc supprimer le
-- conseiller de perf efface ses jeunes, leurs favoris et leurs alertes.
DELETE FROM conseiller WHERE id = :'pool_prefix' || 'conseiller';

INSERT INTO conseiller (
  id, nom, prenom, email, username, structure, id_authentification, date_creation
) VALUES (
  :'pool_prefix' || 'conseiller',
  'Perf',
  'Conseiller',
  :'pool_prefix' || 'conseiller@perf.local',
  :'pool_prefix' || 'conseiller',
  'POLE_EMPLOI',
  :'pool_prefix' || 'conseiller',
  now()
);

INSERT INTO jeune (
  id, nom, prenom, id_conseiller, id_conseiller_initial, date_creation,
  email, structure, id_authentification, dispositif,
  date_derniere_activite, date_premiere_connexion, date_derniere_connexion
)
SELECT
  :'pool_prefix' || i,
  'Perf',
  :'pool_prefix' || i,
  :'pool_prefix' || 'conseiller',
  :'pool_prefix' || 'conseiller',
  now(),
  :'pool_prefix' || i || '@perf.local',
  'POLE_EMPLOI',
  :'pool_prefix' || i,
  'CEJ',
  now(), now(), now()
FROM generate_series(0, :pool_size - 1) AS i;

-- Trois profils répartis par i % 20 : 70 % vides, 25 % courants, 5 % tail.
-- Calés sur les percentiles POLE_EMPLOI du lot 0 (p50 = 0, p99 = 15 favoris).
-- generate_series(1, 0) ne produit aucune ligne : les profils vides le sont.
INSERT INTO favori_offre_emploi (
  id_jeune, id_offre, titre, type_contrat, date_creation,
  nom_entreprise, is_alternance, localisation_nom
)
SELECT
  :'pool_prefix' || i,
  'offre-' || i || '-' || n,
  'Offre de perf ' || n,
  'CDI',
  now(),
  'Entreprise de perf',
  false,
  'Paris'
FROM generate_series(0, :pool_size - 1) AS i
CROSS JOIN LATERAL generate_series(
  1,
  CASE WHEN i % 20 = 19 THEN 15 WHEN i % 20 >= 14 THEN 2 ELSE 0 END
) AS n;

INSERT INTO recherche (
  id, id_jeune, type, titre, metier, localisation, criteres
)
SELECT
  gen_random_uuid(),
  :'pool_prefix' || i,
  'OFFRES_EMPLOI',
  'Alerte de perf ' || n,
  'Boulanger',
  'Paris',
  '{"commune":"75056"}'::jsonb
FROM generate_series(0, :pool_size - 1) AS i
CROSS JOIN LATERAL generate_series(
  1,
  CASE WHEN i % 20 = 19 THEN 5 WHEN i % 20 >= 14 THEN 1 ELSE 0 END
) AS n;

COMMIT;
