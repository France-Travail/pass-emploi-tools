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
| `plugins/`         | Skills Claude Code partagées de l'équipe                       | [plugins/README.md](./plugins/README.md)                     |
| `perf/`            | Harnais de tir de charge (Gatling)                             | [perf/README.md](./perf/README.md)                           |
| `heartbeat/`       | Sonde de disponibilité (Elastic Heartbeat)                     | —                                                            |
| `proxy/`, `stats/` | Briques d'infra annexes                                        | —                                                            |

## Skills Claude Code partagées

Le repo publie une **marketplace de plugins Claude Code** : les skills utiles à
toute l'équipe y sont versionnées, plutôt que dupliquées dans le `~/.claude/`
de chacun.

```bash
/plugin marketplace add France-Travail/pass-emploi-tools   # une fois
/plugin install dependency-tools@pass-emploi               # scope "user"
```

| Plugin             | Skill                | À quoi ça sert                                                              |
|--------------------|----------------------|-----------------------------------------------------------------------------|
| `dependency-tools` | `upgrade-dependency` | Monter une dépendance de version (breaking changes, PR Dependabot/Renovate) |
| `dependency-tools` | `fix-cve`            | Corriger une CVE, ou toutes les CVE d'un repo en un seul plan validé        |

Les skills se déclenchent automatiquement, il n'y a rien à invoquer.

**Installation détaillée, mise à jour (côté utilisateur et côté producteur) et
ajout d'une skill : [plugins/README.md](./plugins/README.md).**

## Liens

- [Contexte transverse Pass Emploi](./docs/CONTEXTE-TRANSVERSE.md) — architecture, glossaire, conventions
- [Index des sujets transverses](./docs/SUJETS-TRANSVERSES.md)
- [Conventions de documentation](./docs/CONVENTIONS-DOC.md)
