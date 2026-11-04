"""API de données : les avis et leur sentiment."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlmodel import Field as DbField
from sqlmodel import Session, SQLModel, create_engine, select

from common.logs import setup_logging
from common.security import require_api_key
from common.settings import get_settings


class Avis(SQLModel, table=True):
    id: int | None = DbField(default=None, primary_key=True)
    texte: str = DbField(max_length=2000)
    sentiment: str = DbField(index=True)
    score: float
    cree_le: datetime = DbField(default_factory=lambda: datetime.now(UTC))


class AvisIn(BaseModel):
    texte: str = Field(min_length=1, max_length=2000)
    sentiment: str = Field(pattern="^(positif|negatif|neutre)$")
    score: float = Field(ge=0, le=1)


engine = None


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global engine
    setup_logging("api_data")
    url = get_settings().database_url
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="API données", lifespan=lifespan)
SessionDep = Annotated[Session, Depends(get_session)]


@app.post("/avis", status_code=201, dependencies=[Depends(require_api_key)])
def create(body: AvisIn, session: SessionDep) -> Avis:
    avis = Avis(**body.model_dump())
    session.add(avis)
    session.commit()
    session.refresh(avis)
    logger.info("avis enregistré", id=avis.id, sentiment=avis.sentiment)
    return avis


@app.get("/avis")
def list_avis(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Avis]:
    return list(session.exec(select(Avis).order_by(Avis.id.desc()).offset(offset).limit(limit)))


@app.get("/avis/{avis_id}")
def get_avis(avis_id: int, session: SessionDep) -> Avis:
    avis = session.get(Avis, avis_id)
    if avis is None:
        raise HTTPException(404, "Avis introuvable")
    return avis


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
