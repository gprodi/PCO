"""« Que puis-je construire avec mon stock ? » — classement des modèles de projets selon l'inventaire."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from microforge.core.allocator import AllocationError, PinAllocator
from microforge.core.builder import ProjectBuilder
from microforge.core.catalog import Catalog, get_catalog
from microforge.core.erc import run_erc
from microforge.core.models import BoardDef, ProjectTemplate, Severity

TOOLING = {"breadboard-830", "jumper-wires", "usb-cable", "perfboard"}


@dataclass
class Suggestion:
    """Un projet réalisable (ou presque) avec le stock."""

    template: ProjectTemplate
    board: BoardDef
    owned_ratio: float
    missing: dict[str, int] = field(default_factory=dict)
    board_owned: bool = True
    electrical_ok: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def feasible_now(self) -> bool:
        """Tout est en stock et le montage passe l'ERC."""
        return self.board_owned and not self.missing and self.electrical_ok

    @property
    def score(self) -> float:
        s = self.owned_ratio * 100 - 12 * sum(self.missing.values())
        s -= 0 if self.board_owned else 25
        s -= 0 if self.electrical_ok else 50
        s -= 2 * (self.template.difficulty - 1)
        return round(s, 1)

    def to_dict(self) -> dict:
        return {
            "template_id": self.template.id,
            "title": self.template.title,
            "description": self.template.description,
            "difficulty": self.template.difficulty,
            "tags": self.template.tags,
            "board": self.board.id,
            "board_name": self.board.name,
            "board_owned": self.board_owned,
            "owned_ratio": round(self.owned_ratio, 2),
            "missing": self.missing,
            "feasible_now": self.feasible_now,
            "electrical_ok": self.electrical_ok,
            "warnings": self.warnings,
            "score": self.score,
            "learning": self.template.learning,
        }


def _board_candidates(
    catalog: Catalog, inventory: Counter[str], tpl: ProjectTemplate
) -> list[tuple[BoardDef, bool]]:
    def compatible(b: BoardDef) -> bool:
        return b.family in tpl.board_families and (b.wifi or not tpl.requires_wifi)

    owned = [catalog.boards[b] for b in inventory if b in catalog.boards and inventory[b] > 0]
    owned_ok = [b for b in owned if compatible(b)]
    if owned_ok:
        return [(b, True) for b in owned_ok]
    # Aucune carte possédée compatible : proposer la moins chère compatible
    others = sorted(
        (b for b in catalog.boards.values() if compatible(b)), key=lambda b: b.price_eur or 99
    )
    return [(b, False) for b in others[:1]]


def suggest_projects(
    inventory: dict[str, int],
    catalog: Catalog | None = None,
    limit: int = 10,
    max_missing: int = 3,
) -> list[Suggestion]:
    """Classe les modèles de projets selon le stock (identifiants ou alias acceptés)."""
    catalog = catalog or get_catalog()
    inv: Counter[str] = Counter()
    for ref, qty in inventory.items():
        key = catalog.resolve(ref)
        if key:
            inv[key] += int(qty)
    allocator = PinAllocator(catalog)
    builder = ProjectBuilder(catalog)
    results: list[Suggestion] = []
    for tpl in catalog.templates.values():
        needed = Counter(p.component for p in tpl.parts)
        needed = Counter({catalog.resolve(k) or k: v for k, v in needed.items()})
        missing = {cid: qty - min(qty, inv.get(cid, 0)) for cid, qty in needed.items()}
        missing = {k: v for k, v in missing.items() if v > 0 and k not in TOOLING}
        if sum(missing.values()) > max_missing:
            continue
        total = sum(needed.values())
        owned = total - sum(missing.values())
        best: Suggestion | None = None
        for board, board_owned in _board_candidates(catalog, inv, tpl):
            spec = builder.spec_from_template(tpl.id, board.id)
            try:
                alloc = allocator.allocate(spec)
            except AllocationError:
                continue
            issues = [*alloc.issues, *run_erc(spec, alloc, catalog)]
            errors = [i for i in issues if i.severity == Severity.ERROR]
            sug = Suggestion(
                template=tpl,
                board=board,
                owned_ratio=owned / total if total else 1.0,
                missing=missing,
                board_owned=board_owned,
                electrical_ok=not errors,
                warnings=[i.message for i in issues if i.severity == Severity.WARNING],
            )
            if best is None or sug.score > best.score:
                best = sug
        if best:
            results.append(best)
    results.sort(key=lambda s: (-s.score, s.template.difficulty, s.template.id))
    return results[:limit]
