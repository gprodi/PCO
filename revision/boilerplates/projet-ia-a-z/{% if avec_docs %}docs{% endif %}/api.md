# API

Documentation interactive (OpenAPI) : http://localhost:8001/docs pour l'API d'IA ; l'API de données
n'est joignable que sur le réseau privé (http://api_data:8000/docs depuis un conteneur).

```{eval-rst}
.. automodule:: api_ia.main
   :members: creer_app, ChatIn, ChatOut
.. automodule:: donnees.api
   :members: lister, lire, importer
```
