"""Базовый интерфейс коллектора. Каждый источник реализует async-генератор сырых элементов."""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator

from apps.digital_shadow.schemas import ShadowItem

# RawItem == ShadowItem на этапе сбора (без анализа). Имя-алиас для читаемости.
RawItem = ShadowItem


class Collector(abc.ABC):
    """Источник сырых элементов (форум/маркет/paste/даркнет).

    Реализации: yield по одному ShadowItem. Дедуп/расписание — на уровне раннера
    (TODO: очередь + хранилище seen-id). Сетевые коллекторы должны уважать robots/таймауты
    и не сохранять ПДн (только маски/хэши, правило §0).
    """

    source_type: str = "clearweb"

    @abc.abstractmethod
    async def collect(self, query: str | None = None) -> AsyncIterator[RawItem]:
        """Вернуть поток сырых элементов (опционально по поисковому запросу)."""
        raise NotImplementedError
        yield  # pragma: no cover  (делает функцию async-генератором для типизации)
