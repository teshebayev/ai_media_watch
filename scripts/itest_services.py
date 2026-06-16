"""Интеграционная проверка слоёв БЕЗ сетевого сервера: те же функции, что дёргают
роутеры, против реальных Qdrant/Neo4j на localhost. Запуск:

    ENABLE_SIMILARITY=true ENABLE_GRAPH=true QDRANT_URL=http://localhost:6333 \
    NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=finguard_pass \
    CUDA_VISIBLE_DEVICES="" .venv/bin/python scripts/itest_services.py
"""

import asyncio

from backend.app.clients.neo4j import make_neo4j_driver
from backend.app.clients.qdrant import make_qdrant_client
from backend.app.services import graph as graph_svc
from backend.app.services import pipeline
from backend.app.services import similarity as sim_svc


async def main():
    qdrant = make_qdrant_client()
    neo4j = make_neo4j_driver()

    print("### analyze_text (regex + signals + Qdrant similarity + Neo4j reuse + risk)")
    text = ("Регистрируйся на casino-x.com промокод PROMO777, бонус на депозит! "
            "Я поднял 500 000 ₸. Пиши @bonus_manager")
    rep = await pipeline.analyze_text("demo1", text, qdrant=qdrant, neo4j=neo4j)
    print("  risk:", rep.risk_level.value, rep.risk_score)
    print("  signals:", [s.signal for s in rep.triggered_signals])
    print("  domains:", rep.entities.domains)

    print("\n### search_similar (Qdrant)")
    neigh = await sim_svc.search_similar(qdrant, "гарантированный доход в неделю инвестиции", limit=3)
    print("  similar_to_known_scam:", sim_svc.similarity_signal(neigh))
    for n in neigh:
        p = n["payload"] or {}
        print(f"   {n['score']:.3f}  {p.get('label')}/{p.get('fraud_type')}  {(p.get('combined_text') or '')[:50]}")

    print("\n### graph entity_reuse (Neo4j)")
    for val in ("casino-x.com", "PROMO777", "@bonus_manager"):
        uses = await graph_svc.entity_reuse(neo4j, val)
        print(f"   {val:16} uses={uses}  graph_entity_reuse={uses > 1}")

    await qdrant.close()
    await neo4j.close()
    print("\nITEST_OK")


if __name__ == "__main__":
    asyncio.run(main())
