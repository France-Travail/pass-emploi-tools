# Post-mortem — Elastic Agent bloqué UNENROLLED après recréation d'une app (11/09/2026)

> **Type** : explication (Diataxis). Comment l'incident s'est produit, pourquoi
> Fleet bloque le ré-enrollment, et comment débloquer sans recréer l'app.
>
> Correctif opérationnel : variable `ELASTIC_AGENT_ID_SUFFIX` dans
> [`logs/README.md`](../../../logs/README.md#elastic-agent-fleet).

## TL;DR

Une erreur de copié-collé des variables d'environnement FLEET sur Scalingo lors
de la création d'une nouvelle app a provoqué la perte de supervision Fleet de
cette app sur Kibana. Le `FLEET_REPLACE_TOKEN` copié ne correspondait pas à
l'identité Fleet de l'app, cassant la corrélation attendue par Fleet.
L'Elastic Agent restait bloqué à l'état **UNENROLLED** et ne parvenait plus à
s'enroller.

| Cause                                                                                                                                                   | Correctif                                                                                        |
|---------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| `ELASTIC_AGENT_ID` dérivé du `HOSTNAME` → même UUID qu'une ancienne instance déjà enrollée avec un `FLEET_REPLACE_TOKEN` différent → corrélation cassée | Poser `ELASTIC_AGENT_ID_SUFFIX=v2` dans les variables Scalingo → nouvel UUID → enrollment propre |

**Résultat dans Fleet** : un agent fantôme `UNENROLLED` (l'ancien) + un agent
`Healthy` (le nouveau). L'agent fantôme peut être ignoré ; il ne consomme rien.

---

## 1. Le symptôme

- L'Elastic Agent de l'app `pass-emploi-logstash-perf` reste au statut
  **UNENROLLED** (grisé) dans la vue Fleet de Kibana.
- Les métriques Logstash n'arrivent plus dans Fleet.
- Les logs du conteneur montrent des erreurs d'enrollment répétées (`invalid API
  key` ou équivalent).

---

## 2. La cause racine

### Fonctionnement de l'enrollment Fleet

`ELASTIC_AGENT_ID` est calculé dans `start.sh` par :

```bash
uuid5(NAMESPACE_DNS, HOSTNAME)
```

Le `HOSTNAME` Scalingo est dérivé du **nom de l'app** (ex :
`pass-emploi-logstash-perf-web-1`). Il est donc **stable et déterministe** par
nom d'app — c'est voulu pour garantir un UUID unique par instance sans
configuration manuelle.

`FLEET_REPLACE_TOKEN` est un token généré **une seule fois** lors du premier
enrollment. Fleet l'associe à l'`ELASTIC_AGENT_ID` de l'instance. Il ne peut
pas être modifié après coup, ni retrouvé dans Fleet (uniquement dans les
variables Scalingo de l'app d'origine).

### Ce qui s'est passé

1. L'app `pass-emploi-logstash-perf` avait déjà été créée et enrollée une
   première fois, avec un `FLEET_REPLACE_TOKEN` T1.
2. L'app a été recréée (ou ses variables réinitialisées par copié-collé depuis
   une autre app), avec un `FLEET_REPLACE_TOKEN` T2 différent.
3. Au démarrage, `start.sh` calcule le même `ELASTIC_AGENT_ID` (même
   `HOSTNAME`, même UUID) — mais Fleet attend T1 pour cet ID, pas T2.
4. **La corrélation ID ↔ token est cassée.** Fleet refuse l'enrollment et
   maintient l'agent à l'état `UNENROLLED`.

> Fleet ne laisse pas supprimer ni ré-enroller un agent déjà enrollé via
> l'interface Kibana. L'agent fantôme reste visible indéfiniment.

### Pourquoi le copié-collé est piégeux

`FLEET_REPLACE_TOKEN` est une valeur **unique par app et par enrollment**. La
copier depuis une autre app (ex : prod → perf) donne un token qui ne correspond
à aucun `ELASTIC_AGENT_ID` connu de Fleet pour cette app → enrollment impossible
dès le premier démarrage.

---

## 3. Déroulé du diagnostic

| Hypothèse                                                     | Verdict                                                                                             |
|---------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| Problème réseau / Fleet Server inaccessible                   | ❌ Éliminé — les autres apps s'enrollent normalement                                                 |
| `FLEET_ENROLLMENT_TOKEN` invalide                             | ❌ Éliminé — remplacé, sans effet                                                                    |
| Mauvais `FLEET_URL`                                           | ❌ Éliminé — identique aux autres apps                                                               |
| Corrélation `ELASTIC_AGENT_ID` ↔ `FLEET_REPLACE_TOKEN` cassée | ✅ **Cause racine** — même HOSTNAME → même UUID, mais token différent de celui enregistré dans Fleet |

Les anciennes valeurs ont finalement été retrouvées dans les **audits Scalingo**,
mais les remettre n'a pas suffi à débloquer la situation (l'état Fleet était
déjà corrompu côté serveur).

---

## 4. Solution

Poser une nouvelle variable dans les variables d'environnement Scalingo de
l'app bloquée :

```
ELASTIC_AGENT_ID_SUFFIX=v2
```

Au prochain démarrage, `start.sh` calcule l'UUID depuis `HOSTNAME:v2` au lieu
de `HOSTNAME` → **nouvel UUID** → Fleet l'enregistre comme un nouvel agent →
enrollment propre.

**Résultat dans Fleet** :
- L'ancien agent (UUID sans suffixe) reste visible à l'état `UNENROLLED` — il
  peut être ignoré, il ne consomme rien.
- Le nouvel agent (UUID avec suffixe) passe à l'état `Healthy`.

> Choisir un suffixe court et mémorable (ex : `v2`, `v3`…). Si l'incident se
> reproduit, incrémenter le suffixe.

---

## 5. Action préventive

> ⚠️ **Stocker `FLEET_REPLACE_TOKEN` dans Bitwarden** dès le premier déploiement
> de chaque app, avec le nom de l'app et l'environnement comme libellé.

`FLEET_REPLACE_TOKEN` est la seule valeur qui permet de ré-enroller un agent
existant sans changer son identité Fleet. Elle n'est visible que dans les
variables Scalingo de l'app d'origine — pas dans Fleet, pas dans les logs.

Sans elle, la seule issue est de changer l'identité de l'agent via
`ELASTIC_AGENT_ID_SUFFIX`, ce qui laisse un agent fantôme dans Fleet.

---

## 6. Leçons à retenir

1. **`FLEET_REPLACE_TOKEN` est unique, non récupérable depuis Fleet, et doit
   être stocké dès le premier déploiement.** Ne pas le copier depuis une autre
   app.
2. **`ELASTIC_AGENT_ID` est déterministe par nom d'app.** Recréer une app avec
   le même nom sans changer le token = collision garantie.
3. **Fleet ne permet pas de supprimer un agent enrollé via l'UI.** Un agent
   fantôme `UNENROLLED` est inoffensif mais permanent — préférer la prévention.
4. **`ELASTIC_AGENT_ID_SUFFIX` est le levier de déblocage.** Il force un nouvel
   UUID sans toucher aux autres apps ni recréer l'app Scalingo.
