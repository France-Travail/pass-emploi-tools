# Lot 0 — Volumétrie de production : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produire une note datée d'agrégats de production qui permet de dimensionner l'image de base et le seed du harnais de tir de perf.

**Architecture:** Deux livrables versionnés. Un jeu de requêtes SQL réutilisable (`docs/perf/volumetrie-prod.sql`), écrit contre le schéma réel de `pass-emploi-api`, exécuté dans Metabase. Une note datée (`docs/perf/volumetrie-prod.md`) qui consigne les résultats et en dérive les paramètres de dimensionnement. Aucune donnée personnelle n'en sort : uniquement des comptages et des percentiles.

**Tech Stack:** PostgreSQL 14+ (fonctions `PERCENTILE_CONT`, `FILTER`), Metabase (`stats.pass-emploi.beta.gouv.fr`), Markdown.

**Spec:** `docs/superpowers/specs/2026-09-01-harnais-tir-perf-design.md` (§5.2)

## Global Constraints

- **Aucune donnée personnelle ne sort de la production.** Les requêtes ne renvoient que des comptages, des percentiles et des libellés de structure. Aucun `SELECT` de colonne nominative, d'email, ou d'identifiant de personne.
- **Lecture seule.** Aucune requête ne modifie quoi que ce soit.
- **Hors heure de pointe** pour les requêtes à balayage complet (Q1 à Q5, Q7).
- Les résultats sont **datés** dans la note : ils vieillissent, et une note non datée devient un piège.
- Périmètre du chantier : scénario v1 = **bénéficiaires France Travail accompagnés**. Les requêtes ventilent par structure pour que ce sous-ensemble soit lisible.

---

### Task 1 : Jeu de requêtes de volumétrie

**Files:**
- Create: `docs/perf/volumetrie-prod.sql`

**Interfaces:**
- Consumes: rien.
- Produces: sept requêtes nommées `Q1` à `Q7`, référencées par ces identifiants dans la note de la Task 2.

Les noms de tables et de colonnes viennent des modèles Sequelize de `pass-emploi-api`
(`src/infrastructure/sequelize/models/`) : `jeune`, `conseiller`, `action`,
`recherche`, `favori_offre_emploi`, `favori_offre_engagement`,
`favori_offre_immersion`, `rendez_vous_jeune_association`.

- [ ] **Step 1 : Écrire le fichier de requêtes**

Créer `docs/perf/volumetrie-prod.sql` avec exactement ce contenu :

```sql
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
```

- [ ] **Step 2 : Vérifier que tables et colonnes existent bien dans le schéma**

Le risque réel ici n'est pas une faute de syntaxe, c'est un nom inventé. Chaque
identifiant doit se retrouver dans les modèles Sequelize.

Run :

```bash
cd ../pass-emploi-api && for t in jeune conseiller action recherche \
  favori_offre_emploi favori_offre_engagement favori_offre_immersion \
  rendez_vous_jeune_association; do
  printf '%-32s ' "$t"
  grep -rq "tableName: '$t'" src/infrastructure/sequelize/models/ \
    && echo OK || echo MANQUANT
done
for c in id_conseiller id_jeune structure date_derniere_activite \
  date_premiere_connexion; do
  printf '%-32s ' "$c"
  grep -rq "field: '$c'" src/infrastructure/sequelize/models/ \
    && echo OK || echo MANQUANT
done
```

Expected : douze lignes `OK`, aucune `MANQUANT`.

Si une ligne ressort `MANQUANT`, corriger la requête concernée dans le `.sql`
avant de continuer — ne pas contourner en supprimant la vérification.

- [ ] **Step 3 : Commit**

```bash
cd ../pass-emploi-tools
git add docs/perf/volumetrie-prod.sql
git commit -m "docs(perf): requêtes de volumétrie de production (lot 0)"
```

---

### Task 2 : Note de volumétrie datée

**Files:**
- Create: `docs/perf/volumetrie-prod.md`
- Modify: `docs/perf/README.md` (ligne « Harnais de tir » du tableau des sous-chantiers)

**Interfaces:**
- Consumes: les sorties de `Q1` à `Q7` de la Task 1.
- Produces: les paramètres de dimensionnement `N` (taille du pool), la cible de volumétrie de l'image de base, et le gabarit d'un jeune semé — consommés par le lot 2 (seed) et le lot 1 (pool du mock).

> **Cette tâche exige un accès Metabase.** Les requêtes doivent être exécutées
> par une personne qui l'a ; le reste de la tâche est de la rédaction.

- [ ] **Step 1 : Exécuter Q6 d'abord**

Dans Metabase, sur la base de production, exécuter `Q6` seule. Elle est sans coût
et donne l'ordre de grandeur qui dit si les requêtes suivantes sont raisonnables
telles quelles.

Si une table dépasse la dizaine de millions de lignes, ne pas lancer Q1-Q5 en
l'état : les faire porter sur un échantillon (`TABLESAMPLE SYSTEM (10)` sur
`jeune`) et le noter dans la note.

- [ ] **Step 2 : Exécuter Q1 à Q5 et Q7, hors heure de pointe**

Consigner les sorties brutes. Vérifier au passage qu'aucune colonne nominative
n'apparaît dans les résultats : si c'est le cas, la requête a été modifiée à
tort, revenir au fichier versionné.

- [ ] **Step 3 : Rédiger la note**

Créer `docs/perf/volumetrie-prod.md` sur ce squelette, en remplaçant chaque
`…` par les valeurs mesurées :

```markdown
# Volumétrie de production — entrées de dimensionnement

> **Mesuré le …** sur la base de production, via Metabase.
> Requêtes : [`volumetrie-prod.sql`](./volumetrie-prod.sql).
> Ces chiffres vieillissent — les remesurer avant une nouvelle campagne de tirs.
>
> Uniquement des agrégats : aucune donnée personnelle.

## Portefeuilles conseiller (Q1)

| Conseillers | p50 | p90 | p99 | max |
|---|---|---|---|---|
| … | … | … | … | … |

## Données par jeune (Q2 à Q5)

Ventilé par structure ; la ligne qui compte pour le scénario v1 est celle des
bénéficiaires France Travail.

| Donnée | Structure | p50 | p90 | p99 | max |
|---|---|---|---|---|---|
| Actions | … | … | … | … | … |
| Favoris | … | … | … | … | … |
| Alertes | … | … | … | … | … |
| Rendez-vous | … | … | … | … | … |

## Volumétrie des tables (Q6)

| Table | Lignes | Poids |
|---|---|---|
| … | … | … |

## Répartition et activité (Q7)

| Structure | Total | Actifs 7j | Actifs 30j | Jamais connectés |
|---|---|---|---|---|
| … | … | … | … | … |

## Ce qu'on en retient pour le harnais

- **Taille du pool `N`** : …
- **Volumétrie cible de l'image de base** : …
- **Gabarit d'un jeune semé** : … actions, … favoris, … alertes, … RDV
- **Écarts notables** : …
```

- [ ] **Step 4 : Dériver les paramètres de dimensionnement**

Remplir la section « Ce qu'on en retient », en explicitant le raisonnement plutôt
qu'en posant des nombres nus :

- Le **gabarit d'un jeune semé** se cale sur le **p90**, pas sur la médiane : un
  seed médian produit des plans d'exécution flatteurs.
- La **taille du pool `N`** doit dépasser le nombre d'utilisateurs concurrents
  visés, sinon les mêmes lignes restent chaudes et le cache masque la charge
  réelle.
- La **volumétrie de l'image de base** vise l'ordre de grandeur de Q6, pas sa
  valeur exacte : c'est la taille des index et la sélectivité qui comptent.

- [ ] **Step 5 : Basculer la ligne du sous-chantier**

Dans `docs/perf/README.md`, tableau « Sous-chantiers », remplacer le contenu de
la ligne « Harnais de tir (env, jeu de données, outillage) » :

- colonne Doc : `TODO` → `[volumetrie-prod.md](./volumetrie-prod.md)`
- colonne Statut : `Non démarré` → `WIP — lot 0 rendu (volumétrie mesurée le …)`

- [ ] **Step 6 : Commit**

```bash
git add docs/perf/volumetrie-prod.md docs/perf/README.md
git commit -m "docs(perf): volumétrie de production mesurée (lot 0)"
```

---

## Points de vigilance

- **Metabase peut être branché sur un réplica ou un schéma dérivé**, pas sur la
  base applicative. Si une requête échoue sur un nom de table, c'est le premier
  soupçon : vérifier le schéma exposé avant de réécrire la requête.
- **`n_live_tup` est une estimation** issue de l'autovacuum. Suffisant pour
  dimensionner, à ne pas citer comme un comptage exact.
- **Q1 ne filtre pas les conseillers inactifs** : un portefeuille à zéro tire la
  médiane vers le bas. Si la p50 ressort très basse, c'est la première piste.
