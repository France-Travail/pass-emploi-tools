from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_mail_brevo_accepte_l_envoi():
    reponse = client.post(
        "/brevo/v3/smtp/email",
        json={"to": [{"email": "perf-migr-1@perf.local"}], "templateId": 1},
    )

    assert reponse.status_code == 201
    assert "messageId" in reponse.json()
