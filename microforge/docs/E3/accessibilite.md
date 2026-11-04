# Accessibilité : audit axe-core (C9, C10)

**Outil** : axe-core 4.10.3 (Deque, licence MPL-2.0), exécuté dans Chromium par Playwright, règles
WCAG 2.0, 2.1 et 2.2 niveaux A et AA (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`).
Chaque page est auditée en thème clair et en thème sombre. axe détecte automatiquement une partie des
critères seulement (environ un tiers) : navigation au clavier, ordre de lecture et pertinence des textes
restent vérifiés à la main (voir plus bas).

## Résultats du 04/11/2026

| Interface | Pages auditées | Avant | Après |
|---|---|---|---|
| Démo en ligne | 9 vues (Découvrir, Explorer, Mon stock, Copilote avec réponse, Projet : câblage, atelier, code, nomenclature, sources) × 2 thèmes | 29 constats « serious » (vue × thème × règle ; 3 règles, 31 éléments) | **0** |
| Application Streamlit | accueil (connexion, création de compte) × 2 thèmes | 1 constat « serious » (thème clair) | **0** |

## Violations trouvées et corrections

| Règle | Où | Problème | Correction |
|---|---|---|---|
| `html-has-lang` | toutes les vues de la démo | langue de la page non déclarée : un lecteur d'écran lit le français avec une prononciation anglaise | `lang="fr"` posé sur l'élément racine au chargement |
| `aria-prohibited-attr` | bloc « Contrôle électrique » (vues Projet) | `aria-label` sur un `div` sans rôle, donc ignoré | `role="group"` |
| `aria-prohibited-attr` | moniteur série de l'atelier (`microforge/sim/static/atelier.js`) | `aria-label` sur un `pre` sans rôle | `role="log"` (sortie qui défile) avec `aria-live="off"`, pour ne pas faire lire chaque ligne |
| `color-contrast` | légende « Chenillard » de l'accueil, thème clair | cuivre `#b06a2c` sur `#f4f7f5` : 3,93:1 (12,5 px, 4,5:1 exigé) | cuivre `#95561f` : 5,37:1 |
| `color-contrast` | légendes `st.caption` de Streamlit, thème clair | `#6c7672` sur `#f4f7f5` : 4,35:1 ; Streamlit calcule la légende à 60 % du texte et 40 % du fond | texte `#0a1510` : légende à 4,77:1, texte à 17,3:1 |

Les contrastes du thème Streamlit (texte, liens, légendes, texte blanc des boutons principaux, couleur
primaire) sont vérifiés à chaque commit par `tests/test_streamlit_theme.py`.

## Vérifications manuelles
- Navigation au clavier : menus, onglets (flèches gauche/droite), boutons et champs atteignables, focus
  visible (contour de 3 px).
- Le statut n'est jamais porté par la couleur seule : pastilles « bloquant », « attention »,
  « réalisable avec ton stock » écrites en toutes lettres ; couleur des fils Dupont toujours accompagnée
  de son nom.
- Animations (chenillard de l'accueil, apparition des vues) désactivées avec
  `prefers-reduced-motion: reduce`.
- Schéma de câblage SVG avec titre et description.

## Reproduire
- Démo : script d'audit appliqué au fichier assemblé (même méthode, une vue après l'autre).
- Streamlit : `docs/E3/axe/audit_streamlit.cjs`, à lancer pendant que l'application tourne.
