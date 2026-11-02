# Modélisation des données et des parcours (C14)

- **Données** : MCD Merise de l'application → voir [E1 Merise](../E1/merise.md) (tables utilisateur, inventaire, projet, photo, retour).
- **Parcours principal** :

```mermaid
flowchart TD
  A[Accueil / connexion] --> B[Photographier le stock]
  B --> C{Résultat correct ?}
  C -- non --> D[Corriger dans le tableau] --> E[Ajouter au stock]
  C -- oui --> E
  E --> F[Que puis-je construire ?]
  F --> G[Choisir un projet]
  A --> H[Je veux construire…]
  H --> G
  G --> I[Câblage · Schéma · Code · Guide · Wokwi · KiCad]
  I --> J[Télécharger le zip] & K[Liste d'achat]
```

Maquettes (Penpot, open-source) : `docs/E4/maquettes/` (exports PNG + lien du fichier Penpot).
