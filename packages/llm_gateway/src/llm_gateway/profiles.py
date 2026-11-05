"""Détection du matériel et choix du profil (modèles locaux, paramètres YOLO, mémoire Spark).

Les trois machines de Gaël :

* Mac mini M4 16 Go unifiés      -> ``mac-m4-16``  (Ollama natif Metal, YOLO sur ``mps``)
* PC bureau Win11, GPU 8 Go      -> ``gpu-8gb``    (CUDA, modèles 8B/14B)
* PC école Win11, GPU 6–8 Go     -> ``gpu-6gb``    (CUDA, modèles 4B)
* tout le reste                  -> ``cpu``
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Any

import yaml
from loguru import logger


@dataclass(frozen=True)
class HardwareInfo:
    """Ce que l'on sait de la machine."""

    system: str
    machine: str
    ram_gb: float | None
    gpu_name: str | None = None
    vram_gb: float | None = None

    @property
    def is_apple_silicon(self) -> bool:
        """Mac à puce Apple (M1…M4)."""
        return self.system == "Darwin" and self.machine in {"arm64", "aarch64"}


@dataclass(frozen=True)
class Profile:
    """Profil résolu."""

    name: str
    description: str
    ollama_models: dict[str, str]
    yolo: dict[str, Any] = field(default_factory=dict)
    spark: dict[str, Any] = field(default_factory=dict)
    remote_models: dict[str, dict[str, str]] = field(default_factory=dict)

    def model_for(self, provider: str, role: str) -> str:
        """Nom du modèle à utiliser pour un fournisseur et un rôle."""
        if provider == "ollama":
            return self.ollama_models.get(role) or self.ollama_models["text"]
        models = self.remote_models.get(provider, {})
        return models.get(role) or models.get("text", "")


def _run(cmd: list[str]) -> str | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True)  # noqa: S603
    except (subprocess.SubprocessError, OSError):
        return None
    return out.stdout.strip()


def _ram_gb() -> float | None:
    if platform.system() == "Darwin":
        out = _run(["sysctl", "-n", "hw.memsize"])
        return round(int(out) / 1024**3, 1) if out and out.isdigit() else None
    try:
        pages, page_size = os.sysconf("SC_PHYS_PAGES"), os.sysconf("SC_PAGE_SIZE")
        return round(pages * page_size / 1024**3, 1)
    except (ValueError, OSError, AttributeError):
        return None


def _nvidia() -> tuple[str | None, float | None]:
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if not out:
        return None, None
    first = out.splitlines()[0]
    name, _, mem = first.rpartition(",")
    try:
        return name.strip(), round(float(mem) / 1024, 1)
    except ValueError:
        return name.strip() or None, None


def detect_hardware() -> HardwareInfo:
    """Inspecte la machine courante (sans dépendance lourde comme torch ou psutil)."""
    gpu_name, vram = _nvidia()
    return HardwareInfo(
        system=platform.system(),
        machine=platform.machine().lower(),
        ram_gb=_ram_gb(),
        gpu_name=gpu_name,
        vram_gb=vram,
    )


def choose_profile_name(hw: HardwareInfo) -> str:
    """Règles de choix du profil à partir du matériel détecté."""
    if hw.is_apple_silicon:
        return "mac-m4-16"
    if hw.vram_gb is not None:
        if hw.vram_gb >= 7.5:
            return "gpu-8gb"
        if hw.vram_gb >= 5.5:
            return "gpu-6gb"
    return "cpu"


@lru_cache(maxsize=1)
def _profiles_data() -> dict[str, Any]:
    text = resources.files("llm_gateway").joinpath("profiles.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


def available_profiles() -> list[str]:
    """Noms des profils déclarés dans profiles.yaml."""
    return list(_profiles_data()["profiles"])


def load_profile(name: str | None = None, hw: HardwareInfo | None = None) -> Profile:
    """Charge un profil par son nom, ou le détecte automatiquement."""
    data = _profiles_data()
    if not name:  # absent ou vide (« LLM_PROFILE= » dans .env.example) : détection automatique
        hw = hw or detect_hardware()
        name = choose_profile_name(hw)
        logger.info("Profil matériel détecté : {} ({})", name, hw)
    if name not in data["profiles"]:
        raise ValueError(f"Profil inconnu : {name!r}. Disponibles : {available_profiles()}")
    raw = data["profiles"][name]
    return Profile(
        name=name,
        description=raw.get("description", ""),
        ollama_models=raw["ollama"],
        yolo=raw.get("yolo", {}),
        spark=raw.get("spark", {}),
        remote_models=data.get("remote", {}),
    )
