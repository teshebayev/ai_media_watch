"""Демо-датасет для графа: листинги, СПЕЦИАЛЬНО делящие общие индикаторы (кошелёк/@ник),
чтобы в графе образовались кластеры по видам торговли (вейпы/алкоголь/наркотики/дропы/утечки)
и один кросс-категорийный мост (общий кошелёк в наркотиках и дропах).

Данные синтетические, реквизиты выдуманы (§0). Назначение — наглядная визуализация
скрытых связей и кластеров акторов для аналитика/демо.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .base import Collector, RawItem

# Валидные по формату TRON-адреса (T + 33 base58) для демо.
_W_DRUG = "TDr9Y2khEsLJW1ChVWFMSMeRDow5Kcbk2v"      # кошелёк наркокластера
_W_BRIDGE = "TBr9Y2khEsLJW1ChVWFMSMeRDow5Kcbk2v"    # МОСТ: наркотики ↔ дропы
_W_VAPE = "TVa9Y2khEsLJW1ChVWFMSMeRDow5Kcbk2v"      # кошелёк вейп-кластера

# Каждый кластер делит общий @ник или кошелёк → связные компоненты в графе.
_FIXTURES = [
    # ── ВЕЙПЫ (общий @vape_opt_kz + кошелёк _W_VAPE) ──
    {"id": "cl_vape_1", "platform": "classifieds", "src": "clearweb",
     "title": "Вейпы оптом без акциз",
     "text": f"Elf bar оптом, жидкости без акциз, контрабанда, доставка по РК. "
             f"Без документов. telegram @vape_opt_kz, оплата USDT {_W_VAPE}."},
    {"id": "cl_vape_2", "platform": "forum", "src": "clearweb",
     "title": "iqos стики оптом",
     "text": "iqos оптом, стики без акциз, электронные сигареты без акциз. "
             "Опт, доставка. Пишите @vape_opt_kz."},
    {"id": "cl_vape_3", "platform": "darkmarket", "src": "darknet",
     "title": "вейп көтерме",
     "text": f"Акцизсіз вейп көтерме, сұйықтық көтерме. Оплата только крипта {_W_VAPE}. session."},

    # ── АЛКОГОЛЬ (общий @alco_opt_kz) ──
    {"id": "cl_alco_1", "platform": "classifieds", "src": "clearweb",
     "title": "Паленый алкоголь оптом",
     "text": "Паленый алкоголь оптом, спирт оптом, контрафактный алкоголь. "
             "Опт, без документов. telegram @alco_opt_kz."},
    {"id": "cl_alco_2", "platform": "forum", "src": "clearweb",
     "title": "акцизсіз арақ",
     "text": "Акцизсіз арақ, спирт көтерме, акцизсіз спирт. Опт. Контакт @alco_opt_kz."},

    # ── НАРКОТИКИ (общий кошелёк _W_DRUG + мост _W_BRIDGE) ──
    {"id": "cl_drug_1", "platform": "darkmarket", "src": "darknet",
     "title": "Проверенный магазин",
     "text": f"Закладки по городу, товар в наличии, реагент, соль. "
             f"Оплата только USDT {_W_DRUG}. Связь только session. Без документов."},
    {"id": "cl_drug_2", "platform": "darkmarket", "src": "darknet",
     "title": "клад оптом и розница",
     "text": f"Клад, меф, шишки, скорость. Оптом и розница. "
             f"Оплата крипта {_W_DRUG} или {_W_BRIDGE}. jabber."},

    # ── ДРОПЫ (общий @drop_team_kz + мост _W_BRIDGE) ──
    {"id": "cl_drop_1", "platform": "forum", "src": "clearweb",
     "title": "Ищем дропов",
     "text": "Ищем дропов: карта в аренду за процент, приём переводов и снять. "
             "Выгодная подработка. telegram @drop_team_kz."},
    {"id": "cl_drop_2", "platform": "darkmarket", "src": "darknet",
     "title": "обнал · приём переводов",
     "text": f"Обнал, переоформление карт, reshipping. Ваша карта за процент. "
             f"@drop_team_kz, оплата {_W_BRIDGE}."},

    # ── УТЕЧКИ БД РК (общий @leak_seller_kz) ──
    {"id": "cl_leak_1", "platform": "leak_forum", "src": "paste",
     "title": "Продам базу РК",
     "text": "Продам базу Казахстан: ФИО, ИИН, телефоны. Свежий дамп, пробив по запросу. "
             "Контакт @leak_seller_kz."},
    {"id": "cl_leak_2", "platform": "leak_forum", "src": "paste",
     "title": "слив базы Казахстан",
     "text": "Слив базы РК, leaked database, утечка. Дамп ИИН. @leak_seller_kz, оплата USDT."},
]


class DemoClusterCollector(Collector):
    """Демо-датасет с заранее связанными индикаторами → кластеры по торговлям в графе."""

    source_type = "darknet"

    async def collect(self, query: str | None = None) -> AsyncIterator[RawItem]:
        for fx in _FIXTURES:
            if query and query.lower() not in (fx["title"] + " " + fx["text"]).lower():
                continue
            yield RawItem(
                id=fx["id"], source_type=fx["src"],
                source_url=f"http://demo-{fx['id']}.onion", platform=fx["platform"],
                title=fx["title"], text=fx["text"], language="ru",
            )
