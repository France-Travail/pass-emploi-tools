# Sécurité du mode invité

## Contexte

Le mode invité rend l’application accessible à des utilisateurs anonymes ou faiblement identifiés.

Cela augmente fortement la surface d’exposition :

- création massive de comptes invités ;
- scraping ;
- abus d’API publiques ;
- consommation excessive d’APIs partenaires ;
- saturation infra ;
- contournement d’autorisations ;
- fuite de données via logs / APM / observabilité.

Objectif de cette note :

- définir les mesures minimales avant ouverture large ;
- préciser l’architecture de rate limiting ;
- proposer une implémentation concrète adaptée à Scalingo.

---

## Risques principaux

| Risque | Exemple | Gravité |
|---|---|---:|
| Création massive d’invités | Bot qui crée des milliers de comptes invités | Élevée |
| Scraping | Requêtes massives sur offres/contenus publics | Élevée |
| Saturation API | Appels fréquents sur endpoints coûteux | Élevée |
| Abus d’APIs externes | Surconsommation d’APIs partenaires via invités | Élevée |
| Élévation de privilège | Payload modifié pour se donner une structure ou un rôle | Critique |
| Accès à données non publiques | Invité accédant à données conseiller/jeune | Critique |
| Logs sensibles | Token, installationId, bearer ou payload sensible loggué | Élevée |
| Explosion des coûts | Trafic anonyme incontrôlé | Élevée |

---

## Principes de sécurité

1. Deny by default pour le profil invité.
2. Rate limiting distribué pour toute route publique ou coûteuse.
3. Aucun champ sensible contrôlé par le client :
   - type ;
   - structure ;
   - rôles ;
   - ids métier.
4. Observabilité dédiée au mode invité.
5. Kill switch activable sans redéploiement.
6. Purge automatique des données invité.
7. CI sécurité obligatoire avant merge.

---

## Matrice d’autorisations invité

À valider précisément avec le produit.

| Fonctionnalité | Invité |
|---|---:|
| Consultation contenus publics | Autorisé |
| Recherche offres | Autorisé avec quota |
| Détail offre publique | Autorisé avec quota |
| Favoris invités | Autorisé uniquement sur ses propres favoris |
| Configuration application invité | Autorisé uniquement sur lui-même |
| Chat / messagerie | Interdit sauf décision explicite |
| Données conseiller | Interdit |
| Données jeune authentifié | Interdit |
| Rendez-vous / actions personnalisées | Interdit sauf décision explicite |
| Admin / support | Interdit |
| Impersonation | Interdit |
| Endpoints partenaires | Interdit |
| Exports | Interdit |
| Uploads | Interdit sauf décision explicite |

Tout endpoint non listé comme autorisé doit être interdit par défaut.

---

# Rate limiting

## Objectif

Limiter les abus tout en gardant une expérience fluide pour un utilisateur réel.

Le rate limiting doit protéger :

1. la création de comptes invités ;
2. les endpoints publics anonymes ;
3. les endpoints authentifiés avec profil invité ;
4. les endpoints coûteux ;
5. les appels indirects vers APIs partenaires ;
6. les endpoints provoquant des écritures en base.

---

## Spécificité Scalingo

Sur Scalingo, l’application peut tourner sur plusieurs containers / instances.

Un rate limit uniquement en mémoire dans le process Node.js est insuffisant pour protéger un endpoint public.

Exemple :

- instance A autorise 100 requêtes/minute ;
- instance B autorise 100 requêtes/minute ;
- instance C autorise 100 requêtes/minute.

Avec 3 instances, la limite réelle devient 300 requêtes/minute.

Donc :

- OK pour du rate limiting en mémoire sur des appels sortants non critiques ;
- pas OK pour protéger le mode invité exposé publiquement.

Pour le mode invité, il faut un backend partagé.

Recommandation : Redis.

---

## Architecture recommandée

    Client public
       |
       v
    Scalingo router / proxy
       |
       v
    pass-emploi-connect ou API publique
       |
       |-- Rate limit IP / device / endpoint via Redis
       |
       v
    pass-emploi-api
       |
       |-- Rate limit métier invité via Redis
       |-- Vérification autorisations invité
       |
       v
    PostgreSQL / APIs externes

Deux niveaux de protection :

1. Edge / entrée publique :
   - par IP ;
   - par endpoint ;
   - par user-agent éventuellement ;
   - protège contre bots simples et floods.

2. Applicatif métier :
   - par invité ;
   - par installationId si disponible ;
   - par action métier ;
   - par API externe consommée.

---

## Où placer le rate limiting ?

| Composant | Protection |
|---|---|
| pass-emploi-connect | création invité par IP/device/global |
| pass-emploi-api | protection secondaire création invité + quotas métier |
| application mobile | UX propre en cas de 429 |
| Scalingo/proxy | limites générales si disponibles |
| Redis | stockage partagé des compteurs |

La première porte publique doit limiter.

Si la création invité est déclenchée depuis pass-emploi-connect, alors le rate limit doit être dans pass-emploi-connect.

pass-emploi-api doit aussi avoir une protection secondaire pour éviter qu’un appel interne mal maîtrisé ou un bug contourne la première barrière.

---

## Stratégie de clés Redis

Utiliser des clés courtes et explicites.

Exemples :

    rl:guest:create:ip:<ipHash>
    rl:guest:create:device:<deviceHash>
    rl:guest:create:global

    rl:guest:api:ip:<ipHash>
    rl:guest:api:user:<guestIdHash>

    rl:guest:search:ip:<ipHash>
    rl:guest:search:user:<guestIdHash>

    rl:guest:favorites:user:<guestIdHash>
    rl:guest:config:user:<guestIdHash>

    rl:external:offres:guest:global
    rl:external:offres:guest:user:<guestIdHash>

Ne pas stocker l’IP brute si ce n’est pas nécessaire.

Préférer un hash HMAC avec un secret applicatif :

    ipHash = hmacSha256(RATE_LIMIT_HASH_SECRET, ip)

---

## Limites recommandées au lancement

Ces valeurs sont volontairement prudentes et doivent être ajustées avec les métriques réelles.

| Action | Clé | Limite initiale |
|---|---|---:|
| Création invité par IP | guest:create:ip | 5 / heure |
| Création invité par device | guest:create:device | 3 / jour |
| Création invité globale | guest:create:global | 1000 / heure |
| Appels API invité par IP | guest:api:ip | 300 / 10 min |
| Appels API par invité | guest:api:user | 600 / 10 min |
| Recherche offres par IP | guest:search:ip | 60 / min |
| Recherche offres par invité | guest:search:user | 120 / 10 min |
| Détail offre par IP | guest:offre-detail:ip | 120 / min |
| Ajout favori par invité | guest:favorites:user | 30 / heure |
| Modification configuration invité | guest:config:user | 20 / heure |
| Endpoint coûteux générique | guest:expensive:user | 30 / 10 min |

Réponse attendue en cas de dépassement :

    HTTP/1.1 429 Too Many Requests
    Retry-After: 60

Payload conseillé :

    {
      "message": "Trop de requêtes. Merci de réessayer plus tard."
    }

Ne pas révéler les seuils exacts dans la réponse publique.

---

## Algorithme recommandé

Pour une première implémentation robuste : fixed window Redis avec TTL.

Principe :

1. INCR key
2. si la valeur vaut 1, alors EXPIRE key windowSeconds
3. si la valeur dépasse la limite, répondre 429
4. sinon autoriser

Avantages :

- simple ;
- rapide ;
- facile à tester ;
- suffisant pour le lancement.

Limite :

- effet de bord en frontière de fenêtre.

Cette limite est acceptable pour une première version.

Une évolution possible plus tard : sliding window ou token bucket Redis via script Lua.

---

## Redis sur Scalingo

Prévoir un addon Redis ou une instance Redis managée.

Variable attendue :

    REDIS_URL=<redis-url>

Bonnes pratiques :

- TLS si disponible ;
- authentification Redis ;
- pas d’exposition publique ;
- timeouts courts ;
- circuit breaker applicatif ;
- fallback strict.

Fallback recommandé :

| Endpoint | Comportement si Redis indisponible |
|---|---|
| Création invité | fail closed : refuser temporairement |
| Endpoint coûteux invité | fail closed ou très restrictif |
| Endpoint public peu coûteux | fail open possible selon criticité |
| Endpoint authentifié non invité | ne pas bloquer si non concerné |

Pour le mode invité, la création de compte doit fail closed.

Si Redis est down, mieux vaut refuser temporairement la création d’invités que permettre un abus massif sans limite.

---

## Implémentation NestJS proposée

### Service Redis-backed

Créer un service dédié :

    src/infrastructure/rate-limiting/redis-rate-limiter.service.ts

Interface :

    export interface RateLimitRule {
      key: string
      limit: number
      windowSeconds: number
    }

    export interface RateLimitResult {
      allowed: boolean
      remaining: number
      retryAfterSeconds?: number
      exceededKey?: string
    }

Implémentation conceptuelle :

    import { Injectable } from '@nestjs/common'

    @Injectable()
    export class RedisRateLimiterService {
      constructor(
        private readonly redisClient: RedisClient
      ) {}

      async check(rule: RateLimitRule): Promise<RateLimitResult> {
        const current = await this.redisClient.incr(rule.key)

        if (current === 1) {
          await this.redisClient.expire(rule.key, rule.windowSeconds)
        }

        if (current > rule.limit) {
          const ttl = await this.redisClient.ttl(rule.key)

          return {
            allowed: false,
            remaining: 0,
            retryAfterSeconds: Math.max(ttl, 1),
            exceededKey: rule.key
          }
        }

        return {
          allowed: true,
          remaining: Math.max(rule.limit - current, 0)
        }
      }

      async checkAll(rules: RateLimitRule[]): Promise<RateLimitResult> {
        for (const rule of rules) {
          const result = await this.check(rule)

          if (!result.allowed) {
            return result
          }
        }

        return {
          allowed: true,
          remaining: Math.min(...rules.map(rule => rule.limit))
        }
      }
    }

À améliorer ensuite avec un script Lua pour garantir totalement l’atomicité INCR + EXPIRE.

---

## Version Lua recommandée à terme

Le script Lua évite le cas limite où INCR réussit mais EXPIRE échoue.

Principe :

    local current = redis.call("INCR", KEYS[1])

    if current == 1 then
      redis.call("EXPIRE", KEYS[1], ARGV[2])
    end

    if current > tonumber(ARGV[1]) then
      local ttl = redis.call("TTL", KEYS[1])
      return {0, 0, ttl}
    end

    return {1, tonumber(ARGV[1]) - current, 0}

---

## Helper de hash des identifiants

Fichier proposé :

    src/infrastructure/rate-limiting/rate-limit-identifier.ts

Contenu :

    import { createHmac } from 'crypto'

    export function hashRateLimitIdentifier(
      secret: string,
      value: string | undefined
    ): string {
      return createHmac('sha256', secret)
        .update(value ?? 'unknown')
        .digest('hex')
        .slice(0, 32)
    }

Secret attendu :

    RATE_LIMIT_HASH_SECRET=<secret>

---

## IP réelle derrière Scalingo

Derrière un router/proxy, l’IP client est généralement transmise via X-Forwarded-For.

Côté NestJS / Express, configurer :

    app.set('trust proxy', true)

Ensuite utiliser :

    const ip = request.ip

Éviter de lire directement :

    request.headers['x-forwarded-for']

sauf si la chaîne de proxy est maîtrisée et validée.

---

## Exception 429

Créer une exception ou un helper permettant d’ajouter Retry-After.

Exemple conceptuel :

    import { HttpException, HttpStatus } from '@nestjs/common'

    export class TooManyRequestsWithRetryAfterException extends HttpException {
      constructor(public readonly retryAfterSeconds: number) {
        super(
          {
            message: 'Trop de requêtes. Merci de réessayer plus tard.'
          },
          HttpStatus.TOO_MANY_REQUESTS
        )
      }
    }

Si besoin du header Retry-After, l’ajouter dans un filtre d’exception NestJS ou directement dans le guard via la response Express.

---

## Guard de création invité

La création invité doit appliquer plusieurs règles cumulées :

1. par IP ;
2. par device / installationId si disponible ;
3. globale.

Pseudo-code :

    @Injectable()
    export class GuestCreationRateLimitGuard implements CanActivate {
      constructor(
        private readonly rateLimiter: RedisRateLimiterService,
        private readonly configService: ConfigService
      ) {}

      async canActivate(context: ExecutionContext): Promise<boolean> {
        const request = context.switchToHttp().getRequest<Request>()

        const enabled = this.configService.get<boolean>('rateLimit.enabled')

        if (!enabled) {
          return true
        }

        const secret = this.configService.get<string>('rateLimit.hashSecret')!
        const ipHash = hashRateLimitIdentifier(secret, request.ip)
        const installationId = request.header('X-InstallationId')
        const deviceHash = hashRateLimitIdentifier(secret, installationId)

        const result = await this.rateLimiter.checkAll([
          {
            key: `rl:guest:create:ip:${ipHash}`,
            limit: this.configService.get<number>('rateLimit.guest.create.ip.limit')!,
            windowSeconds: this.configService.get<number>('rateLimit.guest.create.ip.windowSeconds')!
          },
          {
            key: `rl:guest:create:device:${deviceHash}`,
            limit: this.configService.get<number>('rateLimit.guest.create.device.limit')!,
            windowSeconds: this.configService.get<number>('rateLimit.guest.create.device.windowSeconds')!
          },
          {
            key: 'rl:guest:create:global',
            limit: this.configService.get<number>('rateLimit.guest.create.global.limit')!,
            windowSeconds: this.configService.get<number>('rateLimit.guest.create.global.windowSeconds')!
          }
        ])

        if (!result.allowed) {
          throw new TooManyRequestsWithRetryAfterException(
            result.retryAfterSeconds ?? 60
          )
        }

        return true
      }
    }

---

## Guard générique pour endpoints invités

Objectif :

- ne rien faire pour les utilisateurs non invités ;
- appliquer des quotas pour les utilisateurs invités.

Pseudo-code :

    @Injectable()
    export class GuestApiRateLimitGuard implements CanActivate {
      constructor(
        private readonly rateLimiter: RedisRateLimiterService,
        private readonly configService: ConfigService
      ) {}

      async canActivate(context: ExecutionContext): Promise<boolean> {
        const request = context.switchToHttp().getRequest<RequestWithUser>()
        const utilisateur = request.user

        if (utilisateur?.profil?.structure !== 'INVITE') {
          return true
        }

        const secret = this.configService.get<string>('rateLimit.hashSecret')!
        const ipHash = hashRateLimitIdentifier(secret, request.ip)
        const userHash = hashRateLimitIdentifier(secret, utilisateur.id)

        const result = await this.rateLimiter.checkAll([
          {
            key: `rl:guest:api:ip:${ipHash}`,
            limit: this.configService.get<number>('rateLimit.guest.api.ip.limit')!,
            windowSeconds: this.configService.get<number>('rateLimit.guest.api.ip.windowSeconds')!
          },
          {
            key: `rl:guest:api:user:${userHash}`,
            limit: this.configService.get<number>('rateLimit.guest.api.user.limit')!,
            windowSeconds: this.configService.get<number>('rateLimit.guest.api.user.windowSeconds')!
          }
        ])

        if (!result.allowed) {
          throw new TooManyRequestsWithRetryAfterException(
            result.retryAfterSeconds ?? 60
          )
        }

        return true
      }
    }

---

## Limites spécifiques par feature

En plus du guard générique, ajouter des limites spécifiques sur les actions sensibles.

### Recherche offres

    const rules = [
      {
        key: `rl:guest:search:ip:${ipHash}`,
        limit: 60,
        windowSeconds: 60
      },
      {
        key: `rl:guest:search:user:${userHash}`,
        limit: 120,
        windowSeconds: 600
      }
    ]

### Ajout favori

    const rules = [
      {
        key: `rl:guest:favorites:user:${userHash}`,
        limit: 30,
        windowSeconds: 3600
      }
    ]

### Configuration invité

    const rules = [
      {
        key: `rl:guest:config:user:${userHash}`,
        limit: 20,
        windowSeconds: 3600
      }
    ]

### API externe offres

    const rules = [
      {
        key: 'rl:external:offres:guest:global',
        limit: 5000,
        windowSeconds: 60
      },
      {
        key: `rl:external:offres:guest:user:${userHash}`,
        limit: 60,
        windowSeconds: 60
      }
    ]

---

## Configuration applicative

Ajouter dans les environnements Scalingo :

    RATE_LIMIT_ENABLED=true
    RATE_LIMIT_HASH_SECRET=<secret>

    MODE_INVITE_ACTIF=true
    MODE_INVITE_CREATION_ACTIVE=true

    RATE_LIMIT_GUEST_CREATE_IP_LIMIT=5
    RATE_LIMIT_GUEST_CREATE_IP_WINDOW_SECONDS=3600

    RATE_LIMIT_GUEST_CREATE_DEVICE_LIMIT=3
    RATE_LIMIT_GUEST_CREATE_DEVICE_WINDOW_SECONDS=86400

    RATE_LIMIT_GUEST_CREATE_GLOBAL_LIMIT=1000
    RATE_LIMIT_GUEST_CREATE_GLOBAL_WINDOW_SECONDS=3600

    RATE_LIMIT_GUEST_API_IP_LIMIT=300
    RATE_LIMIT_GUEST_API_IP_WINDOW_SECONDS=600

    RATE_LIMIT_GUEST_API_USER_LIMIT=600
    RATE_LIMIT_GUEST_API_USER_WINDOW_SECONDS=600

    RATE_LIMIT_GUEST_SEARCH_IP_LIMIT=60
    RATE_LIMIT_GUEST_SEARCH_IP_WINDOW_SECONDS=60

    RATE_LIMIT_GUEST_SEARCH_USER_LIMIT=120
    RATE_LIMIT_GUEST_SEARCH_USER_WINDOW_SECONDS=600

    RATE_LIMIT_GUEST_FAVORITES_USER_LIMIT=30
    RATE_LIMIT_GUEST_FAVORITES_USER_WINDOW_SECONDS=3600

    RATE_LIMIT_GUEST_CONFIG_USER_LIMIT=20
    RATE_LIMIT_GUEST_CONFIG_USER_WINDOW_SECONDS=3600

---

## Configuration NestJS

Ajouter les variables dans :

    src/config/configuration.ts
    src/config/configuration.schema.ts

Structure cible :

    rateLimit: {
      enabled: process.env.RATE_LIMIT_ENABLED === 'true',
      hashSecret: process.env.RATE_LIMIT_HASH_SECRET,
      guest: {
        create: {
          ip: {
            limit: process.env.RATE_LIMIT_GUEST_CREATE_IP_LIMIT,
            windowSeconds: process.env.RATE_LIMIT_GUEST_CREATE_IP_WINDOW_SECONDS
          },
          device: {
            limit: process.env.RATE_LIMIT_GUEST_CREATE_DEVICE_LIMIT,
            windowSeconds: process.env.RATE_LIMIT_GUEST_CREATE_DEVICE_WINDOW_SECONDS
          },
          global: {
            limit: process.env.RATE_LIMIT_GUEST_CREATE_GLOBAL_LIMIT,
            windowSeconds: process.env.RATE_LIMIT_GUEST_CREATE_GLOBAL_WINDOW_SECONDS
          }
        },
        api: {
          ip: {
            limit: process.env.RATE_LIMIT_GUEST_API_IP_LIMIT,
            windowSeconds: process.env.RATE_LIMIT_GUEST_API_IP_WINDOW_SECONDS
          },
          user: {
            limit: process.env.RATE_LIMIT_GUEST_API_USER_LIMIT,
            windowSeconds: process.env.RATE_LIMIT_GUEST_API_USER_WINDOW_SECONDS
          }
        }
      }
    }

Validation Joi attendue :

    RATE_LIMIT_ENABLED: Joi.boolean().required(),
    RATE_LIMIT_HASH_SECRET: Joi.string().min(32).required(),

    RATE_LIMIT_GUEST_CREATE_IP_LIMIT: Joi.number().integer().positive().required(),
    RATE_LIMIT_GUEST_CREATE_IP_WINDOW_SECONDS: Joi.number().integer().positive().required(),

    RATE_LIMIT_GUEST_CREATE_DEVICE_LIMIT: Joi.number().integer().positive().required(),
    RATE_LIMIT_GUEST_CREATE_DEVICE_WINDOW_SECONDS: Joi.number().integer().positive().required(),

    RATE_LIMIT_GUEST_CREATE_GLOBAL_LIMIT: Joi.number().integer().positive().required(),
    RATE_LIMIT_GUEST_CREATE_GLOBAL_WINDOW_SECONDS: Joi.number().integer().positive().required()

---

## Rate limiting des APIs externes

Le token bucket mémoire existant est utile pour lisser des appels depuis une instance.

Mais pour les APIs externes sensibles appelées par le mode invité, ajouter aussi un quota distribué Redis.

Clés recommandées :

    rl:external:<apiName>:guest:global
    rl:external:<apiName>:guest:user:<guestIdHash>

Exemples :

| API externe | Clé | Limite |
|---|---|---:|
| offres | global invité | 5000 / min |
| offres | par invité | 60 / min |
| matomo | global | selon quota fournisseur |
| partenaire X | global | selon contrat |

En cas de dépassement :

- répondre 429 si l’action est directement déclenchée par l’utilisateur ;
- ou désactiver temporairement la fonctionnalité non critique ;
- ne pas retry massivement.

---

## Logs

Logger les dépassements sans données sensibles.

Exemple :

    {
      "context": "GuestRateLimit",
      "event": {
        "action": "rate_limit_exceeded",
        "scope": "guest:create:ip",
        "outcome": "failure"
      }
    }

Ne pas logger :

- IP brute ;
- bearer token ;
- API key ;
- payload complet ;
- installationId complet.

---

## Métriques

Métriques à exposer :

    guest_rate_limit_allowed_total
    guest_rate_limit_blocked_total
    guest_account_created_total
    guest_account_retrieved_total
    guest_creation_blocked_total
    guest_search_blocked_total
    guest_api_429_total
    guest_403_total
    guest_external_api_blocked_total

Alertes :

| Signal | Alerte |
|---|---|
| Créations invité > seuil | Suspicion abus |
| 429 en forte hausse | Bot ou limite trop basse |
| 403 invité en hausse | Tentative accès interdit |
| Redis rate limit down | Risque sécurité |
| Ratio créations/récupérations anormal | Bug ou abus |
| APIs externes proches quota | Risque indisponibilité |

---

## Kill switch

Ajouter deux flags :

    MODE_INVITE_ACTIF=true
    MODE_INVITE_CREATION_ACTIVE=true

Comportement attendu :

| Flag | Effet |
|---|---|
| MODE_INVITE_ACTIF=false | désactive tout accès invité |
| MODE_INVITE_CREATION_ACTIVE=false | bloque seulement les nouvelles créations |

Cela permet de stopper une attaque sans redéployer.

---

## Validation des inputs

À vérifier globalement :

- DTO stricts ;
- rejet des propriétés inconnues ;
- limites de taille sur strings ;
- UUID validés ;
- pagination bornée ;
- recherche texte bornée ;
- payload max côté proxy et application.

Configuration NestJS recommandée :

    app.useGlobalPipes(
      new ValidationPipe({
        whitelist: true,
        forbidNonWhitelisted: true,
        transform: true
      })
    )

---

## Purge et rétention

La rétention des invités doit être courte et assumée.

Recommandation initiale :

| Donnée | Rétention |
|---|---:|
| invité inactif | 30 à 90 jours |
| favoris invité | même durée que l’invité |
| tokens/sessions | durée courte |
| logs détaillés | minimisés |

Le job de purge doit être monitoré et alerté.

---

## CI/CD sécurité

Avant ouverture publique :

- CodeQL obligatoire ;
- audit dépendances obligatoire ;
- Dependabot activé ;
- alertes CVE high/critical toutes les 3h ;
- branch protection ;
- checks obligatoires avant merge ;
- pas de référence @master dans les actions critiques ;
- préférer SHA ou tag protégé.

---

## Tests à prévoir

### Tests unitaires

- autorise sous la limite ;
- bloque au-dessus de la limite ;
- ajoute Retry-After ;
- applique plusieurs règles cumulées ;
- hash les identifiants ;
- ne loggue pas d’IP brute.

### Tests d’intégration

- création invité limitée par IP ;
- création invité limitée par device ;
- recherche limitée par invité ;
- favoris limités par invité ;
- endpoint sensible interdit à invité ;
- Redis indisponible sur création invité => refus temporaire.

### Tests de charge / abus

Scénarios minimum :

1. 100 créations invité depuis une IP ;
2. 1000 recherches offres en 1 minute ;
3. pagination profonde ;
4. création depuis plusieurs IPs simulées ;
5. appels concurrents ;
6. Redis lent ou indisponible.

---

## Checklist go/no-go

### P0

- [ ] Rate limit Redis distribué sur création invité.
- [ ] Rate limit Redis distribué sur endpoints invités coûteux.
- [ ] Rate limit par IP, par invité et global.
- [ ] Kill switch mode invité.
- [ ] Kill switch création invité.
- [ ] Matrice d’autorisations validée.
- [ ] Tests négatifs sur accès invité.
- [ ] Validation stricte des inputs.
- [ ] Pagination limitée.
- [ ] Logs sans secret/token/IP brute.
- [ ] Métriques et alertes mode invité.
- [ ] Purge invitée monitorée.
- [ ] CI sécurité obligatoire.
- [ ] Plan d’urgence en cas d’abus.

### P1

- [ ] WAF ou règles proxy si disponible.
- [ ] Cache sur données publiques.
- [ ] Circuit breaker APIs externes.
- [ ] Rotation des secrets avant lancement.
- [ ] Tests de charge et scénarios d’abus.
- [ ] Dashboards dédiés mode invité.

---

## Décision d’architecture recommandée

Pour le lancement public du mode invité :

1. utiliser Redis comme stockage distribué de rate limiting ;
2. appliquer les limites à l’entrée publique et côté API métier ;
3. bloquer la création invité si Redis est indisponible ;
4. conserver le token bucket mémoire existant uniquement pour du lissage local ou des appels sortants non critiques ;
5. ajouter des quotas globaux pour protéger l’infra ;
6. monitorer et alerter dès le premier jour.

---

# Découpage de tickets proposé

## Ticket 1 - Documentation

Créer :

    pass-emploi-tools/docs/securite/mode-invite.md

Y déposer cette spécification.

---

## Ticket 2 - Configuration

Ajouter les variables de rate limiting et de kill switch dans les apps concernées :

- pass-emploi-connect ;
- pass-emploi-api.

---

## Ticket 3 - Redis rate limiter générique

Créer :

    src/infrastructure/rate-limiting/redis-rate-limiter.service.ts
    src/infrastructure/rate-limiting/rate-limit-identifier.ts

Ajouter :

- service Redis-backed ;
- hash HMAC ;
- check simple ;
- check multiple rules ;
- tests unitaires.

---

## Ticket 4 - Rate limit création invité dans pass-emploi-connect

Mettre la protection au premier point d’entrée public.

Règles :

- IP : 5 / heure ;
- device : 3 / jour ;
- global : 1000 / heure.

Si Redis down :

- fail closed ;
- répondre 503 ou 429 selon choix produit/tech ;
- log sécurité sans données sensibles.

---

## Ticket 5 - Rate limit création invité dans pass-emploi-api

Ajouter une seconde protection côté API.

Objectif :

- défense en profondeur ;
- éviter qu’un bug côté connect contourne totalement la protection ;
- disposer de métriques API.

---

## Ticket 6 - Rate limit endpoints invités dans pass-emploi-api

Endpoints à couvrir en priorité :

- recherche offres ;
- détail offre ;
- favoris ;
- configuration application ;
- tout endpoint coûteux accessible à INVITE.

---

## Ticket 7 - Observabilité

Ajouter métriques et alertes :

    guest_rate_limit_allowed_total
    guest_rate_limit_blocked_total
    guest_account_created_total
    guest_account_retrieved_total
    guest_creation_blocked_total
    guest_search_blocked_total
    guest_api_429_total
    guest_403_total
    guest_external_api_blocked_total

Alertes :

- pic de créations ;
- pic de 429 ;
- pic de 403 ;
- Redis down ;
- job purge invité down ;
- APIs externes proches quota.

---

## Ticket 8 - Tests d’abus

Scénarios :

1. 100 créations invité depuis une IP ;
2. 1000 recherches offres en 1 minute ;
3. pagination profonde ;
4. création depuis plusieurs IPs simulées ;
5. appels concurrents ;
6. Redis down ;
7. invité qui tente endpoint conseiller ;
8. invité qui tente de modifier rôles/type/structure.
~~~