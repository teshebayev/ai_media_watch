"""CLI-раннер сбора Digital Shadow: коллектор → пайплайн → (граф + Postgres) → топ угроз.

Источники:
    --file PATH        JSONL экспортированных листингов (офлайн, надёжно)
    --url URL [URL...] публичные страницы (httpx); .onion → через --proxy socks5h://127.0.0.1:9050
    --rss URL [URL...] RSS/Atom-ленты
    --mock             синтетические даркнет-листинги (демо)

Граф/БД подключаются best-effort из окружения (NEO4J_URI, DATABASE_URL, ENABLE_GRAPH/ENABLE_DB).

Примеры:
    python -m apps.digital_shadow.collect --mock
    python -m apps.digital_shadow.collect --file data/shadow/inbox.jsonl
    make shadow-collect ARGS="--rss https://example.com/feed.xml"
"""

from __future__ import annotations

import argparse
import asyncio

from apps.digital_shadow import persistence
from apps.digital_shadow.collectors import (
    DarknetMockCollector,
    FileCollector,
    HttpPageCollector,
    PasteSiteCollector,
    RssCollector,
)
from apps.digital_shadow.pipeline import analyze_item
from apps.digital_shadow.seen_store import SeenStore
from backend.app.config import get_settings


def _build_collector(args):
    if args.file:
        return FileCollector(args.file)
    if args.url:
        return HttpPageCollector(args.url, proxy=args.proxy)
    if args.rss:
        return RssCollector(args.rss)
    if args.paste:
        return PasteSiteCollector(args.paste)
    return DarknetMockCollector()


async def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--file")
    g.add_argument("--url", nargs="+")
    g.add_argument("--rss", nargs="+")
    g.add_argument("--paste", nargs="+", help="URL паст/лент — фильтр по утечкам БД РК")
    g.add_argument("--mock", action="store_true")
    ap.add_argument("--proxy", help="SOCKS-прокси для Tor (.onion), напр. socks5h://127.0.0.1:9050")
    ap.add_argument("--query", help="фильтр по подстроке")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--no-dedup", action="store_true",
                    help="не пропускать уже виденные элементы (выключить инкрементальный сбор)")
    ap.add_argument("--seen-file", help="путь к файлу seen-store (по умолч. data/shadow/seen.txt)")
    args = ap.parse_args()

    s = get_settings()
    driver = None
    if s.enable_graph:
        try:
            from backend.app.clients.neo4j import make_neo4j_driver
            driver = make_neo4j_driver()
        except Exception:  # noqa: BLE001
            driver = None

    seen = None if args.no_dedup else SeenStore(args.seen_file)
    collector = _build_collector(args)
    findings = []
    n = skipped = 0
    async for raw in collector.collect(args.query):
        if n >= args.limit:
            break
        # инкрементальный сбор: пропускаем уже виденные (по id/контенту)
        if seen is not None and not seen.is_new(
                source_type=raw.source_type, item_id=raw.id, text=raw.text):
            skipped += 1
            continue
        n += 1
        f = await analyze_item(raw, driver=driver)
        await persistence.save_finding(
            f, platform=raw.platform, language=raw.language, text=raw.text)
        if seen is not None:
            seen.mark(source_type=raw.source_type, item_id=raw.id, text=raw.text)
        findings.append(f)

    if driver is not None:
        await driver.close()
    written = seen.flush() if seen is not None else 0

    findings.sort(key=lambda f: f.threat_score, reverse=True)
    print(f"\nСобрано и проанализировано: {len(findings)} "
          f"(новых={n}, пропущено дублей={skipped}, seen+={written}; "
          f"граф={'on' if driver else 'off'}, БД={'on' if s.enable_db else 'off'})\n")
    for f in findings[:30]:
        print(f"  {f.priority:6} {f.risk_level:9} thr={f.threat_score:5} {f.category:18} {f.id}")


if __name__ == "__main__":
    asyncio.run(main())
