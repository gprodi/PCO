"""Procédure de tri des données personnelles (RGPD, C4) — exécution hebdomadaire planifiée.

Règles (cf. registre des traitements, docs/E1/rgpd.md) :
  * métadonnées de photos : supprimées après ``delete_after`` (J+30) ;
  * retours de détection : anonymisés (user_id conservé = 0 impossible -> suppression) après 13 mois ;
  * jetons de rafraîchissement expirés ou révoqués : supprimés ;
  * comptes inactifs depuis 24 mois : supprimés (préavis par e-mail géré hors base) ;
  * chaque exécution est tracée dans ``execution_collecte`` (flow = purge_rgpd).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from loguru import logger
from sqlmodel import Session, col, delete, or_, select

from microforge.api_data.db import (
    Feedback,
    IngestionRun,
    InventoryItem,
    Photo,
    Project,
    RefreshToken,
    User,
)


def purge(session: Session, today: date | None = None) -> dict[str, int]:
    today = today or date.today()
    now = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    run = IngestionRun(flow="purge_rgpd", source="base")
    session.add(run)
    counts: dict[str, int] = {}

    res = session.exec(delete(Photo).where(Photo.delete_after < today))  # type: ignore[arg-type]
    counts["photos"] = res.rowcount or 0
    res = session.exec(delete(Feedback).where(Feedback.created_at < now - timedelta(days=396)))  # type: ignore[arg-type]
    counts["retours"] = res.rowcount or 0
    res = session.exec(
        delete(RefreshToken).where(or_(RefreshToken.revoked, RefreshToken.expires_at < now))
    )  # type: ignore[arg-type]
    counts["jetons"] = res.rowcount or 0

    limit = now - timedelta(days=730)
    inactive = session.exec(
        select(User).where(
            User.role != "admin",
            or_(
                col(User.last_login_at) < limit,
                (col(User.last_login_at).is_(None)) & (User.created_at < limit),
            ),
        )
    ).all()
    for user in inactive:
        for model in (Feedback, Photo, InventoryItem, Project, RefreshToken):
            session.exec(delete(model).where(model.user_id == user.id))  # type: ignore[arg-type]
        session.delete(user)
    counts["comptes"] = len(inactive)

    run.status = "success"
    run.rows_out = sum(counts.values())
    run.message = ", ".join(f"{k}={v}" for k, v in counts.items())
    run.finished_at = datetime.now(UTC)
    session.add(run)
    session.commit()
    logger.info("Purge RGPD : {}", run.message)
    return counts
