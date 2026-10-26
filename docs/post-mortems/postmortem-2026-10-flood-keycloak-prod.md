# Post-mortem — Flood HTTP sur le login conseiller CD : Keycloak prod indisponible, web ralenti, chaîne de logs saturée (23/10/2026)

## TL;DR

Un bot appelle en boucle l'autorisation Keycloak du client conseiller CD,
depuis 58 IPs dont 3 portent l'essentiel du volume, et suit les redirections : Keycloak → connect → web. Une
requête du bot coûtait donc trois requêtes chez nous. Volumes : ~1 000 req/s
sur Keycloak (jusqu'à ~70 000 événements écrits en base par minute), jusqu'à
~1 300 req/s sur connect, ~665 req/s sur web.

- **Keycloak** écrivait chaque échec en base : les 30 connexions Postgres
  utilisables ont été épuisées, le conteneur a crashé en boucle et le scale
  s'est bloqué. Rétabli en bornant le pool et en coupant la sauvegarde des
  événements utilisateur.
- **Connect** a tenu grâce à l'autoscaling, mais ses ~2 800 lignes de log/s
  ont saturé la chaîne de logs, et sa redirection a reporté le flood sur web
  (autoscaler au maximum, page d'accueil à ~2,5 s).
- **Correctif connect** déployé à 19:00 : un callback broker en erreur sans
  `state` est rejeté en 400, sans log ni redirection, et une liste d'IPs est
  rejetée en 403. Le bot s'arrête à connect, web n'est plus touché.
- **Chaîne de logs** : les deux Logstash ont perdu leur Redis tampon. Les deux
  add-ons Redis (l'ancien upgradé, un neuf) sont restés bloqués en
  `provisioning`, pendant une maintenance d'infrastructure Scalingo en cours
  depuis le 21/10. Rétablie le 24/10 en supprimant l'add-on bloqué et en
  recréant un Redis business avec TLS forcé. Les logs de la coupure ne sont
  pas indexés (archives Scalingo intactes).

Le bot n'est bloqué nulle part en amont : aucun filtrage entrant n'est
disponible devant nos apps. Le 24/10, deux des trois IPs principales
s'arrêtent à 08:39, la troisième à 14:27 : fin du flood.

| Cause | Correctif |
|---|---|
| Keycloak : sauvegarde des événements utilisateur activée pour tous les types → 1 écriture en base par requête du bot | « Save events » désactivé sur le realm |
| Keycloak : pool par défaut (100) > connexions Postgres utilisables (30) → un conteneur prend toute la base, aucun redémarrage ne peut aboutir | `KC_DB_POOL_MAX_SIZE=14` |
| Keycloak : conteneur M (512 Mo) | Conteneur L (1 Go) |
| Connect : chaque requête du bot traitée, loguée deux fois et redirigée vers web | Rejet en amont des callbacks broker en erreur sans `state` (400) et des IPs de `BLOCKED_IPS` (403), sans log (PR connect #173) |
| Connect : 2 lignes de log par requête du bot, dont une avec stack trace | `LOG_LEVEL=error` en attendant le correctif, temporaire |
| Chaîne de logs : Redis tampon de 256 Mo, puis add-on bloqué | Upgrade et add-on neuf restés en `provisioning` (maintenance Scalingo). Débloqué le 24/10 : add-on supprimé, `redis-business-256` recréé avec TLS forcé, variables `REDIS_*` des deux Logstash mises à jour |

## Impact

- **Conseillers CD** (login via Keycloak) : service dégradé du 23/10 10:49
  à 17:55 (erreurs 500 intermittentes, 6 crashes entre 14:53 et 17:22),
  indisponible de ~17:22 à 17:55. Les autres publics passent par d'autres IdP.
- **Combien** : inconnu. Keycloak ne logue pas les logins réussis à ce niveau
  de log, et Scalingo a jeté une partie des lignes (overflow à 16 384 lignes/min).
- **Conseillers sur web** : page d'accueil à ~2,5 s au moins vers 18:50, et
  jusqu'au correctif connect de 19:00. Revenue à 0,2-0,3 s.
- **Observabilité** : du 23/10 18:17 au plus tard au 24/10 ~11:43, les logs de
  toutes les apps qui drainent vers `pass-emploi-logstash-prod` n'ont pas été
  indexés. Les
  drains peuvent être mis en quarantaine (429 renvoyés par `ingest`), ce qui
  n'affecte pas les apps elles-mêmes. Les logs restent dans les archives
  Scalingo (`logs-archives`), indépendantes du drain.
- **Connect** : pas de dégradation mesurée du trafic légitime (p50 à 7 ms, logins
  France Travail jeune aboutis pendant le flood). Ses redémarrages (variables
  d'env et déploiements, de 18:19 à 19:08) ont pu provoquer de brèves coupures.
- **Données** : aucun indice de compromission. 100 % des requêtes du bot ont
  échoué en `invalid_request`, sans aucun login ni reset de mot de passe.

## Chronologie (heure de Paris)

| Quand | Quoi |
|---|---|
| 21/10 12:40 → 12:52 | 1re vague, 1 IP, ~19 000 requêtes sur Keycloak. Postgres sature dès 12:40:29. Connect passe de 2 à 3 conteneurs à 12:48, puis revient à 2 |
| 23/10 10:49 | Début du flood continu : 3 IPs principales + un pool coordonné de 53 IPs (10:50 → 15:14, vu sur Keycloak) |
| 23/10 10:55 | Connect repasse à 3 conteneurs |
| 23/10 14:53 → 17:22 | 6 crashes du conteneur Keycloak (RAM 98 %, swap 85 %, CPU 159 %) |
| 23/10 17:24 et 17:31 | Deux tentatives de scale M → L, annulées : le nouveau conteneur n'obtient pas de connexion JDBC (`Failed to obtain JDBC connection`), l'ancien reste en `stopping` |
| 23/10 17:44 | Flood sur connect mesuré à ~550 req/s |
| 23/10 17:50 | Keycloak scalé à 0 conteneur → les connexions se libèrent. Mesure : `max_connections` 50, dont 20 réservées superutilisateur |
| 23/10 17:54 | `KC_DB_POOL_MAX_SIZE=14`, scale web:1:L → running à 17:55, 0 erreur de connexion |
| 23/10 17:55 → 18:01 | Keycloak écrit 33 000 à 65 000 événements par minute en base, pool plein (14/14) |
| 23/10 18:02 | Sauvegarde des événements utilisateur coupée (console d'admin) : 999 écritures sur la minute, puis arrêt → CPU Keycloak de 125 % à 55 % à flood constant |
| 23/10 ≤ 18:17 | Les deux Logstash perdent leur Redis (`ECONNRESET`) |
| 23/10 18:19 | Connect : création de comptes invités désactivée (`APP_JEUNE_ACTIF`), redémarrage des conteneurs |
| 23/10 18:27 | Flood sur connect mesuré à ~1 300 req/s (~2 800 lignes de log/s), CPU 80-90 % sur 3 conteneurs L |
| 23/10 18:28 | Autoscaler de connect relevé à 6 conteneurs max (cible 1 200 req/min par conteneur) → 5 conteneurs, puis 6 à 18:34 |
| 23/10 18:32 | Connect : `LOG_LEVEL=error` → plus de `request_completed`, ~1 250 lignes/s restantes (`login_failed`) |
| 23/10 18:36 | Redis tampon : `redis-business-256` → `redis-business-512` → l'add-on passe en `provisioning` et n'en sort plus. Autoscaler CPU (cible 90 %) ajouté sur le Logstash `process` |
| 23/10 ~18:50 | Constat : le bot suit la redirection de connect, ~665 req/s sur web `/autherror`, autoscaler web au maximum (3), page d'accueil à ~2,5 s |
| 23/10 | Ticket Scalingo : ils proposent Cloudflare en urgence ou un filtrage applicatif ; support fermé ensuite |
| 23/10 19:00 | Correctif connect déployé (commit `7127438`, branche de la PR #173) : flood rejeté en 400 en ~0 ms, sans log |
| 23/10 19:02 | `BLOCKED_IPS` posée sur connect (58 IPs), mais pas chargée faute de redémarrage |
| 23/10 19:03 | Fin du flood sur web. CPU web à 0 %, page d'accueil à 0,2-0,3 s |
| 23/10 ~19:05 | Router logs de connect désactivés, par erreur, lors d'un diagnostic (`router-logs` sans option bascule le réglage) |
| 23/10 19:06 | Autoscaler de connect passé sur le CPU (cible 80 %) |
| 23/10 19:07 | Redéploiement de connect (commit `45fd95b`) : `BLOCKED_IPS` chargée à 19:08 |
| 23/10 19:08 → | Le rpm sur connect augmente : le bot reboucle plus vite puisqu'il reçoit une réponse immédiate. CPU Keycloak de 55 % à 65 % |
| 23/10 19:16 | Nouvel add-on `redis-business-512` sur l'app ingest, pour contourner l'ancien : lui aussi bloqué en `provisioning` |
| 24/10 01:30 | Signalements d'abus à OVH, Contabo et Bouygues Telecom |
| 24/10 → 08:37 | Flood stable sur connect, ~1 540 req/s, venant des 3 IPs principales, toutes en 403 |
| 24/10 08:37 | L'IP OVH s'arrête net, en milieu de minute |
| 24/10 08:39 | L'IP Contabo s'arrête. Il ne reste que l'IP résidentielle Bouygues, ~600 req/s (~36 000/min). Keycloak ne déborde plus ses logs |
| 24/10 11:16 | Toujours la seule IP Bouygues, à débit constant. Aucune nouvelle IP |
| 24/10 11:20 | Les deux add-ons Redis sont toujours en `provisioning` ; ingest (`ECONNRESET`) et process (`Redis connection error`) ne joignent plus Redis |
| 24/10 avant 11:37 | Add-on bloqué de process supprimé depuis le dashboard, add-on `redis-business-256` neuf créé à la place : `running` en quelques minutes, TLS forcé activé à la main (créé en `redis://`). Add-on inutilisé d'ingest supprimé |
| 24/10 ~11:40 | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` mis à jour sur les deux Logstash (le CA ne change pas, il est commun à la région). Process redémarre à 11:40:36 ; une erreur `READONLY You can't write against a read only replica` à 11:40:38, puis plus aucune erreur Redis |
| 24/10 11:42:15 | Ingest redémarre. Ses anciens conteneurs restent bloqués à l'arrêt (sortie Redis vers l'add-on supprimé) et sont tués à 11:43:43 ; plus aucune erreur Redis ensuite |
| 24/10 14:27:43 | Dernière requête de l'IP Bouygues sur Keycloak, arrêt net. **Fin du flood.** Cause inconnue (action de Bouygues après le signalement, ou abandon de l'opérateur) |
| 24/10 ≤ 14:29 | Logs de nouveau indexés dans Kibana, sans autre action qu'attendre après la bascule. Aucune erreur sur les deux Logstash depuis 11:43:43 |
| 24/10 après-midi | Durcissement manuel de Keycloak, après la fin du flood : password grant coupé sur `admin-cli` (realms `master` et `pass-emploi`), détection de brute force activée sur `master`. Report en Terraform sur la branche `fix/durcissement-keycloak` de `pass-emploi-auth` |

## Le flood

Une seule requête du bot, qui suit les redirections :

```
bot → Keycloak …/protocol/openid-connect/auth?client_id=pass-emploi-conseiller-dept (sans response_type)
        └─ Keycloak redirige vers connect …/broker/conseildepartemental-conseiller/endpoint
           ?error=invalid_request&error_description=Missing+parameter:+response_type&iss=<keycloak>  (sans state)
              └─ connect redirige (307) vers web /autherror?reason=SessionNotFound…
```

- **Keycloak** : `KC-SERVICES0092` + `LOGIN_ERROR invalid_request`, et une
  écriture en base par requête tant que la sauvegarde des événements était active.
- **Connect** : `login_failed` / `SessionNotFound`, redirection en 1 ms sans
  accès à la base, mais 2 lignes de log par requête.
- **Web** : rendu serveur de `/autherror` (~43 ms) pour chaque requête.
- **Effet du correctif** : la boucle s'arrête à connect. Le bot recevant une
  réponse immédiate, il reboucle plus vite : le rpm vu par le routeur
  augmente, mais le coût par requête devient quasi nul.
- **Signature** : User-Agents Chrome tournants, referers randomisés sur de faux
  domaines (`quora.org`, `reddit.net`, `baidu.co`, `facebook.com/?q=<aléatoire>`).
  C'est la signature des outils de flood HTTP. Aucune app légitime n'envoie
  `/auth` sans `response_type`.
- **Volume** : les volumes tirés des logs sont des minimums, très en dessous
  du réel. Scalingo plafonne à 16 384 lignes/min par conteneur, et les logs
  Keycloak suggéraient ~33 req/s quand la base comptait ~1 000 événements/s.
  Le compte des événements en base fait foi.
- **Sources** : 58 IPs, presque toutes chez des hébergeurs VPS ou des réseaux
  de proxys (une vingtaine de pays), plus une IP résidentielle. Liste complète
  jointe au ticket Scalingo. Le compte de 58 vient des logs Keycloak : sur les
  router logs de connect (23/10 16:18 → 17:05), **3 IPs font 99,6 % du
  volume**, à savoir un VPS OVH, un VPS Contabo et une ligne fixe résidentielle
  Bouygues. Ce sont les mêmes 30 h plus tard.

## Pourquoi Keycloak est tombé et pas connect

Même bot, deux comportements :

- **Connect** répond par une redirection, sans base, et scale à l'horizontale
  (sans état par requête) : jusqu'à ~1 300 req/s absorbées sur 3 à 6 conteneurs L.
- **Keycloak** écrivait chaque échec en base (`events_enabled = true`, tous
  types, rétention 90 jours), sur 1 conteneur M et une base `starter-512`.
  Mesuré : ~60 000 écritures/min avant la coupure, arrêt net après.
  Il ne peut pas scaler à l'horizontale, à cause de son cache local et des
  sessions en mémoire.

Le pool par défaut (100) dépassait les 30 connexions utilisables : un seul
conteneur pouvait vider la base. D'où un blocage en boucle : pas de connexion
libre → le nouveau conteneur ne démarre pas → l'ancien n'est jamais remplacé.

## Pourquoi la chaîne de logs a saturé

Connect logue chaque requête du bot deux fois (`request_completed` en info,
`login_failed` en error avec stack trace). À ~1 300 req/s, ça fait ~2 800
lignes/s pour la seule app connect, qui transitent par le Redis tampon de
256 Mo placé entre `ingest` et `process`. C'est le même mode de défaillance
que l'incident Redis du 14/09/2026 (cf.
[runbook-logstash, scénario 5](../observabilite/runbooks/runbook-logstash.md#scénario-5--backlog-redis-logstashingest)).

Le rétablissement a buté sur la plateforme : l'upgrade de l'add-on, puis un
add-on neuf, sont tous deux restés en `provisioning`. Scalingo affiche une
« Emergency Infrastructure Maintenance - Potential Service Disruptions » sur
les deux régions, « continuously, 24/7, from Wednesday, October 21, to Monday,
October 26, 2026 » ([scalingostatus.com](https://scalingostatus.com/)). Les
redémarrages de conteneurs par `scalingo-platform` vus toute la journée dans les
timelines en relèvent probablement. Elle n'explique pas le flood, dont la 1re
vague (21/10 12:40) précède son début (21/10 15:00).

## Ce qui a marché, ce qui a manqué

- ✅ Les archives de logs Scalingo ont permis de dater le début (21/10) et
  d'isoler le pool d'IPs.
- ✅ Connect a absorbé le flood grâce à l'autoscaling.
- ✅ Couper la boucle de redirection au point le moins coûteux (connect) a
  protégé connect, web et la chaîne de logs d'un seul correctif, testé et
  déployé en ~1 h.
- ❌ La redirection d'erreur de connect a reporté le flood sur web sans qu'on le
  voie : les logs de web ne portent pas l'IP du client.
- ❌ Une commande CLI de diagnostic (`router-logs`) a modifié la prod : sans
  option, elle bascule le réglage au lieu de l'afficher.
- ❌ La 1re vague du 21/10 n'a déclenché aucune alerte (connect a été scalé à
  la main, sans suite).
- ❌ Les logs Keycloak partent vers un autre stack (`pa-logs-prod`), absent
  de notre Kibana.
- ❌ Un flood sur une seule app peut saturer la chaîne de logs de toutes les
  apps : aucun plafond de volume par app.
- ❌ Aucun filtrage entrant n'est possible aujourd'hui : l'Application Firewall
  Scalingo ne fait que de la liste blanche IPv4 (20 règles), sans refus d'IP,
  sans WAF ni limitation de débit.
  ([doc](https://doc.scalingo.com/platform/networking/public/application-firewall))
- ❌ Keycloak n'a pas de domaine personnalisé : un filtre placé devant serait
  contourné par l'URL `*.scalingo.io`.
- ❌ Cloudflare, proposé par Scalingo : changement de domaine donc d'issuer,
  et TLS ouvert chez un acteur américain alors que l'app est hébergée en
  SecNumCloud → à valider par le RSSI France Travail, non retenu en urgence.

## Limites de l'analyse

- La saturation mémoire du Redis tampon n'a pas pu être lue (console Redis
  indisponible avec TLS imposé). Elle est déduite de la perte de connexion
  simultanée des deux Logstash et du précédent du 14/09.
- Le nombre de conseillers réellement bloqués et le volume de logs perdus ne
  sont pas mesurables a posteriori.
- Le correctif connect filtre la signature actuelle du bot. Un bot qui
  ajouterait un `state` quelconque, ou viserait une autre URL, repasserait :
  traitement complet, logs et redirection vers web. La liste d'IPs ne couvre
  que les IPs déjà vues.
- On ignore pourquoi les IPs OVH et Contabo se sont arrêtées le 24/10, 7 h
  après les signalements d'abus : coupure par l'hébergeur ou par l'opérateur
  du bot. Deux arrêts à deux minutes d'écart chez deux hébergeurs différents
  penchent pour l'opérateur, qui peut donc reprendre depuis d'autres IPs. Seule
  une réponse d'OVH ou de Contabo tranchera.
- Un 403 de connect ne réduit pas le volume entrant : Keycloak reçoit toujours
  le premier saut de chaque requête.

## Suites proposées (portées au board)

**Ramener le correctif dans le flux de release**
- Le correctif tourne en prod depuis la branche de la PR #173, pas depuis
  `master` : merger dans `develop` et livrer sur `master`, sinon le prochain
  déploiement de `master` le retire.

**Rétablir la chaîne de logs**
- Dériver `REDIS_HOST`, `REDIS_PORT` et `REDIS_PASSWORD` de
  `SCALINGO_REDIS_URL` au démarrage, pour que process suive un changement
  d'add-on sans mise à jour manuelle. Ingest, qui utilise le Redis d'une autre
  app, reste à mettre à jour à la main.
- Repointer le dashboard `[Metrics Redis] Keys` et l'alerte 7 sur l'add-on retenu.
- Vérifier les trous dans les index de logs sur la période (Discover,
  `logs-prod-default`) et décider de réinjecter ou non depuis les archives Scalingo.

**Revenir à la normale une fois le flood terminé**
- Connect : retirer `LOG_LEVEL=error`, réactiver les router logs, réactiver
  `APP_JEUNE_ACTIF` si la désactivation n'était que conjoncturelle, revoir
  l'autoscaler (passé sur le CPU pendant l'incident).
- Web : revoir le maximum de l'autoscaler.
- Keycloak : revoir la taille du conteneur (passé en L).
- Redis tampon : décider du plan à garder.

**Keycloak**
- Vérifier que le vault prod fournit bien le secret du client conseiller CD.
  Sinon, la prod utilise le secret par défaut commité dans `variables.tf`, et
  il faut le faire tourner (Keycloak et connect).
- Gérer le User profile en Terraform, avec le validateur de domaine email posé
  à la main (points à échapper). Préalable : passer du provider
  `mrparkers/keycloak` 4.4.0 à `keycloak/keycloak`, seul à gérer
  `unmanaged_attribute_policy` (Keycloak 24).
- Merger `fix/durcissement-keycloak` (`pass-emploi-auth`) après un `plan` sur
  staging puis prod : coupure des événements, `admin-cli` et brute force sur
  `master`, sinon le prochain provisionnement annule les réglages manuels.
  `make provision-*` enchaîne un `apply -auto-approve` sans `plan`.
- Documenter `KC_DB_POOL_MAX_SIZE` dans `pass-emploi-auth` avec sa règle :
  (connexions utilisables − marge) / 2.
- Figer `BUILDPACK_URL` (aujourd'hui `#master`) avant tout redéploiement.
- Purger à froid les événements du bot dans `event_entity`.
- Rapatrier les logs Keycloak dans le stack ECS commun.

**Connect et web**
- Bannissement automatique et temporaire d'une IP après N échecs de callback
  en une minute, avec un seuil dérivé du trafic légitime mesuré (NAT mobile).
- Ne plus logguer de stack trace pour les échecs de login attendus
  (`SessionNotFound`).
- Logguer l'IP du client dans web, pour voir un flood quand il arrive par
  redirection.

**Chaîne de logs**
- Plafonner ou échantillonner le volume par app avant le Redis tampon, pour
  qu'une app en flood ne prive pas les autres de logs.
- Alerte sur le débit de lignes par app et sur la mémoire du Redis tampon.

**Détection**
- Alerte sur un pic de requêtes par IP, ou sur un pool d'IPs synchronisées
  (requêtes ES|QL de l'incident).

**Protection périmétrique**
- Point d'entrée filtrant souverain (refus d'IPs, signatures, limitation de
  débit) + domaines personnalisés + liste blanche Scalingo de ce point
  d'entrée, pour api, web, connect et Keycloak.
