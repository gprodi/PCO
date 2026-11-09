"""Workflows GitHub Actions : actions épinglées par empreinte complète, runtime Node 24.

GitHub a retiré Node 20 de ses runners (septembre 2026) ; les actions qui le déclarent encore
tournent de force sous Node 24 (avertissement dans chaque job), et certaines annoncent qu'elles
cesseront de fonctionner (gitleaks-action v2). Veille 2026-46 : les workflows qui tournent sur
les branches de travail sont passés aux versions Node 24.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
USES = re.compile(r"uses: ([\w./-]+)@(\S+)(?: *# *(\S+))?")

#: Empreintes des versions Node 20 remplacées (veille 2026-46).
NODE20 = {
    "11bd71901bbe5b1630ceea73d27597364c9af683",  # actions/checkout v4.2.2
    "d0cc045d04ccac9d8b7881df0226f9e82c39688e",  # astral-sh/setup-uv v6
    "ea165f8d65b6e75b540449e92b4886f43607fa02",  # actions/upload-artifact v4.6.2
    "49933ea5288caeca8642d1e84afbd3f7d6820020",  # actions/setup-node v4
    "ff98106e4c7b2bc287b24eaf42907196329070c7",  # gitleaks/gitleaks-action v2
}
#: Workflows qui tournent sur les branches de travail : migrés et vérifiés par la CI.
MIGRATED = ("ci.yml", "collecte.yml", "docs.yml", "veille.yml")


def _uses(name: str) -> list[tuple[str, str, str | None]]:
    return USES.findall((WORKFLOWS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_actions_epinglees_par_empreinte_avec_version(path):
    """Une étiquette (v4) peut être déplacée ; une empreinte de commit, non (chaîne d'approvisionnement)."""
    for action, ref, version in _uses(path.name):
        if action.startswith("./"):
            continue
        assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{path.name} : {action}@{ref} non épinglée"
        assert version and version.startswith("v"), f"{path.name} : version de {action} non notée"


@pytest.mark.parametrize("name", MIGRATED)
def test_plus_d_action_node20_dans_les_workflows_migres(name):
    refs = {ref for _, ref, _ in _uses(name)}
    assert not refs & NODE20, f"{name} utilise encore une action Node 20"


def test_installation_des_coeurs_arduino_avec_reprise():
    """Les serveurs des cœurs répondent parfois 504 : chaque téléchargement est repris."""
    import yaml

    ci = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    steps = ci["jobs"]["firmware"]["steps"]
    install = next(s["run"] for s in steps if s.get("name", "").startswith("Installer arduino-cli"))
    assert "retry() {" in install
    for cmd in ("arduino-cli core update-index", 'arduino-cli core install "$CORE"', "lib install"):
        line = next(ln for ln in install.splitlines() if cmd in ln)
        assert "retry " in line, f"sans reprise : {line.strip()}"
