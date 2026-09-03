# Seed du jeu de données de perf

Crée en base le pool de bénéficiaires que [`mock-externes`](../mock-externes/README.md)
tire au sort, avec les volumétries mesurées dans
[`docs/perf/volumetrie-prod.md`](../../docs/perf/volumetrie-prod.md).

## Une fois par environnement : poser le marqueur

Le seed est **destructeur**. Il refuse de s'exécuter sur une base qui ne porte
pas de marqueur de perf :

```sh
psql "$DATABASE_URL" -f marquer-environnement.sql
```

> Ce geste est **volontairement manuel et absent du workflow de tir**. Le
> garde-fou ne teste pas le nom de la base : les bases Scalingo ont des noms
> générés, et une heuristique de nommage serait à la fois faillible et
> satisfaite par accident. Un marqueur posé à la main ne peut jamais l'être
> par la production.

## À chaque tir : semer

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
     -v pool_size=200 -v pool_prefix=perf-ft- -f seed.sql
```

> ⚠️ **`pool_prefix` sans guillemets.** Les scripts interpolent avec `:'pool_prefix'`,
> la forme psql qui quote elle-même la valeur. Des guillemets dans le `-v` se
> retrouvent donc *dans* la chaîne : le pool est semé sous `'perf-ft-'0` au lieu
> de `perf-ft-0`, `verifier.sql` annonce `0 jeunes en base`, et un tir échouerait
> en `UTILISATEUR_INEXISTANT`.

Idempotent : rejouable autant de fois que voulu, la base finit dans le même
état. Les FK cascadent depuis le conseiller de perf, donc le nettoyage tient en
une ligne — supprimer le conseiller efface ses jeunes, leurs favoris et leurs
alertes.

Vérifier le résultat :

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v pool_size=200 -f verifier.sql
```

## Appariement avec `mock-externes`

> ⚠️ **`pool_prefix` et `pool_size` doivent valoir exactement `POOL_PREFIX` et
> `POOL_SIZE` du mock.** Le `sub` qu'il rend devient l'`id_authentification`
> cherché en base. S'il n'y correspond aucun jeune, l'API répond
> `UTILISATEUR_INEXISTANT` et le login échoue — elle ne crée aucun bénéficiaire
> France Travail inconnu.

| Paramètre | `seed.sql` | `mock-externes` | Défaut |
|---|---|---|---|
| Préfixe | `-v pool_prefix` | `POOL_PREFIX` | `perf-ft-` |
| Taille | `-v pool_size` | `POOL_SIZE` | `50` |

Le lot 0 recommande **`pool_size ≥ 5 × MAX_USERS`** : à pool trop petit, les
mêmes lignes restent chaudes en cache PostgreSQL et le tir mesure le cache.

## Ce qui est semé

Un conseiller `{prefix}conseiller`, puis `pool_size` bénéficiaires de structure
`POLE_EMPLOI`, répartis en trois profils par `i % 20` :

| Profil | Part | Favoris | Alertes |
|---|---|---|---|
| Vide | 70 % | 0 | 0 |
| Courant | 25 % | 2 | 1 |
| Tail | 5 % | 15 | 5 |

Ces profils reproduisent la **forme** de la distribution de production, qui est
à queue lourde : p50 = 0 favori, p90 = 1, p99 = 15. Un gabarit uniforme calé sur
la p90 donnerait un pool où chaque jeune a un favori — ni le cas courant, ni le
cas coûteux, et des tirs verts qui ne prouvent rien.

## Ce qui n'est pas semé, délibérément

**Ni `action` ni `rendez_vous`.** Le lot 0 a montré qu'elles sont vides côté
France Travail — ce sont des objets MILO. Pour un bénéficiaire FT, démarches et
agenda viennent des APIs partenaires, mockées. Elles sont aussi hors du chemin
de lecture de l'accueil, dont les seules lectures en base sont alertes, favoris
et campagne.

**L'image de base** n'est pas du ressort de ce script : il sème les acteurs du
tir, pas le fond de charge.

## Diagnostic

| Symptôme | Cause probable |
|---|---|
| `GARDE-FOU : la base "…" ne porte pas le marqueur` | Marqueur non posé — vérifier **qu'on vise bien la base de perf** avant de le poser |
| Login en échec `UTILISATEUR_INEXISTANT` | `pool_prefix` / `pool_size` désalignés avec le mock |
| `Pool : 0 jeunes en base` au vérificateur | `pool_prefix` passé avec des guillemets, ou seed joué sur une autre base que celle vérifiée |
| Le tir frappe toujours les mêmes jeunes | `pool_size` trop petit devant `MAX_USERS` |
