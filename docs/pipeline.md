# FakeFace FinGuard — полный пайплайн

```mermaid
flowchart TD
    %% ---------- Источники ----------
    subgraph SRC["📥 Источники"]
        T["Текст / пост"]
        U["URL: YouTube / Instagram / TikTok / HTML / Telegram"]
        AU["Аудио-звонок .wav"]
        VID["Видео .mp4 (загрузка)"]
        SP[("Stop-Piramida.kz<br/>593 видео Vimeo")]
        SY["Синтетика:<br/>gen_call_scripts + gen_posts + MMS-TTS"]
    end

    %% ---------- Ingest / Media ----------
    subgraph ING["🎬 Ingest и медиа-обработка"]
        YT["yt-dlp:<br/>метаданные + субтитры + превью"]
        HT["httpx:<br/>видимый текст + og-мета"]
        FF["ffmpeg:<br/>видео → аудио + кадры"]
        ASR["Whisper ASR<br/>faster-whisper (GPU)"]
        OCR["EasyOCR<br/>кадры / превью"]
    end

    CT(["combined_text<br/>title + desc + transcript + ocr"])

    %% ---------- Извлечение ----------
    subgraph EXT["🔎 Извлечение"]
        RE["regex §10:<br/>домены, @telegram, промокоды,<br/>суммы, крипто-кошельки, телефоны(маска)"]
        NER["KazNERD NER<br/>организации (kk)"]
        LLME["LLM-добор сущностей"]
        SIG["signal_extractor:<br/>risk_signals + этапы звонка"]
    end

    %% ---------- Интеллект-слои ----------
    subgraph INT["🧠 Интеллект-слои"]
        LLM["LLM scenario detection<br/>vLLM · Qwen2.5 → fraud_type"]
        QD[("Qdrant<br/>e5 эмбеддинги · similarity")]
        NEO[("Neo4j<br/>Shadow Graph")]
        DFK["Deepfake-детектор<br/>внешний venv: ViT лицо + Wav2Vec2 голос<br/>→ media_anomalies"]
        OSINT["OSINT/репутация<br/>тайпсквоттинг брендов + TLD<br/>(+PhishTank) → phishing_url"]
    end

    %% ---------- Скоринг ----------
    SAGG{{"агрегатор сигналов"}}
    RISK["Risk Engine<br/>детерминированный скоринг §11"]
    REP[["Analyst Report<br/>risk_score / level · evidence ·<br/>entities · recommendation"]]

    %% ---------- Хранилище ----------
    DS[("unified dataset.jsonl<br/>единый формат §5")]

    %% ---------- Обучение ----------
    subgraph ML["📊 Обучение классификатора"]
        BD["build_dataset"]
        NB["notebook:<br/>TF-IDF · Word2Vec · mBERT · e5<br/>× 5 моделей (LogReg/SVC/RF/HistGB/MLP)"]
    end

    %% ---------- Персистентность (Postgres) ----------
    subgraph PERS["🗄 Postgres — персистентный слой"]
        PG[("analysis_sessions<br/>журнал: отчёт, сигналы, сущности,<br/>media_anomalies, latency")]
        RV[("analyst_reviews<br/>ручная проверка:<br/>confirm / override")]
        ST["/stats<br/>агрегаты: risk_level, fraud_type"]
    end

    %% ---------- AFM-агент (RAG, та же Qdrant) ----------
    subgraph AGT["💬 AFM Knowledge Agent (RAG)"]
        KBQ["вопрос: «звонят из банка,<br/>просят код из SMS — что делать?»"]
        HYB["гибридный поиск<br/>dense e5 + sparse BM25 → RRF"]
        ANS["ответ vLLM + источники<br/>(детерминир. fallback без LLM)"]
    end

    %% ---------- Доступ ----------
    subgraph SERVE["🖥 Доступ"]
        API["FastAPI<br/>/analyze · /graph · /search · /agent<br/>/sessions · /stats · /health"]
        FE["Next.js-консоль + статический фронт<br/>анализ · граф · История/Статистика · AFM-агент"]
    end

    %% ---- потоки источников ----
    T --> CT
    U --> YT --> CT
    U --> HT --> CT
    AU --> ASR
    VID --> FF
    SP --> FF
    SY --> CT
    FF --> ASR
    FF --> OCR
    ASR --> CT
    OCR --> CT

    %% ---- извлечение ----
    CT --> RE
    CT --> NER
    CT --> LLME
    RE --> SIG
    NER --> RE
    LLME --> RE

    %% ---- интеллект ----
    CT --> LLM
    CT --> QD
    RE --> NEO

    %% ---- deepfake-детектор (видео-файл, /analyze/video и url deep) ----
    VID --> DFK
    SP --> DFK
    DFK -- "possible_deepfake / synthetic_voice" --> SAGG

    %% ---- OSINT/репутация (по доменам из сущностей) ----
    RE --> OSINT
    OSINT -- "phishing_url / suspicious_domain" --> SAGG

    %% ---- сигналы → скоринг ----
    SIG --> SAGG
    LLM --> SAGG
    QD -- "similar_to_known_scam" --> SAGG
    NEO -- "graph_entity_reuse" --> SAGG
    SAGG --> RISK --> REP

    %% ---- хранилище / обучение ----
    REP --> DS
    SY --> DS
    SP --> DS
    DS --> QD
    DS --> NEO
    DS --> BD --> NB

    %% ---- персистентность сеансов (Postgres) ----
    REP -- "сохранить сеанс" --> PG
    PG -- "на проверку" --> RV
    PG --> ST
    PG --> API
    RV --> API
    ST --> API
    RV -. "подтверждённые метки" .-> DS

    %% ---- AFM-агент (RAG поверх той же Qdrant) ----
    KBQ --> HYB --> ANS --> API
    HYB -. "коллекция afm_knowledge" .-> QD
    LLM -.-> ANS

    %% ---- доступ ----
    API --> CT
    REP --> API
    NEO --> API
    QD --> API
    API --> FE

    classDef store fill:#10243e,stroke:#4da3ff,color:#e6ecf5;
    classDef llm fill:#241a40,stroke:#7c5cff,color:#e6ecf5;
    classDef pg fill:#13301f,stroke:#35d07f,color:#e6ecf5;
    class SP,QD,NEO,DS store;
    class LLM,LLME,NER,DFK,OSINT,HYB,ANS llm;
    class PG,RV,ST pg;
```

## Слои (соответствие коду)

| Слой | Модуль | Что делает |
|---|---|---|
| Ingest по ссылке | `src/ingest/url_fetcher.py` | yt-dlp (видео-платформы) + httpx (HTML/Telegram) + OCR превью |
| Медиа | `backend/app/services/media.py`, `src/media/{asr_whisper,ocr}.py` | ffmpeg → Whisper ASR + EasyOCR |
| Извлечение сущностей | `src/extraction/regex_extractors.py`, `kaznerd_ner.py` | regex §10 + KazNERD (kk) + LLM-добор |
| Сигналы | `src/extraction/signal_extractor.py` | risk_signals + этапы звонка |
| Scenario / LLM | `backend/app/services/scenario.py` → vLLM | fraud_type §7 |
| Deepfake-детектор | `backend/app/services/deepfake.py` → `external/fakeface-detector` (свой venv) | `media_anomalies` (ViT лицо + Wav2Vec2 голос) → `possible_deepfake`/`synthetic_voice_suspected` |
| OSINT/репутация | `backend/app/services/osint.py` | тайпсквоттинг KZ-брендов + TLD (+PhishTank) → `phishing_url`/`suspicious_domain` |
| Similarity | `backend/app/services/similarity.py` → Qdrant | similar_to_known_scam (коллекция `scam_cases`) |
| Shadow Graph | `backend/app/services/graph.py` → Neo4j | graph_entity_reuse, повторяемость |
| AFM Knowledge Agent | `backend/app/services/knowledge.py`, `api/knowledge.py` | RAG Q&A по базе АФМ: гибридный поиск (dense e5 + sparse BM25, RRF) в Qdrant `afm_knowledge` + ответ vLLM (fallback из карточки) → `/agent/*` |
| Risk Engine | `src/risk/risk_engine.py` | детерминированный скоринг §11 → Analyst Report |
| Оркестратор | `backend/app/services/pipeline.py` | связывает всё в `/analyze/*` |
| Персистентность | `backend/app/db/`, `services/sessions.py`, Alembic | сеансы анализа + ручная проверка (Postgres) → `/sessions` `/stats` |
| Датасет / обучение | `src/build_dataset.py`, `notebooks/fraud_classifier.ipynb` | единый JSONL → 4 представления × 5 моделей |
| Доступ | `backend/app/api/*` | REST: `/analyze/{text,url,audio,video}`, `/graph/{entity,network}`, `/search/similar`, `/agent/{ask,search,reindex,status}`, `/sessions`, `/stats`, `/health` |
| Фронтенд | Next.js (репо `av1cu/ai_media_watch_frontend`) + статический `frontend/index.html` | лендинг + `/console`; граф vis-network, История/Статистика |

## Развёртывание (Docker Compose)

Один стек, контейнеры за `infra/docker-compose.yml`. Backend-образ **слим** (~2.3 ГБ): CPU-torch
+ только runtime-зависимости (`backend/requirements-runtime.txt`), без обучающего стека и CUDA-библиотек.

```mermaid
flowchart LR
    BROWSER["Браузер"] -->|":3000"| FE["frontend<br/>Next.js (158 МБ)"]
    BROWSER -->|"fetch :8088→8080 (CORS *)"| API
    FE -. "NEXT_PUBLIC_API_BASE" .-> API["api<br/>FastAPI (слим ~2.3 ГБ)<br/>alembic upgrade → uvicorn"]
    API -->|"6333"| QD[("qdrant")]
    API -->|"7687"| NEO[("neo4j")]
    API -->|"5432"| PG[("postgres")]
    API -.->|"8000 (profile gpu)"| VLLM["vllm<br/>Qwen2.5 (GPU)"]
    classDef c fill:#10243e,stroke:#4da3ff,color:#e6ecf5;
    class QD,NEO,PG c;
```

- `api` накатывает миграции Alembic на старте и ходит в сервисы по именам (`qdrant`/`neo4j`/`postgres`/`vllm`).
- `vllm` — в профиле `gpu` (нужен GPU + nvidia-container-toolkit), по умолчанию выключен.
- браузерный `fetch` идёт на публичный `http://localhost:8088` (хост-порт api, проброшен на контейнерный 8080; не docker-сеть), CORS открыт.
- одна **Qdrant** хранит две коллекции: `scam_cases` (similarity по кейсам) и `afm_knowledge` (база знаний AFM-агента, гибридный поиск); AFM-агент использует тот же `vllm`.
- **Adminer** (`:8081`) — веб-UI к Postgres; deepfake-детектор в проде запускается отдельным процессом/venv (флаг `ENABLE_DEEPFAKE`, в docker по умолчанию off).

### Команды
| Команда | Что делает |
|---|---|
| `make stack-docker` | `docker compose up -d --build` — qdrant+neo4j+postgres+**api+frontend** (vLLM: `--profile gpu`) |
| `make stack` | то же на хосте без сборки образов: инфра-контейнеры + backend (хост-venv) + Next-фронт (для dev / забитого диска) |
| `make api-cpu` · `make front` | по отдельности: backend без GPU · статический фронт :8090 |
| `make index` · `make test` · `make lint` | индексация Qdrant · pytest · ruff |
