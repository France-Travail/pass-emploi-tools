import json
import os
import subprocess
import sys

from lire_logs import lignes, requetes, requetes_markdown

DEBUT = "2026-10-23T10:00:00Z"


def test_les_requetes_portent_les_deux_chaines_et_la_date():
    toutes = requetes("run-archivage", "run-nettoyage", DEBUT)

    assert set(toutes) == {"lots", "idp", "erreurs"}
    assert "run-archivage" in toutes["lots"] and "run-nettoyage" in toutes["lots"]
    assert "run-nettoyage" in toutes["idp"]
    assert "run-archivage" in toutes["erreurs"]
    assert all(DEBUT in requete for requete in toutes.values())


def test_les_echecs_se_comptent_sans_filtre_dans_stats():
    lots = requetes("a", "n", DEBUT)["lots"]

    assert 'CASE(event.outcome == "failure", 1, 0)' in lots
    assert "WHERE event.outcome" not in lots


def test_un_id_de_chaine_est_quote():
    lots = requetes('a"b', "n", DEBUT)["lots"]

    assert '"a\\"b"' in lots


def test_lignes_d_une_reponse_esql():
    reponse = {
        "columns": [{"name": "lots", "type": "long"}, {"name": "labels.job_type", "type": "keyword"}],
        "values": [[12, "ARCHIVER_JEUNES_MIGRATION"], [200, "NETTOYER_ARCHIVES_JEUNES"]],
    }

    assert lignes(reponse) == [
        {"lots": 12, "labels.job_type": "ARCHIVER_JEUNES_MIGRATION"},
        {"lots": 200, "labels.job_type": "NETTOYER_ARCHIVES_JEUNES"},
    ]


def test_requetes_markdown_a_coller_dans_kibana():
    markdown = requetes_markdown(requetes("a", "n", DEBUT))

    assert markdown.count("```") == 6
    assert "FROM logs-perf-default" in markdown


def test_stats_sans_es_url(tmp_path):
    archivage = tmp_path / "archivage.json"
    nettoyage = tmp_path / "nettoyage.json"
    archivage.write_text(json.dumps({"ligne": {"job_run_id": "a"}}))
    nettoyage.write_text(json.dumps({"ligne": None}))
    env = {k: v for k, v in os.environ.items() if k not in ("ES_URL", "ES_API_KEY")}

    resultat = subprocess.run(
        [sys.executable, "job/lire_logs.py", "stats", str(archivage), str(nettoyage), DEBUT],
        capture_output=True,
        text=True,
        env=env,
    )

    assert resultat.returncode == 0
    assert json.loads(resultat.stdout) == {}
    assert "ES_URL" in resultat.stderr
