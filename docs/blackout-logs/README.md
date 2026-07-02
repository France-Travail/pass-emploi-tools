# Blackouts & perte de logs — ingestion mutualisée

Résilience et scaling de la chaîne d'ingestion de logs `drain Scalingo → Logstash
mutualisé → Elastic Cloud`. **Distinct** des conventions ECS du logging applicatif
(taxonomie, `event.action`…), qui vivent dans [`../logs-ecs/`](../logs-ecs/README.md).

| Fichier | Contenu |
|---|---|
| [conventions.md](./conventions.md) | **Référence** : signatures des 2 modes de panne, garde-fous JVM/Scalingo (XL=2 Go, `JAVA_OPTS`, quarantaine drain), playbook de diagnostic, direction x10. Sert de **contexte de reprise** en session outillée. |
| [postmortem-2026-07.md](./postmortem-2026-07.md) | **Post-mortem** juin–juillet 2026 : le récit, les preuves, les fausses pistes écartées, et les **next steps pour tenir à x10**. |

**Invariant à respecter** : le log-drain Scalingo **quarantine une app 5 min** dès
**10 lignes consécutives** refusées (escalade 10/15/20 min) → un simple hoquet
Logstash = blackout de la plus grosse app (`pass-emploi-api`). Conteneur XL
Scalingo = **2 Go** → `-Xmx` ≤ ~1 Go, piloté via `JAVA_OPTS` (jamais `LS_JAVA_OPTS`).
**Lire [conventions.md](./conventions.md) avant de scaler ou de retoucher l'ingestion.**
