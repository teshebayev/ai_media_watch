# ASR на казахском — эмпирический вывод (Этап 8.4)

Проверка: 160 синтетических звонков (MMS-TTS, 16 кГц моно) прогнаны через
faster-whisper `small` (int8, CPU). WER считался по словам относительно
ground-truth текста, который озвучивали. Скрипт — `src/media/asr_check.py`,
детали по строкам — `data/processed/asr_check.jsonl`.

## Результат

| Язык | mean WER | n | Вывод |
|---|---:|---:|---|
| ru | **0.285** | 80 | приемлемо для MVP; ошибки в основном на «eGov», «SMS», латинице |
| kk | **0.909** | 80 | Whisper `small` казахский практически не распознаёт |

Пример kk: `«SMS кодын айтыңыз»` → ASR `«көдін айтыныз»`.

## Что из этого следует

1. **Для kk-аудио нужен отдельный ASR** — это ровно тот случай, что заложен в
   архитектуре: адаптер в `backend/app/services/media.py`. Кандидаты — Soyle / KSC2
   (ISSAI). Интерфейс сервиса не меняется, переключается только модель для `language="kk"`.
2. **ru можно улучшить** моделью `medium` (на 20 ядрах CPU терпимо) или прогоном на GPU,
   когда он освободится.
3. Для демо kk-сценариев надёжнее использовать **ground-truth transcript** (он уже есть в
   датасете, т.к. текст синтезировали мы), а ASR показывать на ru.

## Воспроизвести

```bash
CUDA_VISIBLE_DEVICES="" .venv/bin/python -m src.media.asr_check --model small
# для ru с medium:
CUDA_VISIBLE_DEVICES="" .venv/bin/python -m src.media.asr_check --model medium --limit 80
```
