---
name: fix-cve
description: Use when fixing dependency vulnerabilities in a Yarn Berry repo - one advisory or every CVE in the repo, interactively or headless (scheduled job, CI). Takes CVE/GHSA ids or package names, or nothing for a full sweep. Triggers - "fix les CVE", "corrige toutes les CVE du repo", "corriger la CVE de <dep>", "fix vulnerability", "GHSA-", "CVE-", "faille de sécu".
argument-hint: "[CVE|GHSA|package ...] [--headless] [--max-risk low|medium|high] [--dev] [--min-age <days>] [--report <path>]"
---

# Fix CVE

Fix dependency vulnerabilities with the **smallest change that removes them**, proven before it
is proposed. One process for one CVE or fifty: **scan → plan → one gate → apply → verify →
report**. The only thing that changes between modes is who answers the gate.

The mechanical part (audit, dependency chains, consumers' ranges, trial fixes) is done by a
script that never touches the working tree. Your job is the judgment: choosing the lever,
investigating majors and migrations, and reporting honestly.

## Arguments and modes

| Argument | Effect |
|---|---|
| ids / package names | restrict to those advisories (`--only`); never widen on your own |
| `--headless` | no human in the loop (see table below) |
| `--max-risk low\|medium\|high` | headless only: highest risk applied without a human. Default `low` |
| `--dev` | include dev dependencies. Default: **production only** |
| `--min-age <days>` | minimum age of a newly resolved version for auto-merge. Default `3` |
| `--report <path>` | headless only: where to write the JSON report. Default `fix-cve-report.json` |

| | Conversational (default) | Headless (`--headless`) |
|---|---|---|
| Gate | the plan, **once** — accepts a partial answer | none: groups with risk ≤ `--max-risk` are applied, the rest is reported |
| Questions | only at the gate | **never** (no `AskUserQuestion`, no waiting) |
| Checks | per the repo's `CLAUDE.md` (hand off if the human runs them) | run the repo's documented typecheck / lint / tests |
| Output | plan, then final report, in the user's language | final report + JSON report (`--report`) |
| Push / PR | only if asked | never — the calling workflow owns push, PR and merge |

## Step 1 — preconditions

```bash
git status --porcelain   # must be empty: every group must be revertable, and only the fix committed
```
Dirty → stop and say so (headless: write a report with `"status": "dirty-tree"` and exit).
On `develop`/`master`/`main`, create a branch before the first commit (`fix/cve-<YYYY-MM-DD>`).

No `node_modules` (fresh checkout, CI, new `git worktree`) → `yarn install` first: git hooks
such as husky + lint-staged need it, and the first commit fails without it.

The repo must be **Yarn Berry** (`yarn.lock` + `.yarnrc.yml`). Otherwise the script exits with
code 3: apply the doctrine below by hand with the package manager's equivalents (`overrides`,
`pnpm.overrides`), or stop in headless.

## Step 2 — scan

```bash
node ${CLAUDE_SKILL_DIR}/scripts/scan.mjs [--dev] [--only <ids,pkgs>] --json /tmp/fix-cve-scan.json
```

~2 min on `pass-emploi-api`. It audits the **lockfile**, groups advisories per package and runs
trial fixes in a throw-away `git worktree` (lockfile only, no install). The markdown summary is
enough to plan; the JSON holds every fact. Per vulnerable package you get:

- installed versions, **safe floor** (highest bound across all its advisories), max severity;
- direct or transitive, the **declared** parents reaching the vulnerable copies (kind, installed,
  latest), each consumer's own range, the `resolutions` entries touching it;
- probe results — `cleared` / `partial` / `no-effect` / `install failed`, the versions resolved
  after, their age, advisories cleared elsewhere (`+N other`) or **introduced** (`⚠`):

| Probe | What it tries | Runs when |
|---|---|---|
| `pin-removal` | delete the package's `resolutions` entries | an entry exists |
| `pin-raise` | set those entries to the safe floor | removal does not clear |
| `refresh` | `yarn up -R <pkg>`: re-resolve within the consumers' existing ranges | not a direct-only case |
| `bump` | declared dependency → latest of its major, then latest | one declared dependency owns the group |

It also lists dev-only advisories (out of scope unless `--dev`), deprecations (declared vs
transitive), the Yarn version and its age gate. **Never re-derive by hand what the scan
reports**; read `references/yarn-berry.md` only when you must investigate beyond it.

**Deprecation notices are not vulnerabilities**: never count them, never let them delay the
work — but always report them (step 4), declared ones with their documented replacement
(e.g. `lodash.isequal` → `node:util.isDeepStrictEqual`).

## Step 3 — choose one lever per group

A group is what one change fixes: a package, or the declared parent that owns several. Take the
**first lever in this order whose probe `cleared`** without introducing an advisory:

| # | Lever | Risk | Why this rank |
|---|---|---|---|
| 1 | remove an obsolete `resolutions` entry | low | deletes a pin; the tree already outgrew it |
| 2 | `refresh` (lockfile only) | low | every consumer already accepts the fixed version, nothing to declare |
| 3 | bump a declared dependency, same major | low | clean fix, no breaking change by semver |
| 4 | bump a declared dependency, **major** | high | still a real fix — propose it, never discard it as "too heavy" |
| 5 | raise an existing entry / add `"<pkg>": ">=<floor>"` | medium | masks the tree; only when no bump fixes it |

Rules that are easy to get wrong:

- **Only dependencies declared in `package.json` are bump candidates.** An intermediate
  transitive (`google-gax` under `firebase-admin`) is a link in the chain, not a lever.
- **A parent bump does not move a transitive whose descriptor is unchanged** (verified:
  `@nestjs/platform-express` 11.2.1 → 12.1.2 leaves `multer` where it is). Trust the probe,
  not the changelog.
- **A major bump beats a resolution.** When lever 4 clears, it is the proposal; lever 5 is
  mentioned only if the user declines the major.
- **Resolutions are always `">=<floor>"`**, never `^` nor exact — `^` caps the major and
  re-creates the CVE when the fix ships in the next one. Anchor the floor on the major that
  actually installs (an entry collapses every copy to one version).
- **An entry that forces a consumer outside its own range's major is not lever 5** (e.g.
  `uuid` wanted as `^8` / `^9`, fixed in `11.1.1`): it is an untested combination → out of plan
  with the migration check below.
- **An `⚠ introduces` probe is disqualified**, even if it clears its own advisory.

### Majors and migrations — the only work that needs investigation

- **Major bump (lever 4)** → invoke the `upgrade-dependency` skill for the declared dependency
  (read-only, returns breaking changes and files to touch).
- **No lever clears, or lever 5 would cross a consumer's major** → run the migration check,
  `references/migration-check.md`: renamed / merged / EOL family, third party blocking the
  migration, upstream issue/PR state, exploitability in this repo. Any hit is **out of plan**,
  named, never turned into a pin.

With several such items, dispatch **one read-only subagent per item, in parallel** (Agent tool,
same model as the session: this is judgment work, do not downgrade it). State in the prompt:
*no file edit, no install, no commit — return the recap*. Low-risk groups need no subagent.

### Out of plan — named, never executed

- migration check hit (see above) → the user's decision, with the options from the reference;
- no fixed version anywhere → options: mitigate, replace, accept documented;
- **age gate**: Yarn ≥ 4.10 refuses versions younger than `npmMinimalAgeGate` (default 1 day
  since Yarn 4.15). A CVE fix is fresh by nature. Conversational → offer to preapprove the
  exact version (`npmPreapprovedPackages: ["<pkg>@<version>"]` in `.yarnrc.yml`), never add it
  silently. Headless → never bypass: report "blocked by the age gate until `<date>`";
- dev-only advisories when the scope is prod → one line each, the user can pull them in.

## Step 4 — the plan (the only gate)

Sort groups by risk, lowest first, and present — in the user's language:

```
## Plan — <N> advisories (<crit>/<high>/<mod>/<low>) on <P> packages, <scope> scope, <G> groups

| # | Lever | Advisories cleared | Max sev | Impact | Risk |
|---|-------|--------------------|---------|--------|------|
| 1 | remove resolution "brace-expansion" | 3 | high | 5.0.9 → 5.0.12, probed | low |
| 2 | refresh undici (via bull, already latest) | 11 | high | 8.10.0 → 8.11.2, lockfile only | low |
| 3 | bump <dep> 11.2.1 → 12.1.2 (MAJOR) | 1 | moderate | <breaking changes, files to touch> | high |

Out of plan — your decision:
- uuid (GHSA-…, moderate): bull wants ^8, gaxios ^9, fixed in 11.1.1 → a pin forces them across
  2 majors. Exploitable here: <assessment>. Options: accept documented / forced pin / <…>

Not security — deprecations: [declared] lodash.isequal → node:util.isDeepStrictEqual · [transitive] glob, inflight
Dev-only (out of scope): fast-uri (high ×6), …

Nothing has changed yet. Apply 1-3, one commit per theme (each major alone)? Drop any group in your answer.
```

- A partial answer ("yes but not 3") is a complete answer. **Never ask a second question.**
- The deprecation and dev-only lines are always present, even as "none": proof you looked.
- Headless: no gate; groups above `--max-risk` are reported as `skipped-risk`.

## Step 5 — apply, group by group, commit by theme

Groups are applied one at a time, but committed **by theme** — one commit per lever of the
step 3 table (obsolete pins, lockfile refresh, same-major bumps, resolutions), except **each
major bump, which gets its own commit** since it is the one likely to be reverted. Few coherent
commits keep the review readable; the index keeps each group revertable meanwhile.

For each approved group, lowest risk first:

1. Change **one** thing: delete / edit the `resolutions` entry, bump the range in
   `package.json` (keep the repo's prefix; every `package.json` in a monorepo), or
   `yarn up -R <pkg> --mode=update-lockfile` for a refresh.
2. `yarn install --mode=update-lockfile` (lockfile only, seconds).
3. Check the advisories are gone:
   `node ${CLAUDE_SKILL_DIR}/scripts/scan.mjs --no-probe --only <group's GHSAs>` → `0 advisories`.
4. `git status`: only `package.json` / `yarn.lock` (plus the code a major announced). Anything
   else → investigate.
5. Accepted → `git add -A`: the group joins its theme in the index.
6. Last group of its theme → commit the theme, naming every package and GHSA it clears:
   `fix(deps): retire les resolutions obsolètes brace-expansion et qs (GHSA-…, GHSA-…)`.

A group that fails (advisory still there, install error, unexpected diff) → `git checkout -- .`
brings the tree back to the index, i.e. the groups already accepted; record the reason, next
group. **Never swap in another lever**: the user approved *that* change, not "whatever works".

Then **one** real `yarn install` and the checks (see modes). Checks fail → revert the major
commits first (`git revert --no-edit <sha>`), re-check, and report which change broke what. A
major whose plan announced code changes is approved work: do the refactor.

## Step 6 — final report

```bash
node ${CLAUDE_SKILL_DIR}/scripts/scan.mjs --no-probe [--dev]   # same scope as the fixes
```

Never claim "fixed" without this re-audit. Report, in the user's language:

```
## Done — <k>/<N> advisories cleared (<n> left)

| # | Change | Advisories | Status |
|---|--------|------------|--------|
| 1 | remove resolution "brace-expansion" | 3 | applied, <sha> |
| 3 | bump <dep> (MAJOR) | 1 | reverted — typecheck broke on <file> |

Left: <pkg> <GHSA> — <reason (out of plan, no patch, age gate until <date>)>
Checks: <commands and result, or "handed off per repo convention">
```

Headless — also write `--report` (the calling workflow reads it to open and merge the PR):

```json
{
  "status": "fixed | partial | nothing-to-do | dirty-tree | failed",
  "scope": "prod",
  "before": { "advisories": 20, "bySeverity": { "high": 5, "moderate": 12, "low": 3 } },
  "after": { "advisories": 1, "bySeverity": { "moderate": 1 } },
  "groups": [
    { "lever": "refresh undici", "advisories": ["GHSA-…"], "risk": "low",
      "status": "applied | reverted | skipped-risk | failed", "commit": "<sha>",
      "newVersions": { "undici": { "version": "8.11.2", "ageDays": 6 } }, "reason": null }
  ],
  "outOfPlan": [{ "package": "uuid", "advisories": ["GHSA-…"], "reason": "…", "options": ["…"] }],
  "deprecations": { "declared": ["lodash.isequal"], "transitive": ["glob"] },
  "checks": { "commands": ["yarn tsc --noEmit", "yarn lint", "yarn test:local:unit"], "passed": true },
  "autoMergeEligible": true,
  "autoMergeBlockers": []
}
```

`autoMergeEligible` is `true` only if at least one group is applied, **every applied group is
low risk**, the checks passed, no advisory was introduced, and every new version is at least
`--min-age` days old. Otherwise `false`, with each reason in `autoMergeBlockers`.

## Red flags — STOP

- Editing anything before the gate (conversational) — the scan's worktree is the only place
  where trial fixes happen.
- A second question after the plan was answered, or a question at all in headless.
- Auditing dev dependencies unasked, or widening a request scoped to one id / package.
- Proposing a resolution when a probe shows a bump or a refresh clears it.
- Turning a migration-check hit (merged family, blocked upstream, cross-major pin) into a pin.
- Bypassing the age gate in headless, or preapproving a version without the user's go.
- A subagent writing files, installing or committing — they would corrupt each other's readings.
- Rescuing a failed group with a different lever.
- Mixing themes in one commit, a major sharing its commit, or one commit per group; a push / PR
  nobody asked for.
- Claiming success without the final re-audit, or counting deprecations as CVEs.
