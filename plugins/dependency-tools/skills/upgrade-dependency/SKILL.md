---
name: upgrade-dependency
description: Use whenever upgrading, bumping or updating any dependency to a new version (minor, major, security), reviewing a Dependabot/Renovate PR, or when a bump caused build/type/runtime errors. Also called by fix-cve to assess a major bump. Triggers - "monter en version", "mettre à jour la dépendance X", "bump", "upgrade", "passer X en vY".
argument-hint: "<package> [target-version] [--headless]"
---

# Upgrade Dependency

Any version bump, from a patch to a multi-major jump. You do not need to know in advance whether
there are breaking changes: this skill investigates, sizes the work, and **reports before
changing anything**.

**Investigate → recap → validation → act.** Never touch code or `package.json` before the recap
is approved.

## Modes

| | Conversational (default) | Headless (`--headless`) or subagent |
|---|---|---|
| Steps | 1 → 7 | 1 → 5, **read-only** |
| Output | recap, then the upgrade once approved | the recap is the final output |
| Writes | after the go | **none** — no edit, no install, no commit |

A subagent shares the caller's working tree: one install from it would rewrite the lockfile under
every other investigation in flight. That is why it never writes.

## 1. Versions and target

Read the installed version and the `package.json` range. Without a version from the user, the
target is **the latest stable, one major at a time**:

- latest within the same major → latest;
- several majors behind (13 → 16) → the **next** major only (13 → 14); each major is its own
  investigation, never chain them silently;
- ignore pre-releases (beta / rc / next / canary) unless asked.

Then read what the target requires — release notes are vague about runtime, metadata is not:

```bash
npm view <pkg>@<target> version engines peerDependencies type exports
```

- **Node / peers** satisfy `engines` / `peerDependencies`?
- **ESM-only** (`"type": "module"`, no `require` condition in `exports`) consumed from a CommonJS
  build (`tsconfig` `module`, `"type"` of the repo) → `ERR_REQUIRE_ESM` at runtime while `tsc`
  passes. Plan a dynamic `import()` or flag it as a blocker.

## 2. Depth

- **Patch / minor** → low risk, no deep dig: go to the recap.
- **Major, security, or anything suspicious** → steps 3 and 4.

## 3. Breaking changes — past the release notes

For each breaking change, open the artifact that carries the real API delta:

- the **linked PR diff** for a discrete change (symbol removed / renamed);
- the **migration guide** for a rewrite or a large reorganisation.

The goal is the concrete before / after API, not the headline.

While the package is open, a non-blocking health check:

```bash
npm view <pkg> deprecated time.modified
```

Flag, without acting, a deprecated or clearly unmaintained package, or a widely adopted modern
alternative you are **sure** of (moment → luxon, request → fetch). Unsure → say nothing.

## 4. Map each breaking change to the code

| Breaking change | Usage in repo | Impact |
|---|---|---|
| `X removed` | `grep -rn "X" src/` → N hits | refactor / none |

Zero hits = ignore. Hits = scope the edit, file by file.

## 5. Recap — stop here

```
## Recap — <pkg> <current> → <target>
- Target: <version> (<n> major(s) up). Health: <maintained / deprecated / …>
- Runtime: Node/peers <OK / problem>; modules <CJS OK / ESM-only blocker>
- Breaking changes: YES / NO
  | Breaking change | Usage in repo | Impact |
  | … | grep → N hits | refactor / none |
- Recommendation: <simple bump | refactor (scope) | too big → quick path + ticket>
- Health note: <deprecated / modern alternative, or "none">

Nothing changed yet — which path?
```

Headless or subagent: return this recap and stop.

## 6. Act on the approved path

- **Small impact** → refactor first, then bump the range, then install. Never bump before the
  refactor compiles.
- **Range**: follow the repo's convention (existing `package.json` style, `CLAUDE.md`). Without
  one, `^<target>` — the caret allows later minors and patches, and the floor states the version
  actually validated (a security bump must not declare a range that admits the vulnerable one).
- **Impact too large** → no silent big refactor. Offer a **quick path** now (stay on the current
  major, partial upgrade, shim) and a **refactor checklist** ready for a ticket: every file and
  symbol, the new API, the order of operations.
- Afterwards, look for `resolutions` entries the bump made obsolete (the tree now resolves
  safely without them) and propose removing them — confirm the tree stays safe first.

## 7. Verify

The repo's typecheck, lint and tests (commands in its `CLAUDE.md` / `package.json`), or hand off
explicitly if the convention is that the human runs them.

## Red flags — STOP

- Editing code or `package.json` before the recap is approved, or at all in headless / subagent.
- A large refactor without offering the quick path + ticket.
- Judging a breaking change from the release notes without the PR diff or migration guide.
- Skipping `engines` or the ESM-only check.
- Chaining several majors in one go.

## Real-world note

firebase-admin 13 → 14: the release notes said "remove legacy namespace support". PR #3164 showed
`admin.firestore()` / `admin.auth()` / `admin.initializeApp` were deleted for modular imports — a
refactor across 3 files — and `npm view` exposed `engines: node>=22`, absent from the notes.
