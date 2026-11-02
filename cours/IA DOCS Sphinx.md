# Docs \- SPHINX

![][image1]

[**Objectif :	1**](#objectif-:)

[**Installation \+ principale commande	1**](#installation-+-principale-commande)

[Installation	1](#installation)

[Installer la doc et Read the Doc	1](#installer-la-doc-et-read-the-doc)

[Pour lire le markdown	1](#pour-lire-le-markdown)

[Compiler la documentation (lancer depuis la racine):	1](#compiler-la-documentation-\(lancer-depuis-la-racine\):)

[**Configuration (conf.py)	1**](#configuration-\(conf.py\))

[Changer le thème	2](#changer-le-thème)

[Définir les chemins pour trouver votre code	3](#définir-les-chemins-pour-trouver-votre-code)

[**Autodoc (index.rst)	3**](#autodoc-\(index.rst\))

[Inclure le Readme.md (myst\_parser)	3](#inclure-le-readme.md-\(myst_parser\))

[Créer l’auto doc:	4](#créer-l’auto-doc:)

[Arborescence plus complète	4](#arborescence-plus-complète)

[**Workflow et GitHub Pages	6**](#workflow-et-github-pages)

[GitHub Pages:	6](#github-pages:)

[Workflow	7](#workflow)

[**Encore plus joli	8**](#encore-plus-joli)

[Les commentaires	8](#les-commentaires)

[Bibliographie type BibTex	8](#bibliographie-type-bibtex)

[Installation de l’extension et configuration de conf.py	8](#installation-de-l’extension-et-configuration-de-conf.py)

[Exemple de citation bibtex (Attention is All You Need)	9](#exemple-de-citation-bibtex-\(attention-is-all-you-need\))

[Afficher toutes les références	9](#afficher-toutes-les-références)

[Citer une référence dans la docstring d’un de vos code	10](#citer-une-référence-dans-la-docstring-d’un-de-vos-code)

[Pour générer automatiquement les fichier .rst	10](#pour-générer-automatiquement-les-fichier-.rst)

# 

# Objectif : {#objectif-:}

L’objectif de ce tutoriel est de transformer votre code source en une documentation vivante, structurée et esthétique, capable de survivre à votre départ du projet. En utilisant **Sphinx** avec le thème moderne **Furo** (ou le standard **Read the Docs**), vous apprendrez à générer automatiquement une documentation technique à partir de vos *docstrings*, tout en intégrant des guides utilisateurs en Markdown ou reStructuredText. Nous mettrons l’accent sur la création d'un "contrat de maintenance" clair : chaque module (`app_data`, `app_ia`) doit être capable d'expliquer ses propres schémas de données et ses choix de modèles, garantissant ainsi que votre architecture distribuée reste compréhensible et évolutive pour tout futur collaborateur.

# Installation \+ principale commande {#installation-+-principale-commande}

## Installation  {#installation}

### Installer la doc et Read the Doc {#installer-la-doc-et-read-the-doc}

`uv add --dev "sphinx-rtd-theme>=3.0.0rc1"`

### Pour lire le markdown {#pour-lire-le-markdown}

`uv add myst_parser`

Créer un dossier docs et aller dedans:

`uv run sphinx-quickstart`

## Compiler la documentation (lancer depuis la racine): {#compiler-la-documentation-(lancer-depuis-la-racine):}

`uv run sphinx-build -b html docs/source public`

# Configuration (conf.py) {#configuration-(conf.py)}

Dans le dossier `docs>source>conf.py` on peut gérer la configuration

import sphinx\_rtd\_theme

extensions \= \[  
    'sphinx\_rtd\_theme',  
    'sphinx.ext.autodoc',  \# Pour extraire la doc du code  
    'sphinx.ext.napoleon', \# Pour supporter les docstrings style Google/NumPy  
    'sphinx.ext.mathjax',  \# Pour latex  
    "sphinx.ext.viewcode", \# pour afficher code source  
    "myst\_parser",         \# pour le markdown  
\]

## Changer le thème {#changer-le-thème}

On change

html\_theme \= 'alabaster'

par 

html\_theme \= "sphinx\_rtd\_theme"

On peut aussi ajouter un logo, il faut créer manuellement le dossier `docs/source/_static`:

html\_logo \= "\_static/img/logo.png"

Changer le texte de l’onglet de la page

html\_title \= "Documentation \- Sphinx \- UV"

## Définir les chemins pour trouver votre code {#définir-les-chemins-pour-trouver-votre-code}

import os

import sys

\# On remonte à la racine, puis on descend dans 'app'

sys.path.insert(0, os.path.abspath('../..'))

sys.path.insert(0, os.path.abspath('../../app'))

Au choix, tout dépend si le projet est directement à la racine ou si le projet est rangé dans un dossier de projet (ici app).

# Autodoc (index.rst) {#autodoc-(index.rst)}

Le fichier **`index.rst`** est la **page d'accueil** qui définit la structure de ton site.

Son rôle principal est de contenir la directive `.. toctree::` (Table of Contents Tree). C'est ce bloc qui indique à Sphinx :

1. Quels fichiers inclure dans la documentation.  
2. Dans quel ordre les afficher.  
3. Comment construire le menu de navigation latéral.

**En résumé :** Si un fichier `.rst` ou `.md` n'est pas listé dans `index.rst`, il n'apparaîtra jamais dans ton site final, même s'il existe dans ton dossier.

## Inclure le [Readme.md](http://Readme.md) (myst\_parser) {#inclure-le-readme.md-(myst_parser)}

.. include:: ../../README.md

   :parser: myst\_parser.sphinx\_

## Créer l’auto doc:  {#créer-l’auto-doc:}

Si vous avez votre `api` dans un dossier `mon_api`, je vous conseille de créer un fichier `mon_api.rst` (pour rester consistant) dans le même dossier que `index.rst`.

Puis de l’appeler depuis `mon_api.rst`: 

.. toctree::  
   :maxdepth: 2  
   :caption: Contents:

   self  
   mon\_api

Attention, retour à la ligne obligatoire entre caption et self

et mon\_api.rst sera du genre: 

Documentation de l'api  
**\======================**

Mon application  
**\---------------**

.. automodule:: mon\_api.api  
   :members:  
   :undoc-members:  
   :show-inheritance:

Dans cette exemple votre api : [apy.py](http://apy.py) se trouve dans le dossier mon\_api

## Arborescence plus complète {#arborescence-plus-complète}

Imaginons qu’on ait plusieurs fichiers dans un dossier de l’application, le dossier module qui contiendrait deux fichiers:

* modules/[modules.py](http://modules.py)  
* modules/my\_maths.py

racine/

├── mon\_api/

│   ├── **\_\_init\_\_**.py        \# Indique que mon\_api est un package

│   ├── app.py             \# Ton fichier principal

│   └── modules/

│       ├── **\_\_init\_\_**.py    \# Indique que modules est un sous-package

│       ├── my\_maths.py

│       └── modules.py

├── docs/

│   └── source/

│       ├── conf.py        \# sys.path.insert(0, os.path.abspath('../../'))

│       ├── mon\_api.rst        

│       └── index.rst

└── pyproject.toml

Modules  
**\===================**

Outils Mathématiques  
**\--------------------**

.. automodule:: api.modules.my\_maths  
   :members:  
   :undoc-members:  
   :show-inheritance:

Logique métier  
**\--------------**

.. automodule:: api.modules.modules  
   :members:  
   :undoc-members:  
   :show-inheritance:

.. \_references:

Bibliographie  
**\-------------**

.. \[1\] Schutz, A. (2026). *\*Manuel de Packaging pour l'IA\**.

La citation peut être appelé dans le documentation:

def calculer\_moyenne(data: list) \-\> float:  
    r"""  
    Calcule la moyenne arithmétique d'une liste de nombres.  
    La formule mathématique est la suivante :

    .. math::  
       \\bar{x} \= \\frac{1}{n} \\sum\_{i=1}^{n} x\_i

    Comme indiqué dans la littérature \[1\]\_, la moyenne est sensible  
    aux valeurs aberrantes.

    Args:  
        data (list): Une liste ou un array de nombres.

    Returns:  
        float: La moyenne calculée.  
    """  
    return data.sum() / len(data)

# Workflow et GitHub Pages {#workflow-et-github-pages}

## GitHub Pages:  {#github-pages:}

Sur GitHub, allez dans les `setting` de votre projet et choisissez `Pages`, réglez le `Build and deployment` sur `GitHub Actions` 

![][image2]

## Workflow {#workflow}

Mettre dans le fichier `.github/workflows/docs.yml` 

name: Deploy Documentation

on:  
  push:  
    branches: \[main\] \# Se lance à chaque fois que tu push sur main

permissions:  
  contents: write  
  pages: write  
  id-token: write

jobs:  
  build-docs:  
    runs-on: ubuntu-latest  
    steps:  
      \- name: Checkout code  
        uses: actions/checkout@v4

      \- name: Install uv  
        uses: astral-sh/setup-uv@v3  
        with:  
          version: "latest"

      \- name: Install dependencies  
        run: uv sync \--all-extras \# Installe Sphinx et le thème RTD définis dans le fichier toml

      \- name: Build Sphinx Documentation  
        \# On génère le HTML dans le dossier "public"  
        run: uv run sphinx-build docs/source public

      \- name: Upload artifact  
        uses: actions/upload-pages-artifact@v3  
        with:  
          path: 'public'

  deploy-docs:  
    needs: build-docs  
    runs-on: ubuntu-latest  
    environment:  
      name: github-pages  
      url: \${{ steps.deployment.outputs.page\_url }}  
    steps:  
      \- name: Deploy to GitHub Pages  
        id: deployment  
        uses: actions/deploy-pages@v4

# Encore plus joli {#encore-plus-joli}

## Les commentaires {#les-commentaires}

![][image3]

On peut améliorer le visuel des commentaires en utilisant des lignes commençant par \>\>\>

"""Description de dossier.mon\_module.py  
:cite:p:\`vaswani2023attentionneed\`

\>\>\> exemple d'utilisation  
\>\>\> uv add mon\_module  
\>\>\> from mon\_module import exe\_app  
\>\>\> exe\_app()

"""

## Bibliographie type BibTex  {#bibliographie-type-bibtex}

Le **BibTeX** est un format de fichier standard (`.bib`) permettant de stocker des références bibliographiques de manière structurée et réutilisable. Il est massivement utilisé par les **chercheurs, les universitaires et les ingénieurs** (notamment en IA et Data Science) pour automatiser la citation de sources dans des documents LaTeX ou Sphinx.

### Installation de l’extension et configuration de [conf.py](http://conf.py) {#installation-de-l’extension-et-configuration-de-conf.py}

On installe le package : `uv add sphinxcontrib-bibtex`

Configuration dans [conf.py](http://conf.py) : 

extensions \= \[  
    'sphinx\_rtd\_theme',  
    'sphinx.ext.autodoc',  \# Pour extraire la doc du code  
    'sphinx.ext.napoleon', \# Pour supporter les docstrings style Google/NumPy  
    'sphinx.ext.mathjax',  \# Pour latex  
    "sphinx.ext.viewcode", \# pour afficher code source  
    "myst\_parser",         \# pour le markdown  
    'sphinxcontrib.bibtex',  
\]  
bibtex\_bibfiles \= \['refs.bib'\]

Le fichier `refs.bib` se trouve dans le dossier `source` et contient toutes les citations

### Exemple de citation bibtex (Attention is All You Need) {#exemple-de-citation-bibtex-(attention-is-all-you-need)}

Provenant de [https\://arxiv.org/abs/1706.03762](https://arxiv.org/abs/1706.03762) en cliquant sur **export BibTeX citation**

`@misc{vaswani2023attentionneed,`  
      `title={Attention Is All You Need},`   
      `author={Ashish Vaswani and Noam Shazeer and Niki Parmar and Jakob Uszkoreit and Llion Jones and Aidan N. Gomez and Lukasz Kaiser and Illia Polosukhin},`  
      `year={2023},`  
      `eprint={1706.03762},`  
      `archivePrefix={arXiv},`  
      `primaryClass={cs.CL},`  
      `url={https://arxiv.org/abs/1706.03762},`   
`}`

### Afficher toutes les références {#afficher-toutes-les-références}

Vous pouvez très bien créer un `biblio.rst` et mettre cela dedans

Bibliographie  
**\-------------**

.. bibliography::  
   :filter: cited

### Citer une référence dans la docstring d’un de vos code {#citer-une-référence-dans-la-docstring-d’un-de-vos-code}

On utilise `` :cite:p:`nom_de_le_référence` `` pour afficher (avec lien) la référence.

"""Description de dossier.mon\_module.py

Comme indiqué dans la littérature :cite:p:\`vaswani2023attentionneed\`

"""

### Pour générer automatiquement les fichier .rst {#pour-générer-automatiquement-les-fichier-.rst}

Pour automatiser la création de votre documentation technique, utilisez l'outil `sphinx-apidoc`. Cette commande analyse l'arborescence de votre code source pour générer les fichiers `.rst` nécessaires à Sphinx. Il vous suffit d'indiquer le dossier de destination des fichiers générés (généralement `docs/source/`) suivi du chemin vers votre package Python (par exemple `./app`) :

Si vous voulez mettre à jour votre documentation en écrasant les anciens fichiers et en séparant bien chaque module sur sa propre page, utilisez ceci :

`sphinx-apidoc -f -e -o docs/source/ ./app`

| Option | Description |
| :---- | :---- |
| \-o / \--output-dir | Chemin du répertoire de destination. |
| \-f / \--force | Force l'écrasement des fichiers existants. |
| \-n / \--dry-run | Simule la génération sans créer de fichiers. |
| \-M | Met les modules avant les sous-packages |
| \-e / \--separate | Met chaque module sur sa propre page |

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,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>