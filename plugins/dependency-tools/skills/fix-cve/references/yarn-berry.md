# Yarn Berry — facts behind the scan

Read only when investigating beyond what `scripts/scan.mjs` reports. Verified on Yarn 4.9.

## Audit

- `yarn npm audit --recursive --environment production --json` reads the **lockfile**, not
  `node_modules`: no install needed to audit a change, `--mode=update-lockfile` is enough.
- Output is **NDJSON**, one `{"value": <pkg>, "children": {ID, Issue, URL, Severity,
  "Vulnerable Versions", "Tree Versions", Dependents}}` per line.
- Deprecations are mixed in: `ID` contains `(deprecation)`, no `URL`.
- No "fixed version" field: it is the upper bound of `Vulnerable Versions`. A package often has
  several advisories with different bounds — the floor is the highest one.
- `Dependents` is the **immediate** parent, not the declared one.

## Dependency chains

- `yarn why <pkg> -R --json` prints each subtree once and leaves its later occurrences empty:
  reachability must be computed on the union of every occurrence, not on one branch.
- The lockfile keeps each consumer's **original** range in its `dependencies`, even when a
  `resolutions` entry rewrites it — that is where "does every consumer already accept the fix?"
  is answered.

## Resolution behaviour

- Removing or loosening a `resolutions` entry re-resolves the package from the consumers' ranges
  on the next install: no `yarn up` needed (unlike npm / Yarn 1).
- An unchanged descriptor keeps its locked version: bumping a parent whose range for the child
  did not change does **not** move the child. `yarn up -R <pkg>` does.
- `yarn install --mode=update-lockfile` updates the lockfile only (about 2 s), no link step.
- A `resolutions` entry collapses every copy of the package to one version, across majors.

## Registry queries

- Never dump `yarn npm info <pkg> versions --json`, and beware `yarn npm info <pkg> dist-tags`:
  Yarn returns the full `versions` array with it. Query the registry with
  `Accept: application/vnd.npm.install-v1+json`, accumulate stdin, parse on `'end'`.
- Publication dates (`time`) are only in the full document, not the abbreviated one.

## Age gate

- `npmMinimalAgeGate` (e.g. `"3d"`) in `.yarnrc.yml` since **4.10.0**; default `1d` since
  **4.15.0**. `npmPreapprovedPackages` exempts descriptors / globs from it.
- Yarn 4.14.0 turned `enableScripts` off by default: upgrading Yarn to get the gate breaks
  dependencies that need a `postinstall` unless they are allowed explicitly.
- Dependabot's `cooldown` only applies to version updates, **not** to security updates.
