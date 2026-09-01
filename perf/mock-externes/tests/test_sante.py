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
