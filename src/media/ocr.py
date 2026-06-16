"""OCR-движок для кадров/превью (CPU). По умолчанию EasyOCR (кириллица+латиница:
промокоды, домены, суммы на скринах). Модель грузится лениво и кешируется.

Запуск:
    python -m src.media.ocr path/to/image.png
"""

from __future__ import annotations

import re
import sys
from functools import lru_cache


@lru_cache(maxsize=1)
def _reader(langs: tuple[str, ...]):
    import easyocr

    # gpu=False — строго CPU, не мешаем другим GPU-задачам.
    return easyocr.Reader(list(langs), gpu=False, verbose=False)


def _to_text(results) -> str:
    # detail=0 → список строк
    return re.sub(r"\s+", " ", " ".join(results)).strip()


def ocr_image(path: str, langs: tuple[str, ...] = ("ru", "en")) -> str:
    return _to_text(_reader(langs).readtext(path, detail=0, paragraph=False))


def ocr_image_bytes(data: bytes, langs: tuple[str, ...] = ("ru", "en")) -> str:
    import cv2
    import numpy as np

    arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return ""
    return _to_text(_reader(langs).readtext(arr, detail=0, paragraph=False))


def ocr_frames(frame_paths: list[str], langs: tuple[str, ...] = ("ru", "en")) -> str:
    """OCR по набору кадров → объединённый дедуплицированный текст."""
    seen: dict[str, None] = {}
    for path in frame_paths:
        for token in ocr_image(path, langs).split():
            seen.setdefault(token, None)
    return " ".join(seen.keys())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    print(ocr_image(sys.argv[1]))
