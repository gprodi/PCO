"""Chat avec les cours (RAG avec citations) et oral blanc (jury simulé à partir du référentiel)."""

from __future__ import annotations

import random

from llm_gateway import Gateway
from pydantic import BaseModel, Field

from revision.config import referentiel
from revision.store import VectorIndex

CHAT_SYSTEM = (
    "Tu es l'assistant de révision de Gaël (titre Développeur en IA). Réponds en français, de façon "
    "pédagogique, UNIQUEMENT à partir des passages fournis ; cite-les entre crochets, ex. [mlflow#3]. "
    "Si la réponse n'est pas dans les passages, dis-le et propose une piste de recherche."
)


class ChatAnswer(BaseModel):
    answer: str
    citations: list[dict]


def chat(
    question: str,
    index: VectorIndex,
    gateway: Gateway,
    courses: list[str] | None = None,
    k: int = 6,
) -> ChatAnswer:
    qv = gateway.embed([question])[0]
    hits = index.search(qv, k=k, courses=courses)
    context = "\n\n".join(f"[{h['id']}] ({h['heading']})\n{h['text']}" for _, h in hits)
    answer = gateway.chat(
        f"Passages :\n{context}\n\nQuestion : {question}",
        system=CHAT_SYSTEM,
        role="text",
        max_tokens=1500,
    )
    return ChatAnswer(
        answer=answer,
        citations=[
            {
                "id": h["id"],
                "course": h["course"],
                "heading": h["heading"],
                "score": round(s, 3),
                "extrait": h["text"][:240],
            }
            for s, h in hits
        ],
    )


class JuryQuestion(BaseModel):
    competence: str
    question: str
    attendus: list[str] = Field(description="éléments de réponse attendus par le jury")


class JuryQuestions(BaseModel):
    questions: list[JuryQuestion]


class Evaluation(BaseModel):
    note: int = Field(ge=0, le=20)
    points_forts: list[str]
    a_ameliorer: list[str]
    criteres_couverts: list[str]


def oral_questions(
    epreuve: str, gateway: Gateway, n: int = 5, seed: int | None = None
) -> JuryQuestions:
    ref = referentiel()
    ep = next(e for e in ref["epreuves"] if e["id"] == epreuve)
    comps = [c for c in ref["competences"] if c["id"] in ep["competences"]]
    rnd = random.Random(seed)  # noqa: S311 — tirage pédagogique, non cryptographique
    picked = rnd.sample(comps, k=min(n, len(comps)))
    details = "\n".join(
        f"{c['id']} — {c['titre']} ; critères : " + " | ".join(c["criteres"]) for c in picked
    )
    prompt = (
        f"Épreuve {epreuve} ({ep['type']}) — contexte : {ep['contexte']}\nProjet du candidat : {ep.get('microforge', '')}\n"
        f"Compétences évaluées :\n{details}\n\nRédige {n} questions de jury (une par compétence), précises, "
        "qui vérifient les critères, avec les éléments de réponse attendus."
    )
    return gateway.structured(prompt, schema=JuryQuestions, role="text")


def evaluate_answer(question: JuryQuestion, answer: str, gateway: Gateway) -> Evaluation:
    prompt = (
        f"Question du jury ({question.competence}) : {question.question}\nAttendus : {question.attendus}\n"
        f"Réponse du candidat : {answer}\n\nÉvalue avec bienveillance et exigence (note sur 20)."
    )
    return gateway.structured(prompt, schema=Evaluation, role="text")
