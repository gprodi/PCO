"""API locale du site de révision (port 8765) : ajout de cours, chat RAG, oral blanc.

uv run revise serve            # puis le site en mode local : npm run dev (dans revision/site)
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from llm_gateway import Gateway
from loguru import logger
from pydantic import BaseModel, Field

from revision.config import PATHS
from revision.ingest.converters import SUPPORTED, convert_bytes, convert_url
from revision.pipeline import add_course, all_courses
from revision.rag import JuryQuestion, chat, evaluate_answer, oral_questions
from revision.site_export import export
from revision.store import VectorIndex

JOBS: dict[str, dict[str, Any]] = {}


@lru_cache(maxsize=1)
def gateway() -> Gateway:
    return Gateway.from_env()


def content_dir() -> Path:
    return PATHS.content


class ChatIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    courses: list[str] | None = None


class OralAnswerIn(BaseModel):
    question: JuryQuestion
    answer: str = Field(min_length=3, max_length=6000)


class UrlIn(BaseModel):
    url: str = Field(pattern=r"^https?://")
    title: str | None = None
    theme: str = "bases"


def _process(
    job_id: str, markdown: str, title: str | None, theme: str, filename: str | None
) -> None:
    JOBS[job_id]["status"] = "running"
    try:
        content = add_course(markdown, title, theme, gateway(), content_dir(), filename=filename)
        export(content_dir=content_dir())
        JOBS[job_id].update(status="done", slug=content.slug, titre=content.titre)
    except Exception as exc:
        logger.exception("Échec du traitement {}", job_id)
        JOBS[job_id].update(status="failed", error=str(exc))


def create_app() -> FastAPI:
    app = FastAPI(title="Révisions DevIA — API locale", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4321", "http://127.0.0.1:4321"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "llm_chain": [p.name for p in gateway().providers]}

    @app.get("/courses")
    def courses() -> dict:
        return all_courses(content_dir())

    @app.post("/sources", status_code=202)
    async def add_source(
        background: BackgroundTasks,
        file: UploadFile = File(...),
        title: str | None = Form(default=None),
        theme: str = Form(default="bases"),
    ) -> dict:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in SUPPORTED:
            raise HTTPException(415, f"Format non pris en charge ({', '.join(SUPPORTED)})")
        data = await file.read(50 * 1024 * 1024 + 1)
        if len(data) > 50 * 1024 * 1024:
            raise HTTPException(413, "Fichier > 50 Mo")
        markdown = convert_bytes(data, file.filename or "cours" + suffix)
        job_id = uuid.uuid4().hex[:10]
        JOBS[job_id] = {"status": "queued", "filename": file.filename}
        background.add_task(
            _process,
            job_id,
            markdown,
            title or Path(file.filename or "cours").stem,
            theme,
            file.filename,
        )
        return {"job_id": job_id}

    @app.post("/sources/url", status_code=202)
    def add_url(body: UrlIn, background: BackgroundTasks) -> dict:
        markdown = convert_url(body.url)
        job_id = uuid.uuid4().hex[:10]
        JOBS[job_id] = {"status": "queued", "url": body.url}
        background.add_task(_process, job_id, markdown, body.title or body.url, body.theme, None)
        return {"job_id": job_id}

    @app.get("/jobs/{job_id}")
    def job(job_id: str) -> dict:
        if job_id not in JOBS:
            raise HTTPException(404, "Tâche inconnue")
        return JOBS[job_id]

    @app.post("/chat")
    def chat_endpoint(body: ChatIn) -> dict:
        index = VectorIndex.load(content_dir() / "_index.json")
        if not index.items:
            raise HTTPException(409, "Index vide : lancer « revise index » d'abord")
        return chat(body.question, index, gateway(), body.courses).model_dump()

    @app.post("/oral-blanc/evaluer")
    def oral_eval(body: OralAnswerIn) -> dict:
        return evaluate_answer(body.question, body.answer, gateway()).model_dump()

    @app.post("/oral-blanc/{epreuve}")
    def oral(epreuve: str, n: int = 5) -> dict:
        if epreuve not in {"E1", "E2", "E3", "E4", "E5"}:
            raise HTTPException(404, "Épreuve inconnue")
        return oral_questions(epreuve, gateway(), n=min(n, 6)).model_dump()

    return app


app = create_app()
