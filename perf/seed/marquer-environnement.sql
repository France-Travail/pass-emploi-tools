-- À jouer UNE FOIS, à la main, sur la base de perf — jamais ailleurs.
--
-- Ce marqueur est la seule chose qui autorise seed.sql à détruire des données.
-- Il n'existe volontairement aucun moyen de le poser depuis le workflow de tir :
-- c'est un geste humain, délibéré, sur une base dont on sait qu'elle est jetable.

CREATE TABLE IF NOT EXISTS perf_marqueur (
  pose_le     timestamptz NOT NULL DEFAULT now(),
  pose_par    text        NOT NULL,
  commentaire text
);

INSERT INTO perf_marqueur (pose_par, commentaire)
SELECT current_user, 'Base de tir de perf — le seed est autorisé à détruire ici'
WHERE NOT EXISTS (SELECT 1 FROM perf_marqueur);
