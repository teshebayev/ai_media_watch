"""AFM Knowledge Agent: RAG-агент по базе знаний AFM stage3.

База знаний — карточки `data/raw/AFM_stage3_json_pack(2)` (что делать в каких
ситуациях при подозрительных звонках/сообщениях). Хранилище — та же Qdrant, что и
у similarity-сервиса, но отдельная коллекция с ГИБРИДНЫМ поиском:

  - dense  : multilingual-e5 (тот же эмбеддер, что и в проекте; семантика ru/kz/en);
  - sparse : BM25-подобный разрежённый вектор (лексика/точные триггер-фразы).

Слияние результатов — серверный RRF (Reciprocal Rank Fusion) в Qdrant. IDF для
sparse считает сам Qdrant (Modifier.IDF), поэтому никаких внешних BM25-зависимостей
не нужно — токенизатор простой и офлайновый.

Ответ генерирует наш LLM в vLLM (OpenAI-совместимый API). Правила поведения берутся
из AFM_stage3_agent_config.json (safe_templates, forbidden_outputs, first_response_rules).
Если LLM выключен флагом ENABLE_LLM=false или недоступен — есть детерминированный
fallback из полей карточки (say_first / why / after_actions).
"""

from __future__ import annotations

import json
import re
import zlib
from functools import lru_cache
from pathlib import Path

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    Fusion,
    FusionQuery,
    Modifier,
    PointStruct,
    Prefetch,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from backend.app.config import get_settings

DENSE = "dense"
SPARSE = "text"

# ── Разрешение пути к базе знаний ──────────────────────────────────────────
# kb_dir может быть относительным (cwd=репо / WORKDIR=/app) — пробуем несколько баз.
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _kb_dir() -> Path:
    s = get_settings()
    raw = Path(s.kb_dir)
    candidates = [raw, _REPO_ROOT / raw, Path("/app") / raw]
    for c in candidates:
        if c.exists():
            return c
    # вернём первый — ошибка чтения будет явной и информативной
    return candidates[0]


def load_cards() -> list[dict]:
    path = _kb_dir() / get_settings().kb_cards_file
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@lru_cache
def load_agent_config() -> dict:
    path = _kb_dir() / get_settings().kb_config_file
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ── Эмбеддеры ──────────────────────────────────────────────────────────────
# Плотный энкодер переиспользуем из similarity-сервиса (одна модель в памяти).
def _encoder():
    from backend.app.services.similarity import _get_encoder

    return _get_encoder()


def embed_dense(text: str, *, is_query: bool) -> list[float]:
    # e5 требует префикс: "query: " для запроса, "passage: " для документа.
    prefix = "query: " if is_query else "passage: "
    return _encoder().encode(prefix + text, normalize_embeddings=True).tolist()


_TOKEN_RE = re.compile(r"[0-9a-zA-Zа-яёА-ЯЁ]{2,}")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def embed_sparse(text: str) -> SparseVector:
    """BM25-style разрежённый вектор: index = стабильный хэш токена, value = частота.

    IDF добавит сам Qdrant (Modifier.IDF), поэтому здесь — только term frequency.
    crc32 даёт стабильный (в отличие от hash()) 32-битный id; коллизии для словаря
    из ~20 карточек пренебрежимо редки.
    """
    freqs: dict[int, float] = {}
    for tok in _tokenize(text):
        idx = zlib.crc32(tok.encode("utf-8")) & 0x7FFFFFFF
        freqs[idx] = freqs.get(idx, 0.0) + 1.0
    if not freqs:  # пустой текст → один фиктивный токен, чтобы вектор был валиден
        freqs[0] = 1.0
    return SparseVector(indices=list(freqs.keys()), values=list(freqs.values()))


# ── Текст карточки для индексации ──────────────────────────────────────────
def card_text(card: dict) -> str:
    """Человекочитаемое представление карточки для эмбеддинга (dense + sparse)."""
    agent = card.get("agent") or {}
    parts = [
        card.get("title", ""),
        f"Категория: {card.get('category', '')}",
        f"Приоритет: {card.get('priority', '')} ({card.get('priority_meaning', '')})",
        f"Когда применять: {card.get('use_when', '')}",
        "Триггер-фразы: " + "; ".join(card.get("trigger_phrases") or []),
        "Риск-сигналы: " + ", ".join(card.get("risk_signals") or []),
        agent.get("say_first", ""),
        agent.get("why", ""),
        agent.get("after_actions", ""),
    ]
    return "\n".join(p for p in parts if p and not p.endswith(": "))


# ── Коллекция + индексация ─────────────────────────────────────────────────
async def ensure_kb_collection(client: AsyncQdrantClient) -> None:
    s = get_settings()
    existing = {c.name for c in (await client.get_collections()).collections}
    if s.kb_collection in existing:
        return
    await client.create_collection(
        collection_name=s.kb_collection,
        vectors_config={DENSE: VectorParams(size=s.embedding_dim, distance=Distance.COSINE)},
        sparse_vectors_config={
            SPARSE: SparseVectorParams(index=SparseIndexParams(), modifier=Modifier.IDF)
        },
    )


async def kb_count(client: AsyncQdrantClient) -> int:
    s = get_settings()
    try:
        return (await client.count(collection_name=s.kb_collection)).count
    except Exception:  # noqa: BLE001 — коллекции может ещё не быть
        return 0


async def index_cards(client: AsyncQdrantClient, *, recreate: bool = False) -> int:
    """Загрузить карточки в Qdrant. recreate=True пересоздаёт коллекцию с нуля."""
    s = get_settings()
    if recreate:
        try:
            await client.delete_collection(s.kb_collection)
        except Exception:  # noqa: BLE001
            pass
    await ensure_kb_collection(client)

    cards = load_cards()
    points = []
    for i, card in enumerate(cards):
        text = card_text(card)
        points.append(
            PointStruct(
                id=i,
                vector={DENSE: embed_dense(text, is_query=False), SPARSE: embed_sparse(text)},
                payload=card,
            )
        )
    await client.upsert(collection_name=s.kb_collection, points=points)
    return len(points)


# ── Гибридный поиск (dense + sparse → RRF) ─────────────────────────────────
async def hybrid_search(client: AsyncQdrantClient, query: str, limit: int = 4) -> list[dict]:
    s = get_settings()
    prefetch_limit = max(limit * 4, 16)
    resp = await client.query_points(
        collection_name=s.kb_collection,
        prefetch=[
            Prefetch(query=embed_dense(query, is_query=True), using=DENSE, limit=prefetch_limit),
            Prefetch(query=embed_sparse(query), using=SPARSE, limit=prefetch_limit),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    return [{"score": p.score, "card": p.payload} for p in resp.points]


# ── Агент: генерация ответа через vLLM ─────────────────────────────────────
def _system_prompt() -> str:
    cfg = load_agent_config()
    forbidden = "\n".join(f"- {x}" for x in cfg.get("forbidden_outputs", []))
    rules = "\n".join(
        f"- ЕСЛИ {r.get('condition', '')} → {r.get('response', '')}"
        for r in cfg.get("first_response_rules", [])
    )
    # Только тексты шаблонов (без ключей) — иначе модель копирует «p0_call:» в ответ.
    templates = "\n".join(f"- {v}" for v in (cfg.get("safe_templates") or {}).values())
    return (
        "Ты — AFM Call Guard, помощник по защите от телефонного мошенничества и "
        "социальной инженерии в Казахстане. Отвечай на русском, кратко и по делу.\n"
        f"Главная цель: {cfg.get('main_goal', '')}\n\n"
        "Опирайся ТОЛЬКО на карточки базы знаний из блока CONTEXT ниже. Если в "
        "карточках нет ответа — честно скажи об этом и дай общий безопасный совет "
        "(проверить через официальный банк/eGov/1414, не называть коды, не переводить деньги).\n\n"
        "ПРАВИЛА ПЕРВОГО ОТВЕТА:\n" + rules + "\n\n"
        "ЗАПРЕЩЕНО:\n" + forbidden + "\n\n"
        "БЕЗОПАСНЫЕ ШАБЛОНЫ (бери как основу формулировок, но пиши естественно "
        "и не выводи служебные подписи/названия шаблонов):\n" + templates + "\n\n"
        "Если ситуация критическая (P0 / emergency) — начни ответ с короткой команды "
        "безопасности, затем кратко объясни почему и что делать дальше. Пиши обычным "
        "текстом без markdown-разметки и без префиксов-ярлыков."
    )


def _context_block(hits: list[dict]) -> str:
    blocks = []
    for h in hits:
        c = h["card"]
        agent = c.get("agent") or {}
        srcs = "; ".join(
            f"{d.get('name', '')} ({d.get('url', '')})" for d in (c.get("source_details") or [])
        )
        blocks.append(
            f"[{c.get('id')}] приоритет={c.get('priority')} опасность={c.get('danger')} "
            f"emergency={(c.get('routing') or {}).get('is_emergency', False)}\n"
            f"Заголовок: {c.get('title')}\n"
            f"Когда применять: {c.get('use_when')}\n"
            f"Сказать сразу: {agent.get('say_first', '')}\n"
            f"Почему: {agent.get('why', '')}\n"
            f"Дальнейшие действия: {agent.get('after_actions', '')}\n"
            f"Источники: {srcs}"
        )
    return "\n\n".join(blocks)


def _fallback_answer(hits: list[dict]) -> str:
    """Ответ без LLM — из полей лучшей карточки (агент остаётся полезным)."""
    if not hits:
        return (
            "Не нашёл подходящей карточки. Общее правило: никому не называйте коды из "
            "SMS/push, не переводите деньги на «безопасный счёт», не устанавливайте "
            "приложения по просьбе звонящего. Проверьте ситуацию через официальный банк "
            "или eGov/1414."
        )
    c = hits[0]["card"]
    agent = c.get("agent") or {}
    lines = [agent.get("say_first", "")]
    if agent.get("why"):
        lines.append(f"Почему: {agent['why']}")
    if agent.get("after_actions"):
        lines.append(f"Что делать: {agent['after_actions']}")
    return "\n".join(x for x in lines if x)


def _sources(hits: list[dict]) -> list[dict]:
    seen, out = set(), []
    for h in hits:
        for d in h["card"].get("source_details") or []:
            url = d.get("url")
            if url and url not in seen:
                seen.add(url)
                out.append({"name": d.get("name"), "url": url})
    return out


async def ask(client: AsyncQdrantClient, llm: AsyncOpenAI, question: str) -> dict:
    """Главная точка входа агента: вопрос → гибридный поиск → ответ LLM (+источники)."""
    s = get_settings()
    hits = await hybrid_search(client, question, limit=s.kb_top_k)
    matched = [
        {
            "id": h["card"].get("id"),
            "title": h["card"].get("title"),
            "priority": h["card"].get("priority"),
            "category": h["card"].get("category"),
            "score": h["score"],
        }
        for h in hits
    ]
    # Emergency, если критическая карточка попала в топ-2 совпадений (а не только в топ-1):
    # частый случай — лексически ближе оказывается смежная P1-карточка, а P0 идёт следом.
    is_emergency = any((h["card"].get("routing") or {}).get("is_emergency") for h in hits[:2])

    answer: str
    used_llm = False
    if s.enable_llm:
        try:
            resp = await llm.chat.completions.create(
                model=s.llm_model,
                messages=[
                    {"role": "system", "content": _system_prompt()},
                    {
                        "role": "user",
                        "content": (
                            f"CONTEXT (карточки базы знаний):\n{_context_block(hits)}\n\n"
                            f"ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}"
                        ),
                    },
                ],
                temperature=0.2,
            )
            answer = (resp.choices[0].message.content or "").strip() or _fallback_answer(hits)
            used_llm = True
        except Exception:  # noqa: BLE001 — vLLM может быть недоступен → детерминированный fallback
            answer = _fallback_answer(hits)
    else:
        answer = _fallback_answer(hits)

    return {
        "answer": answer,
        "is_emergency": is_emergency,
        "matched_cards": matched,
        "sources": _sources(hits),
        "used_llm": used_llm,
    }
