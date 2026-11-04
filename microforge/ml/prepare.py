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
    negatifs: 0.25                    # images sans classe retenue gardées (fraction des positives)
    classes:                          # nom de classe de la source -> classe MicroForge
      Resistor: resistor              #   null : boîte ignorée, image gardée
      Capacitor: exclure              #   exclure : images contenant cette classe retirées (classe ambiguë)

Les images sont au format YOLO : chaque image a un fichier de labels du même nom, à côté d'elle ou dans
le dossier ``labels`` correspondant à ``images`` (export Roboflow, Label Studio, CVAT). Les noms des classes
de la source viennent de ``names`` dans source.yaml, sinon de data.yaml, sinon de classes.txt. Une ligne de
polygone (export « segmentation » : ``classe x1 y1 x2 y2 …``) est convertie en boîte englobante ; une image
dont une ligne est illisible est écartée (sinon ses objets passeraient pour du décor).

Garanties :
- **aucune fuite** : toutes les photos d'un même composant physique, les copies augmentées d'une même
  image (« xxx_jpg.rf.<hash> ») et les quasi-doublons (deux empreintes perceptuelles) restent dans le même
  split ; les plus gros groupes sont placés en premier, donc en entraînement, pour qu'une longue série de
  photos presque identiques ne remplisse pas à elle seule la validation ou le test ;
- **métadonnées retirées** : orientation EXIF appliquée puis image réenregistrée sans EXIF (la position
  GPS d'une photo de téléphone ne quitte pas l'ordinateur) ;
- **traçabilité** : manifest.json (origine, licence, empreinte de chaque image) et ATTRIBUTION.md ;
- validation finale par ``dataset_checks.validate_dataset`` (formats, labels, doublons, fuites).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
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
# Un groupe plus lourd que ce quart d'un split d'évaluation (val, test) de sa source le dominerait :
# il va en entraînement. Plancher en images pour les petites sources.
MAX_EVAL_SHARE, MIN_EVAL_GROUP = 0.25, 10
EXCLURE = EXCLUDE = (
    "exclure"  # valeur de correspondance : retirer les images contenant cette classe
)


@dataclass
class Item:
    source: str
    image: Path
    label: Path | None
    group: str
    sha256: str
    dhash: int
    boxes: list[tuple[str, str]] = field(default_factory=list)  # (classe MicroForge, « cx cy w h »)
    excluded: bool = False
    vhash: int | None = None  # 2e empreinte (différences verticales) : confirme les quasi-doublons


@dataclass
class Summary:
    images: Counter = field(default_factory=Counter)
    instances: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    dropped: Counter = field(default_factory=Counter)
    excluded: Counter = field(default_factory=Counter)
    unlabeled: int = 0
    duplicates: int = 0
    invalid: Counter = field(default_factory=Counter)  # images écartées : ligne de label illisible
    polygons: Counter = field(default_factory=Counter)  # polygones convertis en boîtes


# ---------------------------------------------------------------- lecture des sources
def _pixels(img: Image.Image) -> list[int]:
    # getdata() est déprécié (Pillow 12, retrait prévu en Pillow 14) au profit de get_flattened_data()
    flat = getattr(img, "get_flattened_data", None)
    return list(flat() if flat else img.getdata())


def dhash(img: Image.Image, vertical: bool = False) -> int:
    """Empreinte perceptuelle sur 64 bits : différences entre pixels voisins d'une vignette en gris.

    Horizontale par défaut (vignette 9×8) ; ``vertical=True`` compare les pixels du dessus et du dessous
    (vignette 8×9). Les deux empreintes ensemble évitent de prendre pour des quasi-doublons deux photos
    différentes qui se ressemblent dans un seul sens (fond blanc, breadboard…).
    """
    gray = img.convert("L")
    if vertical:
        gray = gray.transpose(Image.Transpose.TRANSPOSE)
    px = _pixels(gray.resize((9, 8), Image.Resampling.LANCZOS))
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


def parse_label_line(line: str, n_names: int) -> tuple[int, str, bool] | None:
    """``(classe, « cx cy w h », polygone ?)`` ; ``None`` si la ligne est illisible.

    Boîte YOLO : 4 coordonnées. Polygone (segmentation YOLO) : au moins 3 points, convertis en boîte
    englobante bornée à l'image.
    """
    parts = line.split()
    try:
        cls, values = int(parts[0]), [float(v) for v in parts[1:]]
    except (IndexError, ValueError):
        return None
    if not 0 <= cls < n_names:
        return None
    if len(values) == 4:
        cx, cy, w, h = values
        if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < w <= 1 and 0 < h <= 1):
            return None
        return cls, " ".join(parts[1:]), False
    if len(values) < 6 or len(values) % 2:
        return None
    xs = [min(max(v, 0.0), 1.0) for v in values[0::2]]
    ys = [min(max(v, 0.0), 1.0) for v in values[1::2]]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    if w <= 0 or h <= 0:
        return None
    cx, cy = min(xs) + w / 2, min(ys) + h / 2
    return cls, f"{cx:.6f} {cy:.6f} {w:.6f} {h:.6f}", True


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
    unmapped_used: set[str] = set()
    items = []
    for image in sorted(p for p in src.rglob("*") if p.suffix.lower() in IMAGE_EXT):
        label = _label_for(image)
        if label is None:
            summary.unlabeled += 1
            continue
        with Image.open(image) as img:
            upright = ImageOps.exif_transpose(img)
            fingerprint, vertical = dhash(upright), dhash(upright, vertical=True)
        item = Item(
            source=cfg["nom"],
            image=image,
            label=label,
            group=_group(src, image, cfg.get("groupes", "original")),
            sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
            dhash=fingerprint,
            vhash=vertical,
        )
        unreadable = False
        for line in label.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            parsed = parse_label_line(line, len(names))
            if parsed is None:
                unreadable = True
                break
            cls, coords, polygon = parsed
            summary.polygons[cfg["nom"]] += polygon
            source_class = names[cls]
            if source_class not in mapping:
                unmapped_used.add(source_class)
                continue
            target = mapping[source_class]
            if target == EXCLUDE:
                item.excluded = True
            elif target is None:
                summary.dropped[f"{cfg['nom']}:{source_class}"] += 1
            else:
                item.boxes.append((target, coords))
        if unreadable:
            summary.invalid[cfg["nom"]] += 1
            continue
        if item.excluded:
            # classe ambiguë qui recouvre une classe MicroForge (« Capacitor » générique…) : sans boîte,
            # l'objet passerait pour du décor ; l'image entière est donc retirée.
            summary.excluded[cfg["nom"]] += 1
            continue
        items.append(item)
    if unmapped_used:  # une catégorie vide (parent Roboflow) peut rester sans correspondance
        raise ValueError(
            f"{src.name} : classes sans correspondance dans source.yaml : {sorted(unmapped_used)}"
        )
    return cfg, _limit_negatives(items, cfg.get("negatifs"))


def _limit_negatives(items: list[Item], fraction: float | None) -> list[Item]:
    """Garde au plus ``fraction`` × (images positives) images sans objet retenu, choisies de façon stable."""
    if fraction is None:
        return items
    positives = [i for i in items if i.boxes]
    negatives = sorted((i for i in items if not i.boxes), key=lambda i: i.sha256)
    return positives + negatives[: int(len(positives) * fraction)]


# ---------------------------------------------------------------- groupes et découpage
def merge_near_duplicates(items: list[Item]) -> None:
    """Fusionne les groupes dont des images sont quasi identiques (union-find sur les empreintes)."""
    parent: dict[str, str] = {}

    def find(g: str) -> str:
        while parent.setdefault(g, g) != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g

    # Principe des tiroirs : deux empreintes à ≤ 4 bits d'écart ont au moins une des 5 tranches de
    # 13 bits identique. On ne compare que les images qui partagent une tranche (au lieu de n² paires).
    bands = 5
    width = -(-64 // bands)
    buckets: dict[tuple[int, int], list[Item]] = defaultdict(list)
    for item in items:
        for band in range(bands):
            buckets[(band, (item.dhash >> (band * width)) & ((1 << width) - 1))].append(item)
    for bucket in buckets.values():
        for i, a in enumerate(bucket):
            for b in bucket[i + 1 :]:
                if a.group != b.group and _near(a, b):
                    parent[find(a.group)] = find(b.group)
    for item in items:
        item.group = find(item.group)


def _near(a: Item, b: Item) -> bool:
    if (a.dhash ^ b.dhash).bit_count() > NEAR_DUPLICATE_BITS:
        return False
    if a.vhash is None or b.vhash is None:
        return True
    return (a.vhash ^ b.vhash).bit_count() <= NEAR_DUPLICATE_BITS


def assign_splits(items: list[Item], ratios: dict[str, list[float]], seed: str) -> dict[str, str]:
    """Groupe -> split, par source, en visant les proportions (en nombre d'images), de façon déterministe.

    Les groupes sont placés du plus gros au plus petit (à taille égale, dans un ordre pseudo-aléatoire
    fixé par ``seed``) : un gros groupe arrive quand tous les splits sont vides et va donc en
    entraînement, les petits groupes ajustent ensuite les proportions. Un groupe qui pèserait plus
    de ``MAX_EVAL_SHARE`` de la cible d'un split d'évaluation n'y est jamais placé : une seule série
    de photos ne doit pas faire à elle seule le score de validation ou de test.
    """
    by_source: dict[str, dict[str, int]] = defaultdict(Counter)
    for item in items:
        by_source[item.source][item.group] += 1
    out = {}
    for source, groups in by_source.items():
        target = ratios.get(source) or [0.7, 0.2, 0.1]
        total = sum(groups.values())
        filled = dict.fromkeys(SPLITS, 0)
        order = sorted(
            groups,
            key=lambda g: (-groups[g], hashlib.sha256(f"{seed}:{g}".encode()).hexdigest()),
        )
        allowed = [s for s, r in zip(SPLITS, target, strict=True) if r > 0]
        for group in order:
            fits = [
                s
                for s in allowed
                if s == "train"
                or groups[group]
                <= max(MAX_EVAL_SHARE * target[SPLITS.index(s)] * total, MIN_EVAL_GROUP)
            ]
            # le split le plus en retard sur sa cible (en proportion) reçoit le groupe
            split = min(
                fits or allowed,
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
        unknown = {
            t for t in (cfg.get("classes") or {}).values() if t not in (None, EXCLUDE)
        } - set(index)
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
        "par_source": _per_source(manifest, unique),
        "plus_gros_groupes": _largest_groups(manifest),
        "classes_ignorees": dict(summary.dropped),
        "images_exclues": dict(summary.excluded),
        "images_labels_illisibles": dict(summary.invalid),
        "polygones_convertis": {k: v for k, v in summary.polygons.items() if v},
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


def _per_source(manifest: list[dict], items: list[Item]) -> dict:
    """Images par split, boîtes et images négatives de chaque source."""
    out: dict[str, dict] = {}
    for m, item in zip(manifest, items, strict=True):
        entry = out.setdefault(m["source"], {"images": Counter(), "boites": 0, "negatives": 0})
        entry["images"][m["split"]] += 1
        entry["boites"] += len(item.boxes)
        entry["negatives"] += not item.boxes
    return {s: {**e, "images": dict(e["images"])} for s, e in sorted(out.items())}


def _largest_groups(manifest: list[dict], top: int = 5) -> list[dict]:
    """Les plus gros groupes (séries de photos quasi identiques) : à surveiller s'ils dominent un split."""
    sizes = Counter(m["groupe"] for m in manifest)
    split_of = {m["groupe"]: m["split"] for m in manifest}
    return [
        {"groupe": g, "images": n, "split": split_of[g]} for g, n in sizes.most_common(top) if n > 1
    ]


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
    parser.add_argument(
        "--remplacer",
        action="store_true",
        help="effacer d'abord un dataset déjà produit par ce script dans --out",
    )
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.out.exists() and any(args.out.iterdir()):
        if not args.remplacer:
            parser.error(
                f"{args.out} n'est pas vide : ajouter --remplacer ou choisir un dossier neuf"
            )
        if not (args.out / "manifest.json").exists():
            # garde-fou : on n'efface qu'un dossier produit par prepare.py
            parser.error(f"{args.out} ne contient pas de manifest.json : dossier non effacé")
        shutil.rmtree(args.out)
    stats = prepare(args.sources, args.out, args.dataset_yaml, args.seed)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    return 0 if stats["validation"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
