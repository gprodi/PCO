"""Évaluation et porte de non-régression (C12/C13) : rapport Markdown joint à la PR de livraison.

Échoue (code 1) si mAP50 < mAP50(@production) − tolérance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def gate(candidate: float, production: float | None, tolerance: float = 0.02) -> tuple[bool, str]:
    """Décision de promotion (fonction pure, testée)."""
    if production is None:
        return True, f"Premier modèle : mAP50 = {candidate:.3f}"
    ok = candidate >= production - tolerance
    verdict = "✅ promotion possible" if ok else "⛔ régression"
    return (
        ok,
        f"{verdict} : mAP50 {candidate:.3f} vs production {production:.3f} (tolérance {tolerance})",
    )


def report_markdown(metrics: dict[str, float], per_class: dict[str, float], decision: str) -> str:
    lines = [
        "## Rapport d'évaluation du détecteur",
        "",
        decision,
        "",
        "| Métrique | Valeur |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v:.3f} |" for k, v in metrics.items()]
    lines += ["", "### AP50 par classe (10 plus faibles)", "", "| Classe | AP50 |", "|---|---|"]
    lines += [f"| {k} | {v:.3f} |" for k, v in sorted(per_class.items(), key=lambda kv: kv[1])[:10]]
    lines += ["", "![Matrice de confusion](confusion_matrix.png)"]
    return "\n".join(lines) + "\n"


def production_map50(model_name: str) -> float | None:
    try:
        from mlflow import MlflowClient

        client = MlflowClient()
        mv = client.get_model_version_by_alias(model_name, "production")
        return client.get_run(mv.run_id).data.metrics.get("mAP50")
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True)
    parser.add_argument("--data", default=str(HERE / "data" / "dataset.yaml"))
    parser.add_argument("--model-name", default="microforge-detector")
    parser.add_argument("--out", default="reports/evaluation")
    args = parser.parse_args(argv)

    from ultralytics import YOLO

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    res = YOLO(args.weights).val(
        data=args.data, split="test", plots=True, project=str(out), name="val", exist_ok=True
    )
    metrics = {
        "mAP50": float(res.box.map50),
        "mAP50-95": float(res.box.map),
        "precision": float(res.box.mp),
        "recall": float(res.box.mr),
    }
    per_class = {
        res.names[i]: float(ap) for i, ap in zip(res.box.ap_class_index, res.box.ap50, strict=False)
    }
    ok, decision = gate(metrics["mAP50"], production_map50(args.model_name))
    (out / "metrics.json").write_text(
        json.dumps({"metrics": metrics, "per_class": per_class, "ok": ok}, indent=2)
    )
    (out / "report.md").write_text(report_markdown(metrics, per_class, decision))
    print(decision)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
