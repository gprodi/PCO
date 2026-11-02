"""Génération assistée par LLM : « je veux construire X » -> ProjectSpec validée par le catalogue.

Le LLM (local d'abord, via llm_gateway) ne fait que :
  1. choisir des composants **existant dans le catalogue** et une carte ;
  2. écrire la logique (corps de ``loop``) en n'utilisant que les fonctions générées.

Tout le reste (broches, protections, câblage, code de base) reste déterministe. Les réponses sont
validées ; en cas de problème, on relance une fois avec la liste des erreurs, puis on se rabat sur
le modèle de projet du catalogue le plus proche.
"""

from __future__ import annotations

import re

from llm_gateway import Gateway, LLMError, StructuredOutputError
from loguru import logger
from pydantic import BaseModel, Field

from microforge.core.catalog import Catalog, get_catalog, normalize
from microforge.core.models import PartInstance, ProjectSpec

_FUNC = re.compile(r"^\s*(?:inline\s+)?([\w:<>]+[\s&*]+)\$\{name\}_(\w+)\(([^)]*)\)", re.M)


class IdeaPart(BaseModel):
    name: str = Field(description="nom d'instance C++ en minuscules (ex. dht, ecran, led_rouge)")
    component: str = Field(description="identifiant EXACT d'un composant du catalogue")


class ProjectIdea(BaseModel):
    """Format attendu du LLM."""

    title: str
    description: str
    board: str = Field(description="identifiant EXACT d'une carte du catalogue")
    uses_wifi: bool = False
    parts: list[IdeaPart]
    logic: str = Field(description="corps de loop() en C++ Arduino, sans la signature")
    globals_extra: str = ""
    setup_extra: str = ""


class IdeaList(BaseModel):
    ideas: list[ProjectIdea]


def component_api(catalog: Catalog, component_id: str, family: str = "esp32") -> list[str]:
    """Signatures des fonctions offertes par un composant, avec ``<nom>`` pour l'instance."""
    tpl = catalog.component(component_id).code_for(family)
    return [f"{ret.strip()} <nom>_{fn}({args.strip()})" for ret, fn, args in _FUNC.findall(tpl.api)]


def catalog_prompt(catalog: Catalog, only: set[str] | None = None) -> str:
    """Résumé du catalogue pour le prompt (identifiants + fonctions disponibles)."""
    lines = ["CARTES :"]
    for b in catalog.boards.values():
        lines.append(
            f"- {b.id} : {b.name} ({b.family}, {b.logic_v:g} V, wifi={'oui' if b.wifi else 'non'})"
        )
    lines.append("COMPOSANTS (id : description | fonctions) :")
    for c in catalog.components.values():
        if only is not None and c.id not in only and not c.passive:
            continue
        funcs = "; ".join(component_api(catalog, c.id)) or "aucune (passif)"
        lines.append(f"- {c.id} : {c.name} | {funcs}")
    return "\n".join(lines)


SYSTEM = (
    "Tu es MicroForge, assistant en électronique pour makers (ESP32, Arduino, Raspberry Pi Pico). "
    "Tu proposes des montages SÛRS et réalisables. Règles : n'utilise QUE les identifiants du "
    "catalogue fourni ; noms d'instance en minuscules (a-z, 0-9, _) ; la logique C++ n'appelle "
    "que les fonctions listées (en remplaçant <nom> par le nom d'instance), Serial, delay, millis, "
    "map, constrain et des variables déclarées dans globals_extra ; textes affichés en ASCII ; "
    "jamais de 230 V. Réponds en français."
)


class ProjectGenerator:
    """Transforme une intention en ProjectSpec valide."""

    def __init__(self, gateway: Gateway, catalog: Catalog | None = None) -> None:
        self.gateway = gateway
        self.catalog = catalog or get_catalog()

    # ------------------------------------------------------------------ validation
    def validate_idea(self, idea: ProjectIdea) -> tuple[ProjectSpec | None, list[str]]:
        """Corrige ce qui peut l'être (alias, noms), signale le reste."""
        errors: list[str] = []
        board_id = self.catalog.resolve(idea.board)
        if board_id is None or board_id not in self.catalog.boards:
            errors.append(f"carte inconnue « {idea.board} »")
        parts: list[PartInstance] = []
        used: set[str] = set()
        for p in idea.parts:
            cid = self.catalog.resolve(p.component)
            if cid is None or cid not in self.catalog.components:
                errors.append(f"composant inconnu « {p.component} »")
                continue
            name = re.sub(r"[^a-z0-9_]", "_", normalize(p.name).replace(" ", "_")) or "part"
            if name[0].isdigit():
                name = f"c_{name}"
            base, i = name, 2
            while name in used:
                name, i = f"{base}{i}", i + 1
            used.add(name)
            parts.append(PartInstance(name=name, component=cid))
        if not parts:
            errors.append("aucun composant valide")
        if errors:
            return None, errors
        assert board_id is not None
        board = self.catalog.boards[board_id]
        if idea.uses_wifi and not board.wifi:
            errors.append(f"{board.name} n'a pas de Wi-Fi")
            return None, errors
        return (
            ProjectSpec(
                title=idea.title.strip()[:80] or "Projet MicroForge",
                description=idea.description.strip(),
                board=board_id,
                parts=parts,
                uses_wifi=idea.uses_wifi,
                logic=idea.logic.strip(),
                globals_extra=idea.globals_extra,
                setup_extra=idea.setup_extra,
            ),
            [],
        )

    def closest_template(self, goal: str) -> str:
        """Modèle du catalogue le plus proche (recherche lexicale), en secours."""
        words = set(normalize(goal).split())

        def score(tid: str) -> int:
            t = self.catalog.templates[tid]
            text = set(normalize(" ".join([t.title, t.description, *t.tags])).split())
            return len(words & text)

        return max(self.catalog.templates, key=score)

    # ------------------------------------------------------------------ LLM
    def from_goal(
        self, goal: str, inventory: dict[str, int] | None = None, board: str | None = None
    ) -> ProjectSpec:
        """« Je veux construire… » -> ProjectSpec (avec repli sur un modèle du catalogue)."""
        stock = ""
        if inventory:
            stock = "Stock disponible (à privilégier) : " + ", ".join(
                f"{k}×{v}" for k, v in inventory.items()
            )
        prompt = (
            f"Objectif de l'utilisateur : {goal}\n"
            + (f"Carte imposée : {board}\n" if board else "")
            + f"{stock}\n\n{catalog_prompt(self.catalog)}\n\n"
            "Propose UN projet complet."
        )
        errors: list[str] = []
        for _attempt in range(2):
            try:
                idea = self.gateway.structured(
                    prompt + (f"\nCorrige ces erreurs : {errors}" if errors else ""),
                    schema=ProjectIdea,
                    system=SYSTEM,
                    role="code",
                    max_tokens=4096,
                )
            except (LLMError, StructuredOutputError) as exc:
                logger.warning("LLM indisponible pour la génération : {}", exc)
                break
            if board:
                idea.board = board
            spec, errors = self.validate_idea(idea)
            if spec is not None:
                return spec
            logger.info("Idée invalide, nouvelle tentative : {}", errors)
        tid = self.closest_template(goal)
        logger.info("Repli sur le modèle « {} »", tid)
        from microforge.core.builder import ProjectBuilder

        target = board or (
            "esp32-devkit-v1" if self.catalog.templates[tid].requires_wifi else "arduino-uno"
        )
        return ProjectBuilder(self.catalog).spec_from_template(tid, target)

    def ideas_from_inventory(self, inventory: dict[str, int], n: int = 3) -> list[ProjectSpec]:
        """Idées créatives (hors modèles) contraintes au stock, validées une à une."""
        only = {self.catalog.resolve(k) or k for k in inventory}
        prompt = (
            f"Stock de l'utilisateur : {', '.join(f'{k}×{v}' for k, v in inventory.items())}\n\n"
            f"{catalog_prompt(self.catalog, only=only)}\n\n"
            f"Propose {n} projets originaux réalisables UNIQUEMENT avec ce stock "
            "(résistances et fils exceptés)."
        )
        try:
            ideas = self.gateway.structured(prompt, schema=IdeaList, system=SYSTEM, role="code")
        except (LLMError, StructuredOutputError) as exc:
            logger.warning("Pas d'idées LLM : {}", exc)
            return []
        specs = []
        for idea in ideas.ideas[:n]:
            spec, errs = self.validate_idea(idea)
            if spec is not None:
                specs.append(spec)
            else:
                logger.info("Idée écartée : {}", errs)
        return specs
