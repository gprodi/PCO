"""Schémas d'api_ia."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from microforge.core.models import ProjectSpec


class InventoryIn(BaseModel):
    inventory: dict[str, int] = Field(
        description="{identifiant ou alias: quantité}", max_length=300
    )
    limit: int = Field(default=10, ge=1, le=31)
    max_missing: int = Field(default=3, ge=0, le=10)


class BuildIn(BaseModel):
    template_id: str | None = None
    board: str | None = None
    spec: ProjectSpec | None = None
    #: Valeurs de résistances possédées (Ω, cf. api_data /v1/inventory/values) : les résistances
    #: ajoutées par le moteur sont choisies parmi elles quand une valeur voisine convient.
    owned_resistors: list[float] | None = Field(default=None, max_length=200)


class GoalIn(BaseModel):
    goal: str = Field(min_length=5, max_length=500)
    board: str | None = None
    inventory: dict[str, int] | None = None
    components: list[str] | None = Field(default=None, max_length=20)


class ExploreIn(BaseModel):
    inventory: dict[str, int] | None = Field(default=None, max_length=300)


class IdeasIn(BaseModel):
    inventory: dict[str, int] = Field(max_length=300)
    n: int = Field(default=3, ge=1, le=5)


class BuildOut(BaseModel):
    spec: ProjectSpec
    ok: bool
    issues: list[dict[str, Any]]
    assignments: list[dict[str, Any]]
    added_parts: list[dict[str, Any]]
    bom: list[dict[str, Any]]
    libraries: list[str]
    files: dict[str, str]


class CopilotIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    inventory: dict[str, int] | None = Field(
        default=None, max_length=300, description="stock facultatif : projets possibles cités"
    )
