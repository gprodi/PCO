"""Entraînement YOLO avec suivi MLflow (C13) — paramètres adaptés au profil matériel.

uv run --extra ml python microforge/ml/train.py --epochs 80
LLM_PROFILE=gpu-8gb ...   # forcer un profil
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml
from llm_gateway.profiles import load_profile
from loguru import logger

HERE = Path(__file__).parent


def resolve_data(data: str, workdir: Path) -> str:
    """Chemin ``path`` du dataset rendu absolu, par rapport au fichier YAML qui le déclare.

    Ultralytics cherche un ``path`` relatif introuvable depuis le dossier courant dans son propre
    dossier de datasets (``settings.datasets_dir``) : l'entraînement échouait hors du runner. Une copie
    résolue du YAML est écrite dans ``workdir`` ; un YAML déjà absolu est utilisé tel quel.
    """
    src = Path(data)
    if src.suffix not in {".yaml", ".yml"} or not src.exists():
        return data
    cfg = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    root = cfg.get("path")
    if not root or Path(root).is_absolute():
        return data
    cfg["path"] = str((src.parent / root).resolve())
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / f"{src.stem}-resolu.yaml"
    out.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return str(out)


def main(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(HERE / "data" / "dataset.yaml"))
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument(
        "--weights", default=None, help="poids de départ (défaut : selon le profil)"
    )
    parser.add_argument("--experiment", default="microforge-detector")
    parser.add_argument("--project", default="runs/detect", help="dossier des résultats")
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
            data=resolve_data(args.data, Path(args.project).resolve()),
            epochs=args.epochs,
            # chemin absolu : un chemin relatif est préfixé par le runs_dir d'Ultralytics
            project=str(Path(args.project).resolve()),
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
