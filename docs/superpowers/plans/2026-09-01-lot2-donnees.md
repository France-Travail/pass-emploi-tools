# Lot 2 — Jeu de données : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un seed SQL idempotent, paramétré et protégé, qui crée en base le pool d'identités que `mock-externes` tire au sort, avec les volumétries mesurées au lot 0.

**Architecture:** SQL autonome joué par `psql`, sans dépendance au repo `pass-emploi-api`. Le pool est engendré par `generate_series`. L'idempotence repose sur les cascades : supprimer le conseiller de perf efface ses jeunes, leurs favoris et leurs alertes.

**Tech Stack:** PostgreSQL 14 + PostGIS (image `postgis/postgis:14-3.2-alpine` du `docker-compose` de l'API), `psql`.

**Spec:** `docs/superpowers/specs/2026-09-01-harnais-tir-perf-design.md` (§5)
**Volumétrie de référence:** `docs/perf/volumetrie-prod.md`

## Global Constraints

- **Le seed est destructeur.** Il ne doit jamais pouvoir s'exécuter ailleurs que sur une base de perf, et le garde-fou ne peut pas reposer sur une convention de nommage : les bases Scalingo ont des noms générés.
- **Idempotent.** Deux exécutions successives laissent la base dans le même état.
- **Le `sub` fait foi.** `id_authentification` doit valoir `{POOL_PREFIX}{i}`, exactement ce que rend `mock-externes` — sinon le login échoue en `UTILISATEUR_INEXISTANT`.
- **Périmètre identifiable.** Toutes les entités créées portent le préfixe du pool, pour que la suppression soit sûre.
- **Ni `action` ni `rendez_vous`** : vides en production côté France Travail, hors du chemin de lecture de l'accueil (lot 0).

## Schéma réel, relevé le 2026-09-01

Contre la base locale de l'API, migrations appliquées — et non déduit des modèles
Sequelize, qui ne déclarent pas la nullabilité.

| Table | `NOT NULL` sans défaut | À savoir |
|---|---|---|
| `conseiller` | `id`, `nom`, `prenom` | — |
| `jeune` | `id`, `nom`, `prenom`, `date_creation` | FK `id_conseiller` → `conseiller(id)` **ON DELETE CASCADE** |
| `recherche` | `id`, `id_jeune`, `titre`, `type`, `criteres` | `id` est un `uuid` **sans défaut** ; `geometrie` nullable |
| `favori_offre_emploi` | `id_jeune`, `id_offre`, `titre`, `type_contrat`, `date_creation` | `id` vient d'une séquence |

`dispositif` sur `jeune` est nullable depuis la migration `20260725000000`.
Aucune contrainte `CHECK` sur `structure`.

## Profils, issus du lot 0

Répartition par `i % 20`, qui donne exactement 70 / 25 / 5 % :

| Profil | `i % 20` | Part | Favoris | Alertes |
|---|---|---|---|---|
| Vide | 0-13 | 70 % | 0 | 0 |
| Courant | 14-18 | 25 % | 2 | 1 |
| Tail | 19 | 5 % | 15 | 5 |

Calés sur les percentiles `POLE_EMPLOI` (p50 = 0, p99 = 15 favoris / 4 alertes).

---

### Task 1 : Garde-fou et marqueur d'environnement

**Files:**
- Create: `perf/seed/marquer-environnement.sql`
- Create: `perf/seed/garde-fou.sql`

**Interfaces:**
- Produces: table `perf_marqueur`, et un fragment SQL inclus en tête du seed qui lève une exception si elle est absente.

**Pourquoi un marqueur plutôt qu'un test sur le nom de la base :** les bases
Scalingo portent des noms générés, et une heuristique sur le nom serait à la fois
faillible et contournable par accident. Un marqueur **posé à la main une seule
fois** sur la base de perf ne peut jamais être satisfait par la production.

- [ ] **Step 1 : Écrire `marquer-environnement.sql`**

```sql
-- À jouer UNE FOIS, à la main, sur la base de perf — jamais ailleurs.
CREATE TABLE IF NOT EXISTS perf_marqueur (
  pose_le    timestamptz NOT NULL DEFAULT now(),
  pose_par   text        NOT NULL,
  commentaire text
);

INSERT INTO perf_marqueur (pose_par, commentaire)
SELECT current_user, 'Base de tir de perf — le seed est autorisé à détruire ici'
WHERE NOT EXISTS (SELECT 1 FROM perf_marqueur);
```

- [ ] **Step 2 : Écrire `garde-fou.sql`**

```sql
DO $$
BEGIN
  IF to_regclass('public.perf_marqueur') IS NULL
     OR NOT EXISTS (SELECT 1 FROM perf_marqueur) THEN
    RAISE EXCEPTION
      'GARDE-FOU : la base "%" ne porte pas le marqueur de perf. Le seed est destructeur et refuse de s''exécuter. Poser le marqueur avec marquer-environnement.sql si, et seulement si, cette base est bien un environnement de tir.',
      current_database();
  END IF;
END $$;
```

- [ ] **Step 3 : Vérifier que le garde-fou bloque une base non marquée**

Run :

```bash
export PGPASSWORD=passemploi
psql -h localhost -p 55432 -U passemploi -d passemploidb -v ON_ERROR_STOP=1 \
  -f perf/seed/garde-fou.sql
```

Expected : ÉCHEC, message `GARDE-FOU`, code de sortie non nul.

- [ ] **Step 4 : Poser le marqueur, vérifier que le garde-fou passe**

Run : le `marquer-environnement.sql` puis à nouveau le `garde-fou.sql`.
Expected : les deux réussissent, code de sortie 0.

- [ ] **Step 5 : Commit**

---

### Task 2 : Pool de bénéficiaires

**Files:**
- Create: `perf/seed/seed.sql`

**Interfaces:**
- Consumes: `garde-fou.sql`.
- Produces: un conseiller `{prefix}conseiller`, et `POOL_SIZE` jeunes dont `id_authentification` vaut `{prefix}{i}`.

Paramètres `psql` : `-v pool_size=…` et `-v pool_prefix=…`, avec des valeurs par
défaut alignées sur `mock-externes` (`50`, `perf-ft-`).

- [ ] **Step 1 : Écrire l'entête, le nettoyage et les inserts**

Le nettoyage tient en une ligne grâce aux cascades :

```sql
DELETE FROM conseiller WHERE id = :'pool_prefix' || 'conseiller';
```

Puis le conseiller, puis les jeunes par `generate_series(0, :pool_size - 1)`.

- [ ] **Step 2 : Jouer le seed sur la base locale marquée**

Expected : succès.

- [ ] **Step 3 : Vérifier le compte et l'appariement des identités**

```sql
SELECT count(*) FROM jeune WHERE id_authentification LIKE :'pool_prefix' || '%';
```

Expected : `pool_size`.

- [ ] **Step 4 : Vérifier l'idempotence — rejouer, recompter**

Expected : le même compte, pas le double.

- [ ] **Step 5 : Commit**

---

### Task 3 : Profils de données

**Files:**
- Modify: `perf/seed/seed.sql`
- Create: `perf/seed/verifier.sql`

**Interfaces:**
- Produces: favoris et alertes réparties en trois profils ; `verifier.sql` échoue si la répartition n'est pas celle attendue.

- [ ] **Step 1 : Écrire `verifier.sql` en premier**

Assertions en `DO` / `RAISE EXCEPTION` sur : le compte du pool, le nombre total
de favoris et d'alertes attendu pour `pool_size`, et l'existence d'au moins un
jeune de profil « tail ».

Pour `pool_size = 20` : 14 jeunes vides, 5 courants (2 favoris, 1 alerte),
1 tail (15 favoris, 5 alertes) → **25 favoris** et **10 alertes**.

- [ ] **Step 2 : Lancer, vérifier l'échec**

Expected : ÉCHEC — les favoris et alertes ne sont pas encore semés.

- [ ] **Step 3 : Ajouter les inserts de favoris et d'alertes au seed**

`recherche.id` n'a pas de défaut : fournir `gen_random_uuid()`.
`criteres` est un `jsonb` `NOT NULL`.

- [ ] **Step 4 : Rejouer seed puis vérification**

Expected : PASS.

- [ ] **Step 5 : Vérifier l'idempotence de l'ensemble**

Rejouer seed + vérification une seconde fois. Expected : PASS identique.

- [ ] **Step 6 : Commit**

---

### Task 4 : Mode d'emploi

**Files:**
- Create: `perf/seed/README.md`
- Modify: `perf/README.md` (prérequis pour tirer)

Doit couvrir : la pose du marqueur (une fois), l'appariement `POOL_PREFIX` /
`POOL_SIZE` avec `mock-externes`, la commande de seed, et le fait que
`action` et `rendez_vous` ne sont volontairement pas semées.

- [ ] **Step 1 : Écrire le README**
- [ ] **Step 2 : Mettre à jour les prérequis de `perf/README.md`**
- [ ] **Step 3 : Commit**

## Hors périmètre de ce lot

L'**image de base** (§5.1 de la spec) n'est pas traitée ici : elle suppose un
environnement Scalingo pour mesurer la durée d'un `pg_restore`, et le lot 0 a
montré qu'elle se limite à quelques centaines de Mo une fois exclues
`cache_api_partenaire`, `archive_jeune` et `action`. À reprendre quand les apps
existeront.
