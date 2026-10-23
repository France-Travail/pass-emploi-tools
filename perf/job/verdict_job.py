"""Verdict du scénario job d'archivage de migration.

  verdict_job.py <attendus> <archivage> <nettoyage> <redis-bilan> <seuil_minutes> [es-stats]

Markdown sur stdout, code de sortie 1 si un constat est faux. Les logs ES ne
servent qu'au rapport, jamais au verdict.
"""

import json
import sys
from typing import NamedTuple


class Constat(NamedTuple):
    nom: str
    attendu: object
    observe: object
    ok: bool


def _constat(nom: str, attendu: object, observe: object) -> Constat:
    return Constat(nom, attendu, observe, observe == attendu)


def _resultat_ou_constat_bloquant(chaine: dict) -> tuple[dict | None, list[Constat]]:
    ligne = chaine.get("ligne")
    if ligne is None:
        return None, [Constat("ligne suivi_job", "présente", "absente", False)]
    resultat = ligne.get("resultat") or {}
    if resultat.get("chaineDejaEnCours"):
        return None, [Constat("chaine deja en cours", False, True, False)]
    return resultat, []


def juger_archivage(attendus: dict, archivage: dict, seuil_minutes: float) -> list[Constat]:
    resultat, bloquants = _resultat_ou_constat_bloquant(archivage)
    if resultat is None:
        return bloquants
    duree_s = archivage["ligne"].get("duree_totale_s")
    seuil_s = seuil_minutes * 60
    controles = archivage.get("controles") or {}
    return [
        _constat("termine", True, resultat.get("termine")),
        _constat("nbTraites", attendus["population"], resultat.get("nbTraites")),
        _constat("nbEchecs", 0, resultat.get("nbEchecs")),
        _constat("nbEchecsMail", attendus["echecs_mail"], resultat.get("nbEchecsMail")),
        Constat("duree", f"≤ {seuil_s:.0f} s", duree_s, duree_s is not None and duree_s <= seuil_s),
        _constat("jeunes de la population restants", 0, controles.get("jeunes_population_restants")),
        _constat("temoins restants", attendus["temoins"], controles.get("temoins_restants")),
        _constat("archives", attendus["population"], controles.get("archives")),
    ]


def constats_de_comptage_du_nettoyage(attendus: dict, resultat: dict) -> list[Constat]:
    # Seul endroit qui dépend du sens de nbEchecs au nettoyage (contrat C4) :
    # nbEchecs = archives avec au moins une étape en échec, nbTraites = archives
    # entièrement nettoyées. Les seuls échecs injectés sont ceux du chat.
    nb_traites = resultat.get("nbTraites")
    nb_echecs = resultat.get("nbEchecs")
    visitees = nb_traites + nb_echecs if nb_traites is not None and nb_echecs is not None else None
    return [
        _constat("nbTraites", attendus["population"] - attendus["echecs_chat"], nb_traites),
        _constat("nbTraites + nbEchecs", attendus["population"], visitees),
    ]


def juger_nettoyage(attendus: dict, nettoyage: dict, redis: dict) -> list[Constat]:
    resultat, bloquants = _resultat_ou_constat_bloquant(nettoyage)
    if resultat is None:
        return bloquants
    constats = [
        _constat("termine", True, resultat.get("termine")),
        *constats_de_comptage_du_nettoyage(attendus, resultat),
        _constat("nbEchecsIdp", 0, resultat.get("nbEchecsIdp")),
        _constat("nbEchecsChat", attendus["echecs_chat"], resultat.get("nbEchecsChat")),
    ]
    # Sans bilan Redis (one-off indisponible), on rapporte sans juger.
    if "cles_population_restantes" in redis:
        constats.append(
            _constat("cles Redis de la population restantes", 0, redis["cles_population_restantes"])
        )
    return constats


def _tableau(titre: str, constats: list[Constat]) -> list[str]:
    lignes = [f"### {titre}", "", "| Constat | Attendu | Observé | |", "|---|---|---|---|"]
    lignes += [f"| {c.nom} | {c.attendu} | {c.observe} | {'✓' if c.ok else '✗'} |" for c in constats]
    return lignes + [""]


def _duree(secondes) -> str:
    return "non mesurée" if secondes is None else f"{secondes / 60:.1f} min ({secondes:.0f} s)"


def _tableau_de_lignes(nom: str, lignes: list[dict]) -> list[str]:
    if not lignes:
        return [f"**{nom}** : aucune ligne", ""]
    colonnes = list(lignes[0])
    sortie = [f"**{nom}**", "", "| " + " | ".join(colonnes) + " |", "|" + "---|" * len(colonnes)]
    sortie += ["| " + " | ".join(str(ligne.get(c)) for c in colonnes) + " |" for ligne in lignes]
    return sortie + [""]


def resume_markdown(archivage: list[Constat], nettoyage: list[Constat], rapport: dict) -> str:
    lignes = ["## Archivage de migration", ""]
    lignes += _tableau("Archivage", archivage)
    lignes += _tableau("Nettoyage des archives", nettoyage)
    lignes += [
        "### Rapport",
        "",
        f"- Durée de l'archivage : {_duree(rapport.get('duree_archivage_s'))}",
        f"- Durée du nettoyage (sans seuil, Firestore mocké) : {_duree(rapport.get('duree_nettoyage_s'))}",
        f"- DBSIZE du Redis de connect après nettoyage : {rapport.get('dbsize', 'non mesuré')}",
    ]
    keys = rapport.get("keys")
    if keys is None:
        lignes.append("- KEYS : non mesuré")
    else:
        lignes.append(
            f"- KEYS (SLOWLOG, {keys['nb']} derniers) : p50 {keys['p50_ms']} ms,"
            f" p95 {keys['p95_ms']} ms, max {keys['max_ms']} ms"
        )
    lignes.append("")
    for nom, lignes_es in (rapport.get("es") or {}).items():
        lignes += _tableau_de_lignes(nom, lignes_es)
    return "\n".join(lignes)


def _lire_json(chemin: str | None) -> dict:
    if not chemin:
        return {}
    try:
        with open(chemin) as fichier:
            contenu = fichier.read().strip()
    except FileNotFoundError:
        return {}
    return json.loads(contenu) if contenu else {}


def main(argv: list[str]) -> int:
    chemin_attendus, chemin_archivage, chemin_nettoyage, chemin_redis, seuil = argv[:5]
    chemin_es = argv[5] if len(argv) > 5 else None

    attendus = _lire_json(chemin_attendus)
    archivage = _lire_json(chemin_archivage)
    nettoyage = _lire_json(chemin_nettoyage)
    redis = _lire_json(chemin_redis)

    constats_archivage = juger_archivage(attendus, archivage, float(seuil))
    constats_nettoyage = juger_nettoyage(attendus, nettoyage, redis)
    rapport = {
        "duree_archivage_s": (archivage.get("ligne") or {}).get("duree_totale_s"),
        "duree_nettoyage_s": (nettoyage.get("ligne") or {}).get("duree_totale_s"),
        "dbsize": redis.get("dbsize", "non mesuré"),
        "keys": redis.get("keys"),
        "es": _lire_json(chemin_es),
    }
    print(resume_markdown(constats_archivage, constats_nettoyage, rapport))
    return 0 if all(c.ok for c in constats_archivage + constats_nettoyage) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
