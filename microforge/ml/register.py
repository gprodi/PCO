"""Enregistre un run dans le registre MLflow et pose l'alias (``staging`` ou ``production``).

L'api_ia charge ``models:/microforge-detector@production`` (MF_MLFLOW_MODEL_URI) : changer
l'alias suffit à déployer un nouveau modèle, sans toucher au code (cours MLOPS 2).
"""

from __future__ import annotations

import argparse

import mlflow
from mlflow import MlflowClient


def main(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model-name", default="microforge-detector")
    parser.add_argument("--alias", default="staging", choices=["staging", "production"])
    args = parser.parse_args(argv)
    mv = mlflow.register_model(f"runs:/{args.run_id}/weights", args.model_name)
    MlflowClient().set_registered_model_alias(args.model_name, args.alias, mv.version)
    print(f"{args.model_name} v{mv.version} -> @{args.alias}")
    return mv.version


if __name__ == "__main__":
    main()
