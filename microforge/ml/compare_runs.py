"""Compare les entraînements du registre ``ml/experiences.yaml`` (C11, C13).

    uv run python microforge/ml/compare_runs.py                 # tableaux Markdown (test)
    uv run python microforge/ml/compare_runs.py --split validation
    uv run python microforge/ml/compare_runs.py --json          # données pour une page de comparaison

Une classe avec moins de ``--min-objets`` objets dans le split est marquée « non mesurable » : son score
change trop d'un découpage à l'autre pour être comparé.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
REGISTRY = HERE / "experiences.yaml"
SPLITS = ("test", "validation")


def load(path: Path = REGISTRY) -> list[dict]:
    runs = yaml.safe_load(path.read_text(encoding="utf-8"))["runs"]
    ids = [r["id"] for r in runs]
    if len(ids) != len(set(ids)):
        raise ValueError("identifiants de runs en double")
    return runs


def _fmt(v: float | None, digits: int = 3) -> str:
    return "—" if v is None else f"{v:.{digits}f}".replace(".", ",")


def summary(runs: list[dict]) -> str:
    head = (
        "| Run | Données | Classes | Epochs | Image | Matériel | Durée | "
        "Validation mAP50 | Test mAP50 | Test mAP50-95 | Inférence |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|"
    )
    rows = []
    for r in runs:
        val, test = r.get("validation") or {}, r.get("test") or {}
        rows.append(
            f"| {r['id']} ({r['github_run']}) | {r['donnees']} | {r['classes']} | {r['epochs']} | "
            f"{r['imgsz']} px | {r['materiel']} | {_fmt(r['duree_h'], 2)} h | {_fmt(val.get('map50'))} | "
            f"{_fmt(test.get('map50'))} | {_fmt(test.get('map50_95'))} | "
            f"{_fmt(r.get('inference_ms'), 1) + ' ms' if r.get('inference_ms') else '—'} |"
        )
    return "\n".join([head, *rows])


def per_class(runs: list[dict], split: str = "test", min_objets: int = 30) -> list[dict]:
    """Une ligne par classe : score mAP50 de chaque run (None si absente), objets, mesurable ou non."""
    classes: list[str] = []
    for r in runs:
        for cls in (r.get(split) or {}).get("par_classe", {}):
            if cls not in classes:
                classes.append(cls)
    out = []
    for cls in classes:
        cells = {}
        for r in runs:
            values = (r.get(split) or {}).get("par_classe", {}).get(cls)
            if values is None:
                cells[r["id"]] = None
                continue
            n, map50, map50_95 = values
            cells[r["id"]] = {
                "objets": n,
                "map50": map50,
                "map50_95": map50_95,
                "mesurable": n is None or n >= min_objets,
            }
        out.append({"classe": cls, "runs": cells})
    return out


def per_class_markdown(runs: list[dict], split: str = "test", min_objets: int = 30) -> str:
    ids = [r["id"] for r in runs]
    lines = [
        f"| Classe | {' | '.join(ids)} |",
        "|---|" + "---|" * len(ids),
    ]
    for row in per_class(runs, split, min_objets):
        cells = []
        for rid in ids:
            c = row["runs"][rid]
            if c is None:
                cells.append("—")
                continue
            count = "" if c["objets"] is None else f" ({c['objets']})"
            flag = "" if c["mesurable"] else " *"
            cells.append(f"{_fmt(c['map50'])}{count}{flag}")
        lines.append(f"| {row['classe']} | {' | '.join(cells)} |")
    lines.append(
        f"\nmAP50 sur le split « {split} » (objets entre parenthèses) ; * : moins de {min_objets} objets, "
        "score non mesurable ; — : classe absente du run."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registre", type=Path, default=REGISTRY)
    parser.add_argument("--split", choices=SPLITS, default="test")
    parser.add_argument("--min-objets", type=int, default=30)
    parser.add_argument("--json", action="store_true", help="données brutes pour une page")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    runs = load(args.registre)
    if args.json:
        data = {
            "runs": runs,
            "par_classe": {s: per_class(runs, s, args.min_objets) for s in SPLITS},
        }
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        print(summary(runs))
        print()
        print(per_class_markdown(runs, args.split, args.min_objets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
