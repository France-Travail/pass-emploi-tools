-- Sème une population de migration que l'archivage puis le nettoyage ciblent.
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--        -v taille=2000 -v prefixe=perf-migr- -f migration.sql
--
-- prefixe et population se passent sans guillemets, comme pool_prefix dans
-- seed.sql : l'interpolation :'prefixe' quote déjà la valeur.
--
-- DESTRUCTEUR : supprime et recrée tout le périmètre du préfixe, archives de
-- la population comprises. À rejouer avant chaque tir : l'archivage supprime
-- les jeunes semés. Le garde-fou refuse une base non marquée.
--
-- Subs de largeur fixe (préfixe + 6 chiffres) : connect révoque par
-- KEYS *<sub>*, qui matche une sous-chaîne. Avec perf-migr-1, la révocation
-- ramasserait aussi les clés de perf-migr-10, perf-migr-100…
--
-- Les échecs sont portés par les données, que mock-externes lit : echec-chat
-- dans l'id du jeune, echec-mail dans son email. Un jeune marqué echec-chat a
-- donc un id différent de son sub, ce qui prouve que le nettoyage révoque avec
-- le sub archivé.

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
\if :{?nb_agences}
\else
  \set nb_agences 49
\endif
\if :{?portefeuille}
\else
  \set portefeuille 47
\endif
\if :{?inactifs_tous_les}
\else
  \set inactifs_tous_les 5
\endif
\if :{?echec_mail_tous_les}
\else
  \set echec_mail_tous_les 100
\endif
\if :{?echec_chat_tous_les}
\else
  \set echec_chat_tous_les 100
\endif
\if :{?temoins}
\else
  \set temoins 47
\endif

\ir garde-fou.sql

SET perf.taille = :'taille';
DO $$
BEGIN
  IF current_setting('perf.taille')::int > 999999 THEN
    RAISE EXCEPTION 'taille % : au plus 999999, les subs sont sur 6 chiffres',
      current_setting('perf.taille');
  END IF;
END $$;

BEGIN;

DELETE FROM archive_jeune WHERE id_population = :'population';
DELETE FROM deploiement WHERE id_population = :'population';
DELETE FROM population WHERE id = :'population';
DELETE FROM conseiller WHERE id LIKE :'prefixe' || '%';
DELETE FROM agence WHERE id LIKE :'prefixe' || '%';

-- structure legacy POLE_EMPLOI, comme les agences FT de la base : la requête
-- de population ne lit pas cette colonne.
INSERT INTO agence (id, nom_agence, nom_region, code_departement, structure, timezone)
SELECT
  :'prefixe' || 'agence-' || a,
  'Agence de perf ' || a,
  'Perf',
  '75',
  'POLE_EMPLOI',
  'Europe/Paris'
FROM generate_series(0, :nb_agences - 1) AS a
UNION ALL
SELECT :'prefixe' || 'agence-temoin', 'Agence témoin', 'Perf', '75', 'POLE_EMPLOI', 'Europe/Paris';

INSERT INTO conseiller (
  id, nom, prenom, email, username, structure, dispositif, id_agence,
  id_authentification, date_creation
)
SELECT
  id, 'Perf', 'Conseiller', id || '@perf.local', id, 'FRANCE_TRAVAIL', 'CEJ',
  id_agence, id, now()
FROM (
  SELECT
    :'prefixe' || 'conseiller-' || c AS id,
    :'prefixe' || 'agence-' || (c % :nb_agences) AS id_agence
  FROM generate_series(0, (:taille - 1) / :portefeuille) AS c
  UNION ALL
  SELECT :'prefixe' || 'conseiller-temoin', :'prefixe' || 'agence-temoin'
) AS conseillers;

INSERT INTO jeune (
  id, nom, prenom, id_conseiller, id_conseiller_initial, date_creation,
  email, structure, id_authentification, dispositif,
  date_derniere_activite, date_premiere_connexion, date_derniere_connexion
)
SELECT
  id, 'Perf', sub, id_conseiller, NULL, now(),
  email, 'FRANCE_TRAVAIL', sub, 'CEJ',
  CASE WHEN inactif THEN NULL ELSE now() END,
  CASE WHEN inactif THEN NULL ELSE now() END,
  CASE WHEN inactif THEN NULL ELSE now() END
FROM (
  SELECT
    sub,
    sub || CASE WHEN :echec_chat_tous_les > 0 AND i % :echec_chat_tous_les = 0
                THEN '-echec-chat' ELSE '' END AS id,
    sub || CASE WHEN :echec_mail_tous_les > 0 AND i % :echec_mail_tous_les = 1
                THEN '+echec-mail' ELSE '' END || '@perf.local' AS email,
    :inactifs_tous_les > 0 AND i % :inactifs_tous_les = :inactifs_tous_les - 1 AS inactif,
    :'prefixe' || 'conseiller-' || (i / :portefeuille) AS id_conseiller
  FROM generate_series(0, :taille - 1) AS i
  CROSS JOIN LATERAL (SELECT :'prefixe' || lpad(i::text, 6, '0') AS sub) AS s
  UNION ALL
  SELECT
    t.sub, t.sub, t.sub || '@perf.local', false, :'prefixe' || 'conseiller-temoin'
  FROM generate_series(0, :temoins - 1) AS k
  CROSS JOIN LATERAL (SELECT :'prefixe' || 'temoin-' || lpad(k::text, 6, '0') AS sub) AS t
) AS jeunes;

-- Mêmes profils i % 20 que seed.sql : l'archive d'un jeune porte ses favoris
-- et alertes, leur volume pèse sur l'archivage.
INSERT INTO favori_offre_emploi (
  id_jeune, id_offre, titre, type_contrat, date_creation,
  nom_entreprise, is_alternance, localisation_nom
)
SELECT
  j.id, 'offre-' || i || '-' || n, 'Offre de perf ' || n, 'CDI', now(),
  'Entreprise de perf', false, 'Paris'
FROM generate_series(0, :taille - 1) AS i
JOIN jeune j ON j.id_authentification = :'prefixe' || lpad(i::text, 6, '0')
CROSS JOIN LATERAL generate_series(
  1,
  CASE WHEN i % 20 = 19 THEN 15 WHEN i % 20 >= 14 THEN 2 ELSE 0 END
) AS n;

INSERT INTO recherche (id, id_jeune, type, titre, metier, localisation, criteres)
SELECT
  gen_random_uuid(), j.id, 'OFFRES_EMPLOI', 'Alerte de perf ' || n, 'Boulanger',
  'Paris', '{"commune":"75056"}'::jsonb
FROM generate_series(0, :taille - 1) AS i
JOIN jeune j ON j.id_authentification = :'prefixe' || lpad(i::text, 6, '0')
CROSS JOIN LATERAL generate_series(
  1,
  CASE WHEN i % 20 = 19 THEN 5 WHEN i % 20 >= 14 THEN 1 ELSE 0 END
) AS n;

INSERT INTO population (id, description)
VALUES (:'population', 'Population de migration du scénario de perf');

INSERT INTO population_agence_ft (id_population, id_agence, dispositifs)
SELECT :'population', :'prefixe' || 'agence-' || a, NULL
FROM generate_series(0, :nb_agences - 1) AS a;

INSERT INTO deploiement (nature, id_population, id_fonctionnalite, date_activation)
VALUES ('MIGRATION', :'population', NULL, now());

COMMIT;
