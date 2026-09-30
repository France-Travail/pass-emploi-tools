# Pilotage des agents — Fleet

**Fleet** (Fleet Server, intégré à Elastic Cloud) pilote tous les **Elastic
Agents** de la stack : il leur distribue leur configuration (policies et
intégrations) et suit leur état. C'est lui qui garantit qu'on reçoit bien les
métriques de la stack de log management (Logstash, Redis) et des hosts. Il ne
pilote **ni Heartbeat** (binaire autonome, cf.
[collecte/metriques/disponibilite](collecte/metriques/disponibilite.md)) **ni les
SDK APM** (cf. [collecte/traces](collecte/traces/README.md)).

## Les agents pilotés

| Agent | App Scalingo | Policy (Kibana → Fleet → Agent Policies) | Intégrations |
|---|---|---|---|
| co-localisé INGEST | `pass-emploi-logstash-<env>` | une par env | Logstash, System |
| co-localisé PROCESS | `pass-emploi-logstash-process-<env>` | une par env | Logstash, System |
| dédié | `pass-emploi-elastic-agent-<env>` | ex. `pass-emploi-elastic-agent-<env>` | Redis (+ System optionnel) |

**Environnement perf** : ses agents sont **volontairement désactivés** pour
réduire les coûts d'infra — ni supervisés ni alertés (cf.
[alerte 8](supervision/alertes-stack-observabilite.md#alerte-8--elastic-agent-en-défaut)).

La configuration de ce que supervise un agent **n'est pas dans ce repo** : elle
est gérée dans Kibana. Au démarrage, l'agent se connecte au Fleet Server avec
son `FLEET_ENROLLMENT_TOKEN`, télécharge sa policy et applique les intégrations.
Ce qui est collecté : [collecte/metriques](collecte/metriques/README.md).

## Enrôler un agent

1. **Kibana → Fleet → Agent Policies** : créer (ou choisir) la policy.
2. Y ajouter les intégrations (Logstash, Redis, System…).
3. Générer un **Enrollment Token** pour cette policy → variable Scalingo
   `FLEET_ENROLLMENT_TOKEN` (avec `FLEET_URL`, `FLEET_ENROLL=1`).
4. Poser `ELASTIC_AGENT_TAGS` (ex. `scalingo,pass-emploi-logstash`) pour filtrer
   les agents dans Fleet.
5. **Stocker `FLEET_REPLACE_TOKEN` dans Bitwarden** dès le premier déploiement,
   avec le nom de l'app et l'environnement comme libellé (cf. identité ci-dessous).
6. **Rejouer la procédure de contrôle des rétentions**
   ([stockage/README](stockage/README.md#procédure-de-contrôle-à-rejouer-après-toute-nouvelle-intégration-fleet)) :
   toute intégration Fleet sur étagère tombe par défaut sur une policy ILM sans
   phase `delete` → rétention infinie.

Variables détaillées : [`logs/README.md`](../../logs/README.md#elastic-agent-fleet--configuration-requise)
et [`elastic-agent/README.md`](../../elastic-agent/README.md).

## Identité d'un agent — le piège de la recréation d'app

- `ELASTIC_AGENT_ID` n'est **pas** configuré : `start.sh` le dérive du `HOSTNAME`
  (`uuid5(NAMESPACE_DNS, HOSTNAME)`), donc **déterministe par nom d'app** et par
  instance (`web-1`, `web-2`…).
- `FLEET_REPLACE_TOKEN` est généré **une seule fois** au premier enrollment, associé
  à cet ID par Fleet, **non récupérable** depuis Fleet. Ne jamais le copier depuis
  une autre app.
- Recréer une app sous le même nom avec un autre token = corrélation ID ↔ token
  cassée → agent bloqué **UNENROLLED**. Issue : `ELASTIC_AGENT_ID_SUFFIX=v2`
  (incrémenter si ça se reproduit) → nouvel UUID → enrollment propre. L'ancien
  agent reste visible `UNENROLLED`, inoffensif mais permanent (Fleet ne permet pas
  de le supprimer via l'UI).

Récit complet : [postmortem-2026-09-unenrolled-elastic-agent.md](post-mortems/postmortem-2026-09-unenrolled-elastic-agent.md).

## Ressources d'un agent

- L'agent co-localisé **démarre en différé** : il attend que Logstash réponde sur
  le port 9600 avant de se lancer, pour ne pas concurrencer la JVM pendant le boot
  (~60 s de timeout Scalingo).
- Mémoire Go bornée par `ELASTIC_AGENT_GO_OPTS` (`GOMEMLIMIT`) — cf.
  [infrastructure.md](infrastructure.md#garde-fous-jvm--scalingo).
- Agent dédié : **1 seule instance** (plusieurs remonteraient les mêmes métriques
  en doublon), conteneur M (512 Mo).

## Savoir qu'un agent a décroché

Un agent offline ou UNENROLLED, c'est une supervision aveugle : les alertes 4, 5
et 7 (métriques Logstash et Redis) cessent de pouvoir se déclencher. L'alerte 8
**Elastic Agent en défaut** (offline, désenrôlé, unhealthy, erreurs d'écriture) couvre ce cas ([supervision/alertes](supervision/alertes-stack-observabilite.md#alerte-8--elastic-agent-en-défaut)).
État courant : **Kibana → Fleet → Agents** (filtrer par tag).
