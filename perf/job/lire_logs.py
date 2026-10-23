"""Durées par lot, latence IdP et erreurs du scénario job, lues dans ES.

  lire_logs.py stats    <archivage.json> <nettoyage.json> <debut>  > es-stats.json
  lire_logs.py requetes <archivage.json> <nettoyage.json> <debut>  (markdown)

`stats` lit ES_URL et ES_API_KEY dans l'environnement ; sans eux, il rend {}
et le résumé se contente des requêtes, à coller dans Kibana. Ces chiffres ne
servent qu'au rapport, jamais au verdict.
"""

import json
import os
import sys
import urllib.request

SOURCE = "logs-perf-default"


def _chaine(valeur: str) -> str:
    return json.dumps(valeur)


def requetes(job_run_id_archivage: str, job_run_id_nettoyage: str, debut: str) -> dict[str, str]:
    # Pas de COUNT(*) WHERE dans STATS : il demande une version récente d'ES.
    depuis = f"@timestamp >= TO_DATETIME({_chaine(debut)})"
    chaines = f"labels.job_run_id IN ({_chaine(job_run_id_archivage)}, {_chaine(job_run_id_nettoyage)})"
    return {
        "lots": (
            f"FROM {SOURCE}\n"
            f'| WHERE {depuis} AND event.action == "handler_executed" AND {chaines}\n'
            '| EVAL echec = CASE(event.outcome == "failure", 1, 0)\n'
            "| STATS lots = COUNT(*), lots_en_echec = SUM(echec),\n"
            "        p50_ms = PERCENTILE(event.duration, 50) / 1000000,\n"
            "        p95_ms = PERCENTILE(event.duration, 95) / 1000000,\n"
            "        max_ms = MAX(event.duration) / 1000000\n"
            "  BY labels.job_type"
        ),
        "idp": (
            f"FROM {SOURCE}\n"
            f'| WHERE {depuis} AND event.action == "external_api_call" AND log.logger == "OidcClient"\n'
            f'    AND http.request.method == "DELETE" AND labels.job_run_id == {_chaine(job_run_id_nettoyage)}\n'
            "| STATS n = COUNT(*),\n"
            "        p50_ms = PERCENTILE(event.duration, 50) / 1000000,\n"
            "        p95_ms = PERCENTILE(event.duration, 95) / 1000000,\n"
            "        p99_ms = PERCENTILE(event.duration, 99) / 1000000,\n"
            "        max_ms = MAX(event.duration) / 1000000"
        ),
        "erreurs": (
            f"FROM {SOURCE}\n"
            f'| WHERE {depuis} AND log.level == "error" AND {chaines}\n'
            "| STATS n = COUNT(*) BY labels.job_type, labels.etape"
        ),
    }


def lignes(reponse_esql: dict) -> list[dict]:
    noms = [colonne["name"] for colonne in reponse_esql.get("columns", [])]
    return [dict(zip(noms, valeurs)) for valeurs in reponse_esql.get("values", [])]


def requetes_markdown(toutes: dict[str, str]) -> str:
    blocs = ["### Requêtes ES|QL (Kibana)", ""]
    for nom, requete in toutes.items():
        blocs += [f"**{nom}**", "", "```", requete, "```", ""]
    return "\n".join(blocs)


def _interroger(url: str, cle: str, requete: str) -> dict:
    demande = urllib.request.Request(
        f"{url.rstrip('/')}/_query?format=json",
        data=json.dumps({"query": requete}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"ApiKey {cle}"},
        method="POST",
    )
    with urllib.request.urlopen(demande, timeout=60) as reponse:
        return json.load(reponse)


def _job_run_id(chemin: str) -> str:
    with open(chemin) as fichier:
        ligne = json.load(fichier).get("ligne") or {}
    return ligne.get("job_run_id") or ""


def main(argv: list[str]) -> int:
    commande, chemin_archivage, chemin_nettoyage, debut = argv[:4]
    toutes = requetes(_job_run_id(chemin_archivage), _job_run_id(chemin_nettoyage), debut)

    if commande == "requetes":
        print(requetes_markdown(toutes))
        return 0

    url, cle = os.getenv("ES_URL"), os.getenv("ES_API_KEY")
    if not url or not cle:
        print("ES_URL ou ES_API_KEY absent : stats ES non lues", file=sys.stderr)
        print("{}")
        return 0
    print(json.dumps({nom: lignes(_interroger(url, cle, requete)) for nom, requete in toutes.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
