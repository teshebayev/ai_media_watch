"""OCR: кадры видео/изображения → текст через PaddleOCR (Студент 4, ТЗ §13).

paddleocr/paddlepaddle ставятся отдельно (тяжёлые) — см. README. План «Риски»:
если ставится тяжело — прогнать OCR заранее скриптом, в демо отдавать из кэша.

Запуск:
    python -m src.media.ocr_paddle path/to/image.png [lang]
"""

from __future__ import annotations

import sys
from functools import lru_cache


@lru_cache(maxsize=2)
def _get_ocr(lang: str):
    from paddleocr import PaddleOCR

    return PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)


def ocr_image(image_path: str, lang: str = "ru") -> str:
    """Вернуть текст с изображения/кадра одной строкой."""
    ocr = _get_ocr(lang)
    result = ocr.ocr(image_path, cls=True)
    if not result:
        return ""
    lines = []
    for block in result:
        if not block:
            continue
        for line in block:
            # line = [box, (text, confidence)]
            try:
                lines.append(line[1][0])
            except (IndexError, TypeError):
                continue
    return " ".join(lines).strip()


def ocr_frames(frame_paths: list[str], lang: str = "ru") -> str:
    """OCR по набору кадров → объединённый дедуплицированный текст."""
    seen: dict[str, None] = {}
    for path in frame_paths:
        for token in ocr_image(path, lang=lang).split():
            seen.setdefault(token, None)
    return " ".join(seen.keys())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    language = sys.argv[2] if len(sys.argv) > 2 else "ru"
    print(ocr_image(sys.argv[1], lang=language))
