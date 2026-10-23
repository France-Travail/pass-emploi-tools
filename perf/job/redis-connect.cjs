// Seed et bilan du Redis de connect pour le scénario job d'archivage.
//
//   node redis-connect.cjs semer --url <redis> --fond 1000000 --longueur 60 \
//        --prefixe perf-migr- --taille 2000 --ttl 259200
//   node redis-connect.cjs bilan --url <redis> --prefixe perf-migr-
//
// Sans --url, REDIS_URL est lu (cas d'un one-off sur pass-emploi-connect-perf).
// ioredis est résolu depuis le répertoire courant : lancer depuis un checkout de
// pass-emploi-connect, ou depuis /app dans un one-off. Le repo tools n'a aucune
// dépendance npm.
//
// Le nettoyage révoque par KEYS oidc:*<sub>*, qui parcourt tout le keyspace et
// applique le glob à chaque clé : son coût suit le nombre de clés et, au second
// ordre, leur longueur. D'où un fond au DBSIZE de prod, sous le préfixe oidc:
// que portent toutes les clés de connect.
//
// Pipelines de LOT_PIPELINE commandes, un seul en vol : Redis traite un lot puis
// se libère pour les autres clients, au lieu d'être bloqué par un script Lua.

const { createRequire } = require('node:module')

const LOT_PIPELINE = 1000
const PREFIXE_FOND = 'oidc:perf-fond:'
const LARGEUR_SUB = 6
const ENTREES_SLOWLOG = 128

function cleDeFond(n, longueur) {
  const largeur = longueur - PREFIXE_FOND.length
  const compteur = BigInt(n).toString()
  if (compteur.length > largeur) {
    throw new Error(
      `longueur ${longueur} trop courte pour la clé de fond n° ${compteur}`
    )
  }
  return PREFIXE_FOND + compteur.padStart(largeur, '0')
}

function clesDuSub(sub) {
  return [
    `oidc:access_token:JEUNE|POLE_EMPLOI|${sub}`,
    `oidc:refresh_token:JEUNE|POLE_EMPLOI|${sub}`
  ]
}

function subsDeLaPopulation(prefixe, taille) {
  return Array.from(
    { length: taille },
    (_, i) => prefixe + String(i).padStart(LARGEUR_SUB, '0')
  )
}

function percentile(triees, rang) {
  return triees[Math.max(0, Math.ceil((rang / 100) * triees.length) - 1)]
}

function resumerSlowlog(entrees) {
  const durees_ms = entrees
    .filter(([, , , args]) => String(args?.[0] ?? '').toLowerCase() === 'keys')
    .map(([, , dureeUs]) => Number(dureeUs) / 1000)
    .sort((a, b) => a - b)
  if (durees_ms.length === 0) return null
  return {
    nb: durees_ms.length,
    p50_ms: percentile(durees_ms, 50),
    p95_ms: percentile(durees_ms, 95),
    max_ms: durees_ms[durees_ms.length - 1]
  }
}

function lireOptions(argv, env) {
  const [commande, ...reste] = argv
  const brutes = {}
  for (let i = 0; i < reste.length; i += 2) {
    brutes[reste[i].replace(/^--/, '')] = reste[i + 1]
  }
  const url = brutes.url ?? env.REDIS_URL
  if (!url) {
    throw new Error('URL Redis absente : passer --url ou poser REDIS_URL')
  }
  return {
    commande,
    url,
    prefixe: brutes.prefixe ?? 'perf-migr-',
    fond: Number(brutes.fond ?? 1000000),
    longueur: Number(brutes.longueur ?? 60),
    taille: Number(brutes.taille ?? 2000),
    ttl: Number(brutes.ttl ?? 259200)
  }
}

async function ecrireParLots(redis, cles, valeur, ttl) {
  for (let debut = 0; debut < cles.length; debut += LOT_PIPELINE) {
    const pipeline = redis.pipeline()
    for (const cle of cles.slice(debut, debut + LOT_PIPELINE)) {
      pipeline.set(cle, valeur(cle), 'EX', ttl)
    }
    await pipeline.exec()
  }
}

async function semer(redis, options) {
  for (let debut = 0; debut < options.fond; debut += LOT_PIPELINE) {
    const fin = Math.min(debut + LOT_PIPELINE, options.fond)
    const cles = []
    for (let n = debut; n < fin; n++) cles.push(cleDeFond(n, options.longueur))
    await ecrireParLots(redis, cles, () => 'x'.repeat(40), options.ttl)
  }

  const expiresAt = Math.floor(Date.now() / 1000) + options.ttl
  const clesPopulation = subsDeLaPopulation(options.prefixe, options.taille).flatMap(clesDuSub)
  await ecrireParLots(
    redis,
    clesPopulation,
    cle => JSON.stringify({ token: `perf-${cle.slice(-16)}`, expiresAt }),
    options.ttl
  )

  try {
    await redis.slowlog('RESET')
  } catch (e) {
    console.error(`SLOWLOG RESET refusé : ${e.message}`)
  }
  return { dbsize: await redis.dbsize() }
}

async function compterClesPopulation(redis, prefixe) {
  let nb = 0
  const flux = redis.scanStream({ match: `oidc:*${prefixe}*`, count: 1000 })
  for await (const cles of flux) nb += cles.length
  return nb
}

async function bilan(redis, options) {
  let keys = null
  try {
    keys = resumerSlowlog(await redis.slowlog('GET', ENTREES_SLOWLOG))
  } catch (e) {
    console.error(`SLOWLOG GET refusé : ${e.message}`)
  }
  return {
    dbsize: await redis.dbsize(),
    cles_population_restantes: await compterClesPopulation(redis, options.prefixe),
    keys
  }
}

async function main() {
  const options = lireOptions(process.argv.slice(2), process.env)
  const commandes = { semer, bilan }
  const executer = commandes[options.commande]
  if (!executer) throw new Error(`commande inconnue : ${options.commande}`)

  const Redis = createRequire(process.cwd() + '/')('ioredis')
  const redis = new Redis(options.url)
  try {
    console.log(JSON.stringify(await executer(redis, options)))
  } finally {
    redis.disconnect()
  }
}

if (require.main === module) {
  main().catch(e => {
    console.error(e.message)
    process.exit(1)
  })
}

module.exports = {
  cleDeFond,
  clesDuSub,
  subsDeLaPopulation,
  resumerSlowlog,
  lireOptions
}
