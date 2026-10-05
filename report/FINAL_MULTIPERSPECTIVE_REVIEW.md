# Revue finale selon huit points de vue

Date : 05/10/2026. Notes éditoriales argumentées sur 10, **sans valeur de métrique de précision du logiciel**. Document examiné : PDF révisé de 39 pages, 14 figures, 15 tableaux et 14 références.

| Point de vue | Note | Point le plus fort | Point le plus faible | Amélioration restante |
|---|---:|---|---|---|
| Jury ESPRIT | 8,4 | Mission, méthode, contributions et limites désormais lisibles ensemble | Chronologie personnelle de juillet–août non confirmée par journal contemporain | Faire valider le récit du stage et les encadrants avant dépôt officiel |
| Enseignant Data Science | 8,0 | Cohortes, annotations partielles et niveaux de preuve correctement séparés | Aucun jeu final indépendant et OCR réel non rejoué | Constituer un corpus tenu à l'écart avec vérité terrain |
| Ingénieur IA senior | 8,3 | Contrat de preuve et propagation de provenance jusqu'aux fonctions métier | Couverture des formulations arabes et des scans insuffisamment établie | Rejouer les modèles OCR locaux et classer les erreurs de bout en bout |
| Architecte logiciel | 8,5 | Frontière claire entre producteur DI, consommateurs CDC/BOQ et états utilisateur | Stockage local sans droits ni historique d'audit complet | Définir isolation des dossiers, sauvegarde, identité et journalisation |
| Responsable UDGroup / métier | 7,7 | Parcours d'analyste concret avec source, revue et chiffrage séparé | Aucun gain de temps ou impact métier mesuré sur dossier réel | Organiser une étude supervisée avec analystes et dossiers autorisés |
| Recruteur technique | 8,3 | Tableau de contributions relie compétences et modules vérifiables | Attribution personnelle et dates restent à confirmer hors Git | Joindre une démonstration courte et un récit validé par l'étudiant |
| Relecteur scientifique | 7,6 | Résultats chiffrés sans extrapolation abusive ; BOQ réel vide clairement nommé | Échantillons faibles, développement et évaluation insuffisamment séparés | Préenregistrer protocole, cohortes et métriques par champ sur nouveaux documents |
| Relecteur visuel | 8,6 | Hiérarchie sobre, architecture et parcours métier lisibles sur A4 | Trois seules captures UI, dont deux cadrages verticaux étroits | Ajouter seulement une capture de navigation source ou bibliothèque si elle apporte une preuve |

## Cinq faiblesses qui restent prioritaires

1. **Temporalité et attribution** : les commits disponibles commencent après la période administrative ; le récit doit être confirmé par Aymen et UDGroup.
2. **Généralisation documentaire** : pas de corpus indépendant de CDC et de BOQ réels remplis.
3. **OCR scanné et multilingue** : absence de réexécution locale avec modèles Paddle et annotations définitives, notamment pour l'arabe.
4. **Validation métier** : exactitude des décisions, gain de temps et ergonomie n'ont pas été mesurés auprès d'analystes sur des dossiers autorisés.
5. **Exploitation sécurisée** : authentification, droits par dossier, audit, sauvegarde et tests de charge restent à concevoir.

Verdict : rapport académique solide et honnête pour la relecture, avec un prototype techniquement démontré. Les limites ci-dessus empêchent de présenter la plateforme comme validée pour des décisions contractuelles ou un usage multi-utilisateur en production.
