"""C12 — Préparation du dataset : remappage, groupes sans fuite, EXIF retiré, attribution."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest
import yaml
from PIL import Image, ImageDraw

ML = Path(__file__).parents[1] / "ml"
sys.path.insert(0, str(ML))

import dataset_checks as dc  # noqa: E402
import prepare  # noqa: E402

DATASET_YAML = ML / "data" / "dataset.yaml"
NAMES = dc.load_names(DATASET_YAML)
INDEX = {v: k for k, v in NAMES.items()}


def _picture(path: Path, seed: int, size=(96, 64), exif=None, shift=0) -> None:
    rng = random.Random(seed)
    img = Image.new("RGB", size, (rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    draw = ImageDraw.Draw(img)
    for _ in range(6):
        x, y = rng.randrange(size[0] - 20), rng.randrange(size[1] - 20)
        draw.rectangle([x, y, x + 18, y + 14], fill=(rng.randrange(256), 0, rng.randrange(256)))
    if shift:  # copie « augmentée » : légèrement plus claire
        img = img.point(lambda v: min(255, v + shift))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", exif=exif) if exif is not None else img.save(path, "JPEG")


def make_sources(root: Path) -> Path:
    # Export Roboflow : 10 originaux × 2 copies augmentées, classes Resistor / Capacitor / LED
    pub = root / "sources" / "roboflow"
    (pub).mkdir(parents=True)
    (pub / "data.yaml").write_text(yaml.safe_dump({"names": ["Resistor", "Capacitor", "LED"]}))
    (pub / "source.yaml").write_text(
        yaml.safe_dump(
            {
                "nom": "rf",
                "licence": "CC-BY-4.0",
                "url": "https://example.org/jeu",
                "attribution": "Auteur Exemple",
                "classes": {"Resistor": "resistor", "Capacitor": None, "LED": "led"},
            }
        )
    )
    for n in range(10):
        split = "train" if n < 8 else "valid"
        for k, shift in ((1, 0), (2, 6)):
            img = pub / split / "images" / f"img{n}_jpg.rf.{n}{k}abc.jpg"
            _picture(img, seed=n, shift=shift)
            lbl = pub / split / "labels" / f"img{n}_jpg.rf.{n}{k}abc.txt"
            lbl.parent.mkdir(parents=True, exist_ok=True)
            lbl.write_text("0 0.5 0.5 0.2 0.2\n1 0.3 0.3 0.1 0.1\n2 0.7 0.7 0.1 0.2\n")
    # Photos personnelles : 6 composants × 3 photos, EXIF (orientation + appareil) à retirer
    photos = root / "sources" / "photos"
    photos.mkdir(parents=True)
    (photos / "source.yaml").write_text(
        yaml.safe_dump(
            {
                "nom": "photos",
                "licence": "personnelle",
                "attribution": "Gaël",
                "groupes": "composant",
                "ratios": [0.5, 0.25, 0.25],
                "names": ["resistor", "led"],
                "classes": {"resistor": "resistor", "led": "led"},
            }
        )
    )
    for c in range(6):
        cls = "resistor" if c % 2 == 0 else "led"
        for j in range(3):
            exif = Image.Exif()
            exif[0x0112] = 6  # orientation : rotation de 90°
            exif[0x010F] = "TelephoneDeTest"  # fabricant de l'appareil
            img = photos / cls / f"{cls}{c:02d}" / f"IMG_{j}.jpg"
            _picture(img, seed=100 + c * 10 + j, exif=exif)
            img.with_suffix(".txt").write_text(f"{0 if cls == 'resistor' else 1} 0.5 0.5 0.3 0.3\n")
    return root / "sources"


@pytest.fixture
def prepared(tmp_path):
    sources = make_sources(tmp_path)
    out = tmp_path / "dataset"
    stats = prepare.prepare(sources, out, DATASET_YAML)
    manifest = json.loads((out / "manifest.json").read_text())
    return stats, manifest, out


def test_dataset_is_valid_and_classes_are_remapped(prepared):
    stats, manifest, out = prepared
    assert stats["validation"]["ok"], stats["validation"]
    assert sum(stats["images"].values()) == 20 + 18 == len(manifest)
    assert stats["classes_ignorees"] == {"rf:Capacitor": 20}
    rf_label = next(m for m in manifest if m["source"] == "rf")["fichier"]
    lines = (
        (out / rf_label.replace("images/", "labels/").replace(".jpg", ".txt"))
        .read_text()
        .split("\n")
    )
    assert [int(ln.split()[0]) for ln in lines if ln] == [INDEX["resistor"], INDEX["led"]]


def test_groups_never_cross_splits(prepared):
    _, manifest, _ = prepared
    split_of = {}
    for m in manifest:
        assert split_of.setdefault(m["groupe"], m["split"]) == m["split"], m["groupe"]
    photos = [m for m in manifest if m["source"] == "photos"]
    assert len({m["groupe"] for m in photos}) == 6  # un groupe par composant physique
    rf_groups = {m["groupe"] for m in manifest if m["source"] == "rf"}
    assert len(rf_groups) <= 10  # les copies augmentées d'un même original sont groupées
    assert {m["split"] for m in photos} == {"train", "val", "test"}


def test_exif_is_removed_and_orientation_applied(prepared):
    _, manifest, out = prepared
    photo = next(m for m in manifest if m["source"] == "photos")
    with Image.open(out / photo["fichier"]) as img:
        assert dict(img.getexif()) == {}
        assert img.size == (64, 96)  # orientation 6 appliquée avant de retirer l'EXIF


def test_attribution_and_determinism(prepared, tmp_path):
    _, manifest, out = prepared
    attribution = (out / "ATTRIBUTION.md").read_text()
    assert (
        "CC-BY-4.0" in attribution
        and "https://example.org/jeu" in attribution
        and "Auteur Exemple" in attribution
    )
    again = prepare.prepare(tmp_path / "sources", tmp_path / "bis", DATASET_YAML)
    assert again["images"] == prepared[0]["images"]
    second = json.loads((tmp_path / "bis" / "manifest.json").read_text())
    assert [m["split"] for m in second] == [m["split"] for m in manifest]


def test_negative_images_are_limited(tmp_path):
    sources = make_sources(tmp_path)
    cfg_path = sources / "roboflow" / "source.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    cfg["classes"] = {"Resistor": None, "Capacitor": None, "LED": None}  # plus aucun objet retenu
    cfg["negatifs"] = 0.25
    cfg_path.write_text(yaml.safe_dump(cfg))
    stats = prepare.prepare(sources, tmp_path / "out", DATASET_YAML)
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert sum(m["source"] == "rf" for m in manifest) == 0  # 0 positive -> 0 négative gardée
    assert stats["validation"]["ok"]


def test_unused_unmapped_category_is_tolerated(tmp_path):
    sources = make_sources(tmp_path)
    data = yaml.safe_load((sources / "roboflow" / "data.yaml").read_text())
    data["names"].append("parent-roboflow")  # catégorie sans aucune annotation
    (sources / "roboflow" / "data.yaml").write_text(yaml.safe_dump(data))
    assert prepare.prepare(sources, tmp_path / "out", DATASET_YAML)["validation"]["ok"]


def test_iotkits_mapping_targets_existing_classes():
    cfg = yaml.safe_load((ML / "sources" / "iotkits.yaml").read_text())
    targets = {t for t in cfg["classes"].values() if t is not None}
    assert targets <= set(INDEX) and len(cfg["classes"]) == 32
    assert cfg["licence"] == "CC-BY-4.0" and "10.17632/x5thzmkxhy" in cfg["attribution"]


@pytest.mark.parametrize("path", sorted((ML / "sources").glob("*.yaml")), ids=lambda p: p.stem)
def test_every_source_config_is_licensed_and_maps_to_known_classes(path):
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    targets = {t for t in cfg["classes"].values() if t not in (None, prepare.EXCLUDE)}
    assert targets <= set(INDEX), targets - set(INDEX)
    assert (
        cfg["licence"] == "CC-BY-4.0" and cfg["url"].startswith("https://") and cfg["attribution"]
    )


def test_ambiguous_class_removes_the_whole_image(tmp_path):
    sources = make_sources(tmp_path)
    cfg_path = sources / "roboflow" / "source.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    cfg["classes"]["Capacitor"] = "exclure"  # chaque image Roboflow contient un « Capacitor »
    cfg_path.write_text(yaml.safe_dump(cfg))
    stats = prepare.prepare(sources, tmp_path / "out", DATASET_YAML)
    assert stats["images_exclues"] == {"rf": 20}
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert {m["source"] for m in manifest} == {"photos"} and stats["validation"]["ok"]


def test_near_duplicates_are_grouped_across_names(tmp_path):
    a = prepare.Item("s", Path("a.jpg"), None, "s:a", "1", dhash=0b1011 << 40)
    b = prepare.Item(
        "s", Path("b.jpg"), None, "s:b", "2", dhash=(0b1011 << 40) ^ 0b111
    )  # 3 bits d'écart
    c = prepare.Item("s", Path("c.jpg"), None, "s:c", "3", dhash=~(0b1011 << 40) & (2**64 - 1))
    prepare.merge_near_duplicates([a, b, c])
    assert a.group == b.group != c.group


def test_unmapped_or_unknown_classes_are_refused(tmp_path):
    sources = make_sources(tmp_path)
    cfg_path = sources / "roboflow" / "source.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    del cfg["classes"]["LED"]
    cfg_path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError, match="sans correspondance"):
        prepare.prepare(sources, tmp_path / "a", DATASET_YAML)
    cfg["classes"]["LED"] = "licorne"
    cfg_path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError, match="inconnues"):
        prepare.prepare(sources, tmp_path / "b", DATASET_YAML)


def test_cli_refuses_a_non_empty_output(tmp_path):
    sources = make_sources(tmp_path)
    (tmp_path / "plein").mkdir()
    (tmp_path / "plein" / "x").write_text("x")
    with pytest.raises(SystemExit):
        prepare.main(["--sources", str(sources), "--out", str(tmp_path / "plein")])
    assert prepare.main(["--sources", str(sources), "--out", str(tmp_path / "neuf")]) == 0


def test_coco_export_converts_to_yolo(tmp_path):
    import coco_to_yolo

    split = tmp_path / "coco" / "train"
    split.mkdir(parents=True)
    _picture(split / "a.jpg", seed=1, size=(200, 100))
    _picture(split / "b.jpg", seed=2, size=(200, 100))
    (split / "_annotations.coco.json").write_text(
        json.dumps(
            {
                "categories": [
                    {"id": 0, "name": "kits", "supercategory": "none"},
                    {"id": 1, "name": "Arduino Uno", "supercategory": "kits"},
                    {"id": 2, "name": "ESP32", "supercategory": "kits"},
                ],
                "images": [
                    {"id": 10, "file_name": "a.jpg", "width": 200, "height": 100},
                    {"id": 11, "file_name": "b.jpg", "width": 200, "height": 100},
                ],
                "annotations": [
                    {"id": 1, "image_id": 10, "category_id": 1, "bbox": [50, 25, 100, 50]},
                    {"id": 2, "image_id": 10, "category_id": 2, "bbox": [0, 0, 20, 10]},
                    {
                        "id": 3,
                        "image_id": 11,
                        "category_id": 2,
                        "bbox": [10, 10, 0, 5],
                    },  # boîte vide
                ],
            }
        )
    )
    counts = coco_to_yolo.convert(tmp_path / "coco", tmp_path / "yolo")
    assert counts == {"Arduino Uno": 1, "ESP32": 1}
    assert yaml.safe_load((tmp_path / "yolo" / "data.yaml").read_text())["names"] == [
        "kits",
        "Arduino Uno",
        "ESP32",
    ]
    assert (tmp_path / "yolo" / "train" / "labels" / "a.txt").read_text().splitlines() == [
        "1 0.500000 0.500000 0.500000 0.500000",
        "2 0.050000 0.050000 0.100000 0.100000",
    ]
    assert (tmp_path / "yolo" / "train" / "labels" / "b.txt").read_text() == ""


def test_mendeley_licence_check():
    import fetch_mendeley

    assert fetch_mendeley.check_licence(
        {"data_licence": {"short_name": "CC BY 4.0", "full_name": "CC BY 4.0"}}
    )
    for bad in (
        {"data_licence": {"short_name": "CC BY NC 3.0"}},
        {"data_licence": {"short_name": "Proprietary"}},
        {},
    ):
        with pytest.raises(SystemExit):
            fetch_mendeley.check_licence(bad)


def test_label_lines_boxes_polygons_and_garbage():
    assert prepare.parse_label_line("2 0.5 0.5 0.2 0.4", 3) == (2, "0.5 0.5 0.2 0.4", False)
    cls, coords, polygon = prepare.parse_label_line("1 0.1 0.2 0.5 0.2 0.5 0.6 0.1 0.6", 3)
    assert (cls, polygon) == (1, True)
    assert [round(float(v), 6) for v in coords.split()] == [0.3, 0.4, 0.4, 0.4]
    # polygone qui déborde de l'image : borné à [0, 1]
    assert prepare.parse_label_line("0 -0.1 0.2 0.4 0.2 0.4 1.2", 3)[1].split()[3] == "0.800000"
    for bad in (
        "9 0.5 0.5 0.2 0.2",
        "0 0.5 0.5 0.2",
        "0 a b c d",
        "0 0.5 0.5 0 0.2",
        "0 0.1 0.1 0.2",
    ):
        assert prepare.parse_label_line(bad, 3) is None, bad


def test_polygon_labels_are_converted_and_unreadable_images_dropped(tmp_path):
    sources = make_sources(tmp_path)
    labels = sorted((sources / "roboflow").rglob("labels/*.txt"))
    # 1er original (2 copies) : export « segmentation » ; 2e original : une ligne illisible
    for lbl in labels[:2]:
        lbl.write_text("0 0.4 0.4 0.6 0.4 0.6 0.6 0.4 0.6\n2 0.7 0.7 0.1 0.2\n")
    labels[2].write_text("0 0.5 0.5 0.2 0.2\n2 0.7 oups 0.1 0.2\n")
    stats = prepare.prepare(sources, tmp_path / "out", DATASET_YAML)
    assert stats["polygones_convertis"] == {"rf": 2}
    assert stats["images_labels_illisibles"] == {"rf": 1}
    assert stats["par_source"]["rf"]["boites"] == 19 * 2 and stats["validation"]["ok"]
    assert sum(stats["par_source"]["rf"]["images"].values()) == 19


def test_second_fingerprint_rejects_one_way_lookalikes():
    a = prepare.Item("s", Path("a.jpg"), None, "s:a", "1", dhash=7, vhash=0)
    b = prepare.Item("s", Path("b.jpg"), None, "s:b", "2", dhash=7, vhash=2**64 - 1)
    c = prepare.Item("s", Path("c.jpg"), None, "s:c", "3", dhash=6, vhash=1)
    prepare.merge_near_duplicates([a, b, c])
    assert a.group == c.group != b.group


def test_largest_group_goes_to_train():
    def items(group, n):
        return [
            prepare.Item("s", Path(f"{group}{i}.jpg"), None, group, f"{group}{i}", 0)
            for i in range(n)
        ]

    big = items("s:serie", 40)  # longue série de photos presque identiques
    small = [it for k in range(30) for it in items(f"s:g{k}", 2)]
    split_of = prepare.assign_splits(big + small, {}, "graine")
    assert split_of["s:serie"] == "train"
    counts = {s: 0 for s in prepare.SPLITS}
    for it in big + small:
        counts[split_of[it.group]] += 1
    assert counts == {"train": 70, "val": 20, "test": 10}


def test_cli_replaces_only_its_own_output(tmp_path, capsys):
    sources = make_sources(tmp_path)
    out = tmp_path / "dataset"
    assert prepare.main(["--sources", str(sources), "--out", str(out)]) == 0
    (out / "vieux.txt").write_text("reste d'un ancien passage")
    assert prepare.main(["--sources", str(sources), "--out", str(out), "--remplacer"]) == 0
    assert not (out / "vieux.txt").exists() and (out / "manifest.json").exists()
    assert '"par_source"' in capsys.readouterr().out
    autre = tmp_path / "autre"
    autre.mkdir()
    (autre / "precieux.txt").write_text("à garder")
    with pytest.raises(SystemExit):
        prepare.main(["--sources", str(sources), "--out", str(autre), "--remplacer"])
    assert (autre / "precieux.txt").exists()


def test_a_series_too_big_for_an_evaluation_split_goes_to_train():
    def items(group, n):
        return [
            prepare.Item("s", Path(f"{group}{i}.jpg"), None, group, f"{group}{i}", 0)
            for i in range(n)
        ]

    # trois longues séries (comme les photos de résistances de samu) et des petits groupes
    series = {"s:a": 60, "s:b": 40, "s:c": 30}
    small = [it for k in range(60) for it in items(f"s:g{k}", 2)]
    pool = [it for g, n in series.items() for it in items(g, n)] + small
    split_of = prepare.assign_splits(pool, {}, "graine")
    assert {split_of[g] for g in series} == {"train"}
    assert {split_of[f"s:g{k}"] for k in range(60)} >= {"val", "test"}
    # une petite source garde un split de test malgré le plafond (plancher en images)
    tiny = [it for k in range(12) for it in items(f"t:g{k}", 3)]
    for it in tiny:
        it.source = "t"
    assert "test" in set(prepare.assign_splits(tiny, {}, "graine").values())


def test_train_resolves_the_dataset_path_from_the_yaml_file(tmp_path):
    train = pytest.importorskip("train")
    cfg = tmp_path / "ml" / "data" / "dataset.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("path: ../../data/dataset\ntrain: images/train\nnames: {0: led}\n")
    resolved = Path(train.resolve_data(str(cfg), tmp_path / "runs"))
    data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    assert data["path"] == str((tmp_path / "data" / "dataset").resolve())
    assert data["names"] == {0: "led"} and resolved.parent == tmp_path / "runs"
    absolute = tmp_path / "abs.yaml"
    absolute.write_text(f"path: {tmp_path}\nnames: [led]\n")
    assert train.resolve_data(str(absolute), tmp_path / "runs") == str(absolute)
    assert train.resolve_data("coco8.yaml", tmp_path / "runs") == "coco8.yaml"
