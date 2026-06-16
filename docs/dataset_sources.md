# Источники данных

Полные таблицы — ТЗ §3. Кратко по зонам ответственности (ТЗ §13):

| Студент | Зона | Источники | Итоговые файлы |
|---|---|---|---|
| 1 | YouTube | YouTube Data API `search.list` | `youtube_candidates.csv`, `youtube_candidates_clean.jsonl` |
| 2 | Telegram | Telegram export / Telegram Spam or Ham | `telegram_messages.jsonl` |
| 3 | Ready datasets | ScamSpot, phishing-dataset, CryptoScamDB | `ready_dataset_examples.jsonl` |
| 4 | ASR/OCR | Whisper, PaddleOCR | `audio_transcripts.jsonl`, `video_ocr.jsonl` |
| 5 | KZ calls | Синтетика по eGov/Нацбанк warning | `kz_call_scripts.csv`, `kz_call_transcripts.jsonl` |
| 6 | FakeFace | FaceForensics++, DFDC, FakeAVCeleb | `deepfake_examples.jsonl` |
| 7 | Entity + Risk | regex, signal_extractor, risk_engine | `entities_extracted.jsonl`, `risk_engine.py` |
| 8 | Shadow Graph + UI | Neo4j, Streamlit | `entities_nodes.csv`, `entities_edges.csv`, `streamlit_app.py` |

Официальные источники KZ (предупреждения) — ТЗ §3.1. Использовать только открытые
публикации; приватные данные/утечки запрещены (ТЗ §0).
