# Streamlit

## 

[Projet Streamlit : Initiation	1](#projet-streamlit-:-initiation)

[Points à aborder	1](#points-à-aborder)

[Streamlit Pages:	4](#streamlit-pages:)

[Titre du projet : Visualisation interactive d'une fonction affine avec Streamlit	4](#titre-du-projet-:-visualisation-interactive-d'une-fonction-affine-avec-streamlit)

[Objectif :	4](#objectif-:)

[Fonctionnalités :	4](#fonctionnalités-:)

[Instructions :	5](#instructions-:)

[Bonus :	5](#bonus-:)

[Streamlit Pages:	6](#streamlit-pages:-1)

[Titre du projet : Création d'un outil d'analyse de données interactif avec Streamlit	6](#titre-du-projet-:-création-d'un-outil-d'analyse-de-données-interactif-avec-streamlit)

[Objectif :	6](#objectif-:-1)

[Fonctionnalités :	6](#fonctionnalités-:-1)

[Instructions :	7](#instructions-:-1)

[Bonus :	7](#bonus-:-1)

[Aller plus loin\! Au-delà de streamlit\!	7](#aller-plus-loin!-au-delà-de-streamlit!)

[**Alternative	7**](#alternative)

## 

## 

# Projet Streamlit : Initiation {#projet-streamlit-:-initiation}

Ce projet vous guidera pas à pas dans la création d'un dashboard interactif avec Streamlit. Vous commencerez par les bases et progresserez vers des fonctionnalités plus avancées, pour finalement obtenir une application complète de visualisation et d'analyse de données.

## Points à aborder {#points-à-aborder}

1. **Installation et configuration**  
   * Installer Streamlit (pip install streamlit).  
   * Créer un fichier hello.py et faites import streamlit as st  
   * Lancer une application Streamlit simple (streamlit run hello.py).  
2. **Affichage de texte**  
   * Afficher un titre (st.title()).  
   * Afficher des en-têtes (st.header(), st.subheader()).  
   * Afficher du texte (st.write()).  
   * Afficher du Markdown (st.markdown()).  
3. **Chargement et affichage de données**  
   * Charger un jeu de données avec Pandas (pd.read\_csv()).  
   * Afficher un DataFrame Pandas (st.dataframe()).  
   * Afficher un tableau statique (st.table()).  
4. **Widgets interactifs**  
   * Créer un bouton (st.button()).  
   * Créer une case à cocher (st.checkbox()).  
   * Créer un champ de saisie de texte (st.text\_input()).  
   * Créer un sélecteur déroulant (st.selectbox()).  
   * Créer un curseur (st.slider()).  
5. **Mise en page**  
   * Utiliser des colonnes (st.columns()).  
   * Utiliser des conteneurs extensibles (st.expander()).  
   * Utiliser des onglets (st.tabs()).  
6. **Visualisation de données**  
   * Créer des graphiques avec Matplotlib (st.pyplot()).  
   * Créer des graphiques interactifs avec Plotly (st.plotly\_chart()).  
   * Créer des graphiques avec Seaborn (st.pyplot() après avoir créé le graphique avec Seaborn).

exemple:

import streamlit as st

import seaborn as sns

import matplotlib.pyplot as plt

\# Charger le jeu de données 'iris'

df\_iris \= sns.load\_dataset('iris')

\# Créer un graphique de paires Seaborn

sns.pairplot(df\_iris, hue\='species')

\# Afficher le graphique dans Streamlit

st.pyplot(plt.gcf())  \# 'plt.gcf()' récupère la figure courante

7. **Filtres et interactions**  
   * Filtrer les données en fonction des sélections de l'utilisateur. C’est à dire que par exemple avec un select, checkbox vous proposez quelle colonne à afficher.  
   * Afficher des informations détaillées sur un élément sélectionné dans un graphique.  
8. **Gestion des fichiers**  
   * Permettre aux utilisateurs de télécharger des fichiers (st.file\_uploader()).  
   * Enregistrer des fichiers générés par l'application (st.download\_button()).  
9. **Intégration avec d'autres bibliothèques**  
   * Intégrer l'application avec d'autres bibliothèques Python (logging pour journaliser.).  
10. **Tests unitaires**  
    * Écrire des tests unitaires pour les fonctions de l'application.  
11. **Documentation**  
    * Créer un fichier README.md pour documenter l'application.  
12. **Versionner votre code**  
    * Utilisez git pour versioner votre code.  
13. **Déploiement**  
    * Déployer l'application sur Streamlit Cloud ou un autre service de déploiement.

**Conseils**

* Commencez par les bases et ajoutez progressivement des fonctionnalités plus avancées.  
* Utilisez des exemples de code et des tutoriels pour vous aider à apprendre.  
* Testez votre application régulièrement pour vous assurer qu'elle fonctionne correctement.  
* Documentez votre code pour le rendre plus compréhensible et maintenable.

Ce projet vous permettra d'acquérir une solide compréhension de Streamlit et de ses fonctionnalités. N'hésitez pas à explorer et à expérimenter pour créer une application qui répond à vos besoins et à vos intérêts.

## 

## 

## **Streamlit Pages:** {#streamlit-pages:}

- créer un dossier: “pages”  
- dans “pages” créer un fichier 0\_fonction\_affine.py  
- faites le projet suivant dans ce fichier

# **Titre du projet :** Visualisation interactive d'une fonction affine avec Streamlit {#titre-du-projet-:-visualisation-interactive-d'une-fonction-affine-avec-streamlit}

## Objectif : {#objectif-:}

Créer une application Streamlit qui affiche une courbe affine de la forme y \= ax \+ b. Les paramètres a (pente) et b (ordonnée à l'origine) seront contrôlés par des sliders interactifs, et le graphique de la fonction sera mis à jour en temps réel lorsque l'utilisateur modifie les valeurs de a ou b.

## Fonctionnalités : {#fonctionnalités-:}

1. **Interface utilisateur :**

   * Afficher un titre principal avec st.title().  
   * Utiliser st.slider() pour créer deux sliders, un pour le paramètre a et un pour le paramètre b.  
   * Définir des valeurs minimales, maximales et par défaut appropriées pour les sliders.  
2. **Calcul de la fonction :**

   * Générer un ensemble de valeurs x sur un intervalle donné (par exemple, de \-10 à 10).  
   * Calculer les valeurs y correspondantes en utilisant la formule y \= ax \+ b et les valeurs de a et b obtenues des sliders.  
3. **Affichage du graphique :**

   * Utiliser Matplotlib (matplotlib.pyplot) pour créer un graphique de la fonction affine ou la bibliothèque altair.  
   * Afficher le graphique dans l'application Streamlit avec st.pyplot().  
4. **Mise à jour en temps réel :**

   * S'assurer que le graphique est mis à jour en temps réel lorsque l'utilisateur modifie les valeurs des sliders.

### Instructions : {#instructions-:}

* Utiliser Streamlit pour créer l'interface utilisateur et gérer les interactions.  
* Utiliser NumPy pour générer les valeurs x et calculer les valeurs y.  
* Utiliser Matplotlib pour créer le graphique de la fonction affine.  
* Structurer le code de manière claire et concise, en utilisant des commentaires pour expliquer les différentes parties.

### Bonus : {#bonus-:}

* Ajouter des options de personnalisation du graphique, comme le choix de la couleur de la courbe ou l'ajout d'un titre et d'étiquettes aux axes.  
* Permettre à l'utilisateur de modifier l'intervalle des valeurs x affichées sur le graphique.  
* Afficher l'équation de la droite (y \= ax \+ b) avec les valeurs actuelles de a et b.  
* Les valeurs de  a et b peuvent être positives ou négatives. 

## 

## **Streamlit Pages:** {#streamlit-pages:-1}

- dans “pages” créer un fichier 1\_data\_analyst.py

faites le projet suivant dans ce fichier

# **Titre du projet :** Création d'un outil d'analyse de données interactif avec Streamlit {#titre-du-projet-:-création-d'un-outil-d'analyse-de-données-interactif-avec-streamlit}

## Objectif : {#objectif-:-1}

Concevoir une application web interactive avec Streamlit qui permet aux utilisateurs de charger un fichier CSV, d'explorer les données, de visualiser des relations entre les variables et de filtrer les données selon différents critères.

## Fonctionnalités : {#fonctionnalités-:-1}

1. **Chargement de données :**

   * Permettre aux utilisateurs de charger un fichier CSV via un widget st.file\_uploader, on utilisera le dataset de video games sale.  
   * Lire et afficher le contenu du fichier CSV avec Pandas.  
2. **Exploration des données :**

   * Afficher les premières lignes du DataFrame avec data.head().  
   * Afficher les statistiques descriptives du DataFrame avec data.describe().  
   * Permettre aux utilisateurs de sélectionner les colonnes à afficher avec st.multiselect.  
3. **Visualisation interactive :**

   * Permettre aux utilisateurs de choisir deux colonnes pour créer un graphique interactif.  
   * Utiliser Seaborn pour créer un nuage de points (sns.scatterplot) et Matplotlib pour gérer la figure.  
   * Afficher le graphique avec st.pyplot().  
4. **Filtrage des données :**

   * Permettre aux utilisateurs de filtrer les données en fonction d'une colonne et d'une valeur spécifique.  
   * Afficher les données filtrées.  
5. **Histogramme :**

   * Permettre aux utilisateurs de sélectionner une colonne numérique pour créer un histogramme.  
   * Permettre aux utilisateurs de choisir le nombre de bacs de l'histogramme avec st.slider.  
   * Afficher l'histogramme avec Matplotlib et st.pyplot().  
6. **Résumé des données :**

   * Afficher un résumé des types de données et des valeurs manquantes avec data.info().

### Instructions : {#instructions-:-1}

* Utiliser Streamlit pour créer l'interface utilisateur et gérer les interactions.  
* Utiliser Pandas pour charger, manipuler et afficher les données.  
* Utiliser Matplotlib et Seaborn pour créer les graphiques.  
* Structurer le code de manière claire et concise, en utilisant des commentaires pour expliquer les différentes parties.

### Bonus : {#bonus-:-1}

* Implémenter des fonctionnalités supplémentaires, comme le choix du type de graphique (nuage de points, histogramme, etc.), l'exportation des graphiques ou le téléchargement des données filtrées.  
* Déployer l'application sur Streamlit Cloud pour la rendre accessible en ligne.

## Aller plus loin\! Au-delà de streamlit\!  {#aller-plus-loin!-au-delà-de-streamlit!}

[https\://github.com/okld/streamlit-elements](https://github.com/okld/streamlit-elements)

# Alternative {#alternative}

[https\://github.com/Avaiga/taipy](https://github.com/Avaiga/taipy)   
[https\://github.com/holoviz/pane](https://github.com/holoviz/pane)l   
[https\://github.com/posit-dev/py-shiny https\://www\.gradio.app/](https://github.com/posit-dev/py-shiny)

