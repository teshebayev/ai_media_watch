"""Шаг 6 — построить Shadow Graph в Neo4j из единого датасета (ТЗ §12).

Читает ai_media_watch_dataset.jsonl и для каждой записи делает MERGE узлов/связей:
  (Video|Post|Call {id}) -[:MENTIONS]-> (Domain|TelegramUsername)
  (... ) -[:HAS_PROMO]-> (PromoCode)
  (... ) -[:HAS_SIGNAL]-> (RiskSignal)
Телефоны/карты в граф не кладём в сыром виде (ТЗ §0) — только то, что уже в entities.

Запуск (Neo4j поднят):
    NEO4J_URI=bolt://localhost:7687 python -m src.graph.build_from_dataset
"""

from __future__ import annotations

import json
import os

DATASET = "data/processed/ai_media_watch_dataset.jsonl"

# modality → метка узла-источника
NODE_LABEL = {"video": "Video", "audio": "Call", "text": "Post", "url": "Post", "image": "Post"}


def _driver():
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "finguard_pass")),
    )


CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (t:TelegramUsername) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:PromoCode) REQUIRE p.code IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (w:Wallet) REQUIRE w.address IS UNIQUE",
]


def build() -> dict:
    driver = _driver()
    n_nodes = n_edges = 0
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            session.run(stmt)

        with open(DATASET, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                label = NODE_LABEL.get(rec.get("modality", "text"), "Post")
                rid = rec["id"]
                ents = rec.get("entities") or {}
                session.run(
                    f"MERGE (s:{label} {{id: $id}}) "
                    "SET s.fraud_type=$ft, s.risk_level=$rl, s.language=$lang",
                    id=rid, ft=rec.get("fraud_type"), rl=rec.get("risk_level"),
                    lang=rec.get("language"),
                )
                n_nodes += 1
                for dom in ents.get("domains", []):
                    session.run(
                        f"MATCH (s:{label} {{id:$id}}) MERGE (d:Domain {{name:$v}}) "
                        "MERGE (s)-[:MENTIONS]->(d)", id=rid, v=dom)
                    n_edges += 1
                for tg in ents.get("telegram_usernames", []):
                    session.run(
                        f"MATCH (s:{label} {{id:$id}}) MERGE (t:TelegramUsername {{name:$v}}) "
                        "MERGE (s)-[:MENTIONS]->(t)", id=rid, v=tg)
                    n_edges += 1
                for code in ents.get("promo_codes", []):
                    session.run(
                        f"MATCH (s:{label} {{id:$id}}) MERGE (p:PromoCode {{code:$v}}) "
                        "MERGE (s)-[:HAS_PROMO]->(p)", id=rid, v=code)
                    n_edges += 1
                for sig in rec.get("risk_signals", []):
                    session.run(
                        f"MATCH (s:{label} {{id:$id}}) MERGE (r:RiskSignal {{name:$v}}) "
                        "MERGE (s)-[:HAS_SIGNAL]->(r)", id=rid, v=sig)
                    n_edges += 1
    driver.close()
    return {"nodes_src": n_nodes, "edges": n_edges}


def reuse_report(top: int = 10) -> None:
    """Топ повторяемых сущностей (graph_entity_reuse) — главная фича демо."""
    driver = _driver()
    with driver.session() as session:
        print("\n=== Топ доменов по повторяемости ===")
        q = ("MATCH (d:Domain)<-[:MENTIONS]-(s) WITH d, count(s) AS uses "
             "WHERE uses > 1 RETURN d.name AS name, uses ORDER BY uses DESC LIMIT $top")
        for r in session.run(q, top=top):
            print(f"  {r['name']:24} {r['uses']}")
        print("=== Топ промокодов ===")
        q2 = ("MATCH (p:PromoCode)<-[:HAS_PROMO]-(s) WITH p, count(s) AS uses "
              "WHERE uses > 1 RETURN p.code AS code, uses ORDER BY uses DESC LIMIT $top")
        for r in session.run(q2, top=top):
            print(f"  {r['code']:24} {r['uses']}")
    driver.close()


if __name__ == "__main__":
    stats = build()
    print(f"Источников-узлов: {stats['nodes_src']}, связей: {stats['edges']}")
    reuse_report()
