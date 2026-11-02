# Analyse du besoin — user stories (C14)

**Personas** : *Léa*, maker débutante (a un kit Arduino, ne sait pas quoi en faire) ; *Karim*, animateur
de fablab (gère un stock partagé, prépare des ateliers) ; *Gaël*, étudiant (prototypage rapide ESP32).

| # | En tant que… je veux… afin de… | Critères d'acceptation (dont RGAA 4.1) |
|---|---|---|
| US1 | maker, photographier mon stock pour obtenir l'inventaire | ≥ 80 % des composants courants reconnus ; résultat affiché **aussi sous forme de liste texte** (RGAA 1.1, 1.3) ; photo sans EXIF |
| US2 | maker, corriger une détection | tableau éditable **au clavier** (RGAA 7.1, 12.8) ; libellés de champs explicites (11.1) |
| US3 | maker, voir les projets réalisables avec mon stock | tri par faisabilité ; statut indiqué par texte + icône, jamais par la couleur seule (3.1) |
| US4 | maker, obtenir câblage, code et guide de soudure | tableau de câblage avec en-têtes (5.6) ; SVG avec `title`/`desc` (1.1) ; code compilable |
| US5 | maker, décrire un projet en langage naturel | réponse < 60 s ; composants issus du catalogue ; mention « généré par IA » |
| US6 | maker, connaître la liste d'achat et son coût | total TTC ; liens fournisseurs explicites (6.1) |
| US7 | maker, simuler avant de souder | export `diagram.json` Wokwi ; composants non simulables listés |
| US8 | maker, téléverser le firmware depuis le navigateur | WebSerial (PWA) ; message d'erreur clair si navigateur incompatible |
| US9 | maker, exporter vers KiCad | netlist importable dans l'éditeur de PCB |
| US10 | utilisateur, exporter ou supprimer mes données | export JSON ; suppression confirmée (case + bouton) |
| US11 | animateur, partager un stock | (phase 2) |

Format détaillé (contexte, scénarios Gherkin, critères) : gabarit `.github/ISSUE_TEMPLATE/user-story.md` ; chaque US est une issue GitHub.
