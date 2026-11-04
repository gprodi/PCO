"""Entraînement YOLO avec suivi MLflow (C13) — paramètres adaptés au profil matériel.

uv run --extra ml python microforge/ml/train.py --epochs 80
LLM_PROFILE=gpu-8gb ...   # forcer un profil
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from llm_gateway.profiles import load_profile
from loguru import logger

HERE = Path(__file__).parent


def main(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(HERE / "data" / "dataset.yaml"))
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument(
        "--weights", default=None, help="poids de départ (défaut : selon le profil)"
    )
    parser.add_argument("--experiment", default="microforge-detector")
    parser.add_argument("--smoke", action="store_true", help="1 epoch, 64 px, CPU (test fumée CI)")
    parser.add_argument("--imgsz", type=int, default=None, help="taille d'image (défaut : profil)")
    parser.add_argument("--batch", type=int, default=None, help="taille de lot (défaut : profil)")
    args = parser.parse_args(argv)

    import mlflow
    from ultralytics import YOLO, settings

    profile = load_profile(os.getenv("LLM_PROFILE"))
    cfg = dict(profile.yolo)
    if args.smoke:
        cfg.update(device="cpu", imgsz=64, batch=2, workers=0)
        args.epochs = 1
    cfg.update({k: v for k, v in (("imgsz", args.imgsz), ("batch", args.batch)) if v})
    weights = args.weights or cfg.pop("weights", "yolo11n.pt")
    cfg.pop("weights", None)
    settings.update({"mlflow": False})  # on journalise nous-mêmes, explicitement
    mlflow.set_experiment(args.experiment)
    with mlflow.start_run() as run:
        mlflow.log_params(
            {"profile": profile.name, "weights": weights, "epochs": args.epochs, **cfg}
        )
        mlflow.set_tag("dataset_version", os.getenv("DVC_DATA_VERSION", "local"))
        model = YOLO(weights)
        results = model.train(
            data=args.data,
            epochs=args.epochs,
            project="runs/detect",
            name=run.info.run_id,
            exist_ok=True,
            **cfg,
        )
        metrics = {
            k.replace("(B)", "").replace("metrics/", ""): float(v)
            for k, v in results.results_dict.items()
        }
        mlflow.log_metrics(metrics)
        best = Path(results.save_dir) / "weights" / "best.pt"
        mlflow.log_artifact(str(best), artifact_path="weights")
        for png in Path(results.save_dir).glob("*.png"):
            mlflow.log_artifact(str(png), artifact_path="plots")
        logger.info("Run {} : {}", run.info.run_id, metrics)
        return run.info.run_id


if __name__ == "__main__":
    print(main())
