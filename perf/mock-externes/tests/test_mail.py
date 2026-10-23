import os
import subprocess
import sys

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

ROUTE = "/brevo/v3/smtp/email"


def test_mail_accepte_un_destinataire_normal():
    reponse = client.post(
        ROUTE, json={"to": [{"email": "perf-migr-000002@perf.local"}], "templateId": 1}
    )

    assert reponse.status_code == 201
    assert "messageId" in reponse.json()


def test_mail_echoue_si_un_destinataire_porte_le_marqueur():
    reponse = client.post(
        ROUTE,
        json={
            "to": [
                {"email": "perf-migr-000002@perf.local"},
                {"email": "perf-migr-000001+echec-mail@perf.local"},
            ]
        },
    )

    assert reponse.status_code == 500


def test_mail_sans_destinataire_est_rejete():
    reponse = client.post(ROUTE, json={})

    assert reponse.status_code == 422


def test_latence_mail_lue_dans_l_environnement():
    resultat = subprocess.run(
        [sys.executable, "-c", "import app; print(app.LATENCE_MAIL_MS)"],
        capture_output=True,
        text=True,
        check=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={**os.environ, "LATENCE_MAIL_MS": "7"},
    )

    assert resultat.stdout.strip() == "7"
