# Données

## Collecte

Cinq types de sources (`collecte/sources.toml`) : API REST, page web (robots.txt respecté), CSV
(Polars), base SQL (requête paramétrée), gros volume (Polars en flux ou Spark). Les dates passent en
ISO 8601, les notes sur 10, les textes sont nettoyés ; la fusion rapproche les œuvres par identifiant
externe puis par titre proche et année, et garde pour chaque champ la source la plus fiable.

## Modèle conceptuel et physique

```mermaid
erDiagram
  OEUVRE ||--o{ IDENTIFIANT_EXTERNE : possede
  OEUVRE {
    int id PK
    string titre
    string cle_titre "unique avec annee"
    int annee
    string auteur
    string genre
    text resume
    float note
    text provenance "champ vers source (JSON)"
    datetime mis_a_jour
  }
  IDENTIFIANT_EXTERNE {
    string source PK
    string valeur PK
    int oeuvre_id FK
  }
```

Aucune donnée personnelle dans cette base. Les comptes de l'interface (adresse et haché Argon2id)
sont dans la base de l'API d'IA, avec droit à l'effacement (`DELETE /auth/moi`).

```{eval-rst}
.. automodule:: donnees.modeles
   :members:
.. automodule:: collecte.fusion
   :members:
```
