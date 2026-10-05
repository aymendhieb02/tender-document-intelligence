# Inventaire des preuves exploitées

Catégories : **réel** = code, document, sortie ou observation existante ; **synthétique** = fixture ou question contrôlée ; **inféré** = interprétation de conception indiquée comme telle. Les documents de `docs/` sont des descriptions de projet, corroborées lorsque possible par le code, les tests et les artefacts versionnés.

| Catégorie / chemin | Ce que l'élément établit | Type | Usage |
|---|---|---|---|
| Code : `app/document_intelligence/processor.py`, `schemas.py`, `geometry.py`, `recognizer.py` | Parcours natif/OCR, `DocumentResult`, géométrie, diagnostic, provenance | Réel | Ch. 3–4, diagrammes |
| Code : `app/cdc_analysis/{pipeline,headings,requirements,financial_deadline,schema}.py` | Hiérarchie, exigences candidates, valeurs temporelles/financières | Réel | Ch. 5 |
| Code : `app/boq/{detect,extractor,generic,validate,pricing,evaluation_v2}.py` | Famille spécialisée, tentative générique, validation, calcul, séparation des cohortes | Réel | Ch. 5–6 |
| Code : `app/ask_tender/service.py` | Récupération lexicale, concepts, chemin rapide et Ollama optionnel | Réel | Ch. 5 |
| Code : `app/api/{workflow_routes,document_store,contracts_v2}.py` | Routes, stockage local, contrat de réponse V2 | Réel | Ch. 5, 7 |
| UI : `app/static/app/pages/{cdc-upload,cdc-workspace,boq-workspace,pricing-workspace,library}.js` | Parcours de chargement, preuves, bordereau, chiffrage, bibliothèque | Réel | Ch. 5 ; captures éventuelles |
| Tests : `tests/document_intelligence`, `tests/cdc_analysis`, `tests/boq`, `tests/ask_tender`, `tests/test_platform_api.py` | Régressions déterministes et intégrations | Réel, souvent données synthétiques | Ch. 4–6 |
| Document : `datasets/boq/male_municipal_maintenance_v1/reference/MM_Cahier-des-charges-type-Entretien.pdf` | 30 pages natives ; Annexe 05 p. 25, cinq lignes structurelles, cases chiffrées vides | Réel | Ch. 5–6, figure possible |
| Vérité terrain : `datasets/boq/.../ground_truth/reference_empty.json` | Étiquettes explicites de valeurs absentes | Réel | Ch. 6 |
| Fixtures : `datasets/boq/.../synthetic/`, `synthetic_ground_truth.json` | Cas contrôlés de nombre français, case manquante, erreur arithmétique, géométrie | Synthétique | Ch. 6 |
| Benchmark : `benchmarks/cdc_real_v1/{metrics_v2,results_v2}.json`, `ground_truth/` | Scores de développement CDC sur six étiquettes vérifiées ; un scan arabe non scoré | Réel, corpus de développement | Ch. 6 |
| Docs : `docs/DOCUMENT_INTELLIGENCE.md`, `docs/CDC_ANALYZER_V2_EVALUATION.md`, `docs/BOQ_COMPLETION_REPORT.md`, `docs/ASK_TENDER_REPORT.md` | Contrats, méthodes, erreurs et limites | Réel documentaire | Ch. 3–6 |
| Docs : `docs/OVERNIGHT_COMPLETION_REPORT.md`, `docs/PERFORMANCE_REPORT.md`, `docs/EVALUATION_FRAMEWORK.md` | Mesures locales, test de bout en bout, séparation des cohortes | Réel documentaire | Ch. 6–7 |
| Exécution : `requirements-lock-win-py311.txt`, `README.md` | Commande locale et dépendances Windows ; aucun Dockerfile trouvé, Linux/Docker non vérifiés | Réel | Ch. 7 |
| Git : `git log --all`, commits détaillés dans `INTERNSHIP_RECONSTRUCTION.md` | Ordre documenté des changements à partir du 28/09/2026 | Réel | Introduction et Ch. 1 |
| Entreprise : <https://udgroup.com.tn/> | Nom, description générale et solutions visibles sur le site officiel | Réel externe | Ch. 1 |

## Limites de preuve

Le dépôt n'atteste pas la date de réalisation de chaque tâche pendant juillet–août. Aucun bordereau réel rempli n'est inclus. La qualité OCR sur scans n'a pas été rejouée dans l'environnement de rédaction : le test à modèle réel est ignoré. Les questions Ask Tender scorées sont synthétiques ; les mesures de vitesse proviennent d'une seule exécution locale documentée. Aucune installation en production, identité de superviseur ou métrique de gain métier n'est prouvée.
