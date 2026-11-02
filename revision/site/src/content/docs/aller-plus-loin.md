---
title: Aller plus loin
description: Projets existants, sites pour apprendre, banques de projets, données ouvertes, outils et communautés d'entraide — tout ce qui complète les cours et MicroForge.
---

Cette page regroupe ce qui **n'est pas dans les cours** mais aide à progresser, à trouver des idées ou à se
débloquer. Les liens pointent vers des sites officiels ou des projets reconnus ; vérifie toujours la date
des tutoriels (les API évoluent vite).

## 1. Projets existants proches de MicroForge

Utile pour l'analyse de l'existant (C14), le benchmark (C7) et pour expliquer au jury **ce que MicroForge apporte de plus**.

| Projet | Ce qu'il fait | Ce que MicroForge apporte / ce qu'on peut réutiliser |
|---|---|---|
| [Wokwi](https://wokwi.com) | Simulateur en ligne ESP32, Arduino, Pico | MicroForge **génère** le `diagram.json` et le code à simuler |
| [Tinkercad Circuits](https://www.tinkercad.com) | Circuits et Arduino simulés pour débuter | pédagogie ; MicroForge part du stock réel |
| [Fritzing](https://fritzing.org) | Schémas breadboard / schéma / PCB | ses pièces `.fzp` alimentent le catalogue (pipeline E1) |
| [KiCad](https://www.kicad.org) | Conception de circuits imprimés open-source | MicroForge exporte une netlist importable |
| [Flux](https://www.flux.ai) | Conception de PCB assistée par IA (cloud) | MicroForge vise le maker débutant, local et gratuit |
| [Cirkit Designer](https://www.cirkitdesigner.com) | Schémas de câblage et code pour makers | comparaison fonctionnelle pour le benchmark |
| [InvenTree](https://inventree.org) | Gestion d'inventaire de composants open-source | modèle de données d'inventaire, idée d'intégration (API) |
| [PartsBox](https://partsbox.com) | Inventaire et nomenclatures d'électronique (SaaS) | référence pour la liste d'achat et le stock |
| [Octopart](https://octopart.com) | Moteur de recherche de composants et prix | source d'offres complémentaire (API Nexar) |
| [JLCPCB Parts](https://jlcpcb.com/parts) | Catalogue LCSC | source « base de données » du pipeline E1 (jlcparts) |
| [Kitspace](https://kitspace.org) | Projets matériels open-source avec BOM | inspiration pour les modèles de projets |
| [ESPHome](https://esphome.io) | Firmware ESP32 décrit en YAML | idée : exporter les projets MicroForge en ESPHome |
| [Edge Impulse](https://edgeimpulse.com) | TinyML : IA embarquée sur microcontrôleurs | piste « aller plus loin » : de la vision sur l'ESP32-CAM |

## 2. Électronique & microcontrôleurs

| Site | Pour quoi faire |
|---|---|
| [Random Nerd Tutorials](https://randomnerdtutorials.com) | des centaines de projets ESP32/ESP8266/Arduino détaillés |
| [Last Minute Engineers](https://lastminuteengineers.com) | fonctionnement et câblage de chaque module, très illustré |
| [Arduino Docs](https://docs.arduino.cc) | référence du langage et des cartes officielles |
| [Arduino-ESP32 (Espressif)](https://docs.espressif.com/projects/arduino-esp32/en/latest/) | brochage, Wi-Fi, ADC, PWM… sur ESP32 |
| [Raspberry Pi Documentation](https://www.raspberrypi.com/documentation/) | Pico / Pico W, MicroPython |
| [Adafruit Learn](https://learn.adafruit.com) | guides par capteur et bibliothèques |
| [SparkFun Learn](https://learn.sparkfun.com) | bases de l'électronique (loi d'Ohm, pull-up, niveaux logiques) |
| [PlatformIO](https://docs.platformio.org) | compiler/téléverser depuis VS Code, gestion des bibliothèques |
| [Falstad Circuit Simulator](https://www.falstad.com/circuit/) | comprendre visuellement un pont diviseur, un transistor… |
| [EasyEDA](https://easyeda.com) | schéma + PCB en ligne, lié au catalogue LCSC |
| [Hackster.io](https://www.hackster.io) · [Hackaday.io](https://hackaday.io) · [Instructables](https://www.instructables.com) | banques de projets de la communauté |
| [ESP-WHO (Espressif)](https://github.com/espressif/esp-who) | détection de visages/objets directement sur ESP32 |

## 3. IA, machine learning & MLOps — cours de référence

| Ressource | Niveau | Pourquoi |
|---|---|---|
| [Hugging Face Learn](https://huggingface.co/learn) | débutant → avancé | NLP, LLM, agents, vision — gratuit |
| [Google ML Crash Course](https://developers.google.com/machine-learning/crash-course) | débutant | bases du ML, très clair |
| [Kaggle Learn](https://www.kaggle.com/learn) | débutant | micro-cours pratiques (pandas, ML, vision) |
| [fast.ai](https://course.fast.ai) | intermédiaire | deep learning pratique, du code d'abord |
| [Made With ML](https://madewithml.com) | intermédiaire | de l'expérimentation à la production (MLOps) |
| [Full Stack Deep Learning](https://fullstackdeeplearning.com) | avancé | construire des produits avec le ML et les LLM |
| [MLOps Zoomcamp (DataTalksClub)](https://github.com/DataTalksClub/mlops-zoomcamp) | intermédiaire | MLflow, Prefect, monitoring, déploiement : proche du programme |
| [roadmap.sh — MLOps](https://roadmap.sh/mlops) | tous | carte des compétences pour situer ses lacunes |
| [Hugging Face Papers](https://huggingface.co/papers) | veille | articles de recherche du jour, avec code |

**Documentations officielles des outils du cours** : [FastAPI](https://fastapi.tiangolo.com) ·
[SQLModel](https://sqlmodel.tiangolo.com) · [Pydantic](https://docs.pydantic.dev) ·
[scikit-learn](https://scikit-learn.org/stable/user_guide.html) · [MLflow](https://mlflow.org/docs/latest/) ·
[Prefect](https://docs.prefect.io) · [Docker](https://docs.docker.com) · [Kubernetes (FR)](https://kubernetes.io/fr/docs/home/) ·
[Prometheus](https://prometheus.io/docs/) · [Grafana](https://grafana.com/docs/) · [LangChain](https://python.langchain.com) ·
[LangGraph](https://langchain-ai.github.io/langgraph/) · [LlamaIndex](https://docs.llamaindex.ai) · [Ollama](https://ollama.com/library) ·
[Ultralytics YOLO](https://docs.ultralytics.com) · [Streamlit](https://docs.streamlit.io) · [uv](https://docs.astral.sh/uv/) ·
[Python (FR)](https://docs.python.org/fr/3/).

## 4. Listes « awesome » et banques de projets

| Liste | Contenu |
|---|---|
| [project-based-learning](https://github.com/practical-tutorials/project-based-learning) | tutoriels « apprendre en construisant », tous langages |
| [awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) | applications RAG et agents prêtes à étudier |
| [awesome-production-machine-learning](https://github.com/EthicalML/awesome-production-machine-learning) | outils MLOps classés par catégorie |
| [awesome-mlops](https://github.com/visenger/awesome-mlops) | articles, cours et outils MLOps |
| [awesome-esp](https://github.com/agucova/awesome-esp) | bibliothèques et projets ESP32 |
| [Awesome-arduino](https://github.com/Lembed/Awesome-arduino) | bibliothèques et projets Arduino |
| [public-apis](https://github.com/public-apis/public-apis) | des centaines d'API gratuites (idéal pour E1) |
| [Roboflow Universe](https://universe.roboflow.com) | datasets et modèles de vision annotés |

## 5. Idées de projets pour t'entraîner aux épreuves

| Idée | Épreuves | Sources de données / outils |
|---|---|---|
| Météo locale + qualité de l'air, tableau de bord et prédiction | E1, E3 | [Open-Meteo](https://open-meteo.com) (sans clé), [data.gouv.fr](https://www.data.gouv.fr) |
| Analyse nutritionnelle de produits scannés | E1, E4 | [Open Food Facts API](https://world.openfoodfacts.org/data) |
| Assistant RAG sur la documentation d'un outil (ex. FastAPI) | E2, E3 | LlamaIndex/LangChain + Ollama |
| Classification de déchets par photo (tri sélectif) | E3, E4 | datasets [Roboflow Universe](https://universe.roboflow.com) |
| Station IoT ESP32 qui envoie ses mesures à une API FastAPI + Grafana | E1, E4, E5 | MicroForge + Prometheus |
| Surveillance d'une API avec incident simulé et post-mortem | E5 | Uptime Kuma, Loki, issues GitHub |
| Comparatif de LLM locaux (qualité, latence, énergie) | E2 | Ollama + [CodeCarbon](https://codecarbon.io) |

## 6. Données & API ouvertes (pour E1)

[data.gouv.fr](https://www.data.gouv.fr) · [api.gouv.fr](https://api.gouv.fr/rechercher-api) ·
[data.europa.eu](https://data.europa.eu) · [Kaggle Datasets](https://www.kaggle.com/datasets) ·
[Hugging Face Datasets](https://huggingface.co/datasets) · [Open-Meteo](https://open-meteo.com) ·
[public-apis](https://github.com/public-apis/public-apis).

## 7. Outils pratiques

| Besoin | Outil |
|---|---|
| Schémas d'architecture | [Excalidraw](https://excalidraw.com) · [Mermaid Live](https://mermaid.live) |
| MCD / MLD Merise | [Looping](https://www.looping-mcd.fr) · [dbdiagram.io](https://dbdiagram.io) |
| Maquettes (C14) | [Penpot](https://penpot.app) (open-source) |
| Tester une API | [Bruno](https://www.usebruno.com) (open-source) · `/docs` OpenAPI de FastAPI |
| Expressions régulières / cron | [regex101](https://regex101.com) · [crontab.guru](https://crontab.guru) |
| Git par la pratique | [Learn Git Branching](https://learngitbranching.js.org) · [GitHub Skills](https://skills.github.com) |
| LLM locaux avec interface | [LM Studio](https://lmstudio.ai) · [Open WebUI](https://openwebui.com) |
| Accessibilité | [WAVE](https://wave.webaim.org) · [RGAA](https://accessibilite.numerique.gouv.fr) |
| Éco-conception | [EcoIndex](https://www.ecoindex.fr) · [RGESN](https://ecoresponsable.numerique.gouv.fr) · [CodeCarbon](https://codecarbon.io) |

## 8. Réglementation & bonnes pratiques

[CNIL — IA et RGPD](https://www.cnil.fr/fr/intelligence-artificielle) ·
[AI Act Explorer](https://artificialintelligenceact.eu) ·
[OWASP API Security Top 10](https://owasp.org/API-Security/) ·
[CERT-FR](https://www.cert.ssi.gouv.fr) (avis de sécurité).

## 9. Besoin d'aide ?

| Où | Pour quoi |
|---|---|
| [Zeste de Savoir](https://zestedesavoir.com) · [Developpez.com — forums](https://www.developpez.net/forums/) | questions en français, tous niveaux |
| [Stack Overflow en français](https://fr.stackoverflow.com) · [Stack Overflow](https://stackoverflow.com) | erreurs de code précises (avec un exemple minimal) |
| [Forum Arduino](https://forum.arduino.cc) (section française) | câblage, cartes, bibliothèques |
| [Forum Hugging Face](https://discuss.huggingface.co) | modèles, datasets, Transformers |
| Issues GitHub de l'outil concerné | bug d'une bibliothèque (chercher avant de poster) |
| Le chat de ce site (mode local) | questions sur **tes** cours, avec citations |

**Bien poser une question** : contexte (OS, versions), ce que tu essaies de faire, le message d'erreur
complet, ce que tu as déjà tenté, un exemple minimal reproductible.

## 10. Préparer la certification

- Fiche officielle du titre : [RNCP37827 sur France Compétences](https://www.francecompetences.fr/recherche/rncp/37827/).
- Les pages [Référentiel E1–E5](/PCO/referentiel/) de ce site : critères cochables, cours liés, oral blanc.
- Les [idées de projets par thème](/PCO/idees/) (plantes, maison, sécurité…) pour t'entraîner.
- La [documentation MicroForge](https://github.com/gprodi/PCO/tree/main/microforge/docs) : un dossier pré-rempli par épreuve.
