import infra_tir

ETAT = """### pass-emploi-api-perf
┌──────────┬─────────┬──────┬─────────┐
│   NAME   │ STATUS  │ SIZE │ COMMAND │
├──────────┼─────────┼──────┼─────────┤
│ web-1    │ running │ M    │         │
│ worker-1 │ running │ L    │         │
│ worker-2 │ running │ L    │         │
└──────────┴─────────┴──────┴─────────┘
### mock-externes-perf
┌───────┬─────────┬──────┬─────────┐
│ NAME  │ STATUS  │ SIZE │ COMMAND │
├───────┼─────────┼──────┼─────────┤
│ web-1 │ running │ S    │         │
└───────┴─────────┴──────┴─────────┘
"""


def _lire(tmp_path):
    chemin = tmp_path / "etat-scalingo.txt"
    chemin.write_text(ETAT, encoding="utf-8")
    return infra_tir.lire(chemin)


def test_conteneurs_web_inchanges(tmp_path):
    api = _lire(tmp_path)["pass-emploi-api-perf"]

    assert api["conteneur"] == "M"
    assert api["nb_conteneurs"] == 1


def test_conteneurs_worker(tmp_path):
    api = _lire(tmp_path)["pass-emploi-api-perf"]

    assert api["worker"] == {"conteneur": "L", "statut": "running", "nb_conteneurs": 2}


def test_app_sans_worker(tmp_path):
    assert "worker" not in _lire(tmp_path)["mock-externes-perf"]
