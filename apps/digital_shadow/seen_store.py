"""Дедупликация и инкрементальный сбор: файловое хранилище «уже виденных» элементов.

Зачем: коллекторы при повторном прогоне отдают те же листинги — без дедупа пайплайн
переанализирует и пере-пишет одно и то же (шум в очереди, лишняя нагрузка на граф/БД).
SeenStore помнит ключи между запусками → собираем только НОВОЕ (инкрементальный сбор).

Ключ дедупа — контентный (sha1 нормализованного текста) + id источника: ловим и
повторную публикацию того же текста под новым id, и тот же id. ПДн не храним — только хэш
(§0). Хранилище — простой текстовый файл (по ключу в строке), без внешних зависимостей.
"""

from __future__ import annotations

import hashlib
import logging
import os

logger = logging.getLogger(__name__)


def content_key(text: str) -> str:
    """Контентный ключ: sha1 нормализованного (lower+схлопнутые пробелы) текста."""
    norm = " ".join((text or "").lower().split())
    return "h:" + hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def id_key(source_type: str, item_id: str) -> str:
    return f"id:{source_type}:{item_id}"


class SeenStore:
    """Множество виденных ключей с персистом в файл. Best-effort: ошибки I/O не валят сбор."""

    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("SHADOW_SEEN_FILE", "data/shadow/seen.txt")
        self._seen: set[str] = set()
        self._dirty: list[str] = []
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    k = line.strip()
                    if k:
                        self._seen.add(k)
        except FileNotFoundError:
            pass
        except Exception as e:  # noqa: BLE001
            logger.warning("SeenStore: не удалось прочитать %s: %s", self.path, e)

    def is_new(self, *, source_type: str, item_id: str, text: str) -> bool:
        """True, если элемент ещё не встречался (по id ИЛИ по контентному хэшу)."""
        return not (id_key(source_type, item_id) in self._seen
                    or content_key(text) in self._seen)

    def mark(self, *, source_type: str, item_id: str, text: str) -> None:
        """Пометить элемент как виденный (в память + в буфер на запись)."""
        for k in (id_key(source_type, item_id), content_key(text)):
            if k not in self._seen:
                self._seen.add(k)
                self._dirty.append(k)

    def flush(self) -> int:
        """Дозаписать новые ключи в файл (append). Возвращает число записанных."""
        if not self._dirty:
            return 0
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                for k in self._dirty:
                    f.write(k + "\n")
            n = len(self._dirty)
            self._dirty = []
            return n
        except Exception as e:  # noqa: BLE001
            logger.warning("SeenStore: не удалось записать %s: %s", self.path, e)
            return 0
