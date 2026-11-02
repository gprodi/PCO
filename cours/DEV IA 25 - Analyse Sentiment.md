# Développer une Application Web d'Analyse de Sentiment Basée sur une API  {#développer-une-application-web-d'analyse-de-sentiment-basée-sur-une-api}

[**Développer une Application Web d'Analyse de Sentiment Basée sur une API	0**](#développer-une-application-web-d'analyse-de-sentiment-basée-sur-une-api)

[Contraintes générales pour tous les projets :	1](#contraintes-générales-pour-tous-les-projets-:)

[Installation des Bibliothèques et Préparation du Modèle :	1](#installation-des-bibliothèques-et-préparation-du-modèle-:)

[Bibliothèques :	1](#bibliothèques-:)

[Énoncé :	2](#énoncé-:)

[Actions à mener	2](#actions-à-mener)

[Annexe	4](#annexe)

[L’analyseur de sentiment :	4](#l’analyseur-de-sentiment-:)

[Analyser un sentiment	4](#analyser-un-sentiment)

[Validation des données	5](#validation-des-données)

[Journalisation	6](#journalisation)

[Retourner un dictionnaire valide :	6](#retourner-un-dictionnaire-valide-:)

[Envoyer une requête à l’API et afficher les résultats dans streamlit	7](#envoyer-une-requête-à-l’api-et-afficher-les-résultats-dans-streamlit)

[Gérer les résultats	7](#gérer-les-résultats)

[Gérer les exceptions :	8](#gérer-les-exceptions-:)

[du côté streamlit	8](#du-côté-streamlit)

[du côté Fast API	8](#du-côté-fast-api)

## 

## **Contraintes générales pour tous les projets :** {#contraintes-générales-pour-tous-les-projets-:}

- Un environnement virtuel (.`venv`) pour isoler les dépendances.  
- Un fichier `requirements.txt` doit lister toutes les dépendances du projet.  
- Un fichier `README.md` doit décrire le projet, et les instructions d'installation.  
- Un fichier `.ignore` doit refuser le versionnage du .`venv`.

## **Installation des Bibliothèques et Préparation du Modèle :** {#installation-des-bibliothèques-et-préparation-du-modèle-:}

**Création d'un environnement virtuel :**

- Ouvrez votre terminal ou invite de commandes.  
- Exécutez la commande : `python -m venv .venv`

**Activation de l'environnement virtuel :**

- Sous Windows : `.venv\Scripts\activate`  
- Sous macOS/Linux : `source .venv/bin/activate`

**Installation des dépendances :**

- Assurez-vous d'être dans le répertoire du projet.  
- Exécutez la commande : `pip install -r requirements.txt`  
- Sinon installer les bibliothèques vous même

**Téléchargement du lexique VADER :**

- Exécutez la commande :   
  `python -c "import nltk; nltk.download('vader_lexicon')"`

Ceci télécharge ce dont a besoin le model NLTK VADER pour fonctionner.

## **Bibliothèques :** {#bibliothèques-:}

* `nltk`  
* `fastapi uvicorn`  
* `streamlit`  
* `requests`  
* `pydantic`  
* `loguru`

## 

## **Énoncé :** {#énoncé-:}

Ce projet vise à développer une application web fonctionnelle qui intègre un modèle d'intelligence artificielle simple pour l'analyse de sentiment. L'objectif est de créer une architecture modulaire et réutilisable, en séparant le modèle d’IA, la logique de traitement des données et l'interface utilisateur. Cette application permettra aux utilisateurs de saisir du texte et de recevoir une analyse de son sentiment (positif, négatif, neutre), d’insérer ou de charger une citation et d’analyser le sentiment associé. Ce projet est la continuité du projet sur les citations. Il y aura donc deux API, une pour la base de données et une pour le modèle d’IA

## **Actions à mener** {#actions-à-mener}

**Installation de l'environnement :**  
Suivre les instructions détaillées fournies précédemment pour créer un environnement virtuel Python (.**`venv`**) et y installer toutes les dépendances nécessaires et un fichier requirements.txt.

**Création des fichiers et dossiers :**  
Créer les dossiers/fichiers **`API/sentiment_api.py`** et **`APP/sentiment_streamlit.py`** à la racine du projet. Créer un dossier **`logs/`** pour stocker les fichiers journaux.

**Initialisation du dépôt GitHub :**  
Initialiser un nouveau dépôt sur Github et créer un fichier **`.gitignore`**

**Test du modèle de manière simple (Anglophone):**  
Dans un un notebook de développement, importer **`SentimentIntensityAnalyzer`** de **`NLTK`**. Créer une instance de l'analyseur et tester l'analyse de sentiment sur un mot ou une courte phrase :

from nltk.sentiment import SentimentIntensityAnalyzer  
sia \= SentimentIntensityAnalyzer()  
sentiment \= sia.polarity\_scores("bonjour")  
print(sentiment)

Vérifiez que le dictionnaire de scores de polarité est correctement retourné.

**Variables d’environnement :**

Création d’un fichier **`.env`** pour la gestion des variables d’environnement tel que le **`host`**, le **`port`**.

**Création de l'API\_IA FastAPI :**

Dans le fichier **`API_IA/sentiment_api.py`**, implémenter un point de terminaison **`/analyse_sentiment/`** qui reçoit du texte via une requête POST. Utiliser le modèle VADER pour analyser le sentiment du texte reçu. Retourner le dictionnaire contenant les quatre mesures de sentiment (négatif, neutre, positif, composé) au format JSON.

**Ajout de la validation de données :**

Utiliser **`Pydantic`** pour définir un modèle de données (par exemple, Texte) qui valide le format du texte reçu par l'API.

**Ajout de la journalisation (API) :**

Intégrer la bibliothèque loguru pour journaliser les requêtes, les résultats de l'analyse et les éventuelles erreurs dans le fichier **`API_IA/logs/sentiment_api.log`**.

**Création de l'interface Streamlit :**

Dans le fichier **`APP/app.py`**, utiliser l’interface utilisateur de citations, dans la page pour rechercher une citation par son **`ID`** ajouté un bouton "**`Analyser`**" une fois que la citation est affichée. Utiliser la bibliothèque **`requests`** pour envoyer le texte saisi à l'**`API_IA`** FastAPI via une requête **`POST`**. Afficher les résultats de l'analyse de sentiment renvoyés par l'API.

**Ajout de la journalisation (Streamlit) :**

Utiliser loguru pour journaliser les entrées de l'utilisateur, les résultats de l'API et les éventuelles erreurs dans le fichier **`logs/sentiment_streamlit.log`**.

![][image1]

# Annexe {#annexe}

## **L’analyseur de sentiment :** {#l’analyseur-de-sentiment-:}

La classe **`SentimentIntensityAnalyzer`** de NLTK, une fois initialisée avec

from nltk.sentiment import SentimentIntensityAnalyzer  
sia \= SentimentIntensityAnalyzer()

permet d'analyser le sentiment d'un texte anglais donné. Elle prend en entrée une chaîne de caractères (le texte à analyser) et renvoie un dictionnaire contenant quatre scores de polarité : 

- neg (négatif)  
- neu (neutre)  
- pos (positif)  
- compound. 

Les scores **`neg`**, **`neu`** et **`pos`** représentent respectivement la proportion de mots du texte considérés comme **`négatifs`**, **`neutres`** ou **`positifs`**, chacun étant un nombre réel entre 0 et 1\. 

Le score **`compound`**, quant à lui, est une métrique normalisée calculée à partir des trois autres scores, qui résume l'intensité du sentiment global du texte, variant de \-1 (sentiment extrêmement négatif) à \+1 (sentiment extrêmement positif). Ainsi, l'outil prend du texte brut en entrée et produit une mesure quantitative du sentiment exprimé dans ce texte.

Exemple d’un log de sortie pour le mot “congratulation\!”

2025-04-03 18:21:29.966 \| INFO     \| \_\_main\_\_:\<module\>:13 \- Texte à analyser: congratulation\!  
2025-04-03 18:21:29.977 \| INFO     \| \_\_main\_\_:\<module\>:30 \- Résultats affichés: {'neg': 0.0, 'neu': 0.0, 'pos': 1.0, 'compound': 0.636}

###  **Analyser un sentiment** {#analyser-un-sentiment}

La fonction **`sia.polarity_scores()`** est au cœur de l'analyse de sentiment réalisée par l'API. Elle prend en entrée un texte et détermine sa polarité émotionnelle. Dans notre cas spécifique, cette fonction ne reçoit pas directement une simple chaîne de caractères, mais plutôt un objet **`texte`** géré par **`Pydantic`**. 

sentiment \= sia.polarity\_scores(texte\_object.texte)

##  **Validation des données** {#validation-des-données}

**`Pydantic`**, une bibliothèque Python pour la validation de données et la gestion des paramètres, permet de définir des modèles de données en utilisant des annotations de type Python standard.

from pydantic import BaseModel  
class Texte(BaseModel):  
    texte: str

**`BaseModel`** sert de classe de base pour la création de ces modèles. La classe **`Texte`** qui hérite de `BaseModel` définit un modèle de données simple avec un seul champ : **`texte`**. L'annotation de type **`str`** indique que ce champ doit contenir une chaîne de caractères.

Concrètement, cela signifie que lorsque l'API FastAPI reçoit une requête contenant des données qui devraient correspondre au modèle **`Texte`**, **`Pydantic`** s'assure que :

* Les données reçues contiennent un champ nommé "texte".  
* La valeur de ce champ est bien une chaîne de caractères.

Si les données ne correspondent pas à ces critères, **`Pydantic`** lève une exception, signalant une erreur de validation. Cela garantit que les données entrantes respectent le format attendu, ce qui est essentiel pour la fiabilité et la sécurité de l'API.

Ainsi, cette approche permet :

* Une validation automatique des données.  
* Une documentation claire du format des données attendues (url/docs).  
* Une réduction des risques d'erreurs dues à des données mal formées.

Par exemple pour appliquer le modèle Pydantic comme paramètre de la fonction appelée par la route **`analyse_sentiment/`**

@app.post("/analyse\_sentiment/")  
async def analyse\_sentiment(texte\_object: Texte):

## 

## **Journalisation** {#journalisation}

La bibliothèque **`loguru`** est utilisée pour la journalisation (logging) dans l'application, offrant une manière simple et puissante de suivre les événements et les erreurs. La ligne 

\# Configuration de Loguru  
logger.add("logs/sentiment\_api.log", rotation\="500 MB", level\="INFO")

configure **`loguru`** pour enregistrer les messages dans un fichier nommé "sentiment\_api.log" situé dans le dossier "logs/". 

La rotation de fichier est activée, de sorte que lorsque le fichier atteint 500 MB, un nouveau fichier de log est créé, évitant ainsi un fichier de log excessivement volumineux. Seuls les messages de niveau "**`INFO`**" et supérieur (comme les erreurs) seront enregistrés. 

Ensuite, l'appel 

sentiment \= sia.polarity\_scores(texte\_object.texte)  
logger.info(f"Résultats: {sentiment}")

enregistre un message d'information indiquant qu'une analyse de texte est en cours, incluant le texte analysé dans le message. Cela permet de suivre les requêtes reçues par l'API, les données traitées et de faciliter le débogage en fournissant un historique détaillé des opérations.

## **Retourner un dictionnaire valide :** {#retourner-un-dictionnaire-valide-:}

Un dictionnaire est un type de données composés de clés/valeurs entourées par des accolades, la structure en est la suivante.

        return {  
            "neg": sentiment\["neg"\],  
            "neu": sentiment\["neu"\],  
            "pos": sentiment\["pos"\],  
            "compound": sentiment\["compound"\],  
        }

## 

## **Envoyer une requête à l’API et afficher les résultats dans streamlit** {#envoyer-une-requête-à-l’api-et-afficher-les-résultats-dans-streamlit}

On effectue une requête HTTP POST vers l'API FastAPI située à **`http://127.0.0.1:XXXX/analyse_sentiment/`**, en envoyant le texte saisi par l'utilisateur sous forme de JSON. Il vérifie ensuite que la réponse de l'API ne contient pas de codes d'erreur HTTP (4xx ou 5xx). Si la requête est réussie, il extrait les résultats de l'analyse de sentiment (scores de polarité) de la réponse JSON et les affiche dans l'interface Streamlit.

response \= requests.post("http\://127.0.0.1:9000/analyse\_sentiment/", json\={"texte": texte})

\# Lève une exception pour les codes d'erreur HTTP (4xx ou 5xx)  
response.raise\_for\_status() 

sentiment \= response.json()

st.write("Résultats de l'analyse :")  
st.write(f"Polarité négative : {sentiment\['neg'\]}")  
st.write(f"Polarité neutre : {sentiment\['neu'\]}")  
st.write(f"Polarité positive : {sentiment\['pos'\]}")  
st.write(f"Score composé : {sentiment\['compound'\]}")

## **Gérer les résultats** {#gérer-les-résultats}

On interprète le score de sentiment composé (**`sentiment['compound']`**) renvoyé par VADER pour catégoriser le sentiment global du texte comme positif, négatif ou neutre, et affiche le résultat correspondant dans l'interface Streamlit. La journalisation avec **`loguru`** enregistre également le score de sentiment complet.

if sentiment\['compound'\] \>= 0.05 :  
	st.write("Sentiment global : Positif 😀")  
elif sentiment\['compound'\] \<= \-0.05 :  
	st.write("Sentiment global : Négatif 🙁")  
else :  
	st.write("Sentiment global : Neutre 😐")  
	logger.info(f"Résultats affichés: {sentiment}")

 

## 

## **Gérer les exceptions :** {#gérer-les-exceptions-:}

Les blocs **`try...except`** côté client et serveur garantissent la robustesse de l'application. Le client gère les erreurs de communication avec l'API, informe l'utilisateur et journalise pour le débogage, tandis que le serveur gère les erreurs d'analyse, renvoyant des réponses d'erreur HTTP claires.

#### du côté streamlit {#du-côté-streamlit}

if st.button("Analyser"):  
\# Si il y a du text alors  
    if texte:  
        logger.info(f"Texte à analyser: {texte}")  
        try:

            \# envoie du texte à l’API  
            response \= requests.post("http\://127.0.0.1:9000/analyse\_sentiment/", json\={"texte": texte})

	  \# traitement de la réponse  
        except requests.exceptions.RequestException as e:  
            st.error(f"Erreur de connexion à l'API : {e}")  
            logger.error(f"Erreur de connexion à l'API : {e}")  
        except Exception as e :  
            st.error(f"Une erreur est survenue: {e}")  
            logger.error(f"Une erreur est survenue: {e}")  
    else:  
        st.write("Veuillez entrer du texte pour l'analyse.")

#### du côté Fast API {#du-côté-fast-api}

@app.post("/analyse\_sentiment/")  
async def analyse\_sentiment(texte\_object: Texte):  
    logger.info(f"Analyse du texte: {texte\_object.texte}")  
    try:  
        sentiment \= sia.polarity\_scores(texte\_object.texte)  
        logger.info(f"Résultats: {sentiment}")

        \# on retourne la réponse

    except Exception as e:  
        logger.error(f"Erreur lors de l'analyse: {e}")  
        raise HTTPException(status\_code\=500, detail\=str(e))

[image1]: <data:image/png;base64,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>