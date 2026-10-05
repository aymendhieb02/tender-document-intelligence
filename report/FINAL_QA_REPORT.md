# Contrôle final du rapport de stage révisé

Date : 05/10/2026. Source applicative auditée : f292de8 ; version initiale du rapport préservée au commit 2fe989e. Titre final : **Conception et développement d'une plateforme intelligente de traitement documentaire basée sur l'OCR et l'analyse automatisée des cahiers des charges**.

## Livrable

PDF : report/build/rapport_stage_aymen_dhieb_udgroup.pdf — **39 pages A4, 963 998 octets**. Pages physiques : couverture 1 ; remerciements/résumés 2–4 ; tables et abréviations 5–9 ; introduction 10 ; chapitre 1 (mission et méthode) 11–13 ; chapitre 2 (besoins et parcours) 14–16 ; chapitre 3 (état de l'art) 17–19 ; chapitre 4 (Document Intelligence) 20–23 ; chapitre 5 (Tender Intelligence) 24–30 ; chapitre 6 (évaluation) 31–35 ; chapitre 7 (limites) 36 ; conclusion 37 ; références 38 ; annexe 39.

**14 figures** : 10 schémas vectoriels originaux, 3 captures authentiques de l'interface sur fixture synthétique, 1 extrait vectoriel du gabarit BOQ réel vide. **15 tableaux** et **14 références citées**. La page de garde reste typographique, car aucun logo ESPRIT officiel d'impression n'a été fourni.

## Vérification technique et visuelle

- Construction à partir d'un état propre : latexmk -C, puis latexmk -pdf avec Biber. Code de sortie 0.
- Journal final : 0 erreur fatale, 0 référence ou citation non définie, 0 boîte débordante. Les avis de boîtes sous-remplies dans certains tableaux ont été inspectés visuellement, sans texte coupé.
- PDF : 39 pages, aucune page vide, aucun caractère de remplacement, aucun indice « Ã » dans le texte extrait.
- Toutes les pages rendues avec Poppler et examinées en planche contact ; couverture, méthode, organisation, chronologie, contributions, architecture, parcours, comparaison d'approches, OCR, Tender, évaluation, bibliographie et annexe contrôlés en détail.
- L'ordre du parcours « consultation → revue/chiffrage → sauvegarde » a été corrigé après inspection. Le texte de l'annexe sur prix et quantité a été reformulé pour éviter la séquence d'extraction suspecte.
- Compilateur intégré Codex indisponible sur cet hôte (« Unable to find standard directories for platform ») ; PDF livré produit et vérifié avec MiKTeX local.

## Test de l'application

Produit inchangé. pytest -q -rs réexécuté le 05/10/2026 : **305 réussis, 0 échec, 1 ignoré, 1 avertissement, 33,05 s**. L'ignoré nécessite RUN_REAL_OCR=1 et les modèles Paddle locaux ; l'avertissement est une dépréciation Starlette/httpx TestClient. Ces résultats testent le logiciel, non la précision de l'IA.

## Contrôle scientifique

Le vrai formulaire de référence compte 30 pages ; le BOQ de sa page physique 25 est vide. Aucun score de prix extraits sur une offre réelle remplie n'est affirmé. Les métriques CDC appartiennent à un corpus de développement, les tests Ask Tender à des questions synthétiques et les latences à une seule exécution locale. La première trace Git visible date du 28/09/2026, après les deux mois administratifs du stage : ni les figures ni le texte n'inventent une chronologie hebdomadaire. Aucun nom de superviseur, gain métier, déploiement de production, pratique Scrum ou tableau Notion non documenté n'a été ajouté.

## Verdict

Le rapport est **prêt pour relecture académique**, avec des limites méthodologiques mises en évidence. Voir REVISION_REPORT.md pour le détail des modifications, MISSING_ASSETS.md pour les pièces utiles et FINAL_MULTIPERSPECTIVE_REVIEW.md pour huit évaluations critiques.
