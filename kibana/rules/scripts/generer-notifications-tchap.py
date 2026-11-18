#!/usr/bin/env python3
"""Génère les notifications Tchap des règles Kibana : les Workflows de salon
workflows/tchap/generated/tchap-<salon>.console et les rapports quotidiens des jobs, à coller
dans Kibana → Dev Tools. Enchaîne les 3 étapes de notifications/ : 1-extraire.py (commune aux
canaux), puis tchap/2-transformer.py et tchap/3-charger.py.
À lancer après generer-regles.py, dont il lit les règles générées.

Usage : python3 -I generer-notifications-tchap.py [--sans-rapports-jobs]
  --sans-rapports-jobs : ne régénère pas les rapports des jobs (pas besoin de pass-emploi-api ;
  utilisé par les tests).
"""
import importlib.util, os, sys

chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'notifications', 'tchap', '3-charger.py')
spec = importlib.util.spec_from_file_location('charger', chemin)
etape = importlib.util.module_from_spec(spec)
spec.loader.exec_module(etape)

if __name__ == '__main__':
    etape.charger(sys.argv[1:])
