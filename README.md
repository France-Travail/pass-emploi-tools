# Pass Emploi Tools

Outillage transverse de l'équipe Pass Emploi (CEJ) : infra de logs mutualisée,
workflows CI réutilisables, documentation transverse et skills Claude Code
partagées.

Ce repo ne porte aucune fonctionnalité produit — c'est la **boîte à outils
commune** aux repos `api`, `web`, `connect` et `app`.

## Contenu

| Dossier            | Rôle                                                           | Doc                                                          |
|--------------------|----------------------------------------------------------------|--------------------------------------------------------------|
| `logs/`            | Pipeline Logstash + templates Elasticsearch versionnés         | [logs/README.md](./logs/README.md)                           |
| `docs/`            | Documentation transverse (source de vérité partagée)           | [docs/CONTEXTE-TRANSVERSE.md](./docs/CONTEXTE-TRANSVERSE.md) |
| `.github/`         | Workflows et actions GitHub réutilisables par les autres repos | [.github/README.md](./.github/README.md)                     |
| `plugins/`         | Skills Claude Code partagées de l'équipe                       | [voir ci-dessous](#skills-claude-code-partagées)             |
| `perf/`            | Harnais de tir de charge (Gatling)                             | [perf/README.md](./perf/README.md)                           |
| `heartbeat/`       | Sonde de disponibilité (Elastic Heartbeat)                     | —                                                            |
| `proxy/`, `stats/` | Briques d'infra annexes                                        | —                                                            |

## Skills Claude Code partagées

Le repo publie une **marketplace de plugins Claude Code** : les skills utiles à
toute l'équipe y sont versionnées, plutôt que dupliquées dans le `~/.claude/`
de chacun.

### Installation

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

### Plugins disponibles

| Plugin             | Skill                | À quoi ça sert                                                              |
|--------------------|----------------------|-----------------------------------------------------------------------------|
| `dependency-tools` | `upgrade-dependency` | Monter une dépendance de version (breaking changes, PR Dependabot/Renovate) |
| `dependency-tools` | `fix-cve`            | Corriger une CVE / alerte Dependabot (GHSA, sortie `yarn audit`)            |

### Utilisation

Les skills se déclenchent **automatiquement** quand la demande correspond, il
n'y a rien à invoquer :

- « monte axios en v2 », « bump cette dépendance » → `upgrade-dependency`
- « corrige cette cve (avec l'id de la cve par exemple et/ou le nom de la dépendance) »  → `fix-cve`

Pour vérifier qu'elles sont bien chargées : `claude plugin list`.

### Mise à jour

```bash
/plugin marketplace update pass-emploi
```

### Ajouter une skill à la bibliothèque

Une skill utile à plusieurs personnes a vocation à vivre **ici**, pas dans un
`~/.claude/skills/` individuel.

1. Créer `plugins/<plugin>/skills/<nom-skill>/SKILL.md`
2. Si c'est un nouveau plugin : ajouter `plugins/<plugin>/.claude-plugin/plugin.json`
   (nom, description, `version`) et référencer le plugin dans
   [`.claude-plugin/marketplace.json`](./.claude-plugin/marketplace.json)
3. Sinon : bumper la `version` du `plugin.json` du plugin modifié — c'est elle
   qui déclenche la mise à jour chez les autres
4. PR sur `master` : la marketplace est lue depuis la branche par défaut du
   repo, une skill non mergée n'est installable par personne

> Rôle des trois fichiers : `marketplace.json` = catalogue de ce que le repo
> publie · `plugin.json` = manifeste d'un plugin (porte la version) ·
> `enabledPlugins` dans un `settings.json` = ce que chacun active de son côté.

## Liens

- [Contexte transverse Pass Emploi](./docs/CONTEXTE-TRANSVERSE.md) — architecture, glossaire, conventions
- [Index des sujets transverses](./docs/SUJETS-TRANSVERSES.md)
- [Conventions de documentation](./docs/CONVENTIONS-DOC.md)
