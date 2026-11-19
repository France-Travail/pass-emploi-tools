# SLO — ce qu'on promet

Un SLO est une **promesse vue de l'utilisateur** : « X % des événements
réussissent, sur 30 jours glissants ». Le reste (1 − X) est la **marge
d'erreur** du mois. On n'alerte pas sur un taux d'échec brut, mais sur la
**vitesse** à laquelle cette marge se consomme (le *burn rate*).

## Les promesses

| SLO | Unité | Bon événement | Par |
|---|---|---|---|
| **Disponibilité** | ligne de requête de l'api | status < 500 | parcours |
| **Connexion** | tentative de connexion de bout en bout | connexion aboutie, refus métier exclus | mode d'authentification |

**Pourquoi status < 500** : un 4xx est une réponse juste du service (« ce jeune
existe déjà »). Il ne rompt pas la promesse. Les 4xx restent visibles ailleurs :
dans les dashboards (`outcome: failure`) et dans les
[alertes d'anomalie](alertes.md#anomalies).

## Les règles

- **Une ligne par événement utilisateur, jamais le `log.level`.** Une requête
  produit de zéro à plusieurs lignes `error`, et le level est un choix de tri
  qu'on ajuste : retoucher un log ne doit pas changer un SLO.
- **Aucune exception par parcours.** Un parcours qui aurait besoin d'en avoir
  une a un code HTTP qui ment : c'est le code qu'on corrige (cf.
  [le code HTTP](logs.md#le-code-http--ce-que-lappelant-doit-comprendre)).
- **Un objectif par SLO**, réglé avec ses seuils de burn rate dans le
  [mode d'emploi des SLO](../../kibana/slo/README.md).

## Burn rate et fenêtres

Burn rate 1 : la marge serait épuisée en exactement 30 jours. Une fenêtre se
déclenche quand le burn rate dépasse son seuil **sur sa fenêtre longue et sur
sa fenêtre courte** : la longue évite de sonner sur un pic isolé, la courte
fait retomber l'alerte dès que le problème cesse.

| Fenêtre longue / courte | Seuil standard | Marge épuisée en | Gravité |
|---|---|---|---|
| 1 h / 5 min | 14,4 | ~2 jours | 🚨 critique |
| 6 h / 30 min | 6 | 5 jours | ⚠️ avertissement |
| 24 h / 2 h | 3 | 10 jours | dashboard seulement |
| 72 h / 6 h | 1 | 30 jours | dashboard seulement |

Le burn rate ne peut pas dépasser 1 / (1 − objectif). Sous un objectif d'environ
93 %, les seuils standards deviennent inatteignables, et le SLO a ses propres
seuils.

**Faible trafic** : sous un volume minimum, un seul échec suffit à dépasser
n'importe quel seuil. Un SLO à faible trafic n'a que la fenêtre de 6 h.

## Ce que le SLO ne voit pas

| Angle mort | Où on le voit |
|---|---|
| Les 4xx | [anomalies](alertes.md#anomalies), dashboards |
| Un bug hors requête ou après la réponse (job, traitement non attendu, repli) | [diagnostic](alertes.md#diagnostic) par le `log.level` |
| Une panne avant notre app (app arrêtée, routeur) | [vu de l'extérieur](alertes.md#vu-de-lextérieur) |
