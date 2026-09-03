# mock-externes

Se fait passer pour les dépendances **hors de notre contrôle** pendant un tir de
perf, et pour rien d'autre : `pass-emploi-connect` et `pass-emploi-api` restent
réels et sont ce qu'on mesure.

```
Gatling ──► connect-perf ──► mock-externes   (IdP France Travail)
         └► api-perf ──────► mock-externes   (APIs partenaires FT)
                          └► connect-perf    (émetteur du JWT — le vrai)
```

## Ce qu'il sert

| Route | Client | Rôle |
|---|---|---|
| `GET /idp/protocol/openid-connect/auth` | `connect` | Redirige vers `redirect_uri` avec `code` et `state`, sans page de login |
| `POST /idp/protocol/openid-connect/token` | `connect` | `access_token`, `id_token` signé, `refresh_token` |
| `GET /idp/protocol/openid-connect/certs` | `connect` | Clé publique validant l'`id_token` |
| `GET /idp/protocol/openid-connect/userinfo` | `connect` | `sub`, `preferred_username` |
| `GET /poleemploi/peconnect-coordonnees/v1/coordonnees` | `connect` | Nom, prénom, email — **c'est ici** que `connect` les prend pour un bénéficiaire FT, pas dans le `userinfo` |
| `GET /poleemploi/peconnect-statut/v1/statut` | `connect` | Filet : appelé seulement si l'API répond `UTILISATEUR_INEXISTANT` |
| `GET /poleemploi/peconnect-demarches/v1/demarches` | `api` | Démarches de l'accueil |
| `GET /poleemploi/peconnect-gerer-prestations/v1/rendez-vous` | `api` | Prestations (vide) |
| `GET /poleemploi/peconnect-rendezvousagenda/v2/listerendezvous` | `api` | Rendez-vous agenda (vide) |

## Deux principes de conception

**Aucune clé d'un environnement réel.** Le mock génère sa paire RSA au démarrage
et publie la publique sur son `certs`. C'est lui qui signe les `id_token`. Il n'y
a donc plus de JWT à renouveler à la main avant chaque tir — Gatling se logue.

**Aucun état.** L'identité est tirée au hasard dans le pool à l'autorisation,
puis **encodée dans le `code`** rendu à `connect`, que le `/token` décode. Rien
n'est partagé entre les workers uvicorn, ce qui serait un point de
synchronisation — et un mensonge sous charge.

## Le pool d'identités

`connect` ne transmet aucun paramètre client à l'IdP (ni `login_hint`, ni
passe-plat) : **c'est donc le mock qui choisit l'identité**, pas Gatling.

Le `sub` rendu suit `{POOL_PREFIX}{i}`, avec `i` tiré dans `[0, POOL_SIZE)`.

> ⚠️ Ce `sub` doit correspondre à l'`id_authentification` d'un jeune **présent en
> base**. L'API ne crée aucun bénéficiaire FT inconnu : elle répond
> `UTILISATEUR_INEXISTANT` et le login échoue. `POOL_PREFIX` et `POOL_SIZE`
> doivent donc valoir exactement ce qu'a semé le seed.

## Lancer

```sh
make start   # venv + deps + uvicorn sur :8080
make test    # 11 tests
```

## Variables

### Du mock

| Variable | Défaut | Rôle |
|---|---|---|
| `IDP_ISSUER` | `http://127.0.0.1:8080/idp` | `iss` des `id_token`. **Doit valoir exactement `IDP_FT_JEUNE_ISSUER`** côté `connect`, sinon `openid-client` rejette le token |
| `POOL_SIZE` | `50` | Taille du pool d'identités |
| `POOL_PREFIX` | `perf-ft-` | Préfixe des `sub` |

### De `pass-emploi-connect`

En notant `{MOCK}` l'URL à laquelle `connect` joint le mock :

| Variable | Valeur |
|---|---|
| `IDP_FT_JEUNE_ISSUER` | `{MOCK}/idp` |
| `IDP_FT_JEUNE_AUTHORIZATION_URL` | `{MOCK}/idp/protocol/openid-connect/auth` |
| `IDP_FT_JEUNE_TOKEN_URL` | `{MOCK}/idp/protocol/openid-connect/token` |
| `IDP_FT_JEUNE_JWKS` | `{MOCK}/idp/protocol/openid-connect/certs` |
| `IDP_FT_JEUNE_USERINFO` | `{MOCK}/idp/protocol/openid-connect/userinfo` |
| `FT_JEUNE_API_URL` | `{MOCK}/poleemploi` |

`IDP_FT_JEUNE_CLIENT_ID` et `IDP_FT_JEUNE_CLIENT_SECRET` peuvent valoir n'importe
quoi : le mock ne les vérifie pas, il se contente de reprendre le `client_id`
comme `aud`. `IDP_FT_JEUNE_REALM` doit être **non-vide** côté `connect`
(`configuration.schema.ts` l'exige, `Joi.string().required()`), mais sa valeur
n'a pas d'importance ici : les routes du mock (FastAPI) ignorent les query
params qu'elles ne déclarent pas, `realm` y compris.

### De `pass-emploi-api`

| Variable | Valeur |
|---|---|
| `OIDC_ISSUER_URL` | **le vrai `connect-perf`** — c'est lui l'émetteur du JWT |
| `POLE_EMPLOI_API_BASE_URL` | `{MOCK}/poleemploi` |

## Diagnostic

| Symptôme | Cause probable |
|---|---|
| `connect` rejette l'`id_token` | `IDP_ISSUER` ≠ `IDP_FT_JEUNE_ISSUER` |
| Login en échec `UTILISATEUR_INEXISTANT` | Le pool ne correspond pas à ce qu'a semé le seed |
| 401 côté API après un login réussi | `OIDC_ISSUER_URL` pointe encore sur le mock au lieu de `connect-perf` |
| Toutes les requêtes frappent le même jeune | `POOL_SIZE` trop petit devant `MAX_USERS` |
