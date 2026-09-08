#!/usr/bin/env python3
"""Rend le résumé markdown d'un tir pour $GITHUB_STEP_SUMMARY.

Les statistiques par requête n'existent que dans le rapport HTML de Gatling :
la console ne donne que les agrégats globaux, et `simulation.log` est exclu de
l'archive. On lit donc index.html, dont la table de stats a une structure
stable (une ligne `<tr id="req_…" data-parent="ROOT">` par requête, colonnes
`col-2` à `col-14`) — à revérifier lors d'une montée de version de Gatling.

Usage : resume-tir.py <metadonnees.json> <sortie-tir.txt> <etat-scalingo.txt> <racine des rapports>
"""

import html
import json
import pathlib
import re
import sys

COLONNES = {
    "total": 2, "ok": 3, "ko": 4, "pct_ko": 5,
    "min": 7, "p50": 8, "p75": 9, "p95": 10, "p99": 11, "max": 12, "moyenne": 13,
}


def statistiques(index_html):
    """[{nom, total, ko, p50, p95, …}] — la ligne d'agrégat en tête."""
    contenu = index_html.read_text(encoding="utf-8", errors="replace")
    lignes = []
    for bloc in re.split(r'<tr id="(?:ROOT|req_[^"]*)"', contenu)[1:]:
        bloc = bloc.split("</tr>")[0]
        nom = re.search(r'class="ellipsed-name">([^<]*)<', bloc)
        cellules = {
            int(numero): valeur
            for numero, valeur in re.findall(r'col-(\d+)">([^<]*)<', bloc)
        }
        if not cellules.get(2):
            continue
        ligne = {"nom": html.unescape(nom.group(1)) if nom else "Toutes requêtes"}
        ligne.update({cle: cellules.get(col, "?") for cle, col in COLONNES.items()})
        lignes.append(ligne)
    return lignes


def assertions(sortie_tir):
    motif = re.compile(r"^.+: .*is (?:less|greater) than .*: (?:true|false).*$", re.M)
    return motif.findall(sortie_tir.read_text(encoding="utf-8", errors="replace"))


def conteneurs(etat_scalingo):
    """{app: (taille, statut)} — depuis les tables `scalingo ps` déjà collectées."""
    etat, app = {}, None
    for ligne in etat_scalingo.read_text(encoding="utf-8", errors="replace").splitlines():
        if ligne.startswith("### "):
            app = ligne[4:].strip()
            etat.setdefault(app, ("—", "éteint"))
        elif app and "│" in ligne:
            champs = [c.strip() for c in ligne.split("│")[1:-1]]
            if len(champs) >= 4 and champs[0].startswith("web-"):
                etat[app] = (champs[3], champs[1])
    return etat


def tableau(entetes, lignes):
    rendu = ["| " + " | ".join(entetes) + " |", "|" + "---|" * len(entetes)]
    rendu += ["| " + " | ".join(str(c) for c in ligne) + " |" for ligne in lignes]
    return rendu


def main():
    meta_path, sortie_path, etat_path, racine = (pathlib.Path(a) for a in sys.argv[1:5])
    meta = json.loads(meta_path.read_text())
    sortie = ["## Tir de performance — `%s`" % meta["simulation"], ""]

    charge, seuils, donnees = meta["charge"], meta["seuils"], meta["donnees"]
    sortie += tableau(["Paramètre", "Valeur"], [
        ["Verdict du job", meta["verdict"]],
        ["Fenêtre", "`%s` → `%s`" % (meta["fenetre"]["debut"], meta["fenetre"]["fin"])],
        ["Charge", "%s parcours/s, ramp=%ss, hold=%ss"
                   % (charge["users_per_sec"], charge["ramp_s"], charge["hold_s"])],
        ["Pool", "%s identités, préfixe `%s`" % (donnees["pool_size"], donnees["pool_prefix"])],
        ["SLO", "p99 < %s ms par requête, réussite > %s %%"
                % (seuils["p99_ms"], seuils["reussite_pct"])],
    ]) + [""]

    lignes_assertion = assertions(sortie_path) if sortie_path.exists() else []
    rapports = sorted(racine.glob("*/index.html")) if racine.is_dir() else []
    if rapports:
        lignes = statistiques(rapports[-1])
        globales, etapes = lignes[0], lignes[1:]
        # max() sur un p99 non numérique ("?") planterait le résumé d'un tir
        # dont on veut justement lire les autres lignes.
        chiffrables = [e for e in etapes if e["p99"].isdigit()]
        plus_lente = max(chiffrables, key=lambda e: int(e["p99"]), default=None)
        en_echec = [e["nom"] for e in etapes if e["ko"] not in ("0", "?")]

        echouees = [l for l in lignes_assertion if ": false" in l or "false (" in l]
        synthese = [
            ["Requêtes", "%s (%s KO)" % (globales["total"], globales["ko"])],
            ["Erreurs (global)", "%s %%" % globales["pct_ko"]],
        ]
        if plus_lente:
            synthese.append(["Étape la plus lente (p99)",
                             "%s — %s ms" % (plus_lente["nom"], plus_lente["p99"])])
        synthese.append(["Étapes en KO", ", ".join(en_echec) if en_echec else "aucune"])
        synthese.append(["Assertions en échec", len(echouees) if echouees else "aucune"])

        sortie += ["### Résultat", ""] + tableau(["Indicateur", "Valeur"], synthese) + [""]
        sortie += ["### Détail par étape", ""] + tableau(
            ["Étape", "Requêtes", "KO", "p50", "p95", "p99", "max", "moyenne"],
            [[e["nom"], e["total"], e["ko"], e["p50"], e["p95"], e["p99"], e["max"], e["moyenne"]]
             for e in lignes],
        ) + [""]
    else:
        sortie += ["⚠️ Pas de rapport HTML : le tir a échoué avant la fin de Gatling.", ""]

    sortie += ["### Assertions Gatling", "", "```"]
    sortie += lignes_assertion or ["(aucune assertion — le tir a échoué avant la fin)"]
    sortie += ["```", ""]

    if etat_path.exists():
        sortie += ["### Contexte", ""] + tableau(
            ["App", "Conteneur", "Statut"],
            [[app, taille, statut] for app, (taille, statut) in conteneurs(etat_path).items()],
        ) + [""]

    sortie += [
        "**Limite** : image de base PostgreSQL — %s. Sans fond de charge, ces "
        "chiffres valident la chaîne, pas un p95 de production." % donnees["image_de_base"],
        "",
        "Rapport HTML complet dans l'artefact du run : décompresser, puis ouvrir "
        "`perf/build/reports/gatling/<horodatage>/index.html`.",
    ]
    print("\n".join(sortie))


if __name__ == "__main__":
    main()
