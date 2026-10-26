-- Sème la population de migration que vise le scénario d'archivage :
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v nb_jeunes=2000 -f migration.sql
--
-- DESTRUCTEUR et rejouable : supprime puis recrée tout le périmètre du
-- préfixe, archives de la population comprises, puisque l'archivage supprime
-- les jeunes semés. Préfixe distinct du pool de seed.sql : l'archivage
-- détruirait sinon les identités que mock-externes tire au login.

\if :{?nb_jeunes}
\else
  \set nb_jeunes 2000
\endif
\set prefixe 'perf-migr-'
\set population 'perf-migration'
\set nb_agences 49
\set portefeuille 47

\ir garde-fou.sql

BEGIN;

DELETE FROM archive_jeune WHERE id_population = :'population';
DELETE FROM deploiement WHERE id_population = :'population';
DELETE FROM population WHERE id = :'population';
DELETE FROM conseiller WHERE id LIKE :'prefixe' || '%';
DELETE FROM agence WHERE id LIKE :'prefixe' || '%';

-- structure legacy POLE_EMPLOI, comme les agences FT de la base : la requête
-- de population ne lit pas cette colonne.
INSERT INTO agence (id, nom_agence, nom_region, code_departement, structure, timezone)
SELECT :'prefixe' || 'agence-' || a, 'Agence de perf ' || a, 'Perf', '75', 'POLE_EMPLOI', 'Europe/Paris'
FROM generate_series(0, :nb_agences - 1) AS a;

INSERT INTO conseiller (
  id, nom, prenom, email, username, structure, dispositif, id_agence,
  id_authentification, date_creation
)
SELECT
  :'prefixe' || 'conseiller-' || c, 'Perf', 'Conseiller',
  :'prefixe' || 'conseiller-' || c || '@perf.local', :'prefixe' || 'conseiller-' || c,
  'FRANCE_TRAVAIL', 'CEJ', :'prefixe' || 'agence-' || (c % :nb_agences),
  :'prefixe' || 'conseiller-' || c, now()
FROM generate_series(0, (:nb_jeunes - 1) / :portefeuille) AS c;

-- 1 jeune sur 5 inactif : sans dernière activité ni connexion, il est archivé
-- sans recevoir de mail.
INSERT INTO jeune (
  id, nom, prenom, id_conseiller, date_creation, email, structure,
  id_authentification, dispositif,
  date_derniere_activite, date_premiere_connexion, date_derniere_connexion
)
SELECT
  :'prefixe' || i, 'Perf', 'Jeune', :'prefixe' || 'conseiller-' || (i / :portefeuille), now(),
  :'prefixe' || i || '@perf.local', 'FRANCE_TRAVAIL', :'prefixe' || i, 'CEJ',
  CASE WHEN i % 5 = 4 THEN NULL ELSE now() END,
  CASE WHEN i % 5 = 4 THEN NULL ELSE now() END,
  CASE WHEN i % 5 = 4 THEN NULL ELSE now() END
FROM generate_series(0, :nb_jeunes - 1) AS i;

INSERT INTO population (id, description)
VALUES (:'population', 'Population de migration du scénario de perf');

INSERT INTO population_agence_ft (id_population, id_agence, dispositifs)
SELECT :'population', :'prefixe' || 'agence-' || a, NULL
FROM generate_series(0, :nb_agences - 1) AS a;

INSERT INTO deploiement (nature, id_population, id_fonctionnalite, date_activation)
VALUES ('MIGRATION', :'population', NULL, now());

COMMIT;
