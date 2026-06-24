# app: AI Media Watch (контентный продукт)

Постоянный сбор и анализ видео/аудио/постов из Instagram, TikTok, YouTube и др.: признаки
незаконного игорного бизнеса, финансовых пирамид, мошенничества. Риск-оценка + объяснения +
приоритизация для проверки.

## Где код (физически — пока не перемещён)
Этот продукт = **уже построенный** бэкенд FakeFace FinGuard. Чтобы не ломать рабочий стек,
файлы оставлены на месте; ниже — карта.

| Возможность | Модуль |
|---|---|
| Ingest по ссылке (yt-dlp/httpx) | `src/ingest/url_fetcher.py` |
| Медиа: ffmpeg + Whisper + EasyOCR | `backend/app/services/media.py`, `src/media/` |
| Scenario detection (LLM) | `backend/app/services/scenario.py` |
| Deepfake-детектор | `backend/app/services/deepfake.py` (внешний venv) |
| Сущности / сигналы / риск | `core` (общий движок) |
| Similarity / граф / OSINT | `core.similarity_service` / `core.graph_service` / `core.osint_service` |
| API | `backend/app/api/analyze.py` (`/analyze/{text,url,audio,video}`) |
| Persistence | `backend/app/services/sessions.py` + Postgres |

## Что добавить, чтобы продукт стал «постоянным мониторингом»
- [ ] Коллекторы соцвидео по хэштегам/аккаунтам (IG/TikTok/YouTube) + расписание + очередь + дедуп.
- [ ] Визуальные маркеры: логотипы казино / оверлеи / QR на кадрах (расширение OCR-слоя).
- [ ] Профилирование блогеров и трекинг рецидивистов через общий граф (`core.graph_service`).
- [ ] Дашборд трендов + очередь на ручную проверку (поверх `/sessions` `/stats`).

Запуск текущего продукта — `make stack-docker` (см. `docs/guide.md`).
