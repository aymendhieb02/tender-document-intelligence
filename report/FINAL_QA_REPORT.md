# Contrôle final du rapport de stage

Date : 05/10/2026. Source produit auditée : `f292de8` (`main`). Titre final : **Conception et développement d'une plateforme intelligente de traitement documentaire basée sur l'OCR et l'analyse automatisée des cahiers des charges**.

## Livrable et composition

PDF : `report/build/rapport_stage_aymen_dhieb_udgroup.pdf` — **36 pages A4**, 905 795 octets après compilation propre. Répartition physique : page de garde 1 ; remerciements/résumés 2–4 ; tables et abréviations 5–9 ; introduction 10 ; chapitre 1 (UDGroup) 11–12 ; chapitre 2 (besoins) 13–14 ; chapitre 3 (choix techniques) 15–16 ; chapitre 4 (Document Intelligence) 17–20 ; chapitre 5 (Tender Intelligence) 21–27 ; chapitre 6 (évaluation) 28–31 ; chapitre 7 (déploiement et limites) 32–33 ; conclusion 34 ; références 35 ; annexe 36.

**18 figures** : 14 schémas TikZ originaux, 3 captures authentiques de l'interface sur fixture synthétique et 1 extrait vectoriel du véritable formulaire BOQ vide. **13 tableaux** et **7 références bibliographiques** vérifiées (site officiel UDGroup, documentations officielles et article arXiv). Trois captures ont été utilisées ; aucune capture préexistante d'un autre projet n'a été réemployée. La page de garde est typographique : aucun logo ESPRIT non vérifié n'a été emprunté.

## Vérification technique

- `latexmk -C` puis compilation complète `latexmk -pdf` depuis `report/` : réussite, Biber exécuté, listes et références résolues.
- Journal LaTeX final : **0 erreur fatale, 0 référence/citation non définie, 0 boîte débordante**. Il reste 14 avis `Underfull \hbox`, liés à la justification de cellules de tableaux et inspectés visuellement ; aucun texte coupé n'a été observé.
- PDF : 36 pages, 0 page vide, 0 caractère de remplacement dans le texte extrait. Couverture, sommaire, ouvertures de chapitres, tableau de la page BOQ réelle, captures, références et annexe ont été rendus et examinés avec Poppler.
- L'éditeur LaTeX intégré de Codex n'a pas pu initialiser ses répertoires standards sur cet hôte. Le PDF vérifié a été produit par MiKTeX local ; les sources restent éditables et une demande d'ouverture de `main.tex` a été envoyée à Codex.
- Produit inchangé. `pytest -q -rs` final : **305 réussis, 0 échec, 1 ignoré, 1 avertissement, 33,40 s**. Ignoré : Paddle réel sans modèles locaux ; avertissement : dépréciation Starlette/httpx TestClient.

## Contrôle des faits

Le formulaire réel de 30 pages est identifié comme **gabarit vide** avec cinq lignes structurelles page 25 ; aucun score de prix sur offre réelle remplie n'est revendiqué. Les métriques CDC sont rattachées à un corpus de développement, les tests Ask Tender à des questions synthétiques, et les latences à une seule mesure locale. L'histoire Git visible commence le 28/09/2026, après la période administrative du stage ; le rapport évite de dater chaque tâche à juillet–août. Une affirmation incorrecte de Dockerfile a été retirée lors de l'audit. Aucun nom de superviseur, déploiement de production, gain métier ou taux OCR non attesté n'a été ajouté.

## Limites et actifs manquants

Voir `report/MISSING_ASSETS.md`. Les limites principales sont l'absence de BOQ réels remplis et annotés, de validation OCR scannée rejouée, de jeu CDC tenu à l'écart, et de contrôle d'accès multi-utilisateur. Le rapport reste livrable comme document académique honnête et vérifiable.

## Appréciation éditoriale

Scores de revue éditoriale (jugement, **pas** métriques de précision du produit) : structure 9/10 ; traçabilité des affirmations 9/10 ; analyse technique 8/10 ; évaluation scientifique 8/10 ; lisibilité visuelle 8/10 ; reproductibilité 9/10 ; ensemble **8,5/10**.

Améliorations les plus utiles avant une soutenance ou une publication élargie :

1. Faire relire le récit du stage par l'étudiant et l'entreprise pour confirmer l'attribution temporelle des tâches.
2. Ajouter, avec autorisation, des BOQ réels remplis et une annotation indépendante afin de mesurer les valeurs extraites.
3. Rejouer l'OCR sur scans mixtes/arabes avec versions de modèles et vérité terrain documentées.
4. Compléter la page de garde avec les noms d'encadrants et le logo officiel seulement si les informations sont fournies et validées.
5. Évaluer Ask Tender et les exigences sur un corpus tenu à l'écart, avec jugement humain des citations et erreurs par catégorie.

Verdict : **rapport prêt à être remis pour relecture académique**, avec limites scientifiques explicitement exposées et PDF reproductible.
