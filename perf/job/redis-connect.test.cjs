const { test } = require('node:test')
const assert = require('node:assert/strict')

const {
  cleDeFond,
  clesDuSub,
  subsDeLaPopulation,
  resumerSlowlog,
  lireOptions
} = require('./redis-connect.cjs')

test('une clé de fond a la longueur demandée et le préfixe de connect', () => {
  const cle = cleDeFond(7, 60)

  assert.equal(cle.length, 60)
  assert.ok(cle.startsWith('oidc:perf-fond:'))
})

test('une clé de fond trop courte pour son compteur est refusée', () => {
  assert.throws(() => cleDeFond(10 ** 50, 20))
})

test('un sub porte les deux clés que connect révoque', () => {
  assert.deepEqual(clesDuSub('perf-migr-000001'), [
    'oidc:access_token:JEUNE|POLE_EMPLOI|perf-migr-000001',
    'oidc:refresh_token:JEUNE|POLE_EMPLOI|perf-migr-000001'
  ])
})

test('les subs de la population sont sur six chiffres', () => {
  assert.deepEqual(subsDeLaPopulation('perf-migr-', 3), [
    'perf-migr-000000',
    'perf-migr-000001',
    'perf-migr-000002'
  ])
})

test("aucun sub n'est sous-chaîne d'un autre, sinon KEYS *<sub>* déborde", () => {
  const subs = subsDeLaPopulation('perf-migr-', 2000)

  const debordements = subs.filter(sub =>
    subs.some(autre => autre !== sub && autre.includes(sub))
  )

  assert.deepEqual(debordements, [])
})

test('un slowlog sans KEYS ne donne aucune mesure', () => {
  assert.equal(resumerSlowlog([]), null)
  assert.equal(resumerSlowlog([[1, 0, 50000, ['SET', 'a', 'b']]]), null)
})

test('le slowlog ne résume que les KEYS', () => {
  const entrees = [
    [4, 0, 300000, ['KEYS', 'oidc:*perf-migr-000002*']],
    [3, 0, 200000, ['keys', 'oidc:*perf-migr-000001*']],
    [2, 0, 900000, ['SET', 'oidc:x', 'y']],
    [1, 0, 100000, ['KEYS', 'oidc:*perf-migr-000000*']]
  ]

  const resume = resumerSlowlog(entrees)

  assert.equal(resume.nb, 3)
  assert.equal(resume.max_ms, 300)
  assert.equal(resume.p50_ms, 200)
  assert.equal(resume.p95_ms, 300)
})

test("l'URL Redis vient de --url avant REDIS_URL", () => {
  const options = lireOptions(['semer', '--url', 'redis://local:1', '--taille', '10'], {
    REDIS_URL: 'redis://env:2'
  })

  assert.equal(options.commande, 'semer')
  assert.equal(options.url, 'redis://local:1')
  assert.equal(options.taille, 10)
})

test("sans --url, l'URL Redis vient de REDIS_URL", () => {
  const options = lireOptions(['bilan'], { REDIS_URL: 'redis://env:2' })

  assert.equal(options.url, 'redis://env:2')
  assert.equal(options.prefixe, 'perf-migr-')
})

test('sans URL Redis, la commande est refusée', () => {
  assert.throws(() => lireOptions(['bilan'], {}), /URL Redis/)
})
