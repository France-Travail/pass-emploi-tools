# Lot 1 — `mock-externes` : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformer `perf/api-simulator` en `perf/mock-externes` : une brique qui se fait passer pour l'IdP France Travail et les APIs partenaires FT, et pour rien d'autre — de sorte que `connect` et `api` restent réels dans le tir.

**Architecture:** FastAPI, sans état. Le mock génère sa paire de clés RSA au démarrage et signe lui-même les `id_token`. L'identité est tirée au hasard dans un pool à chaque autorisation, puis **encodée dans le `code`** rendu à `connect` : aucun état partagé entre workers.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, `pyjwt[crypto]`, pytest + httpx pour les tests.

**Spec:** `docs/superpowers/specs/2026-09-01-harnais-tir-perf-design.md` (§4)

## Global Constraints

- **Sans état.** Le mock tourne en plusieurs workers uvicorn ; aucune variable globale mutable, aucun cache partagé. Tout ce qui doit survivre entre `/authorize` et `/token` transite par le `code`.
- **Aucune clé d'un environnement réel.** Les clés sont générées au démarrage. Aucune clé publique copiée depuis un Keycloak ou un `connect` existant ne doit subsister dans le code.
- **Le mock ne se substitue jamais à `connect` ni à `api`.** Il n'expose aucune route qui imite l'un des deux.
- Le pool est défini par **convention partagée** avec le seed : `POOL_SIZE` et `POOL_PREFIX`, rien d'autre.
- Python : jamais d'installation globale. Tout passe par le venv du `Makefile`.

## Ce que `connect` attend — contrat vérifié

Relevé dans `pass-emploi-connect` le 2026-09-01 :

| Appel | Origine | Attendu |
|---|---|---|
| `GET {AUTHORIZATION_URL}` | `idp.service.ts:111` | Redirection 302 vers `redirect_uri` avec `code` et `state` |
| `POST {TOKEN_URL}` | `idp.service.ts:170` | `access_token`, `id_token` signé (`nonce` échoé, `aud` = `client_id`, `iss` = issuer configuré), `refresh_token` |
| `GET {JWKS}` | validation de l'`id_token` | Clé publique RSA au format JWK |
| `GET {USERINFO}` | `idp.service.ts:190` | `sub`, `preferred_username` |
| `GET {FT_API}/peconnect-coordonnees/v1/coordonnees` | `idp.service.ts:375` | `nom`, `prenom`, `email` — **c'est ici que viennent les coordonnées, pas du userinfo** |
| `GET {FT_API}/peconnect-statut/v1/statut` | `idp.service.ts:222` | Filet : appelé seulement si `putUser` répond `UTILISATEUR_INEXISTANT` |

Le `sub` rendu doit correspondre au `id_authentification` d'un jeune semé
(`update-utilisateur.command.handler.ts:417-443` — aucune auto-création).

---

### Task 1 : Renommage et socle testable

**Files:**
- Rename: `perf/api-simulator/` → `perf/mock-externes/`
- Modify: `perf/mock-externes/requirements.txt`, `perf/mock-externes/Makefile`
- Create: `perf/mock-externes/requirements-dev.txt`, `perf/mock-externes/tests/test_sante.py`

**Interfaces:**
- Produces: `app` (instance FastAPI) importable par les tests ; cible `make test`.

- [ ] **Step 1 : Renommer le dossier**

```bash
cd perf && git mv api-simulator mock-externes
```

- [ ] **Step 2 : Ajouter les dépendances**

`requirements.txt` :

```
fastapi
uvicorn
pyjwt[crypto]
```

`requirements-dev.txt` :

```
-r requirements.txt
pytest
httpx
```

- [ ] **Step 3 : Écrire le premier test**

`tests/test_sante.py` :

```python
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_jwks_expose_une_cle_rsa():
    reponse = client.get("/idp/protocol/openid-connect/certs")

    assert reponse.status_code == 200
    cles = reponse.json()["keys"]
    assert len(cles) == 1
    assert cles[0]["kty"] == "RSA"
    assert cles[0]["use"] == "sig"
```

- [ ] **Step 4 : Lancer le test, vérifier qu'il échoue**

Run : `cd perf/mock-externes && make test`
Expected : FAIL — la route `/idp/protocol/openid-connect/certs` n'existe pas (404).

- [ ] **Step 5 : Ajouter la cible `test` au Makefile**

```makefile
test: install-dev
	. $(VENV_DIR)/bin/activate && python -m pytest tests -v

install-dev:
	python3 -m venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate && pip install -q --upgrade pip
	. $(VENV_DIR)/bin/activate && pip install -q -r requirements-dev.txt
```

- [ ] **Step 6 : Commit**

```bash
git add perf/mock-externes && git commit -m "refactor(perf): renomme api-simulator en mock-externes"
```

---

### Task 2 : IdP France Travail

**Files:**
- Modify: `perf/mock-externes/app.py`
- Create: `perf/mock-externes/tests/test_idp.py`

**Interfaces:**
- Consumes: `app` de la Task 1.
- Produces: quatre routes sous `/idp` — `.../auth`, `.../token`, `.../certs`, `.../userinfo` ; fonction `identite_du_pool()` retournant un `sub` de la forme `{POOL_PREFIX}{i}`.

**Mécanisme sans état :** `/auth` tire un `sub`, l'encode avec le `nonce` reçu
dans le `code` (`base64url(json)`), et redirige. `/token` décode le `code` pour
reconstruire `sub` et `nonce`. Aucun état serveur.

- [ ] **Step 1 : Écrire les tests**

`tests/test_idp.py` — le test central est le parcours complet, parce que c'est
la seule chose qui prouve que `connect` passera :

```python
import base64
import json
from urllib.parse import parse_qs, urlparse

import jwt
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

CLIENT_ID = "pass-emploi-perf"


def test_authorize_redirige_avec_code_et_state():
    reponse = client.get(
        "/idp/protocol/openid-connect/auth",
        params={
            "client_id": CLIENT_ID,
            "redirect_uri": "http://connect/callback",
            "response_type": "code",
            "scope": "openid",
            "state": "etat-opaque",
            "nonce": "interaction-42",
        },
        follow_redirects=False,
    )

    assert reponse.status_code == 302
    query = parse_qs(urlparse(reponse.headers["location"]).query)
    assert query["state"] == ["etat-opaque"]
    assert query["code"]


def test_id_token_porte_le_nonce_et_un_sub_du_pool():
    code = _obtenir_code(nonce="interaction-42")

    reponse = client.post(
        "/idp/protocol/openid-connect/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": "peu-importe",
            "redirect_uri": "http://connect/callback",
        },
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["token_type"] == "Bearer"
    assert corps["refresh_token"]

    claims = jwt.decode(corps["id_token"], options={"verify_signature": False})
    assert claims["nonce"] == "interaction-42"
    assert claims["aud"] == CLIENT_ID
    assert claims["sub"].startswith("perf-ft-")


def test_id_token_est_verifiable_avec_la_cle_publique_du_jwks():
    """Le vrai test : openid-client fera exactement ça côté connect."""
    jwks = client.get("/idp/protocol/openid-connect/certs").json()
    id_token = client.post(
        "/idp/protocol/openid-connect/token",
        data={
            "grant_type": "authorization_code",
            "code": _obtenir_code(nonce="n"),
            "client_id": CLIENT_ID,
            "client_secret": "peu-importe",
            "redirect_uri": "http://connect/callback",
        },
    ).json()["id_token"]

    cle = jwt.PyJWK(jwks["keys"][0]).key
    claims = jwt.decode(id_token, cle, algorithms=["RS256"], audience=CLIENT_ID)

    assert claims["sub"].startswith("perf-ft-")


def test_le_pool_ne_rend_pas_toujours_la_meme_identite():
    subs = {_sub_depuis_code(_obtenir_code(nonce="n")) for _ in range(40)}

    assert len(subs) > 1


def test_userinfo_rend_le_sub_encode_dans_le_token():
    ...  # renseigné à l'implémentation, cf. Step 3


def _obtenir_code(nonce: str) -> str:
    reponse = client.get(
        "/idp/protocol/openid-connect/auth",
        params={
            "client_id": CLIENT_ID,
            "redirect_uri": "http://connect/callback",
            "response_type": "code",
            "scope": "openid",
            "state": "etat",
            "nonce": nonce,
        },
        follow_redirects=False,
    )
    return parse_qs(urlparse(reponse.headers["location"]).query)["code"][0]


def _sub_depuis_code(code: str) -> str:
    padding = "=" * (-len(code) % 4)
    return json.loads(base64.urlsafe_b64decode(code + padding))["sub"]
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `make test`
Expected : FAIL sur les routes absentes.

- [ ] **Step 3 : Implémenter**

Points non négociables :

- Clé RSA 2048 générée **au chargement du module**, `kid` dérivé de la clé.
- `iss` = variable `IDP_ISSUER`, qui doit valoir exactement `IDP_FT_JEUNE_ISSUER`
  côté `connect` — sinon `openid-client` rejette l'`id_token`.
- `aud` = `client_id` reçu ; `exp` à +1 h ; `iat` et `auth_time` à maintenant.
- `/userinfo` lit le `sub` depuis le Bearer présenté (l'`access_token` porte le
  même encodage que le `code`).
- Le `sub` suit `{POOL_PREFIX}{i}` avec `i` tiré dans `[0, POOL_SIZE)`.

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `make test`
Expected : PASS.

- [ ] **Step 5 : Commit**

```bash
git commit -am "feat(perf): mock-externes sert l'IdP France Travail"
```

---

### Task 3 : APIs partenaires France Travail

**Files:**
- Modify: `perf/mock-externes/app.py`
- Create: `perf/mock-externes/tests/test_partenaires.py`

**Interfaces:**
- Consumes: rien de la Task 2 (routes indépendantes).
- Produces: `/poleemploi/peconnect-coordonnees/v1/coordonnees` et `/poleemploi/peconnect-statut/v1/statut`, en plus des trois routes existantes.

Les coordonnées doivent être **dérivées du `sub`** porté par le Bearer : un nom
constant pour tout le pool masquerait un bug d'appariement d'identité.

- [ ] **Step 1 : Écrire les tests**

```python
def test_coordonnees_derivees_du_sub_du_porteur():
    entetes = {"Authorization": f"Bearer {_access_token_pour('perf-ft-7')}"}

    reponse = client.get(
        "/poleemploi/peconnect-coordonnees/v1/coordonnees", headers=entetes
    )

    assert reponse.status_code == 200
    assert reponse.json()["email"] == "perf-ft-7@perf.local"


def test_statut_rend_un_demandeur_emploi():
    reponse = client.get("/poleemploi/peconnect-statut/v1/statut")

    assert reponse.json()["codeStatutIndividu"] == "1"
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `make test`
Expected : FAIL — routes absentes.

- [ ] **Step 3 : Implémenter les deux routes, conserver les trois existantes**

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `make test`
Expected : PASS, tous fichiers de test confondus.

- [ ] **Step 5 : Commit**

```bash
git commit -am "feat(perf): mock-externes sert les APIs partenaires FT du login"
```

---

### Task 4 : Documentation de branchement

**Files:**
- Modify: `perf/mock-externes/README.md`
- Modify: `perf/README.md`

Le `README` actuel décrit un mock de l'émetteur du JWT — description devenue
fausse. Il doit décrire les deux clients (`connect` et `api`), les variables des
deux côtés, et **la disparition du `USER_TOKEN`** : Gatling se loguera.

- [ ] **Step 1 : Réécrire `mock-externes/README.md`**

Doit contenir le tableau des variables :

| Composant | Variable | Valeur |
|---|---|---|
| `connect` | `IDP_FT_JEUNE_ISSUER` | `{MOCK}/idp` |
| `connect` | `IDP_FT_JEUNE_AUTHORIZATION_URL` | `{MOCK}/idp/protocol/openid-connect/auth` |
| `connect` | `IDP_FT_JEUNE_TOKEN_URL` | `{MOCK}/idp/protocol/openid-connect/token` |
| `connect` | `IDP_FT_JEUNE_JWKS` | `{MOCK}/idp/protocol/openid-connect/certs` |
| `connect` | `IDP_FT_JEUNE_USERINFO` | `{MOCK}/idp/protocol/openid-connect/userinfo` |
| `connect` | `FRANCE_TRAVAIL_API_URL` | `{MOCK}/poleemploi` |
| `api` | `OIDC_ISSUER_URL` | **le vrai `connect-perf`** |
| `api` | `POLE_EMPLOI_API_BASE_URL` | `{MOCK}/poleemploi` |

- [ ] **Step 2 : Mettre à jour `perf/README.md`**

Le schéma de flux et la section « Prérequis pour tirer » décrivent l'ancienne
architecture (simulateur à la place de l'émetteur, `USER_TOKEN` obligatoire).
Les corriger.

- [ ] **Step 3 : Commit**

```bash
git commit -am "docs(perf): branchement de mock-externes sur connect et api"
```

## Point à lever pendant l'implémentation

Le nom exact des variables d'environnement des IdP dans `connect` est déduit de
`configuration.ts` (`IDP_FT_JEUNE_*`). À confirmer contre le `.environment.template`
de `pass-emploi-connect` avant de figer le README de la Task 4.
