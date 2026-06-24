# ТЗ для студентов: мок-данные для демо-прогона на презентации

**Цель.** Подготовить набор «игрушечных» (выдуманных) кейсов под каждый тип входа системы,
чтобы на презентации вживую прогнать полный цикл: **вход → извлечение сущностей и сигналов →
риск-скоринг → похожие кейсы (Qdrant) → граф связей (Neo4j) → отчёт аналитика**, и показать,
что система не просто «всё подряд помечает мошенничеством», а различает scam / spam / legit.

Данные **полностью синтетические**. Реальные люди, карты, ИИН, телефоны, SMS-коды — запрещены
(см. §0). Задача — не собрать «настоящих мошенников», а сделать правдоподобные примеры,
которые наглядно зажигают разные ветки пайплайна.

---

## 0. Жёсткие правила по данным (нарушать нельзя)

Система по ТЗ работает только с **обезличенными** данными. В мок-данных:

- **Нет реальных** номеров карт, ИИН, CVV, SMS-кодов, паролей, реальных ФИО и телефонов.
- Телефоны — только маска: `+7 7XX XXX-XX-XX`.
- Карты — маска: `4400 XX** **** 1234`. ИИН — `XXXXXXXXXXXX`.
- Домены/промокоды/Telegram-ники — **выдуманные** (`casino-x.com`, `kaspi-bonus.click`,
  `@invest_kz_promo`, промокод `WIN5000`). Не использовать реальные бренды как «их официальный» канал.
- Крипто-кошельки — выдуманные строки, не реальные адреса.
- Источник кейса — публичный/выдуманный, без приватных переписок.

> Бренды (Kaspi, Halyk, eGov, АФМ) можно упоминать **как объект имитации** мошенником
> («звонок якобы из Kaspi») — это и есть кейс. Нельзя выдавать свой выдуманный канал за официальный.

---

## 1. Что система принимает на вход (4 канала)

| Эндпоинт | Канал | Что подаём | Лимиты/примечания |
|---|---|---|---|
| `POST /analyze/text` | Текст | SMS, пост, реплика, расшифровка | самый простой — для демо большинства категорий |
| `POST /analyze/url` | Ссылка | YouTube / TikTok / Instagram / HTML-страница / Telegram-пост | **тянет контент вживую из интернета**; `deep:true` для видео → OCR кадров + deepfake-детектор |
| `POST /analyze/audio` | Аудио-файл | звонок (.wav/.mp3) | Whisper-транскрибация → детекция этапов звонка |
| `POST /analyze/video` | Видео-файл | ролик (.mp4) | аудио (Whisper) + кадры (OCR) + deepfake-детектор (лицо/голос/lip-sync) |

Язык: **ru / kk / en** (основное — ru и kk). Для презентации желательно иметь хотя бы 1–2 казахских примера.

> ⚠️ `/analyze/url` требует живого интернета и доступности страницы (Instagram/часть TikTok могут
> просить cookies). Для **надёжного офлайн-демо** опирайтесь на text / audio / video-файлы,
> а 1–2 url держите как «вишенку», проверив заранее, что ссылка открывается.

---

## 2. Контролируемые словари (под что готовим данные)

Каждый кейс должен ложиться в один из типов. Это словарь системы — не выдумывайте новые названия.

**label (итоговая метка):** `scam` · `spam` · `legit` · `unclear`

**fraud_type:**
`illegal_gambling_promo` (онлайн-казино/ставки), `fake_egov_delivery_call` (звонок «из eGov/доставки»),
`fake_bank_call` (звонок «из банка»), `fake_government_call` (звонок «из госоргана/полиции/АФМ»),
`investment_scam` (инвестиции с гарантией), `crypto_scam` (крипто-«заработок»),
`phishing` (фишинговая ссылка/сбор данных), `money_mule_or_drop` («дропы», обнал через свою карту),
`fake_seller` (лжепродавец, предоплата), `fake_credit` (лжекредит/«одобрен займ»),
`deepfake_financial_promo` (дипфейк-реклама с «лицом» известного человека),
`legit_finance` (нормальная финуслуга — **контрольный честный пример**),
`anti_fraud_education` (просвет/памятка — **тоже не мошенничество**),
`ordinary_spam` (обычная назойливая реклама — это `spam`, не `scam`).

**risk_signals** (что движок ищет в тексте — полный список в `backend/app/schemas/enums.py`):
`guaranteed_income, unrealistic_profit, no_risk_claim, urgency, limited_slots, telegram_contact,
whatsapp_contact, referral_scheme, crypto_payment, phishing_url, suspicious_domain, fake_authority,
fake_bank_employee, fake_government_employee, fake_egov_call, safe_account, sms_code_request,
remote_access_request, do_not_tell_anyone, account_blocking_fear, personal_data_request,
card_data_request, possible_deepfake, synthetic_voice_suspected, illegal_gambling_promo,
casino_domain_found, promo_code_found, deposit_bonus, fake_winner_claim, money_mule_request,
only_prepayment, advance_fee` и др.

---

## 3. Что именно сдать (объём)

Минимальный набор на демо — **таблица покрытия**: на каждый тип хотя бы 1 кейс, плюс обязательные «честные».

**Текст (`/analyze/text`) — 10 кейсов**, по одному на каждый:
`illegal_gambling_promo, investment_scam, crypto_scam, phishing, fake_seller, fake_credit,
money_mule_or_drop` + **обязательно** `legit_finance` (честный), `anti_fraud_education` (памятка),
`ordinary_spam` (просто реклама).
→ показывает, что система различает scam / spam / legit, а не красит всё в «critical».

**Аудио (`/analyze/audio`) — 2 файла .wav/.mp3:** `fake_bank_call` и `fake_egov_delivery_call`
(разыграть звонок по сценарию, можно через TTS или просто начитать).

**Видео (`/analyze/video`) — 1–2 файла .mp4:** `deepfake_financial_promo` (есть лицо + голос,
проверяем deepfake-детектор) и/или обычный промо-ролик казино с промокодом на обложке (проверяем OCR).

**URL (`/analyze/url`) — 1–2 ссылки** (заранее проверенные, что открываются): например YouTube/TikTok
с финансовым промо. Подавать с `deep:true` для видео, чтобы сработал OCR кадров + deepfake.

**Бонус — пачка для базы (необязательно):** 20–30 кратких текстовых кейсов в формате JSONL (§5),
чтобы пополнить базу и показать «похожие кейсы» (Qdrant) и «повтор сущности» (Neo4j).

---

## 4. Как «оживить» сигналы (рекомендуемые формулировки)

Движок ищет ключевые слова/паттерны. Чтобы кейс зажёг нужные сигналы, используйте обороты:

- **Гарантия дохода / нереальная прибыль** → «гарантированный доход», «прибыль 300% за неделю»,
  «без риска» → `guaranteed_income, unrealistic_profit, no_risk_claim`.
- **Срочность / ограничение** → «только сегодня», «осталось 3 места» → `urgency, limited_slots`.
- **Увод в мессенджер** → «пишите в Telegram @…», «WhatsApp +7 7XX…» → `telegram_contact, whatsapp_contact`.
- **Казино/ставки** → «1xBet», «депозит-бонус», «промокод WIN5000», домен `casino-x.com`
  → `illegal_gambling_promo, deposit_bonus, promo_code_found, casino_domain_found`.
- **Звонок «из банка»** → «я сотрудник службы безопасности банка», «назовите код из SMS»,
  «переведите на безопасный счёт», «никому не говорите» → `fake_bank_employee, sms_code_request,
  safe_account, do_not_tell_anyone, account_blocking_fear`.
- **Звонок «из eGov/доставки»** → «вам посылка, продиктуйте код», «подтвердите ЭЦП»
  → `fake_egov_call, personal_data_request`.
- **Фишинг** → ссылка `kaspi-bonus.click`, «подтвердите карту по ссылке»
  → `phishing_url, suspicious_domain, card_data_request`.
- **Лжепродавец** → «100% предоплата», «возврата нет» → `only_prepayment, no_return_policy`.
- **Дропы** → «дадим вашу карту в аренду за %», «получите перевод и снимите» → `money_mule_request`.
- **Дипфейк-промо (видео)** → известное «лицо» рекламирует «инвест-платформу» → детектор даст
  `possible_deepfake, synthetic_voice_suspected, lip_sync_anomaly`.

**Контрпримеры (чтобы не было ложных срабатываний):**
- `legit_finance` — спокойное информирование без давления/гарантий/ссылок («ставка по вкладу 16% годовых,
  подробности в отделении»). Ожидаем **low/medium**, label `legit`.
- `anti_fraud_education` — памятка «никогда не сообщайте код из SMS». Ожидаем `legit`.
- `ordinary_spam` — «скидка 20% на пиццу». Ожидаем `spam`, низкий риск.

---

## 5. Форматы файлов

### 5.1 Текстовые кейсы — простой список
Для ручного прогона достаточно текста кейса (его вставляют в UI или в `text`). Удобно вести в
таблице: `id | язык | ожидаемый fraud_type | ожидаемый label | текст`.

### 5.2 JSONL для пополнения базы (формат §5)
Если делаете бонус-пачку — одна строка = один JSON-объект. Минимально нужны поля:

```json
{"id":"mock_invest_001","source":"mock","platform":"telegram","modality":"text","language":"ru","combined_text":"Инвестиции с гарантированным доходом 300% за неделю! Без риска. Осталось 3 места — пишите в Telegram @invest_kz_promo","label":"scam","fraud_type":"investment_scam"}
```

```json
{"id":"mock_legit_001","source":"mock","platform":"web","modality":"text","language":"ru","combined_text":"Ставка по депозиту 16% годовых. Подробные условия — в отделении банка или на официальном сайте.","label":"legit","fraud_type":"legit_finance"}
```

Правила: `id` — уникальный с префиксом `mock_`; `combined_text` — сам текст; `entities`/`risk_signals`
можно не заполнять (система достанет сама), но `label` и `fraud_type` укажите как «эталон» для проверки.
Файл кладите в `data/processed/mock_demo.jsonl`.

### 5.3 Аудио
`.wav` (моно, 16 kHz желательно) или `.mp3`, 20–60 сек, речь на ru/kk. Сценарий звонка — по §4.
Источник звука: запись начитки, TTS — любой. Внутри **только маски** (никаких реальных кодов/карт).

### 5.4 Видео
`.mp4`, 10–60 сек, до ~60 МБ. Для deepfake-демо — в кадре должно быть **лицо** и звучать **голос**.
Для OCR-демо — на обложке/в кадре текст: промокод, домен, «гарантия дохода».

---

## 6. Как прогнать цикл (на презентации)

Система должна быть поднята (`make stack-docker`). Открываем фронт **http://localhost:3000/console**
и подаём кейсы по вкладкам (текст / ссылка / аудио / Shadow Graph). Либо через API (порт **8088**):

```bash
# текст
curl -X POST localhost:8088/analyze/text -H 'Content-Type: application/json' \
  -d '{"id":"demo1","text":"Гарантированный доход 300% за неделю, без риска! Пишите в Telegram @invest_kz_promo"}'

# ссылка (видео с OCR кадров + deepfake)
curl -X POST localhost:8088/analyze/url -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=XXXX","deep":true}'

# аудио / видео (файлом)
curl -X POST localhost:8088/analyze/audio -F file=@call_fake_bank.wav
curl -X POST localhost:8088/analyze/video -F file=@deepfake_promo.mp4
```

**Что показать в отчёте по каждому кейсу:**
1. `risk_score` + `risk_level` (low/medium/high/critical);
2. `fraud_type` и `triggered_signals` (какие сигналы и с каким весом сработали);
3. `entities` (домены, промокоды, Telegram-ники, маски телефонов);
4. для медиа — `media_anomalies` (deepfake/синтетический голос/lip-sync) и `transcript`/`ocr_text`;
5. **похожие кейсы** (Qdrant) и **повтор сущностей в графе** (Neo4j, вкладка Shadow Graph);
6. контраст: честный `legit_finance` и `ordinary_spam` НЕ улетают в critical.

История прогонов — вкладка «История/Статистика» (пишется в Postgres), смотреть данные напрямую можно
в Adminer/Neo4j/Qdrant (см. [services.md](services.md)).

---

## 7. Чек-лист сдачи (критерии приёмки)

- [ ] ≥ 10 текстовых кейсов, покрыты все требуемые `fraud_type` из §3 (включая 3 «честных»).
- [ ] 2 аудио-файла (fake_bank_call, fake_egov_delivery_call), внутри только маски.
- [ ] 1–2 видео (deepfake_financial_promo и/или казино-промо с текстом на кадре).
- [ ] 1–2 заранее проверенные URL (открываются без логина).
- [ ] Для каждого кейса в таблице указан **ожидаемый** `fraud_type` + `label` (эталон для сверки).
- [ ] Нет реальных карт/ИИН/SMS-кодов/телефонов/ФИО — всё маски/выдумка (§0).
- [ ] Есть scam, spam и legit — система показывает, что различает их.
- [ ] (бонус) `data/processed/mock_demo.jsonl` на 20–30 строк для «похожих кейсов» и графа.

Полный смысл словарей и пайплайна — в [services.md](services.md) и [pipeline.md](pipeline.md).
