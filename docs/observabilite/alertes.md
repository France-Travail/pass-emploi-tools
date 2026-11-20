# Alertes applicatives

Chaque alerte répond à **une question**. Elles sont rangées par famille, et
nommées par ce qu'elles détectent. Cette page dit quelles familles existent et
pourquoi ; la liste des règles, leur gravité, leur source et leur salon sont
dans le [catalogue des alertes](catalogue-alertes.md), généré depuis les règles.

## Gravités

Définies par **l'impact**, pas par la source.

| Gravité | Sens | On agit |
|---|---|---|
| 🚨 Critique | des utilisateurs sont touchés maintenant | dans l'heure |
| ⚠️ Avertissement | dégradation, ou cause probable d'une alerte critique | dans la journée |
| ℹ️ Info | fil d'activité | pas d'action |

## Ce que contient une alerte

- **Question, critère, gravité, salon** (cf. [salons](fonctionnement.md#les-salons)).
- **À vérifier**, trois étapes au plus, dans l'ordre où on se pose les
  questions : le fait, la cause, l'impact. Le dashboard de diagnostic d'abord,
  la session Discover en dernier.
- Des liens versionnés, repris à l'identique dans le message et le guide
  d'investigation de la règle.

## Promesse

*Des utilisateurs sont-ils empêchés de faire ce qu'ils viennent faire ?*

| Alerte | Critère |
|---|---|
| Disponibilité d'un parcours | burn rate du [SLO de disponibilité](slo.md) |
| Connexion d'un mode d'authentification | burn rate du [SLO de connexion](slo.md) |

## Vu de l'extérieur

*Ce que reçoit l'utilisateur, indépendamment de nos logs.* Ces alertes restent
un filet quand la chaîne de logs est aveugle.

| Alerte | Critère |
|---|---|
| Service injoignable | sonde Heartbeat en échec (api, web, connect), avec un message au rétablissement |
| 5xx au routeur | alerte de métrique Scalingo ; jamais critique, c'est le SLO qui porte le 🚨 |
| Certificat bientôt expiré | sonde Heartbeat |

## Diagnostic

*Où est la cause ?* Uniquement sur `log.level: error` : la ligne qui porte la
cause (cf. [qui doit lire](logs.md#loglevel--qui-doit-lire)). Ces alertes
accompagnent une alerte de promesse, ou révèlent un bug que le SLO ne voit pas
(job, traitement après la réponse).

| Alerte | Critère |
|---|---|
| Partenaire en panne | part des appels partenaires en `error`, par domaine, au-dessus d'un volume minimum |
| Erreurs applicatives | lignes `error` hors appels partenaires, par service et par famille (base de données, sinon l'`event.action`) |
| Erreurs du front | erreurs JavaScript du web conseiller (RUM) |

## Anomalies

*Un comportement a-t-il changé ?* Elles comparent un taux à **lui-même** : la
même heure des 7 jours précédents. Un parcours qui refuse 40 % des demandes
par nature ne les déclenche pas, un passage soudain à 80 % oui.

| Alerte | Critère |
|---|---|
| Refus anormaux d'un parcours | taux de 4xx du parcours, comparé à son historique |
| Refus partenaire anormaux | taux de `failure` par domaine **et** par status, comparé à son historique |

Grouper par status isole un signal qui serait noyé dans le taux global : un
pic de 401 (nos identifiants ont expiré) au milieu des 404 métier d'un
partenaire.

## Charge

| Alerte | Critère |
|---|---|
| Trafic anormal | requêtes par minute, alerte de métrique Scalingo |

## Événements

| Alerte | Critère |
|---|---|
| Crash ou arrêt d'une app | événement Scalingo |
| Job en échec | un message par job |
| Opération d'infra (déploiement, scaling, variable) | événement Scalingo |

## Environnements

Production uniquement, sauf les **événements**, qui ont aussi leurs salons de
staging : en staging, les autres signaux reflètent les tests en cours, pas une
panne.

## Ce qui n'est pas une alerte

- **Un bug récurrent** (un 4xx présent depuis toujours) fait partie de
  l'historique : aucune anomalie ne le révèle. Il se voit dans un dashboard,
  pas dans une alerte.
- **Les fenêtres longues du SLO** (24 h, 72 h) : sur le dashboard des SLO.
