"""Neo4j-драйвер + констрейнты уникальности из ТЗ §12."""

from neo4j import AsyncDriver, AsyncGraphDatabase

from backend.app.config import get_settings

CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (t:TelegramUsername) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:PromoCode) REQUIRE p.code IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (w:Wallet) REQUIRE w.address IS UNIQUE",
]


def make_neo4j_driver() -> AsyncDriver:
    s = get_settings()
    return AsyncGraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))


async def ensure_constraints(driver: AsyncDriver) -> None:
    async with driver.session() as session:
        for stmt in CONSTRAINTS:
            await session.run(stmt)
