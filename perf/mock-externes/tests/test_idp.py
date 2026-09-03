import base64
import json
from urllib.parse import parse_qs, urlparse

import jwt
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

CLIENT_ID = "pass-emploi-perf"
REDIRECT_URI = "http://connect/callback"


def test_authorize_redirige_avec_code_et_state():
    reponse = client.get(
        "/idp/protocol/openid-connect/auth",
        params={
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
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

    corps = _echanger_le_code(code)

    assert corps["token_type"] == "Bearer"
    assert corps["refresh_token"]
    claims = jwt.decode(corps["id_token"], options={"verify_signature": False})
    assert claims["nonce"] == "interaction-42"
    assert claims["aud"] == CLIENT_ID
    assert claims["sub"].startswith("perf-ft-")


def test_id_token_est_verifiable_avec_la_cle_publique_du_jwks():
    """Le vrai test : openid-client fera exactement ça côté connect."""
    jwks = client.get("/idp/protocol/openid-connect/certs").json()
    id_token = _echanger_le_code(_obtenir_code(nonce="n"))["id_token"]

    cle = jwt.PyJWK(jwks["keys"][0]).key
    claims = jwt.decode(id_token, cle, algorithms=["RS256"], audience=CLIENT_ID)

    assert claims["sub"].startswith("perf-ft-")


def test_le_pool_ne_rend_pas_toujours_la_meme_identite():
    subs = {_sub_depuis_jeton(_obtenir_code(nonce="n")) for _ in range(40)}

    assert len(subs) > 1


def test_userinfo_rend_le_sub_porte_par_l_access_token():
    corps = _echanger_le_code(_obtenir_code(nonce="n"))
    sub_attendu = _sub_depuis_jeton(corps["access_token"])

    reponse = client.get(
        "/idp/protocol/openid-connect/userinfo",
        headers={"Authorization": f"Bearer {corps['access_token']}"},
    )

    assert reponse.status_code == 200
    assert reponse.json() == {
        "sub": sub_attendu,
        "preferred_username": sub_attendu,
    }


def test_le_refresh_token_conserve_l_identite():
    corps = _echanger_le_code(_obtenir_code(nonce="n"))
    sub_initial = _sub_depuis_jeton(corps["access_token"])

    rafraichi = client.post(
        "/idp/protocol/openid-connect/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": corps["refresh_token"],
            "client_id": CLIENT_ID,
            "client_secret": "peu-importe",
        },
    ).json()

    assert _sub_depuis_jeton(rafraichi["access_token"]) == sub_initial


def _obtenir_code(nonce: str) -> str:
    reponse = client.get(
        "/idp/protocol/openid-connect/auth",
        params={
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "openid",
            "state": "etat",
            "nonce": nonce,
        },
        follow_redirects=False,
    )
    return parse_qs(urlparse(reponse.headers["location"]).query)["code"][0]


def _echanger_le_code(code: str) -> dict:
    reponse = client.post(
        "/idp/protocol/openid-connect/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": "peu-importe",
            "redirect_uri": REDIRECT_URI,
        },
    )
    assert reponse.status_code == 200
    return reponse.json()


def _sub_depuis_jeton(jeton: str) -> str:
    padding = "=" * (-len(jeton) % 4)
    return json.loads(base64.urlsafe_b64decode(jeton + padding))["sub"]
