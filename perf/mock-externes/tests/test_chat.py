from datetime import datetime

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_messages_du_chat_au_format_archive():
    reponse = client.get("/chat/perf-migr-000003/messages")

    assert reponse.status_code == 200
    messages = reponse.json()
    assert len(messages) == 20
    for message in messages:
        assert set(message) == {"contenu", "date", "envoyePar", "type"}
        assert message["type"] == "MESSAGE"
        assert message["envoyePar"] in {"conseiller", "jeune"}
        datetime.fromisoformat(message["date"])


def test_messages_deterministes():
    premiere = client.get("/chat/perf-migr-000003/messages").json()
    seconde = client.get("/chat/perf-migr-000003/messages").json()

    assert isinstance(premiere, list) and premiere
    assert premiere == seconde


def test_suppression_du_chat():
    reponse = client.delete("/chat/perf-migr-000003")

    assert reponse.status_code == 204


def test_chat_marque_echoue_en_lecture_et_en_suppression():
    id_jeune = "perf-migr-000000-echec-chat"

    assert client.get(f"/chat/{id_jeune}/messages").status_code == 500
    assert client.delete(f"/chat/{id_jeune}").status_code == 500
