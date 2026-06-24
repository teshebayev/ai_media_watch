"""Killer-демо синергии: один кошелёк всплывает И в Media (:Video), И в Shadow (:ShadowItem)
→ общий Neo4j связывает их в ОДИН узел → /shadow/cross и /shadow/clusters показывают мост.

Печатает: кросс-продуктовые сущности, кластер-мост и метрику
«X% теневых сущностей встречаются и в медиа-контенте».

Запуск (нужен Neo4j):
    ENABLE_GRAPH=true NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=finguard_pass \
    PYTHONPATH=. python scripts/demo_cross_product.py
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from apps.digital_shadow import actors as actors_svc  # noqa: E402
from apps.digital_shadow.pipeline import analyze_item  # noqa: E402
from apps.digital_shadow.schemas import ShadowItem  # noqa: E402
from backend.app.clients.neo4j import make_neo4j_driver  # noqa: E402
from backend.app.schemas.models import Entities  # noqa: E402
from core import graph_service  # noqa: E402

WALLET = "0xcafebabedeadbeefcafebabedeadbeefcafebabe"  # валидный 40-hex ETH

# % теневых сущностей, которые также встречаются в медиа-контенте (мост Media↔Shadow).
BRIDGE_PCT_QUERY = """
MATCH (e)<-[]-(s)
WHERE any(l IN labels(e) WHERE l IN ['Domain','Wallet','TelegramUsername','PromoCode'])
WITH e, collect(DISTINCT labels(s)[0]) AS kinds
WHERE 'ShadowItem' IN kinds
WITH count(e) AS shadow_entities,
     sum(CASE WHEN any(k IN ['Video','Post','Call'] WHERE k IN kinds) THEN 1 ELSE 0 END) AS bridged
RETURN shadow_entities, bridged
"""


async def main() -> None:
    driver = make_neo4j_driver()
    try:
        # 1) Media: блогер-инвестскам (TikTok) упоминает кошелёк
        await graph_service.upsert_entities(
            driver, "demo_video_1",
            Entities(crypto_wallets=[WALLET], domains=["promo-invest.kz"]),
            source_label="Video")
        # 2) Shadow: тот же кошелёк всплывает в даркнет-листинге дропов
        await analyze_item(ShadowItem(
            id="demo_shadow_1", source_type="darknet",
            text=f"Дропы под обнал, карты в аренду, оплата на {WALLET}, контакт session"),
            driver=driver)

        print(f"Засеян кошелёк-мост: {WALLET}\n")

        cross = await actors_svc.cross_product(driver, limit=20)
        print(f"/shadow/cross — кросс-продуктовые сущности: {len(cross)}")
        for a in cross[:10]:
            print(f"  {a['entity']:46} {a['type']:16} kinds={a['kinds']}")

        clusters = await actors_svc.actor_clusters(driver, min_uses=2)
        bridges = [c for c in clusters if c["cross_product"]]
        print(f"\n/shadow/clusters — кластеров: {len(clusters)}, из них мостов: {len(bridges)}")
        for c in bridges[:5]:
            print(f"  мост: {[e['value'] for e in c['entities']]} kinds={c['kinds']}")

        async with driver.session() as s:
            rec = await (await s.run(BRIDGE_PCT_QUERY)).single()
        if rec and rec["shadow_entities"]:
            se, br = rec["shadow_entities"], rec["bridged"]
            print(f"\nМетрика синергии: {br}/{se} = {br / se:.0%} теневых сущностей "
                  "встречаются и в медиа-контенте.")

        # teardown: убираем демо-узлы, чтобы не засорять общий граф и не искажать метрику
        async with driver.session() as s:
            await s.run("MATCH (n) WHERE n.id IN ['demo_video_1','demo_shadow_1'] "
                        "DETACH DELETE n")
        print("\n(демо-узлы demo_* удалены из графа)")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
