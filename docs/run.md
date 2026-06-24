# Запуск — только команды

## 0. Инфраструктура (общая, один раз)
```bash
docker compose -f infra/docker-compose.yml up -d qdrant neo4j postgres
```

## 1. AI Media Watch — контент-антифрод
```bash
make media          # API :8088
# фронт :3000 (в составе stack-docker) — или открыть apps/media_watch напрямую
```
- API:  http://localhost:8088
- Фронт: http://localhost:3000

## 2. Digital Shadow — OSINT/DarkNet
```bash
make shadow         # API :8090
make shadow-front   # UI  :8091  (ходит в API :8090)
```
- API:  http://localhost:8090
- Фронт: http://localhost:8091  (вкладки: Анализ · Сбор · Находки · Граф · Очередь · Watchlist · Акторы)

## Проверка, что всё поднято
```bash
curl localhost:8088/health            # Media
curl localhost:8090/shadow/health     # Shadow → {graph_connected, db_enabled}
curl -X POST localhost:8090/shadow/collect/mock   # демо: листинги → находки
```

## ASR (распознавание речи)
Дефолт — **Whisper `large-v3`** (faster-whisper) для ru/общего; на хосте `make media`
использует GPU (float16, ~3-5с на клип), в CPU-окружении автоматически int8.

**Казахский** определяется автоматически и уходит на дообученную модель
`shyngys879/kazakh-whisper-large-v3-turbo` (transformers) — числа прописью, термины,
полный текст без потерь сегментов. При ошибке/нехватке GPU — мягкий откат на large-v3.

Переопределение через env перед запуском:
```bash
ASR_MODEL_SIZE=large-v3   # small|medium|large-v3 (основной бэкенд)
ASR_DEVICE=auto           # auto|cuda|cpu
ASR_COMPUTE_TYPE=auto     # auto|float16|int8
ASR_KK_ENABLED=true       # авто-переключение на kk-модель при детекте казахского
ASR_KK_MODEL=shyngys879/kazakh-whisper-large-v3-turbo
```
Разовая транскрипция файла:
```bash
PYTHONPATH=. .venv/bin/python -m src.media.asr_whisper data/<файл>.wav
```

## Учётки сервисов
| Сервис | URL | Логин / пароль |
|---|---|---|
| Neo4j Browser | http://localhost:7474 | `neo4j` / `finguard_pass` |
| Postgres | `localhost:5433` | `finguard` / `finguard_pass`, БД `finguard` |
| Qdrant | http://localhost:6333/dashboard | — |

## Остановить
```bash
pkill -f "apps.digital_shadow"        # Shadow API
pkill -f "http.server 8091"           # Shadow фронт
docker compose -f infra/docker-compose.yml down   # инфра (по желанию)
```
