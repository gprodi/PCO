"""Schémas d'api_ia."""

from __future__ import annotations

from typing import Any, Literal

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
    #: Charge de l'atelier virtuel (programme transpilé, composants, broches attendues) ; ``None``
    #: si la logique du projet ne se traduit pas en JavaScript.
    atelier: dict[str, Any] | None = None
    #: Métadonnées du modèle de projet (notions, difficulté, références, cartes compatibles) ;
    #: ``None`` pour un projet libre (``/v1/builds/from-goal``).
    template: dict[str, Any] | None = None
    #: Onglet « Apprendre » : montage pas à pas (avec le pourquoi de chaque fil), programme
    #: expliqué, notions du projet, quiz de son étape du parcours (``None`` hors parcours).
    apprendre: dict[str, Any] | None = None
    #: ``/v1/builds/from-goal`` seulement : « ia » (conçu par le modèle de langage puis validé par
    #: le moteur) ou « repli » (modèle du catalogue le plus proche, faute de proposition valide).
    origin: Literal["ia", "repli"] | None = None
    #: Phrase à montrer à l'utilisateur : d'où vient le projet, ce qui n'a pas été vérifié.
    notice: str | None = None


class CopilotIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    inventory: dict[str, int] | None = Field(
        default=None, max_length=300, description="stock facultatif : projets possibles cités"
    )
