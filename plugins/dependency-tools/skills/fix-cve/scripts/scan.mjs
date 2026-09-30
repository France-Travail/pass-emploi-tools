#!/usr/bin/env node
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const USAGE = `Usage: node scan.mjs [--dev] [--only <id|pkg>[,...]] [--no-probe] [--json <path>]

Collects the facts fix-cve needs (Yarn Berry only), without touching the working tree:
  - real advisories (deprecations split out), aggregated per package
  - direct/transitive, top-level declared parents, consumers' original ranges
  - existing resolutions entries
  - probes run in a throw-away git worktree (lockfile only, no install):
      pin-removal  remove the package's resolutions entries
      pin-raise    raise them to the safe floor (only if the removal does not clear)
      refresh      yarn up -R <pkg>
      bump         bump the group's declared dependency (same-major latest, then latest)

  --dev        audit dev dependencies too (default: production only)
  --only       restrict to GHSA ids, CVE ids or package names
  --no-probe   facts only, skip the probes
  --json       where to write the JSON result (default: $TMPDIR/fix-cve-scan.json)`

const SEVERITY_ORDER = ['info', 'low', 'moderate', 'high', 'critical']
const YARN_ENV = {
  ...process.env,
  FORCE_COLOR: '0',
  YARN_ENABLE_COLORS: '0',
  YARN_ENABLE_PROGRESS_BARS: '0',
  YARN_ENABLE_TELEMETRY: '0'
}

function parseArgs(argv) {
  const opts = { scope: 'prod', only: [], probe: true, json: join(tmpdir(), 'fix-cve-scan.json') }
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    if (arg === '--dev') opts.scope = 'all'
    else if (arg === '--only') opts.only.push(...(argv[++i] ?? '').split(',').filter(Boolean))
    else if (arg === '--no-probe') opts.probe = false
    else if (arg === '--json') opts.json = argv[++i]
    else if (arg === '-h' || arg === '--help') {
      console.log(USAGE)
      process.exit(0)
    } else {
      console.error(`Unknown argument: ${arg}\n\n${USAGE}`)
      process.exit(2)
    }
  }
  return opts
}

function run(cmd, args, cwd) {
  const res = spawnSync(cmd, args, { cwd, encoding: 'utf8', env: YARN_ENV, maxBuffer: 512 * 1024 * 1024 })
  return { code: res.status, out: res.stdout ?? '', err: res.stderr ?? '' }
}

function tail(text, lines = 8) {
  return text.trim().split('\n').slice(-lines).join('\n')
}

function log(message) {
  process.stderr.write(`[scan] ${message}\n`)
}

function versionParts(version) {
  return version.split(/[.+-]/).slice(0, 3).map(n => Number.parseInt(n, 10) || 0)
}

function compareVersions(a, b) {
  const pa = versionParts(a)
  const pb = versionParts(b)
  for (let i = 0; i < 3; i++) if (pa[i] !== pb[i]) return pa[i] - pb[i]
  return 0
}

function major(version) {
  return versionParts(version)[0]
}

function isStable(version) {
  return !version.includes('-')
}

function satisfiesComparators(version, rangePart) {
  return rangePart
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .every(comparator => {
      const [, op = '=', target] = comparator.match(/^(<=|>=|<|>|=)?v?(.+)$/)
      const cmp = compareVersions(version, target)
      return { '<': cmp < 0, '<=': cmp <= 0, '>': cmp > 0, '>=': cmp >= 0, '=': cmp === 0 }[op]
    })
}

function upperBound(rangePart) {
  const match = rangePart.match(/<(=?)\s*v?(\d+\.\d+\.\d+\S*)/)
  if (match) return { version: match[2], inclusive: match[1] === '=' }
  const exact = rangePart.trim().match(/^=?v?(\d+\.\d+\.\d+\S*)$/)
  return exact ? { version: exact[1], inclusive: true } : null
}

function safeFloor(advisories, installedVersions) {
  let floor = null
  for (const advisory of advisories) {
    for (const part of advisory.vulnerable.split('||')) {
      if (!installedVersions.some(v => satisfiesComparators(v, part))) continue
      const bound = upperBound(part)
      if (!bound) continue
      const cmp = floor ? compareVersions(bound.version, floor.version) : 1
      if (cmp > 0 || (cmp === 0 && bound.inclusive)) floor = bound
    }
  }
  if (!floor) return null
  return floor.inclusive ? `>${floor.version}` : `>=${floor.version}`
}

function maxSeverity(severities) {
  return severities.reduce((a, b) => (SEVERITY_ORDER.indexOf(b) > SEVERITY_ORDER.indexOf(a) ? b : a), 'info')
}

function audit(cwd, scope) {
  const environment = scope === 'prod' ? 'production' : 'all'
  const res = run('yarn', ['npm', 'audit', '--recursive', '--environment', environment, '--json'], cwd)
  const rows = []
  for (const line of res.out.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed.startsWith('{')) continue
    try {
      rows.push(JSON.parse(trimmed))
    } catch {
      continue
    }
  }
  if (!rows.length && res.code !== 0) throw new Error(`yarn npm audit failed:\n${tail(res.err || res.out, 20)}`)

  const advisories = []
  const deprecations = []
  for (const { value, children: c } of rows) {
    if (!c.URL || String(c.ID).includes('(deprecation)')) {
      deprecations.push({ name: value, issue: c.Issue, installed: c['Tree Versions'], dependents: c.Dependents })
    } else {
      advisories.push({
        package: value,
        ghsa: c.URL.split('/').pop(),
        url: c.URL,
        title: c.Issue,
        severity: c.Severity,
        vulnerable: c['Vulnerable Versions'],
        installed: c['Tree Versions'],
        dependents: c.Dependents
      })
    }
  }
  return { advisories, deprecations }
}

function parseLockfile(text) {
  const entries = []
  let current = null
  let section = null
  for (const line of text.split('\n')) {
    if (!line.trim() || line.startsWith('#')) continue
    if (!line.startsWith(' ')) {
      const keys = line.replace(/:$/, '').replace(/^"|"$/g, '').split(', ')
      current = { keys, dependencies: {} }
      entries.push(current)
      section = null
      continue
    }
    const match = line.match(/^( +)("?[^":]+"?):\s*(.*)$/)
    if (!match || !current) continue
    const [, indent, rawKey, rawValue] = match
    const key = rawKey.replace(/^"|"$/g, '')
    const value = rawValue.replace(/^"|"$/g, '')
    if (indent.length === 2) {
      section = value === '' ? key : null
      if (value !== '') current[key] = value
    } else if (indent.length === 4 && section === 'dependencies') {
      current.dependencies[key] = value
    }
  }
  return entries
}

function locatorName(locator) {
  return locator.slice(0, locator.indexOf('@', 1))
}

function normalizeLocator(locator) {
  const name = locatorName(locator)
  let reference = locator.slice(name.length + 1)
  const hash = reference.indexOf('#')
  if (reference.startsWith('virtual:') && hash >= 0) reference = reference.slice(hash + 1)
  return `${name}@${reference}`
}

function locatorVersion(locator) {
  const normalized = normalizeLocator(locator)
  const reference = normalized.slice(locatorName(normalized).length + 1)
  return reference.startsWith('npm:') ? reference.slice(4) : reference
}

function lockedVersions(cwd, pkg) {
  const lock = parseLockfile(readFileSync(join(cwd, 'yarn.lock'), 'utf8'))
  return lock
    .filter(entry => entry.resolution && locatorName(entry.resolution) === pkg)
    .map(entry => entry.version)
    .sort(compareVersions)
}

function dependencyGraph(cwd, pkg) {
  const res = run('yarn', ['why', pkg, '-R', '--json'], cwd)
  const graph = new Map()
  const roots = new Set()
  // `yarn why -R` prints each subtree only once and leaves later occurrences empty,
  // so reachability must be computed on the union of every occurrence.
  const walk = (children, parent) => {
    for (const [key, node] of Object.entries(children ?? {})) {
      const locator = normalizeLocator(node.value?.locator ?? key)
      if (!graph.has(locator)) graph.set(locator, new Set())
      if (parent) graph.get(parent).add(locator)
      else roots.add(locator)
      walk(node.children, locator)
    }
  }
  for (const line of res.out.split('\n')) {
    if (line.trim().startsWith('{')) walk(JSON.parse(line).children, null)
  }
  return { graph, roots: [...roots] }
}

function reaches(graph, from, targets, seen = new Set()) {
  if (targets.has(from)) return true
  if (seen.has(from)) return false
  seen.add(from)
  return [...(graph.get(from) ?? [])].some(child => reaches(graph, child, targets, seen))
}

const registryCache = new Map()

async function registryDoc(name, { full = false } = {}) {
  const cacheKey = `${name}${full ? '#full' : ''}`
  if (registryCache.has(cacheKey)) return registryCache.get(cacheKey)
  const headers = full ? {} : { Accept: 'application/vnd.npm.install-v1+json' }
  const res = await fetch(`https://registry.npmjs.org/${name.replace('/', '%2F')}`, { headers })
  const doc = res.ok ? await res.json() : null
  registryCache.set(cacheKey, doc)
  return doc
}

async function releaseInfo(name, installed) {
  const doc = await registryDoc(name)
  if (!doc) return { latest: null, latestSameMajor: null }
  const stable = Object.keys(doc.versions ?? {}).filter(isStable)
  const sameMajor = stable.filter(v => major(v) === major(installed)).sort(compareVersions)
  return { latest: doc['dist-tags']?.latest ?? null, latestSameMajor: sameMajor.at(-1) ?? null }
}

async function ageInDays(name, version) {
  const doc = await registryDoc(name, { full: true })
  const published = doc?.time?.[version]
  return published ? Math.floor((Date.now() - Date.parse(published)) / 86_400_000) : null
}

function yarnInfo(repo, pkgJson) {
  const version = (pkgJson.packageManager ?? '').match(/^yarn@(\d+\.\d+\.\d+)/)?.[1] ?? null
  const yarnrcPath = join(repo, '.yarnrc.yml')
  const yarnrc = existsSync(yarnrcPath) ? readFileSync(yarnrcPath, 'utf8') : ''
  const configured = yarnrc.match(/^npmMinimalAgeGate:\s*["']?([^"'\s#]+)/m)?.[1] ?? null
  let ageGate = configured
  if (!ageGate && version && compareVersions(version, '4.15.0') >= 0) ageGate = '1d (Yarn default)'
  if (!ageGate && version && compareVersions(version, '4.10.0') < 0) ageGate = `unsupported (Yarn ${version} < 4.10.0)`
  return { version, ageGate }
}

async function resolveCveIds(ids) {
  const ghsas = new Set()
  for (const cve of ids) {
    const res = await fetch(`https://api.github.com/advisories?cve_id=${encodeURIComponent(cve)}`, {
      headers: { Accept: 'application/vnd.github+json' }
    })
    if (!res.ok) {
      log(`could not resolve ${cve} (GitHub API ${res.status}) — pass the GHSA id or the package name instead`)
      continue
    }
    for (const advisory of await res.json()) ghsas.add(advisory.ghsa_id)
  }
  return ghsas
}

function bumpRange(currentRange, target) {
  const prefix = currentRange.match(/^[\^~]/)?.[0] ?? ''
  return `${prefix}${target}`
}

function editPackageJson(dir, edit) {
  const path = join(dir, 'package.json')
  const content = readFileSync(path, 'utf8')
  const indent = content.match(/^\{\n(\s+)/)?.[1] ?? '  '
  const json = JSON.parse(content)
  edit(json)
  writeFileSync(path, `${JSON.stringify(json, null, indent)}\n`)
}

async function withWorktree(repo, fn) {
  const dir = join(mkdtempSync(join(tmpdir(), 'fix-cve-probe-')), 'tree')
  const add = run('git', ['worktree', 'add', '--detach', '-q', dir, 'HEAD'], repo)
  if (add.code !== 0) throw new Error(`git worktree add failed:\n${tail(add.err)}`)
  const cleanup = () => {
    run('git', ['worktree', 'remove', '--force', dir], repo)
    rmSync(join(dir, '..'), { recursive: true, force: true })
  }
  process.once('SIGINT', () => {
    cleanup()
    process.exit(130)
  })
  try {
    return await fn(dir)
  } finally {
    cleanup()
  }
}

function makeProber(dir, scope, packageNames) {
  const cache = new Map()
  return (key, action) => {
    if (cache.has(key)) return cache.get(key)
    log(`probe ${key}`)
    run('git', ['checkout', '-q', '--', '.'], dir)
    const res = action(dir)
    let outcome
    if (res.code !== 0) {
      outcome = { ok: false, detail: tail(res.out + res.err) }
    } else {
      const after = audit(dir, scope)
      outcome = {
        ok: true,
        ghsas: new Set(after.advisories.map(a => a.ghsa)),
        advisories: after.advisories,
        diffstat: run('git', ['diff', '--shortstat'], dir).out.trim(),
        resolvedAfter: Object.fromEntries(packageNames.map(name => [name, lockedVersions(dir, name)]))
      }
    }
    run('git', ['checkout', '-q', '--', '.'], dir)
    cache.set(key, outcome)
    return outcome
  }
}

function evaluate(outcome, pkg, baseline) {
  if (!outcome.ok) return { status: 'install-failed', detail: outcome.detail }
  const own = pkg.advisories.map(a => a.ghsa)
  const remaining = own.filter(id => outcome.ghsas.has(id))
  const alsoClears = [...baseline.byGhsa.keys()].filter(id => !own.includes(id) && !outcome.ghsas.has(id))
  const introduced = outcome.advisories.filter(a => !baseline.byGhsa.has(a.ghsa)).map(a => `${a.package} ${a.ghsa}`)
  const status = remaining.length === 0 ? 'cleared' : remaining.length < own.length ? 'partial' : 'no-effect'
  return { status, remaining, alsoClears, introduced, diffstat: outcome.diffstat, resolvedAfter: outcome.resolvedAfter?.[pkg.name] }
}

async function main() {
  const opts = parseArgs(process.argv.slice(2))
  const repo = process.cwd()
  if (!existsSync(join(repo, 'yarn.lock')) || !existsSync(join(repo, '.yarnrc.yml'))) {
    console.error('fix-cve scan supports Yarn Berry repos only (yarn.lock + .yarnrc.yml). Apply the doctrine manually.')
    process.exit(3)
  }
  const pkgJson = JSON.parse(readFileSync(join(repo, 'package.json'), 'utf8'))
  const prodDeps = pkgJson.dependencies ?? {}
  const devDeps = pkgJson.devDependencies ?? {}
  const resolutions = pkgJson.resolutions ?? {}
  const git = {
    branch: run('git', ['branch', '--show-current'], repo).out.trim(),
    head: run('git', ['rev-parse', '--short', 'HEAD'], repo).out.trim(),
    dirty: run('git', ['status', '--porcelain'], repo).out.trim() !== ''
  }

  log(`audit (${opts.scope})`)
  const base = audit(repo, opts.scope)
  let advisories = base.advisories

  if (opts.only.length) {
    const cveGhsas = await resolveCveIds(opts.only.filter(id => /^CVE-/i.test(id)))
    const wanted = new Set(opts.only.map(id => (/^GHSA-/i.test(id) ? id.toLowerCase() : id)))
    advisories = advisories.filter(
      a => wanted.has(a.ghsa.toLowerCase()) || wanted.has(a.package) || cveGhsas.has(a.ghsa)
    )
  }

  const baseline = { byGhsa: new Map(base.advisories.map(a => [a.ghsa, a])) }
  const lock = parseLockfile(readFileSync(join(repo, 'yarn.lock'), 'utf8'))
  const lockByResolution = new Map(lock.filter(e => e.resolution).map(e => [normalizeLocator(e.resolution), e]))

  const byPackage = new Map()
  for (const advisory of advisories) {
    if (!byPackage.has(advisory.package)) byPackage.set(advisory.package, [])
    byPackage.get(advisory.package).push(advisory)
  }

  const packages = []
  for (const [name, pkgAdvisories] of byPackage) {
    log(`facts ${name}`)
    const installed = [...new Set(pkgAdvisories.flatMap(a => a.installed))].sort(compareVersions)
    const dependents = [...new Set(pkgAdvisories.flatMap(a => a.dependents ?? []))]
    const consumers = dependents.map(locator => ({
      locator: normalizeLocator(locator),
      range: lockByResolution.get(normalizeLocator(locator))?.dependencies?.[name] ?? null
    }))
    const matchingResolutions = Object.entries(resolutions)
      .filter(([key]) => key === name || key.endsWith(`/${name}`) || key.startsWith(`${name}@`))
      .map(([key, value]) => ({ key, value }))

    const { graph, roots } = dependencyGraph(repo, name)
    const vulnerableLocators = new Set([...graph.keys()].filter(l => locatorName(l) === name && installed.includes(locatorVersion(l))))
    const directRoot = roots.find(root => vulnerableLocators.has(root))
    const direct = directRoot ? (name in prodDeps ? 'prod' : 'dev') : null
    const directInstalled = directRoot ? locatorVersion(directRoot) : null
    const declaredParents = []
    for (const root of roots) {
      const parentName = locatorName(root)
      if (parentName === name || !reaches(graph, root, vulnerableLocators)) continue
      const kind = parentName in prodDeps ? 'prod' : parentName in devDeps ? 'dev' : 'other'
      const version = locatorVersion(root)
      declaredParents.push({
        name: parentName,
        kind,
        installed: version,
        range: prodDeps[parentName] ?? devDeps[parentName] ?? null,
        ...(await releaseInfo(parentName, version))
      })
    }

    const inScopeParents = declaredParents.filter(p => p.kind === 'prod' || opts.scope === 'all')
    let group
    if (direct && !inScopeParents.length) group = { key: name, via: 'direct' }
    else if (!direct && inScopeParents.length === 1) group = { key: inScopeParents[0].name, via: 'single-declared-parent' }
    else group = { key: name, via: inScopeParents.length ? 'several-declared-parents' : 'no-declared-parent' }

    packages.push({
      name,
      severity: maxSeverity(pkgAdvisories.map(a => a.severity)),
      installed,
      floor: safeFloor(pkgAdvisories, installed),
      direct,
      directRelease: direct ? { installed: directInstalled, ...(await releaseInfo(name, directInstalled)) } : null,
      advisories: pkgAdvisories.map(({ ghsa, severity, title, vulnerable, url }) => ({ ghsa, severity, title, vulnerable, url })),
      consumers,
      resolutions: matchingResolutions,
      declaredParents,
      group,
      probes: {}
    })
  }

  if (opts.probe && packages.length) {
    if (git.dirty) log('working tree is dirty: probes run on HEAD, not on your uncommitted changes')
    await withWorktree(repo, async dir => {
      const probe = makeProber(dir, opts.scope, packages.map(p => p.name))

      for (const pkg of packages) {
        if (pkg.resolutions.length) {
          const keys = pkg.resolutions.map(r => r.key)
          const outcome = probe(`pin-removal:${pkg.name}`, d => {
            editPackageJson(d, json => keys.forEach(k => delete json.resolutions[k]))
            return run('yarn', ['install', '--mode=update-lockfile'], d)
          })
          pkg.probes.pinRemoval = { removed: keys, ...evaluate(outcome, pkg, baseline) }

          if (pkg.probes.pinRemoval.status !== 'cleared' && pkg.floor) {
            const raised = probe(`pin-raise:${pkg.name}`, d => {
              editPackageJson(d, json => keys.forEach(k => (json.resolutions[k] = pkg.floor)))
              return run('yarn', ['install', '--mode=update-lockfile'], d)
            })
            pkg.probes.pinRaise = { to: pkg.floor, keys, ...evaluate(raised, pkg, baseline) }
          }
        }

        if (pkg.group.via !== 'direct' && pkg.probes.pinRemoval?.status !== 'cleared') {
          const outcome = probe(`refresh:${pkg.name}`, d => run('yarn', ['up', '-R', pkg.name, '--mode=update-lockfile'], d))
          pkg.probes.refresh = evaluate(outcome, pkg, baseline)
        }

        const bumpable = pkg.group.via === 'direct'
          ? { name: pkg.name, range: prodDeps[pkg.name] ?? devDeps[pkg.name], ...pkg.directRelease }
          : pkg.group.via === 'single-declared-parent'
            ? pkg.declaredParents.find(p => p.name === pkg.group.key)
            : null
        if (bumpable?.range) {
          const targets = [...new Set([bumpable.latestSameMajor, bumpable.latest])].filter(
            t => t && compareVersions(t, bumpable.installed) > 0
          )
          pkg.probes.bumps = []
          for (const target of targets) {
            const range = bumpRange(bumpable.range, target)
            const outcome = probe(`bump:${bumpable.name}@${range}`, d => {
              editPackageJson(d, json => {
                const section = bumpable.name in (json.dependencies ?? {}) ? 'dependencies' : 'devDependencies'
                json[section][bumpable.name] = range
              })
              return run('yarn', ['install', '--mode=update-lockfile'], d)
            })
            pkg.probes.bumps.push({
              dependency: bumpable.name,
              from: bumpable.installed,
              to: target,
              major: major(target) !== major(bumpable.installed),
              ...evaluate(outcome, pkg, baseline)
            })
          }
        }

        for (const result of [pkg.probes.pinRemoval, pkg.probes.pinRaise, pkg.probes.refresh, ...(pkg.probes.bumps ?? [])]) {
          if (result?.status !== 'cleared' || !result.resolvedAfter) continue
          const fresh = result.resolvedAfter.filter(v => !pkg.installed.includes(v))
          result.freshVersionsAgeDays = Object.fromEntries(
            await Promise.all(fresh.map(async v => [v, await ageInDays(pkg.name, v)]))
          )
        }
      }
    })
  }

  let devOnly = []
  if (opts.scope === 'prod' && !opts.only.length) {
    log('audit (all) to list dev-only advisories')
    const all = audit(repo, 'all')
    const perPackage = new Map()
    for (const a of all.advisories.filter(a => !baseline.byGhsa.has(a.ghsa))) {
      perPackage.set(a.package, [...(perPackage.get(a.package) ?? []), a.severity])
    }
    devOnly = [...perPackage].map(([name, severities]) => ({ name, severity: maxSeverity(severities), count: severities.length }))
  }

  const result = {
    generatedAt: new Date().toISOString(),
    repo: { path: repo, ...git, yarn: yarnInfo(repo, pkgJson) },
    scope: opts.scope,
    only: opts.only,
    counts: {
      advisories: advisories.length,
      packages: packages.length,
      bySeverity: Object.fromEntries(SEVERITY_ORDER.map(s => [s, advisories.filter(a => a.severity === s).length]).filter(([, n]) => n))
    },
    packages: packages.sort((a, b) => SEVERITY_ORDER.indexOf(b.severity) - SEVERITY_ORDER.indexOf(a.severity)),
    devOnly,
    deprecations: base.deprecations.map(d => ({ ...d, declared: d.name in prodDeps || d.name in devDeps }))
  }
  writeFileSync(opts.json, `${JSON.stringify(result, null, 2)}\n`)
  printSummary(result, opts.json)
}

function describeProbe(result) {
  if (!result) return '—'
  if (result.status === 'install-failed') return 'install failed'
  const ages = result.freshVersionsAgeDays ?? {}
  const versions = (result.resolvedAfter ?? ['?']).map(v => (v in ages ? `${v}, ${ages[v] ?? '?'}d old` : v)).join('; ')
  const extra = [
    result.alsoClears?.length ? `+${result.alsoClears.length} other` : '',
    result.introduced?.length ? `⚠ introduces ${result.introduced.length}` : ''
  ].filter(Boolean).join(' ')
  return `${result.status} (${versions})${extra ? ` ${extra}` : ''}`
}

function printSummary(result, jsonPath) {
  const { repo, counts } = result
  console.log(`# fix-cve scan — ${repo.branch || 'detached'}@${repo.head}${repo.dirty ? ' (dirty)' : ''}, scope ${result.scope}`)
  console.log(`Yarn ${repo.yarn.version ?? '?'} — age gate: ${repo.yarn.ageGate ?? 'none'}`)
  console.log(`${counts.advisories} advisories on ${counts.packages} packages ${JSON.stringify(counts.bySeverity)}\n`)
  for (const p of result.packages) {
    const where = p.direct
      ? `direct (${p.direct})`
      : `via ${p.declaredParents.map(d => `${d.name}@${d.installed}${d.latest && d.latest !== d.installed ? `→${d.latest}` : ' (latest)'} [${d.kind}]`).join(', ') || '?'}`
    console.log(`## ${p.name} ${p.installed.join(',')} → ${p.floor ?? '?'} — ${p.severity}, ${p.advisories.length} advisories, group "${p.group.key}" (${p.group.via})`)
    console.log(`   ${where}`)
    if (p.consumers.length) console.log(`   consumers: ${p.consumers.map(c => `${c.locator} wants ${c.range ?? '?'}`).join('; ')}`)
    if (p.resolutions.length) console.log(`   resolutions: ${p.resolutions.map(r => `"${r.key}": "${r.value}"`).join(', ')}`)
    if (p.probes.pinRemoval) console.log(`   probe pin-removal: ${describeProbe(p.probes.pinRemoval)}`)
    if (p.probes.pinRaise) console.log(`   probe pin-raise ${p.probes.pinRaise.to}: ${describeProbe(p.probes.pinRaise)}`)
    if (p.probes.refresh) console.log(`   probe refresh:     ${describeProbe(p.probes.refresh)}`)
    for (const b of p.probes.bumps ?? []) {
      console.log(`   probe bump ${b.dependency} ${b.from}→${b.to}${b.major ? ' (MAJOR)' : ''}: ${describeProbe(b)}`)
    }
  }
  if (result.devOnly.length) {
    console.log(`\nDev-only (out of scope): ${result.devOnly.map(d => `${d.name} (${d.severity} ×${d.count})`).join(', ')}`)
  }
  const declared = result.deprecations.filter(d => d.declared)
  const transitive = result.deprecations.filter(d => !d.declared)
  console.log(`\nDeprecations — declared: ${declared.map(d => d.name).join(', ') || 'none'}; transitive: ${transitive.map(d => d.name).join(', ') || 'none'}`)
  console.log(`\nFull facts: ${jsonPath}`)
}

main().catch(error => {
  console.error(error.stack ?? String(error))
  process.exit(1)
})