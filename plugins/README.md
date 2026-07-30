# Skills Claude Code partagées

Ce répertoire publie une **marketplace de plugins Claude Code** : les skills
utiles à toute l'équipe y sont versionnées, plutôt que dupliquées dans le
`~/.claude/` de chacun.

## Plugins disponibles

| Plugin             | Skill                | À quoi ça sert                                                              |
|--------------------|----------------------|-----------------------------------------------------------------------------|
| `dependency-tools` | `upgrade-dependency` | Monter une dépendance de version (breaking changes, PR Dependabot/Renovate) |
| `dependency-tools` | `fix-cve`            | Corriger une CVE, ou toutes les CVE d'un repo en un seul plan validé        |

## Installation

```bash
# Une fois : déclarer la marketplace de l'équipe
/plugin marketplace add France-Travail/pass-emploi-tools

# Installer le plugin voulu
/plugin install dependency-tools@pass-emploi
```

Puis `/reload-plugins` (ou redémarrer Claude Code) pour que les skills
apparaissent.

L'installation demande un **scope** : choisir `user` pour que les skills soient
disponibles dans **tous tes repos** (c'est le cas d'usage normal — elles servent
surtout dans `api`, `web` et `connect`). Le scope `project` ne les activerait
que dans le repo courant.

En CLI, `user` est le scope par défaut :

```bash
claude plugin install dependency-tools@pass-emploi --scope user
```

## Utilisation

Les skills se déclenchent **automatiquement** quand la demande correspond, il
n'y a rien à invoquer :

- « monte axios en v2 », « bump cette dépendance » → `upgrade-dependency`
- « corrige cette cve (avec l'id de la cve par exemple et/ou le nom de la dépendance) » → `fix-cve`

Pour vérifier qu'elles sont bien chargées : `claude plugin list`.

## Mise à jour — côté utilisateur

Récupérer la dernière version publiée d'un plugin demande **deux** commandes,
puis un redémarrage :

```bash
claude plugin marketplace update pass-emploi        # 1. rafraîchit le catalogue depuis GitHub
claude plugin update dependency-tools@pass-emploi   # 2. installe la nouvelle version
# puis redémarrer Claude Code
```

En session, les mêmes en slash-commands : `/plugin marketplace update pass-emploi`
puis `/plugin update dependency-tools@pass-emploi`.

> ⚠️ **La commande 1 seule ne suffit pas.** Elle met à jour le clone du repo,
> pas la skill qui s'exécute. Ce qui tourne réellement est une **copie figée**
> dans `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, épinglée à
> un commit. Sans la commande 2, tu continues d'exécuter l'ancienne version
> sans aucun signe extérieur.

Vérifier la version réellement installée :

```bash
claude plugin list
#   ❯ dependency-tools@pass-emploi
#     Version: 0.2.0        ← doit correspondre au plugin.json sur master
#     Status: ✔ enabled
```

Rien ne prévient qu'une nouvelle version est sortie : le réflexe est de lancer
ces deux commandes quand l'équipe annonce une publication.

## Mise à jour — côté producteur

Pour publier une modification de skill :

```bash
# 1. modifier la skill dans CE repo (jamais dans ~/.claude/, voir plus bas)
# 2. bumper la version du plugin modifié
#    plugins/<plugin>/.claude-plugin/plugin.json : "version": "0.2.0"
claude plugin validate plugins/<plugin>          # 3. valider le manifeste
# 4. PR sur master, puis merge
```

> ⚠️ **Le bump de version est ce qui déclenche la mise à jour chez les autres.**
> Sans lui, `claude plugin update` ne voit rien à faire et toute l'équipe reste
> sur son ancienne copie — même si le code est mergé sur `master`. C'est
> l'oubli le plus coûteux du process : il est silencieux des deux côtés.

Versionnage : `patch` pour une correction de formulation, `minor` pour une
nouvelle règle ou une nouvelle skill, `major` si le comportement attendu change.
`claude plugin tag` pose un tag `<plugin>--v<version>` en vérifiant que
`plugin.json` et l'entrée marketplace concordent.

Deux pièges de manipulation :

- **Ne jamais éditer une skill dans `~/.claude/plugins/`** — ni dans
  `marketplaces/` (clone géré par Claude Code, la modif fera conflit au
  prochain update), ni dans `cache/` (écrasé à la prochaine installation). La
  source de vérité est ce repo.
- La marketplace est lue depuis la **branche par défaut** du repo : une skill
  non mergée sur `master` n'est installable par personne.

## Ajouter une skill à la bibliothèque

Une skill utile à plusieurs personnes a vocation à vivre **ici**, pas dans un
`~/.claude/skills/` individuel.

1. Créer `plugins/<plugin>/skills/<nom-skill>/SKILL.md`
2. Si c'est un nouveau plugin : ajouter `plugins/<plugin>/.claude-plugin/plugin.json`
   (nom, description, `version`) et référencer le plugin dans
   [`../.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json)
3. Publier en suivant [Mise à jour — côté producteur](#mise-à-jour--côté-producteur)
   (bump de version, validation, PR sur `master`)

> Rôle des trois fichiers : `marketplace.json` = catalogue de ce que le repo
> publie · `plugin.json` = manifeste d'un plugin (porte la version) ·
> `enabledPlugins` dans un `settings.json` = ce que chacun active de son côté.
