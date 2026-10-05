# Rapport de stage — Aymen Dhieb / UDGroup

Source LaTeX modulaire dans `main.tex`, `config/`, `chapters/`, `bibliography/`, `figures/` et `screenshots/`. Les notes de vérification préalable sont dans `research/`. Le PDF livré est `build/rapport_stage_aymen_dhieb_udgroup.pdf`.

## Compilation

Depuis `report/`, avec une distribution LaTeX contenant `latexmk`, `pdflatex`, `biber`, `biblatex`, `babel-french`, TikZ, `hyperref` et les packages déclarés dans `config/packages.tex` :

```powershell
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error -outdir=build -jobname=rapport_stage_aymen_dhieb_udgroup main.tex
```

`latexmk` exécute les passages LaTeX/Biber nécessaires aux références, aux listes et à la bibliographie. Le PDF final doit compter environ 30–40 pages. Les seuls fichiers produits à versionner sous `build/` sont le PDF final ; les auxiliaires sont ignorés par `report/.gitignore`.

## Vérification

1. Contrôler le code de sortie de `latexmk`.
2. Consulter le journal dans `build/` : aucune référence ou citation non définie, aucun dépassement de boîte ; quelques boîtes sous-remplies dans des tableaux sont tolérées après inspection visuelle.
3. Vérifier le nombre de pages avec `pdfinfo build/rapport_stage_aymen_dhieb_udgroup.pdf`.
4. Rendre des pages avec `pdftoppm` et inspecter couverture, table des matières, chapitres, figures, tableaux et annexe.
5. Depuis la racine du dépôt, exécuter `pytest -q -rs` avant de réutiliser les nombres cités dans le rapport.

La compilation intégrée de l'éditeur Codex a été tentée ; elle n'a pas trouvé ses répertoires standards sur cet hôte. Le PDF livré a été compilé avec MiKTeX local. Une demande d'ouverture de `main.tex` a été envoyée à Codex ; tous les chapitres restent éditables individuellement.
