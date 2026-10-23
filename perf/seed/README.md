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
     -v pool_size=50000 -v pool_prefix=perf-ft- -f seed.sql
```

> ⚠️ **`pool_prefix` sans guillemets.** Les scripts interpolent avec `:'pool_prefix'`,
> la forme psql qui quote elle-même la valeur. Des guillemets dans le `-v` se
> retrouvent donc *dans* la chaîne : le pool est semé sous `'perf-ft-'0` au lieu
> de `perf-ft-0`, `verifier.sql` annonce `0 jeunes en base`, et un tir échouerait
> en `UTILISATEUR_INEXISTANT`.

Idempotent : rejouable autant de fois que voulu, la base finit dans le même
état. Les FK cascadent depuis les conseillers de perf, donc le nettoyage tient
en une ligne — les supprimer efface leurs jeunes, favoris et alertes.

Vérifier le résultat :

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v pool_size=50000 -f verifier.sql
```

## Optionnel : le fond de charge

Le pool étant désormais dimensionné sur les arrivées du tir, il porte à lui
seul la volumétrie de prod (≈48 500 bénéficiaires `POLE_EMPLOI`) et le fond est
à **0 par défaut**. Il reste utile pour pousser la table `jeune` *au-delà* de la
prod : `fond-de-charge.sql` sème des bénéficiaires **hors du pool** (préfixe
distinct, jamais tirés par `mock-externes`), aux mêmes distributions que lui :

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
     -v fond_size=48000 -v fond_prefix=perf-fond- -f fond-de-charge.sql
```

Ce n'est **pas** un restore de snapshot de prod (mécanique non tranchée,
cf. `docs/perf/harnais.md`) : une approximation de volume, opt-in, séparée de
`seed.sql` pour ne jamais changer son comportement. Idempotent, garde-fou
anti-prod partagé avec `seed.sql`.

## Population de migration (scénario job d'archivage)

`migration.sql` sème une population que l'archivage de migration puis le
nettoyage des archives ciblent. Le workflow `perf-job-archivage.yml` le rejoue
avant chaque tir, l'archivage étant destructeur.

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v taille=2000 -f migration.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -v taille=2000 -f verifier-migration.sql
psql "$DATABASE_URL" -At -f attendus-migration.sql   # une ligne JSON, lue par le verdict
```

| Paramètre | Défaut | Rôle |
|---|---|---|
| `taille` | `2000` | Jeunes de la population (999 999 au plus) |
| `prefixe` | `perf-migr-` | Préfixe des ids (sans guillemets, comme `pool_prefix`) |
| `population` | `perf-migration` | Id de la population et de son déploiement `MIGRATION` |
| `nb_agences` | `49` | Agences citées par la population |
| `portefeuille` | `47` | Jeunes par conseiller |
| `inactifs_tous_les` | `5` | 1 jeune sur N sans date de dernière activité ni de connexion (`0` : aucun) |
| `echec_mail_tous_les` | `100` | 1 jeune sur N dont le mail échoue (`0` : aucun) |
| `echec_chat_tous_les` | `100` | 1 jeune sur N dont le chat échoue (`0` : aucun) |
| `temoins` | `47` | Jeunes d'une agence non citée, qui doivent survivre à l'archivage |

**Les échecs sont portés par les données**, que `mock-externes` lit sans état :
`echec-mail` dans l'email du jeune, `echec-chat` dans son id. Un jeune
`echec-chat` a donc un id différent de son sub, ce qui prouve que le nettoyage
révoque avec le sub archivé. Les marqués mail sont tous actifs (seuls les actifs
reçoivent le mail).

**Préfixe distinct du pool.** L'archivage supprime les jeunes : avec le préfixe
du pool, il détruirait des identités que le mock tire au login. Et connect
révoque par `KEYS *<sub>*`, une sous-chaîne : les subs sont donc sur 6 chiffres
(`perf-migr-000001`), sinon `perf-migr-1` ramasserait les clés de
`perf-migr-10…`.

**`structure = FRANCE_TRAVAIL`, dispositif `CEJ`**, pour le jeune comme pour le
conseiller : c'est le modèle Profil de l'api. La population cible par agence,
sans filtre de dispositif.

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

**`pool_size` doit couvrir les arrivées du tir** (et non la concurrence, comme
le voulait la règle initiale `5 × MAX_USERS` — un ordre de grandeur trop bas).
Le workflow calcule les arrivées depuis le profil d'injection et refuse de tirer
si le pool ne suit pas. À pool trop petit, les mêmes lignes sont relues pendant
toute la fenêtre, restent chaudes en cache PostgreSQL, et le tir mesure le cache.
Voir l'invariant dans [`docs/perf/harnais.md`](../../docs/perf/harnais.md).

## Ce qui est semé

Des conseillers `{prefix}conseiller-{c}` portant **47 jeunes chacun** (la p90
mesurée, comme `fond-de-charge.sql`), puis `pool_size` bénéficiaires de
structure `FRANCE_TRAVAIL` répartis en trois profils par `i % 20` :

| Profil | Part | Favoris | Alertes |
|---|---|---|---|
| Vide | 70 % | 0 | 0 |
| Courant | 25 % | 2 | 1 |
| Tail | 5 % | 15 | 5 |

Ces profils reproduisent la **forme** de la distribution de production, qui est
à queue lourde : p50 = 0 favori, p90 = 1, p99 = 15. Un gabarit uniforme calé sur
la p90 donnerait un pool où chaque jeune a un favori — ni le cas courant, ni le
cas coûteux, et des tirs verts qui ne prouvent rien.

Chaque conseiller porte un dispositif FT accompagné, choisi par `c % 7` (CEJ,
BRSA, AIJ, AVENIR_PRO, ACCOMPAGNEMENT_INTENSIF, ACCOMPAGNEMENT_GLOBAL,
EQUIP_EMPLOI_RECRUT), que ses jeunes reprennent. La règle est déterministe :
deux seeds produisent la même base, donc deux tirs restent comparables. Le
parcours login puis accueil est le même pour ces sept dispositifs ; les
non-accompagnés (DEMANDEUR_D_EMPLOI, ESPACE_CANDIDAT) en sont exclus.

## Ce qui n'est pas semé, délibérément

**Ni `action` ni `rendez_vous`.** Le lot 0 a montré qu'elles sont vides côté
France Travail — ce sont des objets MILO. Pour un bénéficiaire FT, démarches et
agenda viennent des APIs partenaires, mockées. Elles sont aussi hors du chemin
de lecture de l'accueil, dont les seules lectures en base sont alertes, favoris
et campagne.

**Le fond de charge** n'est pas du ressort de ce script : il sème les acteurs
du tir (le pool), pas le volume qui l'entoure. Voir
[`fond-de-charge.sql`](./fond-de-charge.sql) — un script séparé, opt-in,
sémantiquement distinct (approximation synthétique, pas un restore de vraie
donnée de prod).

## Diagnostic

| Symptôme | Cause probable |
|---|---|
| `GARDE-FOU : la base "…" ne porte pas le marqueur` | Marqueur non posé — vérifier **qu'on vise bien la base de perf** avant de le poser |
| Login en échec `UTILISATEUR_INEXISTANT` | `pool_prefix` / `pool_size` désalignés avec le mock |
| `Pool : 0 jeunes en base` au vérificateur | `pool_prefix` passé avec des guillemets, ou seed joué sur une autre base que celle vérifiée |
| `Population : N jeunes ciblés` au vérificateur de migration | `prefixe` passé avec des guillemets, ou requête de population de l'api modifiée : réaligner `verifier-migration.sql` |
| Le tir frappe toujours les mêmes jeunes | `pool_size` plus petit que le nombre d'arrivées du tir — le workflow le refuse et affiche le minimum à poser |
