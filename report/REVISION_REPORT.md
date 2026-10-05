# Seconde revue académique et technique

Date : 05/10/2026. Révision documentaire uniquement ; code applicatif inchangé. La version antérieure demeure récupérable au commit **2fe989eccbe86f9dc4bee067c6ccd40d690074b9** de main. Dépôt officiel vérifié : https://github.com/aymendhieb02/tender-document-intelligence.git. Avant modification, Git ne montrait que deux archives préexistantes non suivies ; elles n'ont pas été ajoutées.

## A. Avant

| Mesure | Rapport initial |
|---|---:|
| Pages A4 | 36 |
| Figures | 18 (14 TikZ, 3 captures de l'application, 1 extrait du BOQ réel vide) |
| Tableaux | 13 |
| Références citées | 7 |
| Construction | latexmk à jour, PDF existant, 0 erreur fatale |

Les faiblesses prioritaires étaient l'organisation du stage trop peu explicitée, les contributions personnelles dispersées, la chronologie insuffisamment visualisée, l'état de l'art court, l'absence d'un parcours métier immédiat, la bibliographie limitée et plusieurs diagrammes de boîtes répétitifs. Le chapitre d'évaluation distinguait déjà correctement tests logiciels, données synthétiques, corpus de développement et gabarit réel vide : ce point fort a été conservé.

## B. Changements effectués

| Domaine | Révision |
|---|---|
| Méthodologie | Chapitre 1 restructuré : problème, objectifs, boucle itérative de besoin → hypothèse → implémentation → tests → analyse d'erreurs. Aucun Scrum formel revendiqué. |
| Data Science | Tableau reliant six principes de CRISP-DM au code, aux documents et aux évaluations ; analogie explicite, sans conformité formelle. |
| Organisation / Notion | Rôles de Git/GitHub, tests et navigateur précisés. Le brief étudiant évoque Notion ; aucune capture, export ou pratique détaillée n'a été retrouvée. |
| Chronologie | Figure de la période administrative juillet–août séparée d'une succession fonctionnelle non datée. Les commits visibles commencent après le stage. |
| Contributions | Tableau de six axes rattachés aux modules, tests et à l'unique identité d'auteur Git visible ; limites d'attribution indiquées. |
| Architecture | Figure globale en cinq couches, du PDF/image à l'espace de décision, avec contrat de preuve explicite. |
| Parcours métier | Figure de l'import, de l'analyse, de l'ouverture des preuves, de la consultation, de la revue/chiffrage et de la réouverture locale. |
| État de l'art | Comparaison des règles, modèles documentaires neuronaux et architecture à preuves ; discussion de LayoutLM, LayoutLMv2, LayoutXLM et Donut avec limites de transfert. |
| Bibliographie | Sept références nouvelles, chacune citée dans le texte ; total 14. Titres, auteurs, lieux de publication et liens vérifiés sur les pages des éditeurs, auteurs ou organismes officiels. |
| Raisonnement technique | Justification plus explicite du choix natif/OCR par page, du schéma commun, des extracteurs BOQ spécialisés/génériques, de la récupération avant génération et de la séparation source/utilisateur/calcul. |
| Évaluation | Figure de maturité des preuves ajoutée. Chiffres et réserves du chapitre 6 conservés ; test final réexécuté. |
| Typographie | Expression suspecte de l'annexe remplacée par « multiplication entre prix et quantité » ; contrôle du texte extrait et du rendu. |
| Conclusion | Compétences concrètes de Data Science/IA ajoutées sans nouveau résultat expérimental. |

### Audit des figures

| Décision | Figures initiales | Motif |
|---|---|---|
| Conservées | Pipeline DI, coordonnées, hiérarchie CDC, branchement BOQ, extrait du BOQ vide, trois captures UI | Chacune apporte un contrat, une géométrie, un choix ou une observation distincts. |
| Redessinées | Progression conceptuelle, architecture globale ; cohortes BOQ remplacées par une échelle de maturité | Donner plus tôt la vision d'ensemble et mieux distinguer les niveaux de preuve. |
| Fusionnées dans l'architecture ou le texte | Frontière générique/métier, choix de page, relations du schéma DI, pipeline CDC, chaîne Ask Tender, persistance, origines de prix | Information déjà expliquée par une figure plus forte, un tableau ou un paragraphe. |
| Ajoutées | Boucle de travail, chronologie prudente, parcours métier | Répondre aux questions du jury sur la démarche, l'évolution et l'usage. |

Le résultat est **10 figures techniques vectorielles + 3 captures authentiques de l'application sur fixture synthétique + 1 extrait vectoriel d'un vrai gabarit BOQ vide**. Les trois captures ont conservé leur provenance et leur légende ; aucune capture Notion n'a été simulée.

## C. Fondement des nouvelles affirmations

| Affirmation nouvelle ou renforcée | Fondement | Portée |
|---|---|---|
| Démarche itérative et corrections ciblées | Historique Git, tests, docs/CDC_ANALYZER_V2_EVALUATION.md, docs/OVERNIGHT_COMPLETION_REPORT.md | Reconstruction technique ; pas un journal de cérémonies ou de semaines. |
| Ordre des grandes phases | report/research/INTERNSHIP_RECONSTRUCTION.md et commits du dépôt | Ordre fonctionnel ; dates de juillet–août inconnues. |
| Auteur Git unique | git log --format='%an <%ae>' : aymendhieb02 | Attribution du dépôt, non preuve exclusive de l'effort personnel ou de sa date. |
| Fondation DI et provenance | app/document_intelligence/{processor,schemas,geometry,recognizer}.py, tests associés | Contrat et comportements programmés. |
| Analyse CDC / BOQ / Ask Tender | app/cdc_analysis/, app/boq/, app/ask_tender/, benchmarks/ et tests/ | Fonctionnalités locales et mesures bornées. |
| Workspace, revue, chiffrage, persistance | app/api/, app/static/app/pages/, captures et tests API | Prototype local, sans validation de production. |
| Inspiration CRISP-DM | Phases publiées dans la documentation IBM + correspondance avec les artefacts du dépôt | Analogie rétrospective, pas adhésion formelle. |
| Comparaison de modèles documentaires | Publications originales LayoutLM, LayoutLMv2, LayoutXLM et Donut | État de l'art ; ces modèles ne sont pas implémentés dans le produit. |
| Revue humaine | État de revue du code et publication CHI 2019 sur les interactions humain–IA | Choix d'interface et principe de conception, pas audit de production. |
| Distinction rang de passage / réponse juste | Tests Ask Tender et ouvrage Introduction to Information Retrieval | Les rangs synthétiques ne mesurent pas la vérité de réponses libres. |
| Notion | Mention dans la commande de seconde revue ; aucune preuve dans les fichiers accessibles | Mention déclarative seulement, capture à fournir. |

## D. Contenu refusé ou non ajouté

- Aucun tableau Notion, journal de stage, réunion, sprint ou calendrier hebdomadaire fabriqué.
- Aucune localisation des commits de septembre–octobre dans une semaine de juillet–août.
- Aucune précision numérique de BOQ réel rempli : le seul document de référence est vide.
- Aucun score d'OCR arabe réel, de réponse Ask Tender générale, de gain de temps métier ou de déploiement en production.
- Aucun logo ESPRIT ou nom d'encadrant non fourni.
- Aucune copie décorative des captures de facture historiques ni modification du produit.

## E. Après et contrôle final

| Mesure | Rapport révisé |
|---|---:|
| Pages A4 | 39 |
| Figures | 14 |
| Tableaux | 15 |
| Références citées | 14 |
| Compilation | latexmk -C puis latexmk -pdf, Biber inclus ; réussie |
| Journal LaTeX | 0 erreur fatale, 0 référence/citation non définie, 0 boîte débordante |
| PDF | 0 page vide, 0 caractère de remplacement, 0 indice de mojibake « Ã » |
| Application | pytest -q -rs : 305 réussis, 0 échec, 1 ignoré, 1 avertissement, 33,05 s |

Le PDF final a été rendu avec Poppler et inspecté sous forme de planche contact et de pages détaillées : couverture, méthode, Notion/organisation, contributions, chronologie, architecture, parcours métier, état de l'art, OCR, Tender Intelligence, évaluation, conclusion, bibliographie et annexe. Le dernier changement de mise en page a corrigé l'ordre des étapes « revue/chiffrage → sauvegarde » dans le parcours métier. Les avis LaTeX de boîtes sous-remplies concernent des cellules de tableaux inspectées ; aucun texte coupé n'a été vu.
