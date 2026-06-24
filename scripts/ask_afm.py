#!/usr/bin/env python3
"""AFM Knowledge Agent — интерактивный чат в терминале.

Вопрос → гибридный поиск по базе знаний (Qdrant) → ответ нашего LLM (vLLM).

Запуск (локально, Qdrant+vLLM на хосте):
    QDRANT_URL=http://localhost:6333 LLM_BASE_URL=http://localhost:8100/v1 \
        .venv/bin/python scripts/ask_afm.py

Одиночный вопрос без REPL:
    ... scripts/ask_afm.py "у меня просят код из смс, что делать?"
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.app.clients.llm import make_llm_client  # noqa: E402
from backend.app.clients.qdrant import make_qdrant_client  # noqa: E402
from backend.app.config import get_settings  # noqa: E402
from backend.app.services import knowledge as kb  # noqa: E402


def _render(res: dict) -> None:
    if res.get("is_emergency"):
        print("\n🚨 ВНИМАНИЕ: похоже на критическую ситуацию.")
    print("\n" + res["answer"])
    if res.get("matched_cards"):
        cards = ", ".join(f"{c['id']}({c['priority']})" for c in res["matched_cards"])
        print(f"\n  ↳ карточки: {cards}  [llm={res.get('used_llm')}]")
    if res.get("sources"):
        print("  ↳ источники:")
        for src in res["sources"]:
            print(f"     • {src['name']} — {src['url']}")


async def main() -> None:
    s = get_settings()
    client = make_qdrant_client()
    llm = make_llm_client()

    if await kb.kb_count(client) == 0:
        print("База знаний пуста — индексирую…")
        await kb.index_cards(client)

    print(f"AFM Knowledge Agent · Qdrant={s.qdrant_url} · LLM={s.llm_model} (enabled={s.enable_llm})")

    question = " ".join(sys.argv[1:]).strip()
    if question:  # одиночный вопрос
        _render(await kb.ask(client, llm, question))
    else:  # REPL
        print("Задавайте вопросы (пустая строка / Ctrl-D — выход).")
        while True:
            try:
                q = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q:
                break
            _render(await kb.ask(client, llm, q))

    await client.close()
    await llm.close()


if __name__ == "__main__":
    asyncio.run(main())
