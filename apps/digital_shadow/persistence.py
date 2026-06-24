"""Персистентность находок Digital Shadow → таблица shadow_findings (Postgres).

Своя таблица (а не общая analysis_sessions): у Shadow своя таксономия — category, priority,
threat_score, source_type. Best-effort: сбой БД не валит анализ.
"""

from __future__ import annotations

from sqlalchemy import delete, select

from apps.digital_shadow.schemas import ShadowFinding
from backend.app.config import get_settings
from backend.app.db.models import ShadowFinding as ShadowFindingRow
from backend.app.db.models import ShadowReview, ShadowWatchlist

_DECISION_STATUS = {"confirm": "confirmed", "dismiss": "dismissed", "in_review": "in_review"}


def _row_dict(r: ShadowFindingRow) -> dict:
    return {
        "id": str(r.id),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "item_id": r.item_id,
        "source_type": r.source_type,
        "source_url": r.source_url,
        "platform": r.platform,
        "category": r.category,
        "risk_score": r.risk_score,
        "risk_level": r.risk_level,
        "priority": r.priority,
        "threat_score": r.threat_score,
        "signals": r.signals or [],
        "text_preview": r.text_preview,
        "status": r.status,
    }


async def save_finding(finding: ShadowFinding, *, platform: str | None = None,
                       language: str | None = None) -> str | None:
    """Сохранить находку. Возвращает id строки или None (БД выключена/недоступна)."""
    if not get_settings().enable_db:
        return None
    from backend.app.clients.db import get_sessionmaker

    try:
        async with get_sessionmaker()() as db:
            row = ShadowFindingRow(
                item_id=finding.id,
                source_type=finding.source_type,
                source_url=finding.source_url,
                platform=platform,
                language=language,
                category=finding.category,
                risk_score=finding.risk_score,
                risk_level=finding.risk_level,
                priority=finding.priority,
                threat_score=finding.threat_score,
                signals=finding.signals,
                entities=finding.entities.model_dump(),
                wallet_risks=finding.wallet_risks,
                text_preview=" ".join(finding.signals)[:500] or None,
            )
            db.add(row)
            await db.commit()
            return str(row.id)
    except Exception:  # noqa: BLE001 — БД может быть недоступна
        return None


async def list_findings(limit: int = 20, *, category: str | None = None,
                        priority: str | None = None) -> list[dict]:
    """Последние shadow-находки из Postgres (опц. фильтры по category/priority)."""
    if not get_settings().enable_db:
        return []
    from backend.app.clients.db import get_sessionmaker

    try:
        q = select(ShadowFindingRow).order_by(ShadowFindingRow.created_at.desc()).limit(limit)
        if category:
            q = q.where(ShadowFindingRow.category == category)
        if priority:
            q = q.where(ShadowFindingRow.priority == priority)
        async with get_sessionmaker()() as db:
            rows = (await db.execute(q)).scalars().all()
        return [_row_dict(r) for r in rows]
    except Exception:  # noqa: BLE001
        return []


# ── Триаж / ревью аналитика ──────────────────────────────────────────────────
async def list_queue(limit: int = 50, *, status: str | None = None) -> list[dict]:
    """Очередь триажа: находки по убыванию threat_score (опц. фильтр по статусу)."""
    if not get_settings().enable_db:
        return []
    from backend.app.clients.db import get_sessionmaker

    try:
        q = (select(ShadowFindingRow)
             .order_by(ShadowFindingRow.threat_score.desc().nullslast(),
                       ShadowFindingRow.created_at.desc())
             .limit(limit))
        if status:
            q = q.where(ShadowFindingRow.status == status)
        async with get_sessionmaker()() as db:
            rows = (await db.execute(q)).scalars().all()
        return [_row_dict(r) for r in rows]
    except Exception:  # noqa: BLE001
        return []


async def add_review(finding_id: str, decision: str, *, reviewer: str | None = None,
                     notes: str | None = None) -> dict | None:
    """Решение аналитика: ревью + смена статуса. decision: confirm/dismiss/in_review."""
    if not get_settings().enable_db:
        return None
    from backend.app.clients.db import get_sessionmaker

    status = _DECISION_STATUS.get(decision)
    if status is None:
        return None
    try:
        async with get_sessionmaker()() as db:
            db.add(ShadowReview(finding_id=finding_id, decision=decision,
                                reviewer=reviewer, notes=notes))
            row = await db.get(ShadowFindingRow, finding_id)
            if row is not None:
                row.status = status
            await db.commit()
            return {"finding_id": finding_id, "status": status, "decision": decision}
    except Exception:  # noqa: BLE001
        return None


# ── Watchlist ────────────────────────────────────────────────────────────────
async def watchlist_add(value: str, *, kind: str | None = None, note: str | None = None) -> bool:
    if not get_settings().enable_db or not value.strip():
        return False
    from sqlalchemy.dialects.postgresql import insert

    from backend.app.clients.db import get_sessionmaker
    try:
        async with get_sessionmaker()() as db:
            stmt = insert(ShadowWatchlist).values(
                value=value.strip(), kind=kind, note=note).on_conflict_do_nothing(
                index_elements=["value"])
            await db.execute(stmt)
            await db.commit()
        return True
    except Exception:  # noqa: BLE001
        return False


async def watchlist_remove(value: str) -> bool:
    if not get_settings().enable_db:
        return False
    from backend.app.clients.db import get_sessionmaker
    try:
        async with get_sessionmaker()() as db:
            await db.execute(delete(ShadowWatchlist).where(ShadowWatchlist.value == value))
            await db.commit()
        return True
    except Exception:  # noqa: BLE001
        return False


async def watchlist_list() -> list[dict]:
    if not get_settings().enable_db:
        return []
    from backend.app.clients.db import get_sessionmaker
    try:
        async with get_sessionmaker()() as db:
            rows = (await db.execute(
                select(ShadowWatchlist).order_by(ShadowWatchlist.added_at.desc()))).scalars().all()
        return [{"value": r.value, "kind": r.kind, "note": r.note} for r in rows]
    except Exception:  # noqa: BLE001
        return []


async def watchlist_values() -> set[str]:
    """Множество отслеживаемых значений — передаётся в analyze_item(watchlist=...)."""
    return {w["value"] for w in await watchlist_list()}
