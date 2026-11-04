"""Préparation du dataset du détecteur (C12) : fusion des sources, remappage, découpage sans fuite.

uv run python microforge/ml/prepare.py --sources data/sources --out data/dataset

Chaque sous-dossier de ``--sources`` est une source, décrite par un ``source.yaml`` :

    nom: photos-gael                  # préfixe des fichiers produits
    licence: personnelle              # ou CC-BY-4.0, MIT… (reportée dans ATTRIBUTION.md)
    url: ""                           # page d'origine (obligatoire pour une licence CC BY)
    attribution: "Gaël Prodi"         # à citer
    groupes: composant                # « composant » : <classe>/<composant>/photo.jpg = un groupe
                                      # « original » (défaut) : copies augmentées et quasi-doublons groupés
    ratios: [0.6, 0.2, 0.2]           # train / val / test (défaut 0.7 / 0.2 / 0.1)
    classes:                          # nom de classe de la source -> classe MicroForge (null = ignorée)
      Resistor: resistor
      Capacitor: null

Les images sont au format YOLO : chaque image a un fichier de labels du même nom, à côté d'elle ou dans
le dossier ``labels`` correspondant à ``images`` (export Roboflow, Label Studio, CVAT). Les noms des classes
de la source viennent de ``names`` dans source.yaml, sinon de data.yaml, sinon de classes.txt.

Garanties :
- **aucune fuite** : toutes les photos d'un même composant physique, les copies augmentées d'une même
  image (« xxx_jpg.rf.<hash> ») et les quasi-doublons (empreinte perceptuelle) restent dans le même split ;
- **métadonnées retirées** : orientation EXIF appliquée puis image réenregistrée sans EXIF (la position
  GPS d'une photo de téléphone ne quitte pas l'ordinateur) ;
- **traçabilité** : manifest.json (origine, licence, empreinte de chaque image) et ATTRIBUTION.md ;
- validation finale par ``dataset_checks.validate_dataset`` (formats, labels, doublons, fuites).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from PIL import Image, ImageOps

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import dataset_checks as dc  # noqa: E402

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
SPLITS = ("train", "val", "test")
NEAR_DUPLICATE_BITS = 4  # distance de Hamming maximale entre empreintes dHash (64 bits)


@dataclass
class Item:
    source: str
    image: Path
    label: Path | None
    group: str
    sha256: str
    dhash: int
    boxes: list[tuple[str, str]] = field(default_factory=list)  # (classe MicroForge, « cx cy w h »)


@dataclass
class Summary:
    images: Counter = field(default_factory=Counter)
    instances: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    dropped: Counter = field(default_factory=Counter)
    unlabeled: int = 0
    duplicates: int = 0


# ---------------------------------------------------------------- lecture des sources
def dhash(img: Image.Image) -> int:
    """Empreinte perceptuelle (différences horizontales sur 9×8 en niveaux de gris)."""
    small = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    px = list(small.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


def _names(src: Path, cfg: dict) -> list[str]:
    if cfg.get("names"):
        names = cfg["names"]
    elif (src / "data.yaml").exists():
        names = yaml.safe_load((src / "data.yaml").read_text(encoding="utf-8"))["names"]
    elif (src / "classes.txt").exists():
        names = [ln.strip() for ln in (src / "classes.txt").read_text().splitlines() if ln.strip()]
    else:
        raise ValueError(
            f"{src.name} : noms de classes introuvables (names, data.yaml ou classes.txt)"
        )
    if isinstance(names, dict):
        return [names[k] for k in sorted(names, key=int)]
    return list(names)


def _label_for(image: Path) -> Path | None:
    candidates = [image.with_suffix(".txt")]
    parts = list(image.parts)
    if "images" in parts:
        i = len(parts) - 1 - parts[::-1].index("images")
        candidates.append(Path(*parts[:i], "labels", *parts[i + 1 :]).with_suffix(".txt"))
    return next((c for c in candidates if c.exists()), None)


def _group(src: Path, image: Path, mode: str) -> str:
    if mode == "composant":
        rel = image.relative_to(src)
        # <classe>/<composant>/photo.jpg (éventuellement sous images/) : le composant est le groupe
        parts = [p for p in rel.parts[:-1] if p not in {"images", *SPLITS, "valid"}]
        if len(parts) < 2:
            raise ValueError(f"{rel} : rangement attendu <classe>/<composant>/photo.jpg")
        return f"{src.name}:{parts[-2]}/{parts[-1]}"
    # copies augmentées Roboflow : « nom_jpg.rf.<hash>.jpg » partagent « nom_jpg »
    return f"{src.name}:{image.stem.split('.rf.')[0]}"


def read_source(src: Path, summary: Summary) -> tuple[dict, list[Item]]:
    cfg = yaml.safe_load((src / "source.yaml").read_text(encoding="utf-8"))
    cfg.setdefault("nom", src.name)
    names = _names(src, cfg)
    mapping = cfg.get("classes") or {}
    unknown = sorted(set(names) - set(mapping))
    if unknown:
        raise ValueError(f"{src.name} : classes sans correspondance dans source.yaml : {unknown}")
    items = []
    for image in sorted(p for p in src.rglob("*") if p.suffix.lower() in IMAGE_EXT):
        label = _label_for(image)
        if label is None:
            summary.unlabeled += 1
            continue
        with Image.open(image) as img:
            fingerprint = dhash(ImageOps.exif_transpose(img))
        item = Item(
            source=cfg["nom"],
            image=image,
            label=label,
            group=_group(src, image, cfg.get("groupes", "original")),
            sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
            dhash=fingerprint,
        )
        for line in label.read_text().splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            source_class = names[int(parts[0])]
            target = mapping[source_class]
            if target is None:
                summary.dropped[f"{cfg['nom']}:{source_class}"] += 1
            else:
                item.boxes.append((target, " ".join(parts[1:])))
        items.append(item)
    return cfg, items


# ---------------------------------------------------------------- groupes et découpage
def merge_near_duplicates(items: list[Item]) -> None:
    """Fusionne les groupes dont des images sont quasi identiques (union-find sur les empreintes)."""
    parent: dict[str, str] = {}

    def find(g: str) -> str:
        while parent.setdefault(g, g) != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g

    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if a.group != b.group and (a.dhash ^ b.dhash).bit_count() <= NEAR_DUPLICATE_BITS:
                parent[find(a.group)] = find(b.group)
    for item in items:
        item.group = find(item.group)


def assign_splits(items: list[Item], ratios: dict[str, list[float]], seed: str) -> dict[str, str]:
    """Groupe -> split, par source, en visant les proportions (en nombre d'images), de façon déterministe."""
    by_source: dict[str, dict[str, int]] = defaultdict(Counter)
    for item in items:
        by_source[item.source][item.group] += 1
    out = {}
    for source, groups in by_source.items():
        target = ratios.get(source) or [0.7, 0.2, 0.1]
        total = sum(groups.values())
        filled = dict.fromkeys(SPLITS, 0)
        order = sorted(groups, key=lambda g: hashlib.sha256(f"{seed}:{g}".encode()).hexdigest())
        allowed = [s for s, r in zip(SPLITS, target, strict=True) if r > 0]
        for group in order:
            # le split le plus en retard sur sa cible (en proportion) reçoit le groupe
            split = min(
                allowed,
                key=lambda s: (
                    (filled[s] - target[SPLITS.index(s)] * total) / target[SPLITS.index(s)]
                ),
            )
            out[group] = split
            filled[split] += groups[group]
    return out


# ---------------------------------------------------------------- écriture
def write_image(item: Item, dest: Path) -> str:
    with Image.open(item.image) as img:
        clean = ImageOps.exif_transpose(img).convert("RGB")  # orientation appliquée, EXIF supprimé
    dest.parent.mkdir(parents=True, exist_ok=True)
    clean.save(dest, "JPEG", quality=92)  # aucun paramètre exif= : métadonnées retirées
    return hashlib.sha256(dest.read_bytes()).hexdigest()


def prepare(sources: Path, out: Path, dataset_yaml: Path, seed: str = "microforge") -> dict:
    names = dc.load_names(dataset_yaml)
    index = {name: i for i, name in names.items()}
    summary = Summary()
    configs, items = {}, []
    for src in sorted(p for p in sources.iterdir() if (p / "source.yaml").exists()):
        cfg, found = read_source(src, summary)
        unknown = {t for t in (cfg.get("classes") or {}).values() if t is not None} - set(index)
        if unknown:
            raise ValueError(f"{src.name} : classes MicroForge inconnues {sorted(unknown)}")
        configs[cfg["nom"]] = cfg
        items += found
    seen, unique = set(), []
    for item in items:  # doublons exacts (même fichier dans deux sources) : un seul exemplaire
        if item.sha256 in seen:
            summary.duplicates += 1
            continue
        seen.add(item.sha256)
        unique.append(item)
    merge_near_duplicates(unique)
    split_of = assign_splits(unique, {n: c.get("ratios") for n, c in configs.items()}, seed)
    manifest = []
    for item in unique:
        split = split_of[item.group]
        stem = f"{item.source}_{item.sha256[:16]}"
        digest = write_image(item, out / "images" / split / f"{stem}.jpg")
        lines = [f"{index[cls]} {coords}" for cls, coords in item.boxes]
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split / f"{stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else "")
        )
        summary.images[split] += 1
        for cls, _ in item.boxes:
            summary.instances[split][cls] += 1
        manifest.append(
            {
                "fichier": f"images/{split}/{stem}.jpg",
                "source": item.source,
                "licence": configs[item.source].get("licence", ""),
                "origine": str(item.image.relative_to(sources)),
                "groupe": item.group,
                "split": split,
                "sha256_origine": item.sha256,
                "sha256": digest,
            }
        )
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    _attribution(out, configs, manifest)
    report = dc.validate_dataset(out, names)
    stats = {
        "images": dict(summary.images),
        "instances": {s: dict(c) for s, c in summary.instances.items()},
        "classes_ignorees": dict(summary.dropped),
        "images_sans_label": summary.unlabeled,
        "doublons_exacts": summary.duplicates,
        "groupes": len(set(split_of)),
        "validation": {
            "ok": report.ok,
            "erreurs": report.errors[:20],
            "avertissements": len(report.warnings),
        },
    }
    (out / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return stats


def _attribution(out: Path, configs: dict, manifest: list[dict]) -> None:
    counts = Counter(m["source"] for m in manifest)
    lines = [
        "# Sources des images",
        "",
        "| Source | Images | Licence | Auteur | Lien |",
        "|---|---|---|---|---|",
    ]
    for name, cfg in configs.items():
        lines.append(
            f"| {name} | {counts[name]} | {cfg.get('licence', '')} | {cfg.get('attribution', '')} | {cfg.get('url', '')} |"
        )
    lines += [
        "",
        "Les images sous licence CC BY doivent être créditées ainsi dans toute diffusion du jeu de données.",
    ]
    (out / "ATTRIBUTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sources", type=Path, default=Path("data/sources"))
    parser.add_argument("--out", type=Path, default=Path("data/dataset"))
    parser.add_argument("--dataset-yaml", type=Path, default=HERE / "data" / "dataset.yaml")
    parser.add_argument("--seed", default="microforge")
    args = parser.parse_args(argv)
    if args.out.exists() and any(args.out.iterdir()):
        parser.error(f"{args.out} n'est pas vide : choisir un dossier de sortie neuf")
    stats = prepare(args.sources, args.out, args.dataset_yaml, args.seed)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    return 0 if stats["validation"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
