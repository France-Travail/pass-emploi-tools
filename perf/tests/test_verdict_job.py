import json
import subprocess
import sys

from verdict_job import juger_archivage, juger_nettoyage, resume_markdown

ATTENDUS = {
    "id_population": "perf-migration",
    "population": 2000,
    "actifs": 1600,
    "echecs_mail": 20,
    "echecs_chat": 20,
    "temoins": 47,
}
CONTROLES_CONFORMES = {"jeunes_population_restants": 0, "temoins_restants": 47, "archives": 2000}


def _archivage(resultat=None, duree_totale_s=600.0, controles=None):
    return {
        "ligne": {
            "resultat": resultat
            if resultat is not None
            else {"termine": True, "nbTraites": 2000, "nbEchecs": 0, "nbEchecsMail": 20},
            "duree_totale_s": duree_totale_s,
        },
        "controles": controles or CONTROLES_CONFORMES,
    }


def _nettoyage(resultat=None):
    return {
        "ligne": {
            "resultat": resultat
            if resultat is not None
            else {"termine": True, "nbTraites": 1980, "nbEchecs": 20, "nbEchecsIdp": 0, "nbEchecsChat": 20},
            "duree_totale_s": 1800.0,
        },
        "controles": {},
    }


def _faux(constats):
    return [c.nom for c in constats if not c.ok]


def test_archivage_conforme():
    constats = juger_archivage(ATTENDUS, _archivage(), 15)

    assert constats
    assert _faux(constats) == []


def test_archivage_trop_long():
    constats = juger_archivage(ATTENDUS, _archivage(duree_totale_s=901), 15)

    assert _faux(constats) == ["duree"]


def test_ligne_absente():
    constats = juger_archivage(ATTENDUS, {"ligne": None, "controles": CONTROLES_CONFORMES}, 15)

    assert len(constats) == 1
    assert constats[0].nom == "ligne suivi_job"
    assert constats[0].observe == "absente"
    assert not constats[0].ok


def test_chaine_arretee():
    resultat = {"termine": False, "nbTraites": 500, "nbEchecs": 0, "nbEchecsMail": 5}

    constats = juger_archivage(ATTENDUS, _archivage(resultat=resultat), 15)

    assert "termine" in _faux(constats)


def test_echecs_mail_differents_de_l_injection():
    resultat = {"termine": True, "nbTraites": 2000, "nbEchecs": 0, "nbEchecsMail": 0}

    constats = juger_archivage(ATTENDUS, _archivage(resultat=resultat), 15)

    assert _faux(constats) == ["nbEchecsMail"]


def test_temoins_supprimes_par_l_archivage():
    controles = {**CONTROLES_CONFORMES, "temoins_restants": 40}

    constats = juger_archivage(ATTENDUS, _archivage(controles=controles), 15)

    assert _faux(constats) == ["temoins restants"]


def test_nettoyage_conforme():
    constats = juger_nettoyage(ATTENDUS, _nettoyage(), {"cles_population_restantes": 0})

    assert constats
    assert _faux(constats) == []


def test_nettoyage_compte_mal_les_archives_visitees():
    resultat = {"termine": True, "nbTraites": 1980, "nbEchecs": 0, "nbEchecsIdp": 0, "nbEchecsChat": 20}

    constats = juger_nettoyage(ATTENDUS, _nettoyage(resultat=resultat), {"cles_population_restantes": 0})

    assert _faux(constats) == ["nbTraites + nbEchecs"]


def test_chaine_deja_en_cours():
    constats = juger_nettoyage(
        ATTENDUS, _nettoyage(resultat={"chaineDejaEnCours": True}), {"cles_population_restantes": 0}
    )

    assert [(c.nom, c.ok) for c in constats] == [("chaine deja en cours", False)]


def test_cles_redis_restantes():
    constats = juger_nettoyage(ATTENDUS, _nettoyage(), {"cles_population_restantes": 4})

    assert _faux(constats) == ["cles Redis de la population restantes"]


def test_redis_non_mesure_ne_juge_pas():
    constats = juger_nettoyage(ATTENDUS, _nettoyage(), {})

    assert _faux(constats) == []
    assert all(c.nom != "cles Redis de la population restantes" for c in constats)


def test_resume_sans_slowlog():
    markdown = resume_markdown(
        juger_archivage(ATTENDUS, _archivage(), 15),
        juger_nettoyage(ATTENDUS, _nettoyage(), {}),
        {"keys": None},
    )

    assert "KEYS : non mesuré" in markdown


def test_resume_avec_slowlog():
    markdown = resume_markdown(
        [], [], {"keys": {"nb": 3, "p50_ms": 200, "p95_ms": 300, "max_ms": 300}}
    )

    assert "KEYS" in markdown and "300" in markdown


def test_cli_code_de_sortie(tmp_path):
    fichiers = {
        "attendus.json": ATTENDUS,
        "archivage.json": _archivage(controles={**CONTROLES_CONFORMES, "archives": 1999}),
        "nettoyage.json": _nettoyage(),
        "redis-bilan.json": {"cles_population_restantes": 0, "keys": None, "dbsize": 1000000},
    }
    for nom, contenu in fichiers.items():
        (tmp_path / nom).write_text(json.dumps(contenu))

    resultat = subprocess.run(
        [
            sys.executable,
            "job/verdict_job.py",
            *(str(tmp_path / nom) for nom in fichiers),
            "15",
        ],
        capture_output=True,
        text=True,
    )

    assert resultat.returncode == 1
    assert "archives" in resultat.stdout


def test_cli_conforme_et_fichier_redis_vide(tmp_path):
    fichiers = {
        "attendus.json": json.dumps(ATTENDUS),
        "archivage.json": json.dumps(_archivage()),
        "nettoyage.json": json.dumps(_nettoyage()),
        "redis-bilan.json": "",
    }
    for nom, contenu in fichiers.items():
        (tmp_path / nom).write_text(contenu)

    resultat = subprocess.run(
        [sys.executable, "job/verdict_job.py", *(str(tmp_path / nom) for nom in fichiers), "15"],
        capture_output=True,
        text=True,
    )

    assert resultat.returncode == 0, resultat.stderr
