---
title: Mode d'emploi
description: Réviser en ligne, utiliser l'application locale, ajouter un cours, générer les podcasts.
---

## Réviser en ligne (site publié)
Tout fonctionne sans compte : tes scores de QCM, l'état des flashcards (répétition espacée FSRS) et les
check-lists du référentiel sont enregistrés **dans ton navigateur** uniquement.

## Application locale (IA sur ta machine)
```bash
uv sync --all-packages
uv run llm-gateway doctor          # vérifie ta machine et les modèles Ollama conseillés
uv run revise seed && uv run revise export   # contenu + données du site
uv run revise index                 # index sémantique pour le chat (une fois, avec Ollama)
uv run revise start                 # API locale (port 8765) + site, ouvre le navigateur ; Ctrl+C arrête tout
```
http://localhost:4321/PCO/ s'ouvre : le **chat**, l'**ajout de cours** et l'**oral blanc** sont actifs.
Marche sous Windows, macOS et Linux (la première fois, `revise start` installe aussi les dépendances du site).

## Ajouter un cours
- Depuis le site local : page « Ajouter un cours » (PDF, PowerPoint, Word, HTML, Markdown, notebook, texte ou URL).
- En ligne de commande : `uv run revise add chemin/vers/cours.pdf --theme mlops` ou `uv run revise add https://…`.
- Le cours est converti, découpé, indexé, puis l'IA locale génère fiche, QCM, flashcards, exercices, carte mentale et
  script de podcast (cache : un cours inchangé n'est jamais régénéré). Un `git push` republie le site.

## Podcasts audio
`uv sync --extra podcast` puis `uv run revise podcast <cours>` (voix Piper locales). Sans audio, le site lit le script
avec la synthèse vocale du navigateur.

## Publier
Le workflow `pages.yml` construit le site statique et le publie sur GitHub Pages à chaque push sur `main`
(Paramètres du dépôt > Pages > Source : GitHub Actions). Si le dépôt est privé, GitHub Pages demande un abonnement
payant : Cloudflare Pages ou Netlify sont des alternatives gratuites.

> Les fiches sont dérivées des supports du formateur : demande son accord avant de rendre le site public.
