**Investiguer**

1. **Mémoire** : seule limite, celle du conteneur. Pas de `maxmemory`, politique `noeviction` : plein, le conteneur est tué. Le **swap** qui monte est le signal d'alarme.
2. **File Bull qui grossit** (`wait`, `delayed`, `completed`) : jobs non consommés, ou jamais purgés.
3. **Compteurs cumulés** (connexions refusées, clés évincées ou expirées) : se lisent à la pente ; une chute signale un redémarrage.
