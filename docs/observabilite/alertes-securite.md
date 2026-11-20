# Alertes de sécurité

Les alertes sur les **vulnérabilités des dépendances** de nos repos (les CVE
remontées par Dependabot, que le workflow GitHub Actions
[`security-alerts.yml`](../../.github/workflows/security-alerts.yml) envoie
dans `logs-alertes-github-default`) et sur une **suspicion d'attaque par déni
de service**, lue dans les alertes de métriques Scalingo (cf.
[collecte par webhook](infra/collecte/webhooks/README.md)) : aucune des deux ne
dépend des logs des apps. Seule la **limite de débit déclenchée** (S3) les lit.

Liste, gravités, sources et salons : [catalogue des alertes](catalogue-alertes.md) ;
cette page en donne le pourquoi et le calibrage.

## S1 — CVE high ou critical ouverte

**Objectif** : qu'aucune CVE high ou critical ne reste ouverte sans être vue.

`security-alerts.yml` renvoie **à chaque passage** toutes les CVE encore
ouvertes : S1 les notifie donc à chaque passage, une ligne par CVE (repo, CVE,
paquet, sévérité, résumé, lien vers l'alerte Dependabot ; le nom du repo mène à
la page de ses alertes, `labels.dependabot_url` posé par le pipeline). Chaque exécution ne compte que les documents
arrivés depuis la précédente (`excludeHitsFromPreviousRun`) : un passage = une
notification.

Liens vers Dependabot : dans le message, celui du repo de chaque CVE, sur son
nom ; une règle ne sait pas choisir ses liens selon les CVE qu'elle liste, donc
l'Investigation guide, qui ne voit pas les CVE, garde ceux des 3 repos.

## S2a / S2b — Suspicion d'attaque DDoS

**Objectif** : désigner l'app attaquée dès les premières minutes, même quand le
log drain et Logstash ont décroché. Le 23/10/2026, 3 IP ont envoyé à connect
27 400 requêtes par minute et 9 800 erreurs 5xx en 5 min, et les logs ont
disparu pendant 25 h ; le même scénario, d'une seule IP, était passé inaperçu le
21/10.

Une règle ES|QL sur les alertes de métriques Scalingo ([collecte par webhook](infra/collecte/webhooks/README.md)) :
pour chaque app, le dernier événement de ses alertes `Requests per Minute` et
`5xx Errors` ; elle sonne si les deux sont des dépassements, à moins de 10 min
d'intervalle. Fenêtre de 45 min : au-delà du rappel de 30 min des alertes, une
alerte toujours dépassée y garde un événement. Le RPM seul (un pic légitime qui
passe) ne la déclenche pas ; rejouée sur les 30 jours d'octobre 2026 avec les
seuils retenus, elle n'aurait sonné que les 21 et 23/10, sur connect.

## S3a / S3b — Limite de débit déclenchée

**Objectif** : savoir dès qu'une limite de débit de l'api ou de connect refuse
des requêtes (429), qu'il s'agisse d'un abus ou d'un seuil trop bas pour un pic
légitime. La règle ne se déclenche que sur une app où la limite est activée.

Une ligne `rate_limit_exceeded` est émise au premier refus de chaque fenêtre de
la limite, puis au 10e, au 100e… (`labels.rate_limit_palier`) : une seule ligne
suffit à déclencher. Un blocage qui dure ne renvoie pas de message à chaque
exécution : seules les nouvelles alertes sont notifiées. Limite connue : tant
qu'il reste des refus dans la fenêtre, une autre limite ou une autre app qui se
déclenche à son tour n'envoie pas de nouveau message ; la règle, dans Kibana,
montre l'état courant.

Les champs `labels.rate_limit*` sont déclarés d'avance dans le mapping
([`2-component-templates.console`](infra/stockage/logs/2-component-templates.console)) :
sans eux, la requête ES|QL échoue tant qu'aucune limite n'a refusé de requête.
