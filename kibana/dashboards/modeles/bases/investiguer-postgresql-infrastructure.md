**Investiguer : l'infrastructure**

1. **Mémoire à 100 % la nuit** : le cache des sauvegardes et exports, normal. Le signal d'alarme est le **swap** qui monte.
2. **Connexions** : près du max du plan, l'api ne peut plus en ouvrir. Si celles qui exécutent une requête grimpent alors que le total reste plat, les requêtes s'empilent : chercher lesquelles dans les tableaux plus bas.
3. **Transaction longue ou sessions en attente de verrou** : une transaction ouverte bloque le vacuum et peut bloquer les écritures.
4. **Graphes vides** : regarder « Erreurs de collecte » (mot de passe, certificat, réseau) avant de conclure à une base sans activité.
