# Reconstruction factuelle du projet

État examiné : `f292de8` sur `main`, 5 octobre 2026. Le dépôt ne contient pas de journal daté de juillet–août : ses premiers commits accessibles datent du 28 septembre. La chronologie ci-dessous décrit donc **l'ordre attesté par Git**, et ne prétend pas dater chaque réalisation pendant les deux mois de stage. La période du stage et l'identité de l'étudiant proviennent du cahier des charges fourni pour ce rapport.

| Étape attestée | Preuve Git et documentaire | Décision ou résultat |
|---|---|---|
| Base CDC et preuve source | `a829b4a`, `eec78a9`, `docs/CDC_ANALYZER_V1_CONTRACT.md` | Analyseur déterministe, sortie structurée et premier jeu de régression. |
| Bordereau spécialisé | `b4b0d01`, `8aa82ab`, `app/boq/extractor.py` | Extraction de la famille MALE ; conservation des coordonnées de preuve. |
| Contrat générique Document Intelligence | `58d3e89`, `app/document_intelligence/{processor,schemas,geometry}.py` | `DocumentResult` partagé, traitement physique page par page, texte natif ou OCR, géométrie et diagnostics. |
| Intégration API et interface | `39c7974`, `9a947c4`, `1251d3f`, `app/api/workflow_routes.py` | Même preuve documentaire réutilisée par les consommateurs CDC et BOQ ; consultation visuelle de la page source. |
| Corpus de développement et structure V2 | `cc6e456`, `1a62803`, `8b36a7e`, `docs/CDC_ANALYZER_V2_EVALUATION.md` | Pilote sur sept documents, six annotations vérifiées ; amélioration des titres arabes, des parties et lots. Il s'agit d'un corpus de développement, pas d'un test aveugle. |
| Intelligence métier complémentaire | `8f7b5e0`, `6b00aa4`, `c7e097c`, `b93344a` | Obligations, résumé, dossier et normalisation de faits financiers/temporels avec provenance. |
| Workspace et interrogation | `b130e5c`, `e4696ca`, `ac3e642`, `15e062f` | Ask Tender à récupération lexicale, interface unifiée, validation et export CSV du bordereau. |
| Persistance et parcours local | `bd5f383`, `f0d6f48`, `app/api/document_store.py` | Analyses enregistrées, bibliothèque, réouverture, candidat BOQ générique et navigation par preuve. |
| Chiffrage, revue et consolidation | `705e81c`, `f292de8`, `docs/OVERNIGHT_COMPLETION_REPORT.md` | Brouillon de prix séparé de la source, calcul `Decimal`, états de revue, tests et documentation des limites. |

## Problème et évolution architecturale

La couche OCR historique apparaît dans le dépôt comme infrastructure réutilisée depuis un flux de factures ; les commits disponibles commencent après ce travail initial. Le nouveau `DocumentProcessor` retire les règles propres aux factures du contrat générique. Il préserve pour chaque élément le texte brut, la page physique, la boîte, le moteur d'origine et, lorsque disponible, la confiance. Le CDC consomme ce contrat, puis le BOQ et Ask Tender exploitent ses références de preuve. Cette séparation évite de traiter une reconnaissance de caractères comme une compréhension du cahier des charges.

`auto` choisit le texte natif page par page selon une heuristique explicite ; `ocr` et `hybrid` sont aussi disponibles. Une couche texte trompeuse et des pages peu remplies peuvent rendre le choix automatique inadéquat (`docs/DOCUMENT_INTELLIGENCE.md`). Le contrat V1 ne fusionne pas les doublons natifs/OCR en mode hybride. Le parseur MALE connaît la géométrie du formulaire ; le parseur générique essaie une association de colonnes par en-têtes et positions, avec des limites sur cellules fusionnées et continuation multipage. Le document réel de référence est un **gabarit vide** : il permet d'éprouver détection et structure, pas la précision des montants.

## Défauts et corrections observés

| Défaut | Preuve | Correction / limite résiduelle |
|---|---|---|
| Titres arabes non reconnus, parties confondues avec lots | `docs/CDC_ANALYZER_V2_EVALUATION.md`, `app/cdc_analysis/headings.py` | Règles de titres multilingues et types distincts ; faits arabes et OCR scanné encore difficiles. |
| Bornes de source perdues au bordereau | `8aa82ab`, `app/boq/models.py` | Conservation de boîtes et éléments sources dans l'extraction. |
| Décalage des extraits financiers accentués | `docs/OVERNIGHT_COMPLETION_REPORT.md`, `app/cdc_analysis/financial_deadline.py` | Correspondance entre texte normalisé et offsets de la source. |
| En-têtes sur deux lignes et désignations coupées | `f292de8`, `app/boq/generic.py`, tests BOQ | Jointure prudente en gardant les deux preuves ; variations complexes non validées. |
| Risque de confondre montant calculé et valeur du CDC | `705e81c`, `app/boq/pricing.py` | Origines `source`, `user`, `computed`, brouillon indépendant, contrôle d'empreinte. |

## Vérification présente

`pytest -q -rs` exécuté le 5 octobre 2026 : **305 réussis, 1 ignoré, 1 avertissement, 0 échec, 33,40 s**. Le test Paddle réel requiert `RUN_REAL_OCR=1` et les modèles locaux. L'avertissement vient de la compatibilité Starlette/httpx TestClient. Ces nombres sont un état du dépôt au moment de la rédaction, et non une mesure de performance du produit ou une preuve que toutes les fonctions ont été réalisées avant le 31 août.
