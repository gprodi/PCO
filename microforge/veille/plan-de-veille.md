# Plan de veille — MicroForge

## 1. Thématiques (liées au projet, critère C6)

| # | Thématique | Questions suivies | Impact attendu sur le projet |
|---|---|---|---|
| T1 | **Vision embarquée & VLM open-source** | Nouveaux détecteurs (YOLO, RF-DETR), VLM locaux (Qwen-VL, Gemma, Moondream), quantification, performances sur Mac/GPU 6–8 Go | choix du modèle, du profil matériel, benchmark C7 |
| T2 | **Outillage LLM local** | Ollama, LiteLLM, sécurité de la chaîne d'approvisionnement (incidents Trivy / LiteLLM en mars 2026) | paramétrage C8, épinglage des versions |
| T3 | **Réglementation IA & données** | AI Act (Règlement 2024/1689 + omnibus numérique 2026 : art. 50 transparence applicable au 02/08/2026, haut risque reporté), RGPD/CNIL (fiches IA), photos et données personnelles | mentions « contenu généré par IA », registre RGPD |
| T4 | **Accessibilité & éco-conception** | RGAA 4.1, European Accessibility Act (applicable depuis le 28/06/2025), RGESN | critères d'acceptation des user stories, choix d'hébergeur |
| T5 | **Écosystème maker** | Espressif (ESP32-C6/P4), Arduino, Raspberry Pi, Wokwi, KiCad | catalogue, cartes supportées |

## 2. Planning
- **Lundi 9 h – 10 h** : lecture et tri des flux FreshRSS, notation des nouvelles sources (≥ 1 h/semaine exigée).
- **Vendredi 16 h 30 – 16 h 45** : rédaction/relecture de la synthèse hebdomadaire.
- **Fin de mois** : synthèse mensuelle + recommandations pour le backlog.
- Chaque session est tracée dans `journal.md` (date, durée, sources lues, décisions).

## 3. Outils
| Besoin | Outil | Justification |
|---|---|---|
| Agrégation | **FreshRSS auto-hébergé** (Docker) | gratuit, open-source, sobre, export OPML, API ; données chez soi |
| Flux sans RSS | « Releases » GitHub (`/releases.atom`), newsletters redirigées vers FreshRSS | couvre les projets open-source |
| Pré-synthèse | `veille_weekly.py` + LLM local (Ollama) | gain de temps ; **relecture humaine obligatoire** |
| Diffusion | page accessible du site de documentation + message Discord/e-mail à la promo et au formateur | format HTML structuré, lisible par lecteur d'écran |

## 4. Diffusion et accessibilité (recommandations Valentin Haüy / AcceDe)
- Titres hiérarchisés (H1 > H2 > H3), phrases courtes, langage clair, sigles développés à la 1re occurrence.
- Liens explicites (« Lire l'avis CERT-FR sur LiteLLM », jamais « cliquez ici »).
- Alternatives textuelles des images ; aucune information portée uniquement par la couleur.
- Contraste AA minimum ; si PDF : PDF balisé, langue déclarée.
