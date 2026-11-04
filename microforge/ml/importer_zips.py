"""Importe les jeux de photos téléchargés (zips Roboflow…) posés à la racine du dépôt PCO.

Depuis la racine de PCO (Windows, macOS, Linux) :

    uv run python microforge/ml/importer_zips.py              # extrait les zips et affiche le rapport
    uv run python microforge/ml/importer_zips.py --appliquer  # installe les source.yaml préparés

1. Chaque ``<nom>.zip`` de la racine est vérifié (aucun chemin absolu, ``..`` ni lien symbolique),
   puis extrait dans ``microforge/data/sources/<nom>/`` (jamais suivi par Git). Un dossier déjà
   présent n'est pas écrasé.
2. Le rapport donne, pour chaque jeu : images par split, classes (``data.yaml``) et les lignes de
   licence et d'origine des README Roboflow. **À copier dans la conversation** : la correspondance
   des classes et la licence sont ensuite écrites dans ``microforge/ml/sources/<nom>.yaml``.
3. ``--appliquer`` copie chaque ``microforge/ml/sources/<nom>.yaml`` en ``source.yaml`` du jeu ; il
   reste à lancer ``microforge/ml/prepare.py``. Les jeux non retenus sont listés, avec la raison, dans
   ``microforge/ml/jeux_ecartes.yaml``.
"""

from __future__ import annotations

import argparse
import re
import shutil
import stat
import sys
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

import yaml

ROOT = Path(__file__).resolve().parents[2]
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
README_HINTS = re.compile(r"licen|cc by|cc-by|http|provided by|author|creat|exported|images", re.I)


def slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "jeu"


def check_archive(zf: zipfile.ZipFile) -> None:
    """Refuse les archives qui écriraient hors du dossier cible."""
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", name):
            raise ValueError(f"chemin refusé dans l'archive : {info.filename}")
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError(f"lien symbolique refusé dans l'archive : {info.filename}")


def extract(zip_path: Path, dest: Path) -> bool:
    """Extrait ``zip_path`` dans ``dest`` ; False si ``dest`` existe déjà (rien n'est écrasé)."""
    if dest.exists():
        return False
    with zipfile.ZipFile(zip_path) as zf:
        check_archive(zf)
        dest.mkdir(parents=True)
        zf.extractall(dest)
    return True


def _names(dest: Path) -> list[str] | None:
    data_yaml = next(iter(sorted(dest.rglob("data.yaml"))), None)
    if data_yaml is None:
        return None
    names = (yaml.safe_load(data_yaml.read_text(encoding="utf-8", errors="replace")) or {}).get(
        "names"
    )
    if isinstance(names, dict):
        return [str(names[k]) for k in sorted(names, key=int)]
    return [str(n) for n in names] if names else None


def describe(dest: Path) -> list[str]:
    images = [p for p in dest.rglob("*") if p.suffix.lower() in IMAGE_EXT]
    splits: dict[str, int] = {}
    for img in images:
        parts = img.relative_to(dest).parts
        split = parts[0] if len(parts) > 1 else "(racine)"
        splits[split] = splits.get(split, 0) + 1
    labels = sum(1 for p in dest.rglob("*.txt") if p.parent.name == "labels")
    names = _names(dest)
    lines = [
        f"### {dest.name}",
        f"- images : {len(images)} {splits} ; fichiers de labels YOLO : {labels}",
        f"- classes ({len(names) if names else 0}) : {names if names else 'data.yaml introuvable (export YOLO ?)'}",
    ]
    for readme in sorted(
        p for p in dest.rglob("*") if p.name.lower().startswith("readme") and p.is_file()
    ):
        kept = [
            ln.strip() for ln in readme.read_text(encoding="utf-8", errors="replace").splitlines()
        ]
        kept = [ln for ln in kept if ln and README_HINTS.search(ln)]
        if kept:
            lines.append(f"- {readme.name} :")
            lines += [f"  > {ln[:200]}" for ln in kept[:12]]
    return lines


def load_rejected(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {
        str(k): " ".join(str(v).split())
        for k, v in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).items()
    }


def apply_configs(
    sources: Path, configs: Path, rejected: dict[str, str] | None = None
) -> list[str]:
    out = []
    rejected = rejected or {}
    for dest in sorted(p for p in sources.iterdir() if p.is_dir()):
        cfg = configs / f"{dest.name}.yaml"
        if dest.name in rejected:
            out.append(f"- {dest.name} : écarté ({rejected[dest.name]})")
        elif cfg.exists():
            shutil.copyfile(cfg, dest / "source.yaml")
            out.append(f"- {dest.name} : source.yaml installé")
        elif not (dest / "source.yaml").exists():
            out.append(
                f"- {dest.name} : pas encore de correspondance (microforge/ml/sources/{dest.name}.yaml)"
            )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Importe les zips de jeux de photos posés à la racine de PCO."
    )
    parser.add_argument("--racine", type=Path, default=ROOT, help="dossier où chercher les zips")
    parser.add_argument("--sources", type=Path, default=ROOT / "microforge" / "data" / "sources")
    parser.add_argument("--configs", type=Path, default=ROOT / "microforge" / "ml" / "sources")
    parser.add_argument(
        "--ecartes", type=Path, default=ROOT / "microforge" / "ml" / "jeux_ecartes.yaml"
    )
    parser.add_argument(
        "--appliquer", action="store_true", help="installer les source.yaml préparés"
    )
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args.sources.mkdir(parents=True, exist_ok=True)
    report = ["# Jeux de photos importés", ""]
    zips = sorted(args.racine.glob("*.zip"))
    if not zips and not any(args.sources.iterdir()):
        print(f"Aucun zip trouvé dans {args.racine} : place les fichiers .zip à la racine de PCO.")
        return 1
    for zip_path in zips:
        dest = args.sources / slug(zip_path.stem)
        try:
            state = "extrait" if extract(zip_path, dest) else "déjà présent, non réextrait"
        except (ValueError, zipfile.BadZipFile) as exc:
            report += [f"### {zip_path.name}", f"- **refusé** : {exc}", ""]
            continue
        report.append(f"<!-- {zip_path.name} -> microforge/data/sources/{dest.name} ({state}) -->")
    for dest in sorted(p for p in args.sources.iterdir() if p.is_dir()):
        report += [*describe(dest), ""]
    if args.appliquer:
        report += [
            "## source.yaml",
            *apply_configs(args.sources, args.configs, load_rejected(args.ecartes)),
            "",
        ]
        report.append(
            "Ensuite : uv run python microforge/ml/prepare.py --sources microforge/data/sources "
            "--out microforge/data/dataset"
        )
    else:
        report.append("Copie tout ce rapport dans la conversation avec Claude.")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
