#!/usr/bin/env python3
"""Structure le contexte d'infrastructure d'un tir, pour le versionner.

`metadonnees.json` est le seul fichier structuré d'un tir, donc le seul
candidat à un journal versionné (docs/perf/README.md, sous-chantier harnais).
Un p99 ne se compare d'un tir à l'autre que si l'on sait sur quoi il a été
mesuré : taille des conteneurs, SHA déployés, plans des addons. Ce module
convertit les tables du CLI Scalingo, déjà collectées en brut, en JSON.

Les tables sont lues via leur ligne d'en-tête plutôt qu'à coup d'index de
colonne : le CLI peut en ajouter une sans casser la lecture.

Usage : infra_tir.py <etat-scalingo.txt> <metadonnees.json>
        (fusionne la clé "infrastructure" dans les métadonnées)
"""

import json
import pathlib
import sys


def _tables(lignes):
    """[(en-têtes, [ligne, …]), …] pour chaque table encadrée du bloc."""
    tables, entetes, corps, attend_entete = [], None, [], False
    for ligne in lignes:
        if ligne.startswith("┌"):
            if entetes:
                tables.append((entetes, corps))
            entetes, corps, attend_entete = None, [], True
        elif ligne.startswith("│"):
            champs = [c.strip() for c in ligne.split("│")[1:-1]]
            if attend_entete:
                entetes, attend_entete = champs, False
            elif entetes:
                corps.append(dict(zip(entetes, champs)))
    if entetes:
        tables.append((entetes, corps))
    return tables


def lire(chemin):
    """Le contexte d'infra d'un tir : par app, conteneurs, déploiement, addons."""
    infra, section = {}, None
    blocs = {}
    for ligne in pathlib.Path(chemin).read_text(encoding="utf-8", errors="replace").splitlines():
        if ligne.startswith("### "):
            section = ligne[4:].strip()
            blocs[section] = []
        elif section is not None:
            blocs[section].append(ligne)

    for section, lignes in blocs.items():
        cible = infra.setdefault(section.replace("addons ", ""), {})
        for entetes, corps in _tables(lignes):
            for entree in corps:
                if entree.get("NAME", "").startswith("web-"):
                    cible["conteneur"] = entree.get("SIZE")
                    cible["statut"] = entree.get("STATUS")
                elif "GIT REF" in entetes and entree.get("GIT REF"):
                    cible.setdefault("deploiement", {
                        "git_ref": entree["GIT REF"],
                        "date": entree.get("DATE"),
                        "statut": entree.get("STATUS"),
                    })
                elif "PLAN" in entetes:
                    cible.setdefault("addons", []).append(
                        {"addon": entree.get("ADDON"), "plan": entree.get("PLAN")}
                    )
        cible.setdefault("statut", "éteint")
    return infra


def main():
    etat, metadonnees = (pathlib.Path(a) for a in sys.argv[1:3])
    meta = json.loads(metadonnees.read_text())
    meta["infrastructure"] = lire(etat)
    metadonnees.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
