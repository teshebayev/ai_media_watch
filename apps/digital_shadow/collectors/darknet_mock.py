"""Синтетический даркнет-коллектор для демо (выбор пользователя: мок вместо реального Tor).

Отдаёт правдоподобные .onion-листинги под каждую категорию таксономии. Данные выдуманы,
реквизиты — маски/выдуманные строки (правило §0). Для реального Tor см. README (SOCKS-прокси).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .base import Collector, RawItem

# Демо-фикстуры: текст специально содержит триггеры лексикона/сущностей, чтобы зажечь сигналы.
_FIXTURES = [
    {
        "id": "dn_drugs_001",
        "title": "Проверенный магазин · товар в наличии",
        "text": "Закладки по городу, товар в наличии оптом и в розницу. "
                "Оплата только USDT (TRC20) TQn9Y2khEsLJW1ChVWFMSMeRDow5Kcbk2v. "
                "Связь только session. Без документов, анонимно.",
        "platform": "darkmarket",
    },
    {
        "id": "dn_drop_001",
        "title": "Ищем дропов · выгодная подработка",
        "text": "Ищем дропов: карта в аренду за процент, приём переводов и снять. "
                "Telegram @drop_team_kz. Оплата в крипте BTC "
                "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh.",
        "platform": "forum",
    },
    {
        "id": "dn_leak_001",
        "title": "Продам базу РК · свежий слив",
        "text": "Продам базу Казахстан: ФИО, ИИН, телефоны. Свежий дамп, пробив по запросу. "
                "Цена в USDT. Контакт jabber.",
        "platform": "leak_forum",
    },
    {
        "id": "dn_vape_001",
        "title": "Вейпы оптом без акциз",
        "text": "Elf bar оптом, жидкости без акциз, контрабанда, доставка по РК. Без документов. "
                "Пишите telegram @vape_opt_kz, оплата Kaspi или USDT.",
        "platform": "classifieds",
    },
]


class DarknetMockCollector(Collector):
    source_type = "darknet"

    async def collect(self, query: str | None = None) -> AsyncIterator[RawItem]:
        for fx in _FIXTURES:
            if query and query.lower() not in (fx["title"] + " " + fx["text"]).lower():
                continue
            yield RawItem(
                id=fx["id"],
                source_type=self.source_type,
                source_url=f"http://example{fx['id']}.onion",  # выдуманный
                platform=fx["platform"],
                title=fx["title"],
                text=fx["text"],
                language="ru",
            )
