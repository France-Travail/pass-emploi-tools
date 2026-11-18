**Investiguer : les requêtes**

1. **Avant de conclure** : la date de remise à zéro (« Remise à zéro des statistiques », colonne « Depuis ») et la période choisie. Un index servi par un job mensuel paraît inutile sur une semaine.
2. **Index jamais utilisé** : supprimable s'il ne porte aucune contrainte et qu'aucune requête du code ne s'en sert ; d'abord les plus lourds face à leur table.
3. **Index peu sélectif** (« Sélectivité des index ») : une grande part de la table lue à chaque scan, ou peu des lignes lues réellement récupérées. Repère indicatif : plus de 1 000 lignes par scan, moins de 10 % récupérées.
4. **Trop d'index** (« Hygiène des index ») : nombreux au regard des écritures de la table, ou plus lourds que la table. Repère indicatif : 5 à 15 index. Chaque index ralentit les écritures et le vacuum.
5. **Table lue sans index** : `EXPLAIN (ANALYZE)` sur la requête. Un `Seq Scan` sur une petite table est normal ; une écriture se teste entre `BEGIN` et `ROLLBACK`.
6. **Plan qui se dégrade d'un coup** : estimations loin du réel, ou beaucoup de modifications depuis le dernier `ANALYZE` (« Entretien des tables ») : `ANALYZE` sur la table.
7. **Après une migration** : aucun index invalide (« Index invalides ou en doublon ») : un `CREATE INDEX CONCURRENTLY` interrompu laisse un index que le planificateur ignore.
8. **Table lente sans changement de code** : son entretien. Lignes mortes nombreuses ou `ANALYZE` ancien : `VACUUM (ANALYZE)` sur la table.
