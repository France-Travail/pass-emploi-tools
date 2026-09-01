# Volumétrie de production — entrées de dimensionnement

> **Mesuré le 2026-09-01** sur la base de production, via Metabase.
> Requêtes : [`volumetrie-prod.sql`](./volumetrie-prod.sql).
> Ces chiffres vieillissent — les remesurer avant une nouvelle campagne de tirs.
>
> Uniquement des agrégats : aucune donnée personnelle.

## Portefeuilles conseiller (Q1)

| Conseillers | p50 | p90 | p99 | max |
|---|---|---|---|---|
| 21 513 | 0 | 47 | 105 | 300 |

**La p50 à zéro n'est pas une anomalie de mesure** : plus de la moitié des comptes
conseiller n'ont aucun bénéficiaire rattaché (comptes inactifs, transférés,
supervision). Un dimensionnement fondé sur la médiane serait absurde ; c'est la
p90 (47) et la p99 (105) qui décrivent un portefeuille réel.

Sans effet sur le scénario v1, qui est côté bénéficiaire. À reprendre pour un
futur scénario conseiller.

## Données par jeune (Q2 à Q5)

Ligne de référence pour le scénario v1 : **`POLE_EMPLOI`**, structure des
bénéficiaires France Travail accompagnés.

| Donnée | Structure | p50 | p90 | p99 | max |
|---|---|---|---|---|---|
| Actions | POLE_EMPLOI | 0 | 0 | 0 | 11 |
| Actions | MILO *(comparaison)* | 14 | 152 | 361 | 1 852 |
| Favoris | POLE_EMPLOI | 0 | 1 | 15 | 853 |
| Alertes | POLE_EMPLOI | 0 | 0 | 4 | 44 |
| Rendez-vous | POLE_EMPLOI | 0 | 0 | 0 | 0 |
| Rendez-vous | MILO *(comparaison)* | 2 | 7 | 24 | 161 |

Répartition des favoris et alertes sur les autres structures France Travail
(p99 / max), pour situer `POLE_EMPLOI` dans son ensemble :

| Structure | Jeunes | Favoris p99 / max | Alertes p99 / max |
|---|---|---|---|
| FT_ACCOMPAGNEMENT_INTENSIF | 59 294 | 13 / 625 | 6 / 266 |
| POLE_EMPLOI | 48 521 | 15 / 853 | 4 / 44 |
| POLE_EMPLOI_AIJ | 20 445 | 11 / 283 | 3 / 624 |
| POLE_EMPLOI_BRSA | 12 440 | 12 / 265 | 6 / 331 |
| FT_EQUIP_EMPLOI_RECRUT | 8 766 | 11 / 178 | 5 / 448 |
| FT_ACCOMPAGNEMENT_GLOBAL | 6 505 | 10 / 1 338 | 5 / 35 |

Total France Travail toutes structures confondues : **≈ 156 000 bénéficiaires**,
contre 134 781 côté MILO.

### Deux constats structurants

**1. `action` et `rendez_vous` sont vides côté France Travail.** Les percentiles
sont à zéro sur toutes les structures FT, jusqu'au max (11 actions sur 48 521
bénéficiaires `POLE_EMPLOI`, zéro rendez-vous). Ce ne sont pas des données
manquantes : pour un bénéficiaire FT, les démarches et les rendez-vous d'agenda
viennent des **APIs France Travail**, pas de notre base. Les tables `action` et
`rendez_vous` sont des objets MILO.

Conséquence directe : **le seed n'a aucune raison de peupler `action` ni
`rendez_vous`** pour le scénario v1. Ça recoupe exactement le flux documenté de
l'accueil FT, dont les seules lectures en base sont **alertes, favoris et
campagne**.

**2. Les distributions sont à queue lourde, pas seulement basses.** Pour les
favoris `POLE_EMPLOI` : p50 = 0, p90 = 1, p99 = 15, max = 853. L'écrasante
majorité des bénéficiaires n'a rien, et le coût réel se concentre dans une
minorité. Un seed uniforme calé sur la p90 produirait un pool où **chaque jeune
a un favori** — ni le cas médian réel, ni le cas coûteux. Voir la conséquence en
fin de note.

## Volumétrie des tables (Q6)

| Table | Lignes | Poids |
|---|---|---|
| `cache_api_partenaire` | 699 904 | **6 638 MB** |
| `archive_jeune` | 372 525 | **4 408 MB** |
| `action` | 6 873 587 | **3 926 MB** |
| `jeune` | 292 018 | 442 MB |
| `fichier` | 1 026 266 | 405 MB |
| `rendez_vous` | 497 688 | 243 MB |
| `rendez_vous_jeune_association` | 412 507 | 182 MB |
| `favori_offre_emploi` | 187 465 | 135 MB |
| `notification_jeune` | 289 849 | 145 MB |
| `situations_milo` | 134 290 | 128 MB |
| `transfert_conseiller` | 271 889 | 98 MB |
| `suggestion` | 71 887 | 79 MB |
| `recherche` | 60 535 | 66 MB |
| `evenement_engagement_hebdo` | 339 704 | 62 MB |
| `session_milo` | 340 551 | 41 MB |
| `conseiller` | 21 513 | 22 MB |

Total prod ≈ 17 Go, mais **trois tables en portent les deux tiers** :

- `cache_api_partenaire` (6,6 Go) — cache de réponses partenaires, **repeuplé à
  l'usage**. Aucun intérêt à le restaurer : le tir le remplira lui-même, et le
  restaurer fausserait même la mesure en offrant un cache déjà chaud.
- `archive_jeune` (4,4 Go) — comptes archivés, hors de tout chemin de lecture du
  scénario.
- `action` (3,9 Go) — données MILO, hors périmètre v1.

## Répartition et activité (Q7)

| Structure | Total | Actifs 7j | Actifs 30j | Jamais connectés |
|---|---|---|---|---|
| MILO | 134 781 | 49 168 (36 %) | 65 902 (49 %) | 10 705 |
| FT_ACCOMPAGNEMENT_INTENSIF | 59 293 | 11 875 (20 %) | 19 067 (32 %) | 20 813 |
| POLE_EMPLOI | 48 520 | 16 414 (34 %) | 24 460 (50 %) | 6 440 |
| POLE_EMPLOI_AIJ | 20 445 | 4 680 (23 %) | 7 475 (37 %) | 5 502 |
| POLE_EMPLOI_BRSA | 12 440 | 2 002 (16 %) | 3 187 (26 %) | 3 979 |
| FT_EQUIP_EMPLOI_RECRUT | 8 766 | 1 058 (12 %) | 1 804 (21 %) | 4 219 |
| FT_ACCOMPAGNEMENT_GLOBAL | 6 505 | 875 (13 %) | 1 521 (23 %) | 2 769 |

Environ **un tiers des bénéficiaires `POLE_EMPLOI` sont actifs à 7 jours**, la
moitié à 30 jours. Le fond de charge en base est donc environ deux fois le volume
réellement sollicité — ce qui compte pour la taille des index, pas pour le trafic.

## Ce qu'on en retient pour le harnais

### Taille du pool `N`

**`N ≥ 5 × MAX_USERS`, avec un plancher à 50.**

C'est une règle, pas un nombre, parce que `MAX_USERS` change d'un tir à l'autre.
Le seul impératif est que le pool dépasse largement le nombre d'utilisateurs
concurrents : à `N` proche de `MAX_USERS`, les mêmes lignes restent chaudes en
cache PostgreSQL et le tir mesure le cache, pas la base.

Aucune contrainte de réalisme ne limite `N` par le haut : la production compte
48 521 bénéficiaires `POLE_EMPLOI`, tout `N` envisageable pour un tir reste
négligeable devant ce volume.

### Gabarit d'un jeune semé — trois profils, pas un

C'est le point où je corrige la règle posée dans la spec (« caler sur la p90 »).
Elle supposait une distribution où la p90 est représentative ; les mesures
montrent une **queue lourde**, où la p90 vaut 0 ou 1. Caler dessus donnerait un
pool uniformément vide, qui ne mesurerait ni le cas courant ni le cas coûteux.

Le seed doit donc reproduire la **forme** de la distribution, en trois profils
répartis sur le pool :

| Profil | Part du pool | Favoris | Alertes | Ce qu'il mesure |
|---|---|---|---|---|
| Vide | 70 % | 0 | 0 | Le cas courant : coût d'un accès qui ne ramène rien |
| Courant | 25 % | 2 | 1 | Le cas nominal |
| Tail | 5 % | 15 | 5 | Le p99, où se concentre le coût réel |

Valeurs tirées des percentiles `POLE_EMPLOI` (Q3, Q4). Les 5 % de profil « tail »
garantissent qu'un tir de quelques centaines d'utilisateurs en frappe plusieurs.

**Ni `action` ni `rendez_vous` ne sont semées** : hors du chemin de lecture de
l'accueil FT, et vides en production pour cette structure.

### Volumétrie cible de l'image de base

**Exclure `cache_api_partenaire`, `archive_jeune` et `action`** — les deux tiers
du poids, aucune sur le chemin du scénario, et restaurer le cache partenaire
fausserait la mesure.

L'image utile se limite aux tables du chemin de lecture et à leur environnement :
`jeune`, `conseiller`, `favori_offre_*`, `recherche`, `campagne`,
`reponse_campagne`. Soit un ordre de grandeur de **quelques centaines de Mo**
plutôt que 17 Go, ce qui rend le `pg_restore` compatible avec un rythme de
campagne soutenu.

Cible de volumétrie : conserver l'ordre de grandeur de `jeune` (≈ 290 000 lignes),
qui détermine la taille des index et la sélectivité des accès.

### Écarts notables

- **MILO et France Travail n'ont rien de comparable** en base : MILO porte les
  actions et les rendez-vous, FT quasiment rien. Un scénario MILO exigerait un
  seed d'une tout autre nature — à ne pas déduire de cette note.
- **`POLE_EMPLOI` n'est pas la plus grosse structure FT** :
  `FT_ACCOMPAGNEMENT_INTENSIF` la dépasse (59 294 contre 48 521), avec des
  distributions proches. Le choix de `POLE_EMPLOI` comme référence tient à sa
  correspondance directe avec le parcours v1, pas à son volume.
- **`cache_api_partenaire` pèse 6,6 Go pour 700 000 lignes**, soit ≈ 9 ko par
  ligne. À surveiller pendant les tirs : c'est la table que le tir fait grossir.
