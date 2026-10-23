"""Compare les p95/p99 du login avant et pendant le nettoyage des archives.

  comparer_logins.py <rapport-reference> <rapport-pendant>

Chaque argument est un répertoire de rapport Gatling (contenant un index.html).
Sans assertion : sans débit de nuit connu, un seuil ne jugerait rien.
"""

import importlib.util
import pathlib
import sys

_RESUME_TIR = pathlib.Path(__file__).resolve().parent.parent / "resume-tir.py"


def _ecart(reference: str, pendant: str) -> str:
    try:
        return f"{int(pendant) - int(reference):+d}"
    except (TypeError, ValueError):
        return "?"


def comparer(reference: list[dict], pendant: list[dict]) -> str:
    par_nom_reference = {ligne["nom"]: ligne for ligne in reference}
    par_nom_pendant = {ligne["nom"]: ligne for ligne in pendant}
    noms = list(par_nom_reference) + [nom for nom in par_nom_pendant if nom not in par_nom_reference]

    lignes = [
        "### Logins avant et pendant le nettoyage (ms)",
        "",
        "| Étape | p95 avant | p95 pendant | écart | p99 avant | p99 pendant | écart |",
        "|---|---|---|---|---|---|---|",
    ]
    for nom in noms:
        avant = par_nom_reference.get(nom, {})
        apres = par_nom_pendant.get(nom, {})
        cellules = [nom]
        for centile in ("p95", "p99"):
            valeur_avant, valeur_apres = avant.get(centile, "?"), apres.get(centile, "?")
            cellules += [valeur_avant, valeur_apres, _ecart(valeur_avant, valeur_apres)]
        lignes.append("| " + " | ".join(cellules) + " |")
    return "\n".join(lignes) + "\n"


def _statistiques(repertoire: str) -> list[dict]:
    spec = importlib.util.spec_from_file_location("resume_tir", _RESUME_TIR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    index = next(pathlib.Path(repertoire).glob("**/index.html"), None)
    return module.statistiques(index) if index else []


def main(argv: list[str]) -> None:
    print(comparer(_statistiques(argv[0]), _statistiques(argv[1])))


if __name__ == "__main__":
    main(sys.argv[1:])
