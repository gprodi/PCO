"""Télécharge les jeux Roboflow Universe retenus, après contrôle de leur licence (CC BY ou domaine public).

    ROBOFLOW_API_KEY=… uv run --no-project --with httpx --with pyyaml \\
        python microforge/ml/fetch_roboflow.py data/sources

Sont téléchargés les jeux décrits dans ``microforge/ml/sources/*.yaml`` qui portent un champ
``roboflow_version`` (l'espace de travail et le projet viennent de ``url``). Pour chacun :

1. licence lue par l'API (``GET /<espace>/<projet>``) : refus si elle n'est ni CC BY ni domaine public, ou
   si elle ne correspond plus à celle notée dans le fichier de correspondance (licence changée en amont) ;
2. export YOLOv11 demandé puis attendu (``GET /<espace>/<projet>/<version>/yolov11`` répond 202 tant
   qu'il est en préparation), zip téléchargé, contrôlé (aucun chemin absolu, ``..`` ni lien) et extrait
   dans ``<dossier>/<nom du fichier de correspondance>/`` avec son ``source.yaml`` ;
3. ligne ``License:`` du README de l'export vérifiée à son tour.

La clé (compte Roboflow gratuit) n'est lue que dans la variable d'environnement ``ROBOFLOW_API_KEY`` et
n'apparaît dans aucun message, même d'erreur. Sur GitHub : secret ``ROBOFLOW_API_KEY`` du dépôt.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile
from collections.abc import Callable
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from importer_zips import IMAGE_EXT, check_archive  # noqa: E402

API = "https://api.roboflow.com"
FORMAT = "yolov11"
UNIVERSE = re.compile(r"^https://universe\.roboflow\.com/([\w.-]+)/([\w.-]+)/?$")
UA = {"User-Agent": "MicroForge-collecte/0.2 (projet pedagogique; +https://github.com/gprodi/PCO)"}


class RoboflowError(RuntimeError):
    """Erreur de l'API, sans la clé."""


def _norm(licence: str) -> str:
    return re.sub(r"[\s_-]+", "", licence).upper()


def check_licence(licence: str, expected: str | None = None) -> str:
    """Licence acceptée (CC BY, sans NC ni ND, ou domaine public) et identique à celle attendue."""
    norm = _norm(licence or "")
    if not norm or "NC" in norm or "ND" in norm:
        raise RoboflowError(f"licence refusée : {licence!r}")
    if not (norm.startswith("CCBY") or norm in {"PUBLICDOMAIN", "CC0", "CC01.0"}):
        raise RoboflowError(f"licence refusée : {licence!r}")
    if expected is not None and _norm(expected) != norm:
        raise RoboflowError(
            f"licence {licence!r} différente de celle du fichier de correspondance ({expected!r})"
        )
    return licence


def reference(cfg: dict) -> tuple[str, str, int]:
    match = UNIVERSE.match(cfg.get("url", ""))
    if not match or not isinstance(cfg.get("roboflow_version"), int):
        raise ValueError(f"{cfg.get('nom')} : url Roboflow Universe et roboflow_version attendus")
    return match.group(1), match.group(2), cfg["roboflow_version"]


class Client:
    def __init__(self, api_key: str, http: httpx.Client | None = None):
        self._key = api_key
        self._http = http or httpx.Client(timeout=120, headers=UA, follow_redirects=True)

    def get(self, path: str) -> tuple[int, dict]:
        try:
            response = self._http.get(f"{API}{path}", params={"api_key": self._key})
        except httpx.HTTPError as exc:  # le message d'httpx contiendrait l'URL, donc la clé
            raise RoboflowError(f"{path} : {type(exc).__name__}") from None
        if response.status_code not in (200, 202):
            raise RoboflowError(f"{path} : HTTP {response.status_code}")
        try:
            return response.status_code, response.json()
        except ValueError:
            raise RoboflowError(f"{path} : réponse non JSON") from None

    def download(self, link: str, target: Path) -> str:
        """Télécharge le zip d'export (lien signé, sans la clé) ; renvoie son SHA-256."""
        sha = hashlib.sha256()
        try:
            with self._http.stream("GET", link) as response:
                if response.status_code != 200:
                    raise RoboflowError(f"export : HTTP {response.status_code}")
                with target.open("wb") as fh:
                    for chunk in response.iter_bytes():
                        sha.update(chunk)
                        fh.write(chunk)
        except httpx.HTTPError as exc:
            raise RoboflowError(f"export : {type(exc).__name__}") from None
        return sha.hexdigest()


def export_link(
    client: Client,
    path: str,
    attempts: int = 120,
    pause: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Lien du zip ; l'export est généré à la première demande (202 tant qu'il n'est pas prêt)."""
    for _ in range(attempts):
        status, payload = client.get(path)
        link = (payload.get("export") or {}).get("link")
        if status == 200 and link:
            return link
        sleep(pause)
    raise RoboflowError(f"{path} : export toujours en préparation")


def _check_readme(readme: Path, expected: str) -> None:
    if not readme.exists():
        return
    lines = readme.read_text(encoding="utf-8", errors="replace").splitlines()
    line = next((ln for ln in lines if ln.lower().startswith("license:")), "")
    if line:
        check_licence(line.split(":", 1)[1].strip(), expected)


def fetch_one(client: Client, cfg_path: Path, dest_root: Path, **wait) -> dict:
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    workspace, project, version = reference(cfg)
    expected = cfg.get("licence", "").replace("-", " ")
    _, info = client.get(f"/{workspace}/{project}")
    licence = check_licence((info.get("project") or info).get("license", ""), expected)
    link = export_link(client, f"/{workspace}/{project}/{version}/{FORMAT}", **wait)
    dest = dest_root / cfg_path.stem
    if dest.exists():
        shutil.rmtree(dest)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "export.zip"
        digest = client.download(link, archive)
        with zipfile.ZipFile(archive) as zf:
            check_archive(zf)
            dest.mkdir(parents=True)
            zf.extractall(dest)
    try:
        _check_readme(dest / "README.dataset.txt", expected)
    except RoboflowError:
        shutil.rmtree(dest)  # rien ne reste d'un jeu refusé
        raise
    shutil.copyfile(cfg_path, dest / "source.yaml")
    return {
        "nom": cfg.get("nom", cfg_path.stem),
        "dossier": dest.name,
        "url": cfg["url"],
        "version": version,
        "licence_api": licence,
        "sha256_zip": digest,
        "images": sum(1 for p in dest.rglob("*") if p.suffix.lower() in IMAGE_EXT),
    }


def main(argv: list[str] | None = None, http: httpx.Client | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    dest_root = Path(args[0]) if args else Path("data/sources")
    configs = Path(args[1]) if len(args) > 1 else HERE / "sources"
    key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if not key:
        print("ROBOFLOW_API_KEY absente : rien n'est téléchargé.")
        return 2
    client = Client(key, http)
    report, failed = [], []
    for cfg_path in sorted(configs.glob("*.yaml")):
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        if "roboflow_version" not in cfg:
            continue
        try:
            report.append(fetch_one(client, cfg_path, dest_root))
        except (RoboflowError, ValueError, zipfile.BadZipFile) as exc:
            failed.append((cfg_path.stem, str(exc).replace(key, "***")))
    dest_root.mkdir(parents=True, exist_ok=True)
    (dest_root / "roboflow-provenance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("| Jeu | Version | Licence (API) | Images |\n|---|---|---|---|")
    for r in report:
        print(f"| {r['nom']} | {r['version']} | {r['licence_api']} | {r['images']} |")
    for name, reason in failed:
        print(f"| {name} | — | **non téléchargé** : {reason} | 0 |")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
