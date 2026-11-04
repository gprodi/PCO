"""Téléchargement des jeux Roboflow Universe sur le runner : licence, export, zip sûr, clé jamais affichée."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import httpx
import pytest
import yaml

ML = Path(__file__).resolve().parents[1] / "ml"
sys.path.insert(0, str(ML))

import fetch_roboflow as fr  # noqa: E402

KEY = "cle-secrete-123"


def _zip(readme_licence: str = "CC BY 4.0", extra: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.yaml", "names: ['Resistor']\n")
        zf.writestr(
            "README.dataset.txt", f"Provided by a Roboflow user\nLicense: {readme_licence}\n"
        )
        zf.writestr("train/images/r1_jpg.rf.a.jpg", b"\xff\xd8jpeg")
        zf.writestr("train/labels/r1_jpg.rf.a.txt", "0 0.5 0.5 0.2 0.2\n")
        for name, data in (extra or {}).items():
            zf.writestr(name, data)
    return buf.getvalue()


def _config(dir_: Path, name="jeu-v3i-yolov11", **over) -> Path:
    cfg = {
        "nom": "jeu",
        "licence": "CC-BY-4.0",
        "url": "https://universe.roboflow.com/espace/projet-abc",
        "roboflow_version": 3,
        "classes": {"Resistor": "resistor"},
        **over,
    }
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / f"{name}.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return path


def _api(licence="CC BY 4.0", pending=2, archive: bytes | None = None, calls=None):
    state = {"pending": pending}

    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        if request.url.host == "storage.example":
            assert "api_key" not in str(request.url)  # le lien d'export est signé, sans la clé
            return httpx.Response(200, content=archive if archive is not None else _zip(licence))
        assert request.url.params["api_key"] == KEY
        if request.url.path == "/espace/projet-abc":
            return httpx.Response(
                200, json={"project": {"license": licence, "type": "object-detection"}}
            )
        if request.url.path == "/espace/projet-abc/3/yolov11":
            if state["pending"]:
                state["pending"] -= 1
                return httpx.Response(202, json={"ready": False, "progress": 0.5})
            return httpx.Response(
                200, json={"export": {"link": "https://storage.example/x.zip?sig=1"}}
            )
        return httpx.Response(404, json={"error": "inconnu"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_licences():
    for ok in ("CC BY 4.0", "CC-BY-4.0", "Public Domain", "CC0 1.0"):
        assert fr.check_licence(ok) == ok
    for bad in ("CC BY-NC 4.0", "CC BY-NC-SA 4.0", "CC BY-ND 4.0", "Private", "", "MIT"):
        with pytest.raises(fr.RoboflowError):
            fr.check_licence(bad)
    with pytest.raises(fr.RoboflowError, match="différente"):
        fr.check_licence("Public Domain", "CC BY 4.0")


def test_reference_comes_from_the_universe_url():
    cfg = {
        "url": "https://universe.roboflow.com/cv2024-4skvf/electronic-components-detection-jzf42"
    }
    assert fr.reference({**cfg, "roboflow_version": 4}) == (
        "cv2024-4skvf",
        "electronic-components-detection-jzf42",
        4,
    )
    with pytest.raises(ValueError):
        fr.reference(cfg)


def test_fetch_waits_for_export_checks_licence_and_installs_source(tmp_path, monkeypatch, capsys):
    configs = tmp_path / "configs"
    cfg_path = _config(configs)
    # fichier sans roboflow_version (photos personnelles, IoTKITs) : ignoré
    (configs / "sans-roboflow.yaml").write_text("nom: local\nlicence: personnelle\n")
    monkeypatch.setattr(fr.time, "sleep", lambda s: None)
    monkeypatch.setenv("ROBOFLOW_API_KEY", KEY)
    calls: list[str] = []
    code = fr.main([str(tmp_path / "sources"), str(configs)], http=_api(calls=calls))
    out = capsys.readouterr().out
    assert code == 0, out
    dest = tmp_path / "sources" / "jeu-v3i-yolov11"
    assert (dest / "source.yaml").read_text(encoding="utf-8") == cfg_path.read_text(
        encoding="utf-8"
    )
    assert (dest / "train" / "labels" / "r1_jpg.rf.a.txt").exists()
    assert calls.count("/espace/projet-abc/3/yolov11") == 3  # 2 réponses 202 puis le lien
    provenance = json.loads((tmp_path / "sources" / "roboflow-provenance.json").read_text())
    assert provenance[0]["licence_api"] == "CC BY 4.0" and provenance[0]["images"] == 1
    assert len(provenance[0]["sha256_zip"]) == 64 and KEY not in out


@pytest.mark.parametrize(
    ("api_licence", "archive", "reason"),
    [
        ("CC BY-NC 4.0", None, "licence refusée"),
        ("CC BY 4.0", _zip(extra={"../evil.txt": b"x"}), "chemin refusé"),
        ("CC BY 4.0", _zip(readme_licence="CC BY-NC 4.0"), "licence refusée"),
    ],
)
def test_bad_datasets_are_not_installed(
    tmp_path, monkeypatch, capsys, api_licence, archive, reason
):
    configs = tmp_path / "configs"
    _config(configs)
    monkeypatch.setattr(fr.time, "sleep", lambda s: None)
    monkeypatch.setenv("ROBOFLOW_API_KEY", KEY)
    code = fr.main(
        [str(tmp_path / "sources"), str(configs)], http=_api(api_licence, archive=archive)
    )
    out = capsys.readouterr().out
    assert code == 1 and reason in out and KEY not in out
    assert not (tmp_path / "sources" / "jeu-v3i-yolov11").exists()
    assert not (tmp_path / "evil.txt").exists()


def test_api_errors_never_show_the_key(tmp_path, monkeypatch, capsys):
    def boom(request):
        raise httpx.ConnectError(f"échec vers {request.url}")  # l'URL contient la clé

    configs = tmp_path / "configs"
    _config(configs)
    monkeypatch.setenv("ROBOFLOW_API_KEY", KEY)
    http = httpx.Client(transport=httpx.MockTransport(boom))
    assert fr.main([str(tmp_path / "sources"), str(configs)], http=http) == 1
    out = capsys.readouterr().out
    assert "ConnectError" in out and KEY not in out


def test_export_that_never_finishes(monkeypatch):
    client = fr.Client(KEY, _api(pending=10**6))
    with pytest.raises(fr.RoboflowError, match="toujours en préparation"):
        fr.export_link(client, "/espace/projet-abc/3/yolov11", attempts=3, sleep=lambda s: None)


def test_missing_key(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("ROBOFLOW_API_KEY", raising=False)
    assert fr.main([str(tmp_path)]) == 2 and "absente" in capsys.readouterr().out


def test_every_roboflow_source_is_downloadable():
    configs = sorted((ML / "sources").glob("*.yaml"))
    roboflow = [p for p in configs if "universe.roboflow.com" in p.read_text(encoding="utf-8")]
    assert len(roboflow) >= 6
    for path in roboflow:
        workspace, project, version = fr.reference(yaml.safe_load(path.read_text(encoding="utf-8")))
        assert workspace and project and version >= 1, path.name
