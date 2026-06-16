"""Загрузка Shadow Graph из CSV (entities_nodes.csv / entities_edges.csv, Студент 8).

Каркас: читает CSV и делает MERGE узлов/связей в Neo4j. Реквизиты (телефоны, карты)
ожидаются уже в виде хэша/маски (ТЗ §0) — скрипт их не разворачивает.

Запуск (когда Neo4j поднят):
    python -m src.graph.build_graph data/processed/entities_nodes.csv \
                                    data/processed/entities_edges.csv
"""

from __future__ import annotations

import csv
import os
import sys


def _driver():
    from neo4j import GraphDatabase

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "finguard_pass")
    return GraphDatabase.driver(uri, auth=(user, password))


def load(nodes_csv: str, edges_csv: str) -> None:
    driver = _driver()
    with driver.session() as session, open(nodes_csv, encoding="utf-8") as nf:
        for row in csv.DictReader(nf):
            # ожидаемые колонки: label, key, value  (напр. Domain,name,casino-x.com)
            session.run(
                f"MERGE (n:{row['label']} {{{row['key']}: $value}})", value=row["value"]
            )
    with driver.session() as session, open(edges_csv, encoding="utf-8") as ef:
        for row in csv.DictReader(ef):
            # ожидаемые колонки: src_label,src_key,src_value,rel,dst_label,dst_key,dst_value
            session.run(
                f"MATCH (a:{row['src_label']} {{{row['src_key']}: $sv}}) "
                f"MATCH (b:{row['dst_label']} {{{row['dst_key']}: $dv}}) "
                f"MERGE (a)-[:{row['rel']}]->(b)",
                sv=row["src_value"],
                dv=row["dst_value"],
            )
    driver.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    load(sys.argv[1], sys.argv[2])
