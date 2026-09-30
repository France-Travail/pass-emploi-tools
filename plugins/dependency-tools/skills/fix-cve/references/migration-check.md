# Migration check — is this a pin, or a decision?

Loaded from `SKILL.md` step 3 when **no lever clears** an advisory, or when the only resolution
would force a consumer outside its own range's major. Read-only from start to finish.

"No bump fixes it" is not a licence to pin. Run the four checks below. **Any hit → out of plan**:
name it, hand the decision to the user, never write the pin yourself.

## (a) Query the registry under the advisory's name, not the wrapper's

The audit names the vulnerable package; the repo may declare a *wrapper* around it (declares
`react-router-dom`, the advisory hits `react-router`).

```bash
curl -s -H 'Accept: application/vnd.npm.install-v1+json' https://registry.npmjs.org/<advisory-pkg> \
  | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>console.log('latest:',JSON.parse(s)['dist-tags'].latest))"
```

Always accumulate stdin and parse on `'end'` (the first chunk alone is not valid JSON), and keep
the `Accept` header: it returns the abbreviated document instead of megabytes.

## (b) Stalled, or absorbed / end of life?

```bash
curl -s -H 'Accept: application/vnd.npm.install-v1+json' https://registry.npmjs.org/<wrapper> \
  | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{const j=JSON.parse(s);console.log('latest:',j['dist-tags'].latest);console.log('majors:',[...new Set(Object.keys(j.versions).map(v=>v.split('.')[0]))].sort((a,b)=>a-b).join(','))})"
```

Verified example: `react-router-dom` stops at major 7 while `react-router` is at 8.x — no major 8
exists under the wrapper's name, the fix is unreachable by any bump the repo can make. Wrapper's
highest major below the fix's major **and** the fix shipped under the other name → the family
**merged**. Write "absorbed into `<pkg>` at v<N>", never "no newer release" (that wording invites
a pin). A wrapper whose code is a few-hundred-byte re-export file confirms it is a shim.

## (c) Who blocks the migration, and what does upstream say?

```bash
grep -rn "<wrapper>" node_modules/<blocking-pkg>/src node_modules/<blocking-pkg>/dist 2>/dev/null | head
curl -s "https://api.github.com/search/issues?q=repo:<org>/<repo>+<wrapper>+in:title" \
  | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>(JSON.parse(s).items||[]).slice(0,5).forEach(i=>console.log(i.state,'|',i.pull_request?'PR ':'issue',i.number,'|',i.title)))"
```

A third party hard-coding `import … from '<wrapper>'` blocks the migration: swapping the declared
dependency would fail at runtime. Report the blocker by name and the upstream state (open issue,
pending PR, maintainer objection). Verified example: `elastic/apm-agent-rum-js` issue 1656 and
PR 1655 both open, the PR held back because dropping router < 7 is breaking. That turns "accept
the risk" into "accept until `<repo>#<PR>` ships".

GitHub HTML pages (advisories, alerts) need authentication even on public repos; the JSON API
above does not.

## (d) Is the advisory reachable in this application?

```bash
curl -s https://api.github.com/advisories/<GHSA-id> \
  | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{const j=JSON.parse(s);console.log(j.severity,'|',j.summary,'\n---\n',(j.description||'').slice(0,1200))})"
grep -rn "<pkg>" --include='*.ts' --include='*.tsx' --include='*.js' src 2>/dev/null | head
```

Look for a scope condition in the advisory ("only with the unstable RSC APIs", "only when parsing
untrusted input", "browser only"). For a transitive, read how the consumer actually calls it
(`node_modules/<consumer>/…`). **No reachable call + a condition the repo does not meet = not
exploitable here** — say so explicitly: it can turn a "high" into a documented acceptance instead
of a forced major.

## Hand-off template

```
<pkg> (<GHSA>, <severity>) — your decision
- Why no lever: <family merged into <pkg> at v<N> | consumers want ^8 / ^9, fix in 11.x | no patch>
- Blocked by: <blocking-pkg> (<file>), upstream <org>/<repo>#<n> <state since date>
- Exploitability here: <advisory condition> + <how the repo / consumer uses it> → <assessment>
- Options: (1) accept, documented, revisit when <event>
           (2) forced pin ">=<fixed>" across a major — untested combination, full checks required
           (3) drop / replace <blocking-pkg> — costs <what>
```

In headless mode this becomes an `outOfPlan` entry of the JSON report, with the same fields.
