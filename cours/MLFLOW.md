# MLFlow

## 

[Suivi des Performances avec MLflow	2](#suivi-des-performances-avec-mlflow)

[Prérequis :	2](#prérequis-:)

[Introduction :	2](#introduction-:)

[Partie 1 : Qu'est-ce que MLflow ?	2](#partie-1-:-qu'est-ce-que-mlflow-?)

[Partie 2 : Structure du projet	2](#partie-2-:-structure-du-projet)

[Partie 3 : Code minimal avec tracking	3](#partie-3-:-code-minimal-avec-tracking)

[Partie 4 : Lancer MLflow UI	3](#partie-4-:-lancer-mlflow-ui)

[Partie 5 : Ajouter des paramètres	4](#partie-5-:-ajouter-des-paramètres)

[Partie 6 : Automatiser le réentraînement avec Luigi (bonus)	4](#heading=h.gqquznm9vuti)

[Enregistrer un modèle avec MLflow	5](#enregistrer-un-modèle-avec-mlflow)

[Charger un modèle avec MLflow	5](#charger-un-modèle-avec-mlflow)

## 

## 

# Suivi des Performances avec MLflow {#suivi-des-performances-avec-mlflow}

## Prérequis : {#prérequis-:}

* Environnement virtuel `(.venv)` configuré.  
* Fichier requirements.txt contenant les dépendances nécessaires (mlflow, scikit-learn, pandas, matplotlib).  
* Avoir un modèle de machine learning simple  
* Fichier README.md décrivant l'installation et les routes de l'API.

## Introduction : {#introduction-:}

Ce projet vous guide dans l’utilisation de **MLflow**, un outil de tracking de machine learning, pour suivre les performances d’un modèle qui est régulièrement réentraîné avec de nouvelles données. L’objectif est de mesurer les changements de performance (ex: accuracy, RMSE) entre différentes versions du modèle.

### **Partie 1 : Qu'est-ce que MLflow ?** {#partie-1-:-qu'est-ce-que-mlflow-?}

MLflow est une plateforme open-source permettant de gérer le cycle de vie d’un projet de machine learning. Elle offre quatre composants principaux :

* **Tracking** : enregistrer les expériences, hyperparamètres, métriques et artefacts.  
* **Projects** : organiser et reproduire des projets ML.  
* **Models** : gérer les modèles pour les déployer facilement.  
* **Registry** : versionner et approuver les modèles dans un registre central.

Dans ce projet, on se concentre sur **MLflow Tracking**.

### **Partie 2 : Structure du projet** {#partie-2-:-structure-du-projet}

Créez un fichier `train.py` contenant le script de réentraînement et de tracking. L’idée est que chaque fois qu'on lance ce script, une nouvelle exécution est enregistrée.

### **Partie 3 : Code minimal avec tracking** {#partie-3-:-code-minimal-avec-tracking}

import mlflow

from sklearn.linear\_model import LinearRegression

from sklearn.metrics import mean\_squared\_error

from sklearn.model\_selection import train\_test\_split

from sklearn.datasets import make\_regression

\# Générer un jeu de données de régression synthétique

X, y \= make\_regression(n\_samples\=1000, n\_features\=5, noise\=0.1, random\_state\=42)

X\_train, X\_test, y\_train, y\_test \= train\_test\_split(X, y)

\# MLflow tracking

with mlflow.start\_run():

    model \= LinearRegression()

    model.fit(X\_train, y\_train)

    preds \= model.predict(X\_test)

   

    mse \= mean\_squared\_error(y\_test, preds)

    mlflow.log\_metric("mse", mse)

    mlflow.sklearn.log\_model(model, "model")

### **Partie 4 : Lancer MLflow UI** {#partie-4-:-lancer-mlflow-ui}

Dans le terminal:

mlflow ui

Allez sur [http\://localhost:5000](http://localhost:5000) pour visualiser vos expériences : nom de run, timestamp, hyperparamètres, métriques, et version du modèle.

### **Partie 5 : Ajouter des paramètres** {#partie-5-:-ajouter-des-paramètres}

On peut aussi sauvegarder les paramètres propres à l’expérience

with mlflow.start\_run():

    alpha \= 0.5  \# exemple fictif si on utilisait Ridge

    mlflow.log\_param("alpha", alpha)

## Enregistrer un modèle avec MLflow {#enregistrer-un-modèle-avec-mlflow}

import mlflow

import mlflow.sklearn

from sklearn.linear\_model import LinearRegression

from sklearn.datasets import make\_regression

from sklearn.model\_selection import train\_test\_split

\# Créer un jeu de données synthétique pour l'exemple

X, y \= make\_regression(n\_samples\=1000, n\_features\=5, noise\=0.1, random\_state\=42)

X\_train, X\_test, y\_train, y\_test \= train\_test\_split(X, y, test\_size\=0.2, random\_state\=42)

\# Initialiser et entraîner le modèle

model \= LinearRegression()

model.fit(X\_train, y\_train)

\# Enregistrer le modèle dans MLflow

\# Démarre une nouvelle exécution MLflow

with mlflow.start\_run():  

    \# Enregistrer le modèle

    mlflow.sklearn.log\_model(model, "linear\_regression\_model")  

   \# Optionnel : enregistrer des paramètres

    mlflow.log\_param("model\_type", "linear\_regression")

    print("Le modèle a été enregistré avec succès dans MLflow.")

## Charger un modèle avec MLflow {#charger-un-modèle-avec-mlflow}

\# Charger le modèle depuis MLflow

loaded\_model \= mlflow.sklearn.load\_model("runs:/\<run\_id\>/linear\_regression\_model")

\# Faire des prédictions avec le modèle chargé

predictions \= loaded\_model.predict(X\_test)

print("Predictions : ", predictions)