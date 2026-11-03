"""Schémas Pydantic d'entrée/sortie (validation stricte, aucune fuite de champ sensible — OWASP API3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    city: str | None = Field(default=None, max_length=80)
    consent_training: bool = False

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not (any(c.isdigit() for c in v) and any(c.isalpha() for c in v)):
            raise ValueError("le mot de passe doit contenir des lettres et des chiffres")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    city: str | None
    role: str
    consent_training: bool
    created_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 — type OAuth2, pas un secret
    expires_in: int


class RefreshIn(BaseModel):
    refresh_token: str


class ComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    category_id: str
    description: str
    supply_min_v: float | None
    supply_max_v: float | None
    interfaces: str
    reference_price_eur: float | None
    datasheet_url: str | None


class ComponentDetail(ComponentOut):
    pins: list[dict[str, Any]] = []
    libraries: list[str] = []
    notes: list[str] = []


class OfferOut(BaseModel):
    supplier: str
    unit_price_eur: float
    stock: int | None
    url: str
    collected_at: datetime


class InventoryIn(BaseModel):
    component_id: str = Field(max_length=60)
    #: Valeur des passifs : nombre (4700) ou saisie libre (« 4k7 », « 100 nF ») ; 0 = sans valeur.
    value: float = Field(default=0.0, ge=0)
    quantity: int = Field(default=1, ge=0, le=10000)
    location: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=200)

    @field_validator("value", mode="before")
    @classmethod
    def parse_value(cls, v: object) -> float:
        from microforge.core.values import parse_value

        if v is None or v == "":
            return 0.0
        parsed = parse_value(v)  # type: ignore[arg-type]
        if parsed is None:
            raise ValueError(f"valeur illisible : {v!r} (ex. 4k7, 220, 100nF)")
        return parsed


class InventoryPatch(BaseModel):
    quantity: int | None = Field(default=None, ge=0, le=10000)
    location: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=200)


class InventoryOut(InventoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    updated_at: datetime


class BulkInventoryIn(BaseModel):
    items: list[InventoryIn] = Field(max_length=200)
    location: str = Field(default="", max_length=80)


class FeedbackIn(BaseModel):
    kind: str = Field(pattern=r"^(correct|wrong_label|false_positive|missed)$")
    predicted_component_id: str | None = None
    corrected_component_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: str = Field(default="yolo", pattern=r"^(yolo|vlm)$")
    model_version: str = Field(default="", max_length=60)
    photo_id: int | None = None


class PhotoIn(BaseModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    width: int = Field(gt=0, le=10000)
    height: int = Field(gt=0, le=10000)
    model_version: str = Field(default="", max_length=60)


class ProjectIn(BaseModel):
    title: str = Field(max_length=120)
    board_id: str
    template_id: str | None = None
    spec: dict[str, Any]


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    board_id: str
    template_id: str | None
    created_at: datetime


class ShoppingIn(BaseModel):
    project_id: int | None = None
    template_id: str | None = None
    board_id: str | None = None
