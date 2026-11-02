"""Schémas des livrables de révision (identiques pour le contenu généré par LLM et le contenu initial)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Notion(BaseModel):
    terme: str
    definition: str


class CodeExample(BaseModel):
    titre: str
    lang: str = "python"
    code: str
    explication: str = ""


class Fiche(BaseModel):
    titre: str
    resume: str = Field(description="5 à 8 phrases")
    objectifs: list[str] = Field(default_factory=list)
    notions: list[Notion] = Field(default_factory=list)
    points_cles: list[str] = Field(default_factory=list)
    code: list[CodeExample] = Field(default_factory=list)
    pieges: list[str] = Field(default_factory=list)
    competences: list[str] = Field(default_factory=list, description="identifiants C1..C21")
    sources: list[str] = Field(
        default_factory=list, description="identifiants de passages <slug>#n"
    )

    @field_validator("competences")
    @classmethod
    def valid_competences(cls, v: list[str]) -> list[str]:
        return [
            c for c in v if c.upper().startswith("C") and c[1:].isdigit() and 1 <= int(c[1:]) <= 21
        ]


class Question(BaseModel):
    question: str
    choix: list[str] = Field(min_length=2, max_length=5)
    bonne: int = Field(ge=0, description="index de la bonne réponse")
    explication: str = ""
    difficulte: int = Field(default=1, ge=1, le=3)

    @field_validator("bonne")
    @classmethod
    def in_range(cls, v: int, info) -> int:
        choix = info.data.get("choix") or []
        if choix and v >= len(choix):
            raise ValueError("index de bonne réponse hors des choix")
        return v


class Quiz(BaseModel):
    questions: list[Question]


class Flashcard(BaseModel):
    recto: str
    verso: str
    tags: list[str] = Field(default_factory=list)


class Flashcards(BaseModel):
    cartes: list[Flashcard]


class Exercice(BaseModel):
    titre: str
    niveau: int = Field(default=1, ge=1, le=3)
    enonce: str
    indices: list[str] = Field(default_factory=list)
    corrige: str


class Exercices(BaseModel):
    exercices: list[Exercice]


class Replique(BaseModel):
    voix: str = Field(description="A (animatrice) ou B (expert)")
    texte: str


class Podcast(BaseModel):
    titre: str
    repliques: list[Replique]


class MindMap(BaseModel):
    markdown: str = Field(
        description="liste Markdown hiérarchique (markmap), titre de niveau 1 = cours"
    )


class CourseContent(BaseModel):
    """Tout le contenu d'un cours (format du fichier seed et de content/<slug>/content.json)."""

    slug: str
    titre: str
    theme: str
    fiche: Fiche
    quiz: Quiz
    flashcards: Flashcards
    exercices: Exercices
    mindmap: MindMap
    podcast: Podcast
    origine: str = "seed"  # seed | llm
