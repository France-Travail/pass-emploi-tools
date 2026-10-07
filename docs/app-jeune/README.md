# App Jeune — invariants

L'app s'ouvre à tous les jeunes, y compris non accompagnés et non inscrits.
Ce qui suit ne doit pas casser quand on y ajoute un public ou une fonctionnalité.

## Publics et authentification

- **Trois notions à ne pas confondre** : le public (qui il est pour le produit),
  le mode d'authentification (comment il prouve son identité), la
  représentation dans l'API (comment on range ses droits). Plusieurs publics
  partagent un même mode ; mélanger les trois est la dette historique du modèle.
- **Côté France Travail, un seul mode d'authentification.** Le public est décidé
  par la porte d'entrée choisie au login, pas par l'IDP.
- **Le public est un état, pas une identité.** Un jeune pris en accompagnement,
  ou dont le conseiller s'en va, change de public sans changer d'identifiant ni
  perdre ses données.

## Droits

- **Les droits se déduisent de trois questions** : le jeune a-t-il un conseiller
  chez nous ? un dossier de demandeur d'emploi France Travail ? relève-t-il
  d'une Mission Locale ? Jamais du mode d'authentification.
- **Le compteur d'heures est propre à la Mission Locale**, et au seul CEJ.
- **Sans conseiller chez nous, pas de messagerie.** Les bénéficiaires dont le
  conseiller part sur une autre application la perdent pour cette raison, pas
  par une restriction propre à leur public.

## Invité

- **Un invité est authentifié, sous une identité pseudonyme** : il a un jeton
  comme les autres, ce n'est pas un appelant anonyme.
- **Son identifiant est fabriqué par le serveur**, jamais fourni par le client :
  sinon il serait forgeable, donc usurpable. Seul son refresh token le rattache
  à son appareil.
- **Une fonctionnalité ne s'ouvre à l'invité qu'explicitement.** Le mécanisme
  d'autorisation ne le garantit pas de lui-même : toute nouvelle route doit
  vérifier qu'elle rejette l'invité s'il n'y a pas droit.

## Plan d'action

- **Le générateur ne rend que des identifiants de solutions**, jamais de
  contenu. Libellés et liens viennent de notre référentiel, et un identifiant
  inconnu est écarté : le pire cas est un plan plus pauvre, jamais un plan faux.
- **Ce n'est pas l'IA qui décide à quoi un jeune a droit** : l'éligibilité est
  une règle déterministe.
- **Un identifiant venu du générateur n'est jamais une clé chez nous.** Plan,
  objectifs et tâches ont nos propres identifiants : c'est ce qui rend le
  générateur remplaçable sans migration.
- **Le référentiel ne s'écrit que par sa synchronisation**, jamais en effet de
  bord d'une génération. Une solution retirée est **désactivée, jamais
  supprimée** : les plans déjà sauvegardés y font référence.
- **Le mobile ne parle jamais au générateur.** Le contrat du générateur peut
  changer sans livraison sur les stores, et son secret reste côté serveur.
- **L'invité garde son plan sur son appareil** ; le jeune connecté l'a côté API.
