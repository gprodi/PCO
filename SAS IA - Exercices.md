# 

# Sommaire

# 

[**Numpy	2**](#numpy)

[Exercices:	2](#exercices:)

[**Pyplot	3**](#pyplot)

[Exercices	3](#exercices)

[**Le Pendu	4**](#le-pendu)

[Objectifs pédagogiques :	4](#objectifs-pédagogiques-:)

[Déroulement du projet :	5](#déroulement-du-projet-:)

[1\. Choix d'un mot :	5](#choix-d'un-mot-:)

[2\. Boucle de jeu :	5](#boucle-de-jeu-:)

[3\. Fin de partie :	5](#fin-de-partie-:)

[Astuce:	5](#astuce:)

[**Pierre-feuille-**](#pierre-feuille--ciseaux)  
[**ciseaux	7**](#pierre-feuille--ciseaux)

[**Mini-jeu de devinettes	8**](#mini-jeu-de-devinettes)

[**Création d'un jeu de Morpion	9**](#création-d'un-jeu-de-morpion)

[Objectif :	9](#objectif-:)

[Fonctionnalités clés :	9](#fonctionnalités-clés-:)

[● Affichage de la grille :	9](#affichage-de-la-grille-:)

[● Gestion des tours de jeu :	9](#gestion-des-tours-de-jeu-:)

[● Détection de victoire :	9](#détection-de-victoire-:)

[● Détection de match nul :	9](#détection-de-match-nul-:)

[Fonctions suggérées :	9](#fonctions-suggérées-:)

[Gestion des inputs :	10](#gestion-des-inputs-:)

[Création des fonctions croix et rond :	10](#création-des-fonctions-croix-et-rond-:)

[**Pytest	11**](#pytest)

[mise en oeuvre et installation	11](#mise-en-oeuvre-et-installation)

[astuce pour le chemin	11](#astuce-pour-le-chemin)

[**SAS IA \- Github Actions	12**](#sas-ia---github-actions)

[**Pandas	13**](#pandas)

[Exercices	13](#exercices-1)

[**Pandas Mon premier CRUD	16**](#pandas-mon-premier-crud)

[**Seaborn	17**](#seaborn)

[Exercices	17](#exercices-2)

[Exercice sur le jeu de données "sales\_data" :	19](#exercice-sur-le-jeu-de-données-"sales_data"-:)

[Exercices partie 2	19](#exercices-partie-2)

[**Mini projet de remise en route	21**](#mini-projet-de-remise-en-route)

[Fonctionnalités supplémentaire (quand tout le reste fonctionne):	21](#heading=h.psztw9gwp0mn)

[Projet 1: Zorglangue	22](#projet-1:-zorglangue)

[Son principe est simple :	22](#son-principe-est-simple-:)

[Exemples :	22](#exemples-:)

[Particularités :	22](#particularités-:)

[Projet 2: Code Caesar	23](#projet-2:-code-caesar)

[Objectif :	23](#objectif-:-1)

[Fonctionnalités :	23](#fonctionnalités-:)

[Amélioration:	23](#amélioration:)

[Projet 3-4 : Cryptage d’une image ou d’un texte	23](#projet-3-4-:-cryptage-d’un-texte)

# 

# Numpy {#numpy}

## **Exercices:** {#exercices:}

1. Créez un tableau NumPy contenant les entiers de 1 à 10 (inclus).  
     
2. Créez un tableau NumPy contenant 5 valeurs flottantes générées aléatoirement entre 0 et 1\.  
     
3. Créez une fonction qui prend un tableau NumPy en entrée et renvoie la somme de ses éléments.  
     
4. Créez une fonction qui prend deux tableaux NumPy en entrée et renvoie le produit scalaire de ces deux tableaux (dot product).  
     
5. Créez une fonction qui prend un tableau NumPy en entrée et renvoie un nouveau tableau contenant uniquement les éléments uniques du tableau d'origine.  
     
6. Créez une fonction qui prend un tableau NumPy en entrée et renvoie un nouveau tableau contenant les éléments triés par ordre croissant.  
     
7. Créez une fonction qui prend un tableau NumPy en entrée et renvoie la moyenne, la médiane et l'écart type de ses éléments.  
     
8. Créez une fonction qui prend un tableau NumPy en entrée et renvoie un nouveau tableau où tous les éléments inférieurs à 5 sont remplacés par 0 et tous les éléments supérieurs ou égaux à 5 sont remplacés par 1\.  
     
9. Créez une fonction qui prend un tableau NumPy de nombres entiers en entrée et renvoie un nouveau tableau contenant uniquement les nombres premiers du tableau d'origine.  
     
10. Créez un tableau NumPy 2D de taille 3x3 contenant des valeurs entières générées aléatoirement entre 1 et 10\.  
    

    # Pyplot {#pyplot}

## **Exercices**  {#exercices}

1. Tracer un graphe linéaire des points (x, y) où x \= \[0, 1, 2, 3, 4\] et y \= \[1, 4, 3, 8, 5\].  
     
2. Tracer un histogramme à partir de données aléatoires générées par NumPy.  
     
3. Tracer un diagramme à barres à partir des données suivantes :   
   categories \= \['A', 'B', 'C', 'D', 'E'\], valeurs \= \[25, 30, 15, 20, 10\]  
     
4. Tracer un nuage de points à partir de données aléatoires générées par NumPy.  
     
5. Tracer une courbe sinusoïdale en utilisant NumPy.  
     
6. Tracer deux courbes sur le même graphe à partir des données suivantes :  
   x \= np.linspace(0, 10, 100\)  
   y1 \= np.sin(x)  
   y2 \= np.cos(x)  
     
7. Tracer un diagramme en secteurs (camembert) à partir des données suivantes :  
   categories \= \['A', 'B', 'C', 'D'\], valeurs \= \[30, 25, 15, 20\]  
     
8. Tracer une courbe polynomiale à partir des données suivantes :  
   x \= np.linspace(-5, 5, 100\)  
   y \= 3 \* x\*\*3 \+ 2 \* x\*\*2 \- 8 \* x \+ 5  
     
9. Tracer un diagramme en barres empilées à partir des données suivantes :  
   categories \= \['A', 'B', 'C', 'D'\]  
   valeurs1 \= \[10, 15, 20, 25\], valeurs2 \= \[5, 10, 15, 20\]  
     
10. Tracer un graphique en boîte (boxplot) à partir des données suivantes :  
    data \= \[np.random.normal(0, 1, 100), np.random.normal(2, 1, 100), np.random.normal(-3, 2, 100)\]

    # Le Pendu {#le-pendu}

      
      
      
    ![][image1]  
      
      
    

## **Objectifs pédagogiques :** {#objectifs-pédagogiques-:}

* Manipulation de chaînes de caractères  
* Utilisation de listes et de dictionnaires  
* Conditions et boucles (boucles for et while, conditions if, elif, else)  
* Fonctions  
* Gestion des entrées utilisateur  
* Affichage de résultats à l'écran

## **Déroulement du projet :** {#déroulement-du-projet-:}

1. ### **Choix d'un mot :**  {#choix-d'un-mot-:}

   * Créer une liste de mots.  
   * Utiliser la fonction random.choice pour sélectionner un mot aléatoire.  
   * Créer une variable pour stocker le mot masqué (initialement, une chaîne de caractères composée de tirets “\_” de la même longueur que le mot).

2. ### **Boucle de jeu :**  {#boucle-de-jeu-:}

   * Tant que le joueur n'a pas trouvé le mot et qu'il lui reste des tentatives :  
     * Afficher le mot masqué et le nombre de tentatives restantes.  
       * avec des étoiles ou des underscores. “le pen\*\*” ou “le pen\_\_”  
     * Demander au joueur de deviner une lettre.  
     * Vérifier si la lettre est dans le mot :  
       * Si oui, mettre à jour le mot masqué en remplaçant les tirets correspondants.  
       * Si non, décrémenter le nombre de tentatives et afficher une partie du pendu.

3. ### **Fin de partie :**  {#fin-de-partie-:}

   * Si le joueur a trouvé le mot, afficher un message de victoire.  
   * Sinon, afficher un message de défaite et révéler le mot.

## **Astuce:**  {#astuce:}

- transformer les caractères en minuscule  
- tracer un cercle:

https\://matplotlib.org/stable/api/\_as\_gen/matplotlib.patches.Circle.html

**idée pour l’affichage**

**import matplotlib.pyplot as plt**

**def afficher\_pendu(nb\_erreurs):**

    **"""**

    **Affiche le pendu en fonction du nombre d'erreurs.**

    **"""**

    **plt.figure()  \# Crée une nouvelle figure**

    **\# Dessine la potence**

    **plt.plot(\[0, 1\], \[0, 0\], 'k')  \# Base**

    **plt.plot(\[0.5, 0.5\], \[0, 1\], 'k')  \# Poteau vertical**

    **plt.plot(\[0.5, 1\], \[1, 1\], 'k')  \# Barre horizontale**

    **plt.plot(\[1, 1\], \[0.9, 0.8\], 'k')  \# Corde**

    **\# Dessine le corps du pendu en fonction du nombre d'erreurs**

    **if nb\_erreurs \> 0:\# Tête**

    **if nb\_erreurs \> 1:\# Corps**

    **if nb\_erreurs \> 2:\# Bras gauche**

    **if nb\_erreurs \> 3:\# Bras droit**

    **if nb\_erreurs \> 4:\# Jambe gauche**

    **if nb\_erreurs \> 5:\# Jambe droite**

    **\# Paramètres d'affichage**

    **plt.axis('off')  \# Cache les axes**

    **plt.xlim(-0.2, 1.4)  \# Ajuste les limites de l'axe x**

    **plt.ylim(-0.2, 1.2)  \# Ajuste les limites de l'axe y**

    **plt.show()  \# Affiche le pendu**

# Pierre-feuille- ciseaux {#pierre-feuille--ciseaux}

* Jeu simple contre l'ordinateur.  
* Utilise des variables, des entrées utilisateur, la fonction random.choice pour le choix de l'ordinateur, et des instructions conditionnelles pour déterminer le gagnant.

  # 

  # Mini-jeu de devinettes {#mini-jeu-de-devinettes}

* L'ordinateur choisit un nombre aléatoire entre 1 et 100\.  
* L'utilisateur doit deviner le nombre en un nombre limité de tentatives.  
* L'ordinateur donne des indices (plus grands, plus petits) à chaque tentative.


  # Création d'un jeu de Morpion {#création-d'un-jeu-de-morpion}

## **Objectif :** {#objectif-:}

* Développer un jeu de Morpion en Python où deux joueurs peuvent s'affronter.  
* Utiliser NumPy pour représenter la grille de jeu et gérer les coups des joueurs.  
* Utiliser Matplotlib (Pyplot) pour afficher la grille et les marques (X et O).

## **Fonctionnalités clés :** {#fonctionnalités-clés-:}

* ### **Affichage de la grille :** {#affichage-de-la-grille-:}

  * Afficher une grille 3x3 représentant le plateau de jeu.  
  * Utiliser Pyplot pour dessiner les lignes de la grille.

* ### **Gestion des tours de jeu :** {#gestion-des-tours-de-jeu-:}

  * Alterner les tours entre les deux joueurs.  
  * Demander au joueur courant de saisir les coordonnées de la case où il souhaite placer sa marque.  
  * Vérifier si la case est valide (vide et dans les limites de la grille).  
  * Placer la marque du joueur sur la grille (en utilisant NumPy pour mettre à jour la représentation interne de la grille).  
  * Mettre à jour l'affichage de la grille avec la nouvelle marque.

* ### **Détection de victoire :** {#détection-de-victoire-:}

  * Après chaque coup, vérifier si un joueur a gagné :  
    * Vérifier les lignes, les colonnes et les diagonales pour voir si trois marques identiques sont alignées.  
  * Si un joueur a gagné, afficher un message de victoire et terminer la partie.

* ### **Détection de match nul :** {#détection-de-match-nul-:}

  * Si toutes les cases sont remplies et qu'aucun joueur n'a gagné, afficher un message de match nul et terminer la partie.

## **Fonctions suggérées :** {#fonctions-suggérées-:}

* `afficher_grille(grille)`:  
  * Prend en entrée la grille de jeu représentée par un tableau NumPy.  
  * Utiliser Pyplot pour dessiner la grille et afficher les marques (X et O) aux positions correspondantes.  
* `recuperer_coordonnees()`:  
  * Demande au joueur de saisir les coordonnées de la case (ligne, colonne).  
  * Gère les erreurs de saisie (coordonnées invalides, case déjà occupée).  
  * Retourne les coordonnées valides sous forme d'un tuple (ligne, colonne).  
* `placer_marque(grille, ligne, colonne, joueur)`:  
  * Prend en entrée la grille, les coordonnées et le joueur courant ('X' ou 'O').  
  * Met à jour la grille en plaçant la marque du joueur à la position spécifiée.  
* `verifier_victoire(grille, joueur)`:  
  * Vérifie si le joueur a gagné en alignant trois de ses marques.  
  * Retourne `True` si le joueur a gagné, `False` sinon.  
* `verifier_match_nul(grille)`:  
  * Vérifiez si toutes les cases de la grille sont remplies.  
  * Retourne `True` si match nul, `False` sinon.

## **Gestion des inputs :** {#gestion-des-inputs-:}

* Utiliser `input()` pour demander au joueur de saisir les coordonnées.  
* Utiliser des blocs `try-except` pour gérer les erreurs de saisie (par exemple, si l'utilisateur entre des lettres au lieu de chiffres).  
* Convertir les entrées en nombres entiers à l'aide de `int()`.  
* Valider les coordonnées pour s'assurer qu'elles sont dans les limites de la grille et que la case est vide.

## **Création des fonctions croix et rond :** {#création-des-fonctions-croix-et-rond-:}

* Dans la fonction `afficher_grille`, vous pouvez utiliser `plt.text` pour placer les symboles 'X' et 'O' aux coordonnées correspondantes sur la grille.  
* Vous pouvez personnaliser la taille, la couleur et la police des symboles pour améliorer l'apparence du jeu.  
  


  # 

  # Pytest {#pytest}

## **mise en oeuvre et installation** {#mise-en-oeuvre-et-installation}

* Dans votre environnement virtuel  
  * **`pip install pytest`**  
* Créer un dossier **test** ou **tests** dans lequel vous mettez des fichiers de tests:  
  * un module est testé par un ou plusieur fichier de test  
  * dans un fichier un fonction commençant par **test\_** testera une fonction de votre programme  
* Utilisez la commande suivante pour exécuter les tests:  
  * **`pytest votre_dossier_de_test/`**   
  * **`pytest votre_dossier_de_test/votre_fichier_test.py`** 

## 

  dans des cas plus avancés, regardez la notion de **fixture** pour simuler des inputs particuliers pour des fonctions de type connexion à une base de données etc.. 

  Faites une veille technologique sur Pytest

## **astuce pour le chemin** {#astuce-pour-le-chemin}

import os

import sys

sys.path.insert(0,

                os.path.abspath(

                    os.path.join(

                        os.path.dirname(\_\_file\_\_),

                        ".."

                    ) ))

[Tirez le maximum de ce cours \- Testez votre projet Python \- OpenClassrooms](https://openclassrooms.com/fr/courses/7155841-testez-votre-projet-python/7155848-tirez-le-maximum-de-ce-cours)

# [SAS IA - Github Actions](https://docs.google.com/document/d/1EgYEtMalAhMkZm5m78RHs62w6ngZxsqZOKuqMbj2E8c/edit?usp=sharing) {#sas-ia---github-actions}

# 

# Pandas {#pandas}

## **Exercices** {#exercices-1}

**Exercice 1 \- Chargement de données :**

* Téléchargez le fichier CSV "titanic.csv" à partir du lien suivant : [https\://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv](https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv)  
* Utilisez Pandas pour charger ce fichier dans un DataFrame nommé "titanic\_df".  
* Affichez les 5 premières lignes du DataFrame pour inspecter les données.  
    
  **Exercice 2 \- Exploration des données :**  
* Trouvez le nombre total de passagers dans le Titanic.  
* Déterminez le pourcentage de passagers qui ont survécu.  
    
  **Exercice 3 \- Analyse des âges :**  
* Calculez l'âge moyen des passagers.  
* Trouvez l'âge le plus fréquent des passagers.  
    
  **Exercice 4 \- Filtrage des données :**  
* Créez un nouveau DataFrame "survived\_df" contenant uniquement les passagers qui ont survécu.  
* Créez un nouveau DataFrame "non\_survived\_df" contenant uniquement les passagers qui n'ont pas survécu.  
    
  **Exercice 5 \- Statistiques des tarifs :**  
  Trouvez le tarif minimum, maximum, moyen et médian payé par les passagers.  
    
    
  **Exercice 6 \- Traitement des valeurs manquantes :**  
* Téléchargez le fichier CSV "sales\_data.csv" à partir du lien suivant : [https\://github.com/ine-rmotr-curriculum/FreeCodeCamp-Pandas-Real-Life-Example/blob/master/data/sales\_data.csv](https://github.com/ine-rmotr-curriculum/FreeCodeCamp-Pandas-Real-Life-Example/blob/master/data/sales_data.csv)  
* Chargez le fichier dans un DataFrame nommé "sales\_df".  
* Affichez le nombre de valeurs manquantes dans chaque colonne du DataFrame.  
    
  **Exercice 7 \- Suppression des doublons :**  
* Téléchargez le fichier CSV "GlobalLandTemperaturesByMajorCity.csv" à partir du lien suivant : [https\://www\.kaggle.com/datasets/berkeleyearth/climate-change-earth-surface-temperature-data?select=GlobalLandTemperaturesByMajorCity.csv](https://www.kaggle.com/datasets/berkeleyearth/climate-change-earth-surface-temperature-data?select=GlobalLandTemperaturesByMajorCity.csv)  
* Chargez le fichier dans un DataFrame nommé "duplicate\_df".  
* Supprimez les lignes en double du DataFrame.  
* Afficher la taille des Dataframes avant et après  
    
  **Exercice 8 \- Remplacement des valeurs incorrectes :**  
* Chargez le fichier dans un DataFrame nommé "temperature\_df".  
* Remplacez les valeurs négatives dans la colonne "AverageTemperature" par la valeur absolue de ces valeurs.  
* Afficher le minimum avant et après  
    
  **Exercice 9 \- Extraction de données :**  
* Téléchargez le fichier CSV "email\_jetable.csv" à partir du lien suivant : [https\://sql.sh/ressources/sql-email-jetable/email\_jetable.csv](https://sql.sh/ressources/sql-email-jetable/email_jetable.csv)  
* Chargez le fichier dans un DataFrame nommé "emails\_df".  
* Donnez un nom aux colonnes: \[index, emails\]  
* Créez une nouvelle colonne "extension" contenant uniquement l’extension du domaines des adresses e-mail (com, fr etc…).  
* Affichez les valeurs unique de la colonne “extension”  
    
    
    
  **Exercice 10 \- Transformation de données :**  
* Téléchargez le fichier CSV "student\_grades.csv" à partir du lien suivant : [https\://github.com/DeVerMyst/DEVIA2023/blob/master/data/student\_grades.csv](https://github.com/DeVerMyst/DEVIA2023/blob/master/data/student_grades.csv)  
* Chargez le fichier dans un DataFrame nommé "grades\_df".  
* Donnez un nom aux colonnes: \['ID','salle','note'\]  
* Ajoutez une colonne “note\_dec” qui contient les notes de 0 à 17 (E- à A+)  
* Convertissez les notes pour qu’elles soient entre 0 et 20 en appliquant une fonction  
* Ajoutez une colonne "result" qui contiendra "Réussite" pour les étudiants ayant une note supérieure ou égale à 10, sinon "Échec".

  # 

  # [Pandas Mon premier CRUD](https://docs.google.com/document/d/1NXs0s43JoTvVE1bC2rg71fNTUwu_oyNxBillxfiyWBk/edit?usp=sharing) {#pandas-mon-premier-crud}

  # Seaborn {#seaborn}

## **Exercices** {#exercices-2}

**Exercice 1 \- Visualisation des notes des étudiants :**

a) Chargez le fichier "student\_grades.csv" dans un DataFrame nommé "grades\_df".

b) Utilisez Seaborn pour créer un histogramme représentant la distribution des notes des étudiants.

**Exercice 2 \- Comparaison des notes en fonction des salles :**

a) Utilisez le DataFrame "grades\_df" pour créer un graphique à barres montrant la moyenne des notes des étudiants pour chaque salle.

**Exercice 3 \- Comparaison des notes en fonction du statut de réussite :**

a) Utilisez le DataFrame "grades\_df" pour créer un graphique à barres montrant le nombre d'étudiants ayant réussi et échoué.

**Exercice 4 \- Visualisation de la corrélation entre les variables :**

a) Chargez le fichier "titanic.csv" dans un DataFrame nommé "titanic\_df".

b) Utilisez Seaborn pour créer une matrice de corrélation pour les variables numériques du DataFrame "titanic\_df".

**Exercice 5 \- Comparaison des tarifs en fonction du statut de survie :**

a) Utilisez le DataFrame "titanic\_df" pour créer un graphique en boîte (boxplot) montrant la distribution des tarifs payés par les passagers en fonction de leur statut de survie (survit ou non).

**Exercice 6 \- Visualisation des âges des passagers :**

a) Utilisez le DataFrame "titanic\_df" pour créer un histogramme représentant la distribution des âges des passagers.

**Exercice 7 \- Comparaison des âges en fonction du statut de survie :**

a) Utilisez le DataFrame "titanic\_df" pour créer un graphique en boîte montrant la distribution des âges des passagers en fonction de leur statut de survie.

**Exercice 8 \- Visualisation de la répartition des tarifs :**

a) Utilisez le DataFrame "titanic\_df" pour créer un histogramme représentant la répartition des tarifs payés par les passagers.

**Exercice 9 \- Comparaison des tarifs en fonction de la classe :**

a) Utilisez le DataFrame "titanic\_df" pour créer un graphique en boîte montrant la distribution des tarifs payés par les passagers en fonction de leur classe (1ère, 2ème ou 3ème classe).

**Exercice 10 \- Visualisation de la répartition du genre des passagers**

a) Utilisation du DataFrame "titanic\_df" pour créer un histogramme représentant la répartition des genres.

**Exercice 11 \- Comparaison des âges des étudiants en fonction du statut de réussite :**

D'accord, merci de me fournir les noms corrects des colonnes du fichier CSV "sales\_data.csv". Voici l'exercice mis à jour en utilisant les bonnes colonnes :

## **Exercice sur le jeu de données "sales\_data" :** {#exercice-sur-le-jeu-de-données-"sales_data"-:}

Le jeu de données "sales\_data.csv" contient des informations sur les ventes de produits dans un magasin. Chaque ligne représente une transaction avec les colonnes suivantes :

* \`Date\`: La date de la transaction.  
* \`Product\`: Le nom du produit vendu.  
* \`Unit\_Price\`: Le prix unitaire du produit.  
* \`Order\_Quantity\`: Le nombre d'unités vendues.


**Votre tâche est de réaliser les étapes suivantes :**

a) Chargez le fichier "sales\_data.csv" dans un DataFrame nommé "sales\_df".

b) Affichez les 10 premières lignes du DataFrame pour visualiser les données.

c) Calculez le chiffre d'affaires total réalisé sur l'ensemble des transactions.

d) Tracez un graphique à barres montrant les 5 produits les plus vendus (en termes de quantité) avec le nom du produit sur l'axe des x et la quantité vendue sur l'axe des y.

## **Exercices partie 2** {#exercices-partie-2}

**~~Exercice 12 \- Visualisation de la répartition des notes des étudiants :~~**

~~Utilisez le DataFrame "grades\_df" pour créer un histogramme représentant la répartition des notes des étudiants.~~

**Exercice 13 \- Comparaison des notes des étudiants en fonction de la salle :**

Utilisez le DataFrame "grades\_df" pour créer un graphique en boîte montrant la distribution des notes des étudiants en fonction de la salle.

**Exercice 14 \- Visualisation des tarifs des passagers en fonction de la classe :**

Utilisez le DataFrame "titanic\_df" pour créer un graphique en boîte montrant la distribution des tarifs payés par les passagers en fonction de leur classe.

**Exercice 15 \- Comparaison des tarifs des passagers en fonction du port d'embarquement :**

Utilisez le DataFrame "titanic\_df" pour créer un graphique en boîte montrant la distribution des tarifs payés par les passagers en fonction du port d'embarquement (C \= Cherbourg, Q \= Queenstown, S \= Southampton).

**Exercice 16 \- Visualisation de la répartition des tarifs des passagers :**

Utilisez le DataFrame "titanic\_df" pour créer un histogramme représentant la répartition des tarifs payés par les passagers.

**Exercice 17 \- Comparaison des tarifs des passagers en fonction du sexe :**

Utilisez le DataFrame "titanic\_df" pour créer un graphique en boîte montrant la distribution des tarifs payés par les passagers en fonction du sexe (homme ou femme).

**Exercice 18 \- Visualisation des tarifs des passagers en fonction du statut de survie :**

Utilisez le DataFrame "titanic\_df" pour créer un graphique en boîte montrant la distribution des tarifs payés par les passagers en fonction de leur statut de survie (survécu ou non).

**Exercice 19 \- Comparaison des âges des passagers en fonction du port** d'embarquement 

Utilisez le DataFrame "titanic\_df" pour créer un graphique en boîte montrant la distribution des âges des passagers en fonction du port d'embarquement.

**Exercice 20 \- Visualisation de la répartition des âges des passagers :**

Utilisez le DataFrame "titanic\_df" pour créer un histogramme représentant la répartition des âges des passagers.

# Mini projet de remise en route  {#mini-projet-de-remise-en-route}

En respectant les bonnes pratiques que l’on a vu jusqu’à présent:

- structure app/components  
- readme.md  
- requirements.txt  
- **pytest simple vérifier que le code décodé correspond au code**  
- docstring [SAS IA - DocString](https://docs.google.com/document/d/19Ge_fkfmvAeiq3fE_06Qg-Ya4LYNfH9DtCqbDJcxoIo/edit?usp=sharing)  
- journalisation [SAS IA - Logging](https://docs.google.com/document/d/1PHNeWnjjs86GmLt61PuUndAocbanWS8Byt4V3hjmQ1I/edit?usp=sharing)  
- redmail [SAS IA - Redmail](https://docs.google.com/document/d/1gFpcfXmlVYpUFJ9z_5gKgkyVYZaDKPHJLInCTJUAdLY/edit?usp=sharing)  
- github action \- test automatique [SAS IA - Github Actions](https://docs.google.com/document/d/1EgYEtMalAhMkZm5m78RHs62w6ngZxsqZOKuqMbj2E8c/edit?usp=sharing)


## 

## 

## 

## **Projet 1: Zorglangue**  {#projet-1:-zorglangue}

Ah, vous parlez de la Zorglangue \!

Il s'agit du langage inventé par le célèbre Zorglub, personnage de la bande dessinée Spirou et Fantasio.

### **Son principe est simple :**  {#son-principe-est-simple-:}

On inverse l'ordre des lettres dans chaque mot, tout en conservant l'ordre des mots dans la phrase.

### **Exemples :** {#exemples-:}

"`Bonjour`" devient "`ruojnoB`"

"`Vive Zorglub !`" devient "eviV bulgroZ \!"

"Ceci est un message secret" devient "iceC tse un egassam terces"

### **Particularités :** {#particularités-:}

La ponctuation est conservée à sa place.

Les majuscules restent des majuscules, même après inversion (ex: "Zorglub" devient "bulgroZ").

## 

## **Projet 2: Code Caesar** {#projet-2:-code-caesar}

Le code Caesar est le plus simple algorithme de cryptage possible, il est basé sur un décalage des lettres par une valeur donnée. Exemple avec un décalage de 3

* clair : ABCDEFGHIJKLMNOPQRSTUVWXYZ  
* chiffré : DEFGHIJKLMNOPQRSTUVWXYZABC

### **Objectif :**  {#objectif-:-1}

Implémenter un programme Python qui chiffre et déchiffre du texte en utilisant le chiffrement de César.

### **Fonctionnalités :** {#fonctionnalités-:}

* Chiffrement d'un texte avec une clé donnée (décalage des lettres de l'alphabet).  
* Déchiffrement d'un texte chiffré avec la même clé.  
* Gestion des lettres majuscules et minuscules.  
* Gestion des caractères non alphabétiques (ponctuation, espaces, etc.).  
* Tests unitaires avec Pytest pour vérifier le bon fonctionnement du chiffrement et du déchiffrement.

### **Amélioration:** {#amélioration:}

prendre en compte les majuscules, les espaces et la ponctuation.

## **Projet 3-4 : Cryptage d’un texte** {#projet-3-4-:-cryptage-d’un-texte}

Le projet consiste à crypter un texte en utilisant une clé secrète. Le cryptage des caractères du texte peut être réalisé avec différentes méthodes comme celle de “cryptography” [SAS IA - hash - cryptage](https://docs.google.com/document/d/1EJL0QoB4Z4FXdLuFtGSYvj0lYwg8prAe79kWRyNVcy0/edit?usp=sharing)

### **Objectif :** 

Implémenter un programme Python qui chiffre et déchiffre du texte en utilisant le chiffrement d’une bibliothèque python.

[image1]: <data:image/png;base64,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>