"""Administration (rôle admin requis — OWASP API5 BFLA)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from microforge.api_data.catalog_sync import sync_catalog
from microforge.api_data.db import Feedback, IngestionRun, User, get_session
from microforge.api_data.deps import admin_user

router = APIRouter(prefix="/v1/admin", tags=["administration"])


@router.get("/ingestion-runs")
def ingestion_runs(
    limit: int = 50, _admin: User = Depends(admin_user), session: Session = Depends(get_session)
) -> list[IngestionRun]:
    return list(
        session.exec(
            select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(min(limit, 200))
        )
    )  # type: ignore[attr-defined]


@router.post("/catalog/sync")
def catalog_sync(
    _admin: User = Depends(admin_user), session: Session = Depends(get_session)
) -> dict[str, int]:
    return {"components": sync_catalog(session)}


@router.get("/feedback-stats")
def feedback_stats(
    _admin: User = Depends(admin_user), session: Session = Depends(get_session)
) -> dict:
    """Taux de corrections (métrique C11) par source de détection."""
    rows = session.exec(
        select(Feedback.source, Feedback.kind, func.count()).group_by(
            Feedback.source, Feedback.kind
        )
    )
    stats: dict[str, dict[str, int]] = {}
    for source, kind, n in rows:
        stats.setdefault(source, {})[kind] = n
    rates = {}
    for source, kinds in stats.items():
        total = sum(kinds.values())
        wrong = total - kinds.get("correct", 0)
        rates[source] = round(wrong / total, 3) if total else 0.0
    return {"counts": stats, "correction_rate": rates}
