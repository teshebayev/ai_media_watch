"""Персистентность находок Digital Shadow → таблица shadow_findings (Postgres).

Своя таблица (а не общая analysis_sessions): у Shadow своя таксономия — category, priority,
threat_score, source_type. Best-effort: сбой БД не валит анализ.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, func, select

from apps.digital_shadow.schemas import ShadowFinding
from backend.app.config import get_settings
from backend.app.db.models import ShadowEntityReputation as ReputationRow
from backend.app.db.models import ShadowFinding as ShadowFindingRow
from backend.app.db.models import ShadowReview, ShadowWatchlist

logger = logging.getLogger(__name__)

_DECISION_STATUS = {"confirm": "confirmed", "dismiss": "dismissed", "in_review": "in_review"}

# Поля сущностей-индикаторов (публичные, НЕ ПДн) → kind для репутации/watchlist.
_INDICATOR_FIELDS = {
    "domains": "domain", "crypto_wallets": "wallet",
    "telegram_usernames": "telegram", "promo_codes": "promo",
}


def _safe_preview(text: str | None, signals: list[str]) -> str | None:
    """Превью для триажа/active learning без сырых ПДн (§0): маскируем телефоны/ИИН/карты.
    Нет текста → перечень сигналов (как раньше)."""
    from apps.digital_shadow.leak_detector import mask_pii

    raw = text or " ".join(signals)
    return mask_pii(raw)[:500] or None if raw else None


def _indicators(entities: dict) -> list[tuple[str, str]]:
    """(value, kind) публичных индикаторов из entities-словаря находки."""
    out: list[tuple[str, str]] = []
    for field, kind in _INDICATOR_FIELDS.items():
        for v in entities.get(field, []) or []:
            if isinstance(v, str) and v.strip():
                out.append((v.strip(), kind))
    return out


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
                       language: str | None = None, text: str | None = None) -> str | None:
    """Сохранить находку. text — исходный текст элемента (для триажа и active learning);
    при отсутствии — фолбэк на перечень сигналов. Возвращает id строки или None."""
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
                # §0: НЕ персистим сырые ПДн — маскируем телефоны/ИИН/карты в превью.
                text_preview=_safe_preview(text, finding.signals),
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
            reputation = 0
            if row is not None:
                row.status = status
                # flywheel: решение → репутация сущностей (+ авто-watchlist при confirm)
                reputation = await _apply_reputation(db, row.entities or {}, decision)
            await db.commit()
            return {"finding_id": finding_id, "status": status,
                    "decision": decision, "entities_updated": reputation}
    except Exception as e:  # noqa: BLE001
        logger.warning("add_review(%s) не удался: %s", finding_id, e)
        return None


async def _apply_reputation(db, entities: dict, decision: str) -> int:
    """Инкремент репутации индикаторов находки по решению аналитика. confirm →
    abuse/confirmed +1 и авто-watchlist; dismiss → dismissed +1. Возвращает кол-во сущностей."""
    from sqlalchemy.dialects.postgresql import insert

    inds = _indicators(entities)
    if not inds or decision == "in_review":
        return 0
    confirm = decision == "confirm"
    ab, cf, dm = (1, 1, 0) if confirm else (0, 0, 1)
    for value, kind in inds:
        stmt = insert(ReputationRow).values(
            value=value, kind=kind, abuse_count=ab,
            confirmed_count=cf, dismissed_count=dm).on_conflict_do_update(
            index_elements=["value"], set_={
                "abuse_count": ReputationRow.abuse_count + ab,
                "confirmed_count": ReputationRow.confirmed_count + cf,
                "dismissed_count": ReputationRow.dismissed_count + dm,
                "last_seen": func.now()})
        await db.execute(stmt)
        if confirm:  # подтверждённый индикатор — на постоянное наблюдение
            wl = insert(ShadowWatchlist).values(
                value=value, kind=kind, note="auto: confirmed review"
            ).on_conflict_do_nothing(index_elements=["value"])
            await db.execute(wl)
    return len(inds)


async def bad_entity_values() -> set[str]:
    """Множество индикаторов с подтверждённым abuse (abuse_count>0) — в analyze_item
    для сигнала known_bad_entity. Best-effort: БД выключена/недоступна → пустое."""
    if not get_settings().enable_db:
        return set()
    from backend.app.clients.db import get_sessionmaker

    try:
        async with get_sessionmaker()() as db:
            rows = (await db.execute(
                select(ReputationRow.value).where(ReputationRow.abuse_count > 0))).scalars().all()
        return set(rows)
    except Exception as e:  # noqa: BLE001
        logger.warning("bad_entity_values недоступно: %s", e)
        return set()


async def fetch_review_rows() -> list[dict]:
    """Размеченные ревью для active learning: {text, category, decision}.
    Текст берём из находки (text_preview), категорию — её category. Best-effort."""
    if not get_settings().enable_db:
        return []
    from backend.app.clients.db import get_sessionmaker

    try:
        q = (select(ShadowReview.decision, ShadowFindingRow.category,
                    ShadowFindingRow.text_preview)
             .join(ShadowFindingRow, ShadowReview.finding_id == ShadowFindingRow.id))
        async with get_sessionmaker()() as db:
            rows = (await db.execute(q)).all()
        return [{"decision": d, "category": c, "text": t}
                for (d, c, t) in rows if t and c]
    except Exception as e:  # noqa: BLE001
        logger.warning("fetch_review_rows недоступно: %s", e)
        return []


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
