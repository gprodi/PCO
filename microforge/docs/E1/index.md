# E1 — Base de connaissances composants & prix (C1 à C5)

**Service numérique** : collecter, nettoyer et mettre à disposition les données dont MicroForge a
besoin (caractéristiques des composants, brochages, bibliothèques Arduino, prix fournisseurs).

```{toctree}
:maxdepth: 1

specifications
requetes
agregation
merise
rgpd
api
```

## Contexte du projet (critère C1)
| Élément | Contenu |
|---|---|
| Acteurs | Gaël (développeur, PO délégué), formateur (commanditaire), makers (utilisateurs finaux) |
| Objectifs fonctionnels | catalogue fiable, prix actualisés en euros, brochages, bibliothèques recommandées |
| Objectifs techniques | collecte automatisée et planifiée, jeu unique nettoyé, base relationnelle RGPD, API REST sécurisée |
| Contraintes | budget ≈ 0 €, quotas des API, CGU/robots.txt, 3 machines hétérogènes, données personnelles minimisées |
| Budget | 0 € (offres gratuites : DigiKey/Mouser développeurs, GitHub, Frankfurter, BigQuery 1 To/mois) |
| Organisation | sprints S1–S2 (16/11 → 13/12/2026), cf. [planning](../E4/agile.md) |
