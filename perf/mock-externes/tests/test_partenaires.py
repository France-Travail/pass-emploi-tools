import base64
import json

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_coordonnees_derivees_du_sub_du_porteur():
    entetes = {"Authorization": f"Bearer {_access_token_pour('perf-ft-7')}"}

    reponse = client.get(
        "/poleemploi/peconnect-coordonnees/v1/coordonnees", headers=entetes
    )

    assert reponse.status_code == 200
    assert reponse.json()["email"] == "perf-ft-7@perf.local"


def test_statut_rend_un_demandeur_emploi():
    reponse = client.get("/poleemploi/peconnect-statut/v1/statut")

    assert reponse.status_code == 200
    assert reponse.json()["codeStatutIndividu"] == "1"


def test_demarches_rend_une_demarche():
    reponse = client.get("/poleemploi/peconnect-demarches/v1/demarches")

    assert reponse.status_code == 200
    assert len(reponse.json()) == 1


def test_prestations_et_agenda_rendent_du_vide():
    prestations = client.get("/poleemploi/peconnect-gerer-prestations/v1/rendez-vous")
    agenda = client.get("/poleemploi/peconnect-rendezvousagenda/v2/listerendezvous")

    assert prestations.json() == []
    assert agenda.json() == []


def _access_token_pour(sub: str) -> str:
    brut = json.dumps({"sub": sub, "nonce": ""}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(brut).decode().rstrip("=")
