# Benchmark des services d'IA (C7)

Protocole reproductible : **même jeu de photos annotées** pour chaque service, mêmes métriques.

```bash
# jeu de test : dossier d'images + labels.json {"photo1.jpg": {"dht22": 1, "led": 3}, ...}
uv run python microforge/benchmark/run_benchmark.py --images data/bench --services ollama:qwen3-vl:8b ollama:gemma3:4b gemini fake
```

| Mesure | Définition |
|---|---|
| Précision / rappel / F1 | sur les paires (composant, quantité) par photo |
| Latence p50 / p95 | durée d'analyse d'une photo (s) |
| Énergie | kWh et gCO₂e estimés par CodeCarbon (local) ; non mesurable pour les API distantes (noté « n/d ») |
| Coût | € / 1 000 photos (tarif public ; 0 en local) |
| Confidentialité | photo envoyée hors UE ? données réutilisées pour l'entraînement ? |

Résultats : `results/benchmark-AAAA-MM-JJ.md` (tableau prêt à insérer dans `docs/E2/benchmark.md`).
