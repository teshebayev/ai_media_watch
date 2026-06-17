"""Ingest по ссылке: URL → текст для анализа.

Определяет тип ссылки и извлекает контент БЕЗ скачивания тяжёлых медиа:
  - YouTube (watch/shorts/youtu.be) → yt-dlp extract_info(download=False):
    title + description + tags + (best-effort) автосубтитры;
  - обычная HTML-страница / Telegram-пост (t.me) → httpx GET + извлечение
    видимого текста и og:title/og:description.

Безопасность (ТЗ §0): только GET публичных страниц, таймаут, лимит размера,
никакого исполнения JS и скачивания файлов. Извлекаем лишь текст для risk-анализа.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

import httpx

UA = "FakeFaceFinGuard/0.1 (educational analyst tool)"
TIMEOUT = 15
MAX_CHARS = 20000

# Guard-ы для deep-режима (скачивание видео + OCR кадров)
MAX_DEEP_SECONDS = 600          # видео длиннее 10 мин не качаем (deep пропускается)
MAX_DEEP_BYTES = 60_000_000     # лимит размера скачивания (~60 МБ)
MAX_DEEP_FRAMES = 6             # сколько кадров OCR-ить максимум
FFMPEG_TIMEOUT = 60             # сек на нарезку кадров

KZ_CHARS = set("әғқңөұүһі")


def detect_language(text: str) -> str:
    low = text.lower()
    if any(c in low for c in KZ_CHARS):
        return "kk"
    if re.search(r"[а-яё]", low):
        return "ru"
    return "en"


# Хосты, которые умеет тянуть yt-dlp (метаданные + субтитры + превью).
VIDEO_HOSTS = (
    "youtube.com", "youtu.be", "instagram.com", "tiktok.com", "vm.tiktok.com",
    "facebook.com", "fb.watch", "vk.com", "vimeo.com", "twitter.com", "x.com",
)


def classify_url(url: str) -> str:
    u = url.lower()
    if any(h in u for h in VIDEO_HOSTS):
        return "video"
    return "html"


def _platform_from(info: dict, url: str) -> str:
    key = (info.get("extractor_key") or info.get("extractor") or "").lower()
    for name in ("youtube", "instagram", "tiktok", "facebook", "vk", "vimeo", "twitter"):
        if name in key or name in url.lower():
            return "twitter" if name == "x.com" else name
    return "video"


# --- HTML --------------------------------------------------------------------

class _HTMLText(HTMLParser):
    _SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__()
        self._skip = 0
        self._in_title = False
        self.title = ""
        self.og_title = ""
        self.og_desc = ""
        self._chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            a = dict(attrs)
            prop = (a.get("property") or a.get("name") or "").lower()
            content = a.get("content") or ""
            if prop in ("og:title", "twitter:title") and not self.og_title:
                self.og_title = content
            elif prop in ("og:description", "twitter:description", "description") and not self.og_desc:
                self.og_desc = content

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
        self._chunks.append(text)

    def get_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._chunks)).strip()


def fetch_html(url: str) -> dict:
    headers = {"User-Agent": UA, "Accept-Language": "ru,kk,en"}
    with httpx.Client(follow_redirects=True, timeout=TIMEOUT, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype:
            raise ValueError(f"не HTML-страница (content-type: {ctype or '?'})")
        html = r.text
    p = _HTMLText()
    p.feed(html)
    title = p.og_title or p.title
    desc = p.og_desc
    text = p.get_text()
    combined = " ".join(x for x in (title, desc, text) if x)[:MAX_CHARS]
    return {
        "modality": "url",
        "platform": "telegram" if "t.me/" in url.lower() else "website",
        "title": title or None,
        "description": desc or None,
        "channel": None,
        "transcript": None,
        "combined_text": combined,
        "url": str(r.url),
        "source": "web_url",
    }


# --- YouTube -----------------------------------------------------------------

def _parse_captions(text: str, ext: str) -> str:
    if ext == "json3":
        import json
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return ""
        out = []
        for ev in data.get("events", []):
            for seg in ev.get("segs", []) or []:
                if seg.get("utf8"):
                    out.append(seg["utf8"])
        return re.sub(r"\s+", " ", "".join(out)).strip()
    # vtt / srv: убрать таймкоды и номера
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line == "WEBVTT" or "-->" in line or line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)  # inline теги
        lines.append(line)
    # дедуп подряд идущих повторов (типично для автосабов)
    dedup = []
    for ln in lines:
        if not dedup or dedup[-1] != ln:
            dedup.append(ln)
    return re.sub(r"\s+", " ", " ".join(dedup)).strip()


def _youtube_captions(info: dict, langs=("ru", "kk", "en")) -> str:
    for store in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for lang in langs:
            fmts = store.get(lang)
            if not fmts:
                continue
            chosen = next((f for f in fmts if f.get("ext") in ("json3", "vtt", "srv1")), fmts[0])
            try:
                r = httpx.get(chosen["url"], timeout=TIMEOUT)
                r.raise_for_status()
                txt = _parse_captions(r.text, chosen.get("ext", ""))
                if txt:
                    return txt[:MAX_CHARS]
            except Exception:  # noqa: BLE001
                continue
    return ""


def _best_thumbnail(info: dict) -> str:
    if info.get("thumbnail"):
        return info["thumbnail"]
    thumbs = info.get("thumbnails") or []
    # берём самый большой по площади (если указаны размеры)
    best = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0), default=None)
    return best.get("url") if best else ""


def _thumbnail_ocr(thumb_url: str) -> str:
    """OCR превью видео (промокод/домен часто только на картинке, не в описании)."""
    if not thumb_url:
        return ""
    try:
        r = httpx.get(thumb_url, timeout=TIMEOUT, headers={"User-Agent": UA})
        r.raise_for_status()
        from src.media.ocr import ocr_image_bytes
        return ocr_image_bytes(r.content)
    except Exception:  # noqa: BLE001
        return ""


def _download_video(url: str) -> str | None:
    """Скачать видео в низком качестве во временную папку → путь к файлу (или None).

    Папку НЕ удаляем: файл нужен и для OCR кадров, и для deepfake-детектора.
    Чистит вызывающая сторона (роутер) через cleanup_media_path().
    """
    import glob
    import os
    import tempfile

    import yt_dlp

    tmp = tempfile.mkdtemp(prefix="finguard_v_")
    out = os.path.join(tmp, "v.%(ext)s")
    opts = {"quiet": True, "noplaylist": True, "no_warnings": True,
            "format": "worst[ext=mp4]/worst", "outtmpl": out, "max_filesize": MAX_DEEP_BYTES}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        vids = glob.glob(os.path.join(tmp, "v.*"))
        return vids[0] if vids else None
    except Exception:  # noqa: BLE001
        return None


def _extract_frames_ocr(video_path: str) -> str:
    """ffmpeg кадры (fps=0.5, ≤MAX_DEEP_FRAMES) → OCR. Из уже скачанного файла."""
    import glob
    import os
    import subprocess

    from src.media.ocr import ocr_frames

    fdir = os.path.join(os.path.dirname(video_path), "frames")
    os.makedirs(fdir, exist_ok=True)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vf", "fps=0.5",
             os.path.join(fdir, "f_%03d.png")],
            check=True, capture_output=True, timeout=FFMPEG_TIMEOUT,
        )
        frames = sorted(glob.glob(os.path.join(fdir, "*.png")))[:MAX_DEEP_FRAMES]
        return ocr_frames(frames)
    except Exception:  # noqa: BLE001
        return ""


def cleanup_media_path(media_path: str | None) -> None:
    """Удалить временную папку скачанного видео (вызывает роутер после анализа)."""
    if not media_path:
        return
    import os
    import shutil
    shutil.rmtree(os.path.dirname(media_path), ignore_errors=True)


def fetch_video(url: str, deep: bool = False, ocr: bool = True) -> dict:
    """Видео-платформа через yt-dlp: метаданные + субтитры + OCR превью (+ кадры при deep)."""
    import yt_dlp

    opts = {"quiet": True, "skip_download": True, "noplaylist": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        # process=False — только метаданные, без выбора видео-форматов.
        info = ydl.extract_info(url, download=False, process=False)
    if not info:
        raise ValueError("yt-dlp не вернул метаданные")

    title = info.get("title") or ""
    desc = info.get("description") or ""
    channel = info.get("channel") or info.get("uploader") or ""
    tags = info.get("tags") or []
    captions = _youtube_captions(info)

    ocr_text = ""
    ocr_note = None
    media_path = None  # путь к скачанному видео (deep) — для deepfake-детектора; чистит роутер
    if ocr:
        ocr_text = _thumbnail_ocr(_best_thumbnail(info))
    if deep:
        duration = info.get("duration")  # секунды, если известно
        if duration and duration > MAX_DEEP_SECONDS:
            ocr_note = (f"видео {int(duration // 60)} мин длиннее лимита "
                        f"{MAX_DEEP_SECONDS // 60} мин — OCR кадров пропущен (только превью)")
        else:
            media_path = _download_video(url)  # скачиваем 1 раз: и для OCR кадров, и для deepfake
            if media_path:
                frame_text = _extract_frames_ocr(media_path)
                if frame_text:
                    ocr_text = (ocr_text + " " + frame_text).strip()
            else:
                ocr_note = "видео не удалось скачать (лимит размера / yt-dlp)"

    parts = [title, desc, " ".join(tags), captions, ocr_text]
    combined = " ".join(p for p in parts if p)[:MAX_CHARS]
    return {
        "modality": "video",
        "platform": _platform_from(info, url),
        "title": title or None,
        "description": desc or None,
        "channel": channel or None,
        "transcript": captions or None,
        "ocr_text": ocr_text or None,
        "ocr_note": ocr_note,
        "media_path": media_path,
        "duration": info.get("duration"),
        "combined_text": combined,
        "url": info.get("webpage_url", url),
        "source": "video_url",
    }


def ingest(url: str, deep: bool = False) -> dict:
    """URL → нормализованный dict (modality, combined_text, title, language, …).

    deep=True для видео — дополнительно скачивает низкокачественную копию и OCR-ит кадры.
    """
    if not re.match(r"^https?://", url, re.I):
        raise ValueError("URL должен начинаться с http:// или https://")
    data = fetch_video(url, deep=deep) if classify_url(url) == "video" else fetch_html(url)
    if not data["combined_text"].strip():
        raise ValueError("со страницы не удалось извлечь текст")
    data["language"] = detect_language(data["combined_text"])
    return data


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print("usage: python -m src.ingest.url_fetcher <url>")
        raise SystemExit(1)
    res = ingest(sys.argv[1])
    res["combined_text"] = res["combined_text"][:300] + "…"
    print(json.dumps(res, ensure_ascii=False, indent=2))
