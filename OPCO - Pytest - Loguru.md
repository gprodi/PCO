# Pytest Loguru

## 

[**Loguru	1**](#loguru)

[Installation et import	1](#installation-et-import)

[Utilisation simple	1](#utilisation-simple)

[Sauvegarde dans un fichier de log	2](#sauvegarde-dans-un-fichier-de-log)

[Configuration	2](#configuration)

[Configuration des fichiers	4](#configuration-des-fichiers)

[Rotation	4](#rotation)

[retention	4](#retention)

[compression	5](#compression)

[enqueue	5](#enqueue)

[Exemple complet (login d’un api)	5](#exemple-complet-\(login-d’un-api\))

[**Pytest pytest documentation	7**](#pytest-pytest-documentation)

[Installation et utilisation	7](#installation-et-utilisation)

[Architecture	7](#architecture)

[Test unitaire simple	8](#test-unitaire-simple)

[Tests multiples avec parametrize	8](#tests-multiples-avec-parametrize)

[Les fixtures pour préparer des données	9](#les-fixtures-pour-préparer-des-données)

[exemple avec une fixture de base de données SQLite	9](#exemple-avec-une-fixture-de-base-de-données-sqlite)

[Test de route d’une API:	10](#test-de-route-d’une-api:)

# Loguru {#loguru}

**Loguru** est une librairie Python qui rend la journalisation (logging) simple, agréable et puissante. Contrairement au module `logging` standard, Loguru offre :

- Une configuration ultra-simple  
- Une sortie colorée par défaut dans le terminal  
- Des infos contextuelles (fichier, ligne, etc.)  
- Une gestion facile des fichiers de logs (rotation, rétention, compression)  
- Un seul logger préconfiguré : `logger`

## Installation et import {#installation-et-import}

Pour installer Loguru, utilisez la commande pip suivante dans votre terminal ou intégrer le dans votre requirements.txt:

pip install loguru

`Pour importer Loguru dans votre code Python, utilisez simplement :`

from loguru import logger

## Utilisation simple {#utilisation-simple}

from loguru import logger

\# Niveaux de log standard (par ordre de sévérité)

\# TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL

logger.trace("Ceci est un message de trace.")

logger.debug("Informations de débogage.")

logger.info("Informations générales.")

logger.warning("Attention")

logger.error("Une erreur s'est produite.")

logger.critical("Erreur critique \!")

Ces différents niveaux de log donne les résultats suivant: 

![][image1]

## Sauvegarde dans un fichier de log {#sauvegarde-dans-un-fichier-de-log}

### **Configuration** {#configuration}

Afin de sauvegarder les informations dans un fichier de log, il faut configurer votre logger : 

from loguru import logger

\# Fichier pour les erreurs et les niveaux critiques

logger.add("errors.log", level\="ERROR", format\="{time} {level} {message}")

\# Fichier pour les avertissements

logger.add("warnings.log", level\="WARNING", format\="{time} {level} {message}")

\# Fichier pour les informations générales

logger.add("info.log", level\="INFO", format\="{time} {level} {message}")

\# Un fichier pour tout, du débogage au critique (si vous le souhaitez)

logger.add("all.log", level\="DEBUG", format\="{time} {level} {message}")

logger.debug("Ceci est un message de débogage.")

logger.info("Informations importantes.")

logger.warning("Attention \!")

logger.error("Une erreur s'est produite.")

logger.critical("Erreur critique \!")

**Loguru enregistre tout ce qui est du niveau spécifié *et supérieur***.

| `TRACE` | `TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| :---: | ----: |
| **`DEBUG`** | **`DEBUG`**, **`INFO`**, **`WARNING`**, **`ERROR`**, **`CRITICAL`** |
| **`INFO`** | **`INFO`**, **`WARNING`**, **`ERROR`**, **`CRITICAL`** |
| **`WARNING`** | **`WARNING`**, **`ERROR`**, **`CRITICAL`** |
| **`ERROR`** | **`ERROR`**, **`CRITICAL`** |
| **`CRITICAL`** | **`CRITICAL`** |

Exemple du fichier warnings.log

2025-04-11T11:13:19.786676\+0200 WARNING Attention \!

2025-04-11T11:13:19.787362\+0200 **ERROR** Une erreur s'est produite.

2025-04-11T11:13:19.788241\+0200 **CRITICAL** Erreur critique \!

## Configuration des fichiers {#configuration-des-fichiers}

Loguru permet de gérer automatiquement la taille, la durée de vie et la compression des fichiers de log grâce à quelques options très simples. Ainsi on peut décider de la taille maximum des fichiers, du taux de compression ou combien de temps on veut garder le fichier. 

logger.add(

	\# Fichier avec timestamp

   	"logs/log\_{time}.log", 

	\# Nouveau fichier tous les 10 Mo

   	rotation\="10 MB",            

	\# Conserver les logs 7 jours

   	retention\="7 days",         

\# Compresser les anciens logs 

   	compression\="zip",          

\# Niveau minimal 

   	level\="DEBUG",               

   	format\="{time} {level} {message}"

)

### **Rotation**  {#rotation}

Quand créer un nouveau fichier. 

- `"10 MB"` → à partir de 10 Mo  
- `"1 week"` → chaque semaine  
- `"00:00"` → chaque jour à minuit

### **retention** {#retention}

Combien de temps ou combien de fichiers garder. 

• `"7 days"` → garde les fichiers 7 jours

• `5` → garde les 5 derniers fichiers

Loguru conserve uniquement les 5 derniers fichiers générés par rotation. Dès qu’un 6ᵉ fichier est créé (suite à une nouvelle rotation), le plus ancien est automatiquement supprimé. 

### **compression** {#compression}

Compression des  anciens fichiers dans différents format : "zip", "gz", "bz2"

### **enqueue** {#enqueue}

Sécurise l’écriture en contexte multi-thread/process (recommandé en cas de logs depuis plusieurs threads/process)

### **Exemple complet (login d’un api)** {#exemple-complet-(login-d’un-api)}

from fastapi import FastAPI, HTTPException, Form

from loguru import logger

app \= FastAPI()

\# \=== CONFIGURATION LOGURU \===

logger.remove()  \# Nettoie la config de base

\# \--- CONFIG DEV \---

logger.add("logs/dev\_{time}.log",

          rotation\="10 MB",

          retention\="7 days",

          compression\="zip",

          level\="TRACE",

          enqueue\=True,

          format\="{time:YYYY-MM-DD HH:mm:ss} \| {level} \| {message}")

\# \--- CONFIG PROD (commentée) \---

\# logger.add("/var/log/app/app.log",

\#            rotation="100 MB",

\#            retention="30 days",

\#            compression="gz",

\#            level="INFO",

\#            enqueue=True,

\#            format="{time:YYYY-MM-DD HH:mm:ss} \| {level} \| {message}")

\# \=== ROUTE LOGIN \===

@app.post("/login")

def login(username: str \= Form(...), password: str \= Form(...)):

   logger.trace("Requête de login reçue")

   logger.debug(f"Tentative de login pour l'utilisateur : {username}")

   try:

       \# Simulation de vérification

       if not username or not password:

           logger.warning("Identifiants manquants")

           raise HTTPException(status\_code\=400, detail\="Identifiants requis")

       \# Simuler un utilisateur en base

       if username \!= "admin":

           logger.info(f"Utilisateur inconnu : {username}")

           raise HTTPException(status\_code\=401, detail\="Utilisateur non trouvé")

       if password \!= "secret":

           logger.warning(f"Mot de passe incorrect pour {username}")

           raise HTTPException(status\_code\=403, detail\="Mot de passe invalide")

       logger.info(f"Connexion réussie pour {username}")

       return {"message": f"Bienvenue, {username}\!"}

   except HTTPException as http\_exc:

       logger.error(f"Erreur de login pour {username} : {http\_exc.detail}")

       raise

   except Exception as e:

       logger.critical(f"Erreur inattendue lors du login : {e}")

       logger.exception("Détail de l'exception")

       raise HTTPException(status\_code\=500, detail\="Erreur serveur")

# Pytest [pytest documentation](https://docs.pytest.org/en/stable/how-to/assert.html) {#pytest-pytest-documentation}

Pytest est un framework de test pour Python à la fois simple et puissant. Il permet d'écrire rapidement des tests unitaires, des tests d'API, et de simuler ("mocker") des objets comme les bases de données. Il fonctionne sans configuration spéciale et reconnaît automatiquement les fichiers et les fonctions de test contenues dans les fichiers.

## Installation et utilisation {#installation-et-utilisation}

Pour installer pytest il suffit d’utiliser pip ou de l’inclure dans le requirements.txt: 

pip install pytest

Il n’est pas toujours nécessaire de l’importer.

Pour exécuter les tests il suffit de lancer :

pytest

dans un terminal, on peut aussi spécifier le dossier ou un des fichiers en particulier:

pytest tests/test\_math.py

## Architecture {#architecture}

Pour bien organiser son code, on range les fichiers de tests dans un dossier tests:

tests/

├── test\_math.py

├── test\_login.py

└── conftest.py  

## Test unitaire simple {#test-unitaire-simple}

Pytest exécute automatiquement les fonctions commençant par `test_` dans les fichiers `test_*.py`.

par exemple, le fichier : `test_math.py`

def add(a, b):

   return a \+ b

def test\_add():

   assert add(2, 3) \== 5

Il faut noter que la fonction add aurait pu être située dans un autre dossier (modules par exemple) et être importée dans le fichier de test. 

## Tests multiples avec parametrize {#tests-multiples-avec-parametrize}

On peut effectuer des séries de tests de la même fonction de test d’un seul coup: 

import pytest

@pytest.mark.parametrize("a, b, result", \[

   (2, 3, 6),

   (0, 10, 0),

   (-1, 5, \-5),

\])

def test\_multiply(a, b, result):

   assert multiply(a, b) \== result

collected 3 items

tests/test\_multiply.py ...                     \[100%\]

\================= 3 passed in 0.01s \=================

## Les fixtures pour préparer des données {#les-fixtures-pour-préparer-des-données}

Une fixture rend accessible aux fonctions des paramètres prédéfinis. 

import pytest

@pytest.fixture

def user():

   return {"username": "admin", "password": "secret"}

def test\_user\_data(user):

   assert user\["username"\] \== "admin"

La fixture `user` est nécessaire à l'exécution du test : `test_user_data` Ici,il s’agit d’un dictionnaire mais cela aurait pu être une donnée issue d’une base de données, d’un fichier ou un objet comme un connecteur etc… 

### **exemple avec une fixture de base de données SQLite** {#exemple-avec-une-fixture-de-base-de-données-sqlite}

import sqlite3  
import pytest

@pytest.fixture

def sqlite\_db():  
   conn \= sqlite3.connect(":memory:")  
   cursor \= conn.cursor()  
   cursor.execute("CREATE TABLE …")  
   cursor.execute("INSERT INTO users … ")  
   conn.commit()  
   yield conn  
   conn.close()

def get\_user\_by\_username(conn, username):  
   cursor \= conn.cursor()  
   cursor.execute("SELECT \* FROM users …", (username,))

   return cursor.fetchone()

## Test de route d’une API:  {#test-de-route-d’une-api:}

from fastapi.testclient import TestClient

from main import app

client \= TestClient(app)

def test\_root\_route():

   response \= client.get("/")

   assert response.status\_code \== 200

   assert response.json()\["message"\] \== "Bienvenue sur l'API"

def test\_faq\_route():

   response \= client.get("/FAQ")

   assert response.status\_code \== 200

   assert "faq" in response.json()

de l’API: 

from fastapi import FastAPI, Form, HTTPException

app \= FastAPI()

@app.get("/")

def root():

   return {"message": "Bienvenue sur l'API"}

@app.get("/FAQ")

def faq():

   return {"faq": "Voici la foire aux questions."}

[image1]: <data:image/png;base64,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>