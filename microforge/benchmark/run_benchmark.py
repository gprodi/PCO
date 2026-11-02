"""Benchmark C7 : compare plusieurs services/modèles de vision sur un même jeu de photos annotées."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import date
from pathlib import Path

from llm_gateway import FakeProvider, Gateway, GatewaySettings
from llm_gateway.profiles import load_profile
from llm_gateway.providers.openai_compat import gemini_provider, ollama_provider
from microforge.vision import InventoryScanner


def make_gateway(service: str) -> Gateway:
    """« ollama:<modèle> », « gemini », « fake »."""
    settings = GatewaySettings()
    profile = load_profile("cpu")
    if service == "fake":
        return Gateway([FakeProvider()], profile)
    if service.startswith("ollama:"):
        model = service.split(":", 1)[1]
        prof = load_profile(settings.llm_profile)
        prof.ollama_models["vision"] = model  # type: ignore[index]
        return Gateway([ollama_provider(settings.ollama_base_url)], prof)
    if service == "gemini":
        return Gateway(
            [gemini_provider(settings.gemini_api_key, settings.gemini_base_url)], profile
        )
    raise ValueError(service)


def score(pred: dict[str, int], truth: dict[str, int]) -> tuple[int, int, int]:
    """Vrais positifs, faux positifs, faux négatifs (en nombre d'exemplaires)."""
    tp = sum(min(pred.get(k, 0), v) for k, v in truth.items())
    fp = sum(max(0, q - truth.get(k, 0)) for k, q in pred.items())
    fn = sum(max(0, v - pred.get(k, 0)) for k, v in truth.items())
    return tp, fp, fn


def run(service: str, images: Path, labels: dict[str, dict[str, int]]) -> dict:
    scanner = InventoryScanner(make_gateway(service), detector=None)
    tp = fp = fn = 0
    latencies = []
    tracker = None
    if service.startswith("ollama:"):
        try:
            from codecarbon import OfflineEmissionsTracker

            tracker = OfflineEmissionsTracker(country_iso_code="FRA", log_level="error")
            tracker.start()
        except ImportError:
            tracker = None
    for name, truth in labels.items():
        start = time.perf_counter()
        result = scanner.scan((images / name).read_bytes())
        latencies.append(time.perf_counter() - start)
        pred = {i.component_id: i.quantity for i in result.items if i.component_id}
        a, b, c = score(pred, truth)
        tp, fp, fn = tp + a, fp + b, fn + c
    emissions = tracker.stop() if tracker else None
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "service": service,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "latence_p50_s": round(statistics.median(latencies), 2) if latencies else None,
        "latence_p95_s": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 2)
        if latencies
        else None,
        "gCO2e_par_photo": round(emissions * 1000 / len(labels), 3) if emissions else "n/d",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--images", type=Path, required=True)
    p.add_argument("--services", nargs="+", default=["fake"])
    args = p.parse_args()
    labels = json.loads((args.images / "labels.json").read_text())
    rows = [run(s, args.images, labels) for s in args.services]
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    keys = list(rows[0])
    md = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)] + [
        "| " + " | ".join(str(r[k]) for k in keys) + " |" for r in rows
    ]
    path = out / f"benchmark-{date.today()}.md"
    path.write_text(
        f"# Benchmark vision — {date.today()} ({len(labels)} photos)\n\n" + "\n".join(md) + "\n",
        encoding="utf-8",
    )
    print("\n".join(md))


if __name__ == "__main__":
    main()
