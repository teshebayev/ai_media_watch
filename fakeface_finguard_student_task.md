# FakeFace FinGuard + Shadow Graph  
## Техническое задание для студентов по сбору данных, разметке и MVP

Версия: 1.0  
Язык проекта: русский / казахский / английский  
Цель: собрать учебный датасет и MVP-систему для выявления риск-сигналов в видео, постах и звонках: реклама азартных онлайн-игр, финансовые пирамиды, фишинг, fake eGov/КНБ-звонки, deepfake-реклама и связанные цифровые следы.

---

## 0. Важные правила безопасности

Студентам запрещено:

- парсить приватные Telegram-чаты;
- скачивать или распространять реальные утечки персональных данных;
- сохранять реальные номера карт, ИИН, SMS-коды, пароли, CVV, ЭЦП;
- использовать реальные записи звонков жертв без согласия;
- заходить в DarkNet и покупать/скачивать незаконные материалы;
- делать выводы вида “этот человек преступник”.

Разрешено:

- использовать открытые официальные предупреждения;
- использовать готовые публичные датасеты;
- использовать публичные видео/metadata в рамках правил платформ;
- создавать синтетические учебные звонки и посты;
- хранить только маскированные или хэшированные реквизиты;
- делать выводы только в формате risk scoring: `low / medium / high / critical`.

Правильная формулировка результата:

> Система не выносит юридическое обвинение. Она автоматически выявляет риск-сигналы, объясняет причины и передаёт материал на ручную проверку аналитика.

---

## 1. Концепт проекта

**FakeFace FinGuard** — мультимодальная аналитическая система, которая анализирует видео, аудио, посты и ссылки на признаки мошенничества.

**Shadow Graph Extension** — модуль, который строит граф цифровых следов: блогер → видео → сайт → промокод → Telegram → кошелёк → повторяющиеся связи.

---

## 2. Общая схема взаимодействия

```text
Пользователь / аналитик
  ↓
Загружает видео, аудиозвонок, пост или ссылку
  ↓
Media Agent
  - видео → аудио + кадры
  - аудио → transcript
  - кадры → OCR-текст
  ↓
Entity Extraction Agent
  - URL
  - домены
  - Telegram usernames
  - телефоны
  - промокоды
  - суммы
  - crypto-wallets
  - названия проектов
  ↓
Scenario Detection Agent
  - illegal_gambling_promo
  - fake_egov_call
  - fake_government_call
  - investment_scam
  - phishing
  - crypto_scam
  - deepfake_financial_promo
  ↓
OSINT / Reputation Agent
  - проверка домена
  - проверка URL
  - проверка проекта
  - повторяемость Telegram / домена / промокода
  ↓
Shadow Graph
  - nodes
  - edges
  - clusters
  ↓
Risk Engine
  - risk_score
  - risk_level
  ↓
Analyst Report
  - evidence
  - detected entities
  - triggered signals
  - recommendation
```

---

## 3. Основные источники и ссылки

### 3.1. Официальные источники Казахстана

| Источник | Для чего использовать | Ссылка |
|---|---|---|
| Stop-Piramida.kz | Таксономия мошеннических схем, признаки пирамид, фишинга, дропперства, лжепродавцов и т.д. | https://stop-piramida.kz/ |
| Методика Stop-Piramida | Правила и признаки риск-категорий | https://stop-piramida.kz/metodika-opredeleniya-priznakov |
| Проверка проектов Stop-Piramida | Примеры проектов с признаками риска | https://stop-piramida.kz/proverit-riski |
| eGov — что делать, если позвонили мошенники | Сценарии телефонного мошенничества, SMS-коды, кредиты, удалённый доступ | https://egov.kz/cms/ru/articles/legal_relations/pass_scammers |
| eGov — персональные данные | Почему нельзя сообщать SMS-коды, ЭЦП, данные карт | https://egov.kz/cms/ru/articles/communications/personaldata |
| Нацбанк — схема eGov/доставка/КНБ/безопасный счёт | Актуальный сценарий многоэтапного телефонного мошенничества | https://nationalbank.kz/ru/news/informacionnye-soobshcheniya/19505 |
| Нацбанк — Антифрод-центр не звонит гражданам | Проверка легенды мошенников “мы из Антифрод-центра” | https://nationalbank.kz/ru/news/informacionnye-soobshcheniya/16901 |
| АФМ — блогеры и онлайн-казино | Кейс рекламы азартных онлайн-игр блогерами | https://www.gov.kz/memleket/entities/afm/press/news/details/1058244?lang=ru |

### 3.2. Платформы и технические API

| Источник | Для чего использовать | Ссылка |
|---|---|---|
| YouTube Data API `search.list` | Поиск видео по ключевым словам | https://developers.google.com/youtube/v3/docs/search/list |
| YouTube quota calculator | Понимание лимитов API | https://developers.google.com/youtube/v3/determine_quota_cost |
| Whisper | ASR: аудио → текст | https://github.com/openai/whisper |
| PaddleOCR | OCR: изображение/кадр → текст | https://github.com/PaddlePaddle/PaddleOCR |
| PhishTank API | Проверка фишинговых URL | https://phishtank.net/api_info.php |
| PhishTank developer info | Требования к User-Agent и API | https://www.phishtank.net/developer_info.php |

### 3.3. Готовые датасеты

| Датасет | Для чего использовать | Ссылка |
|---|---|---|
| ScamSpot | Финансовые scam/spam комментарии Instagram | https://scamspot.github.io/ |
| ScamSpot paper | Описание системы и подхода | https://aclanthology.org/2024.eacl-demo.9/ |
| Telegram Spam or Ham | Telegram spam/ham baseline | https://www.kaggle.com/datasets/mexwell/telegram-spam-or-ham |
| ealvaradob/phishing-dataset | Phishing/legitimate URL и HTML | https://huggingface.co/datasets/ealvaradob/phishing-dataset |
| CryptoScamDB | Crypto scam URL / адреса | https://cryptoscamdb.org/ |
| Chainabuse | Публичные crypto scam reports | https://www.chainabuse.com/ |
| FaceForensics++ | Deepfake video detection examples | https://github.com/ondyari/faceforensics |
| DFDC | Большой deepfake video dataset | https://ai.meta.com/datasets/dfdc/ |
| FakeAVCeleb | Multimodal deepfake: video + cloned audio | https://github.com/DASH-Lab/FakeAVCeleb |

---

## 4. Кейсы проекта

Проект делится на кейсы. Каждый кейс должен иметь:

- описание сценария;
- источники данных;
- способ сбора;
- ключевые слова;
- поля датасета;
- правила разметки;
- risk-signals;
- пример JSON.

---

# Кейс 1. Блогер рекламирует азартные онлайн-игры

## 1.1. Сценарий

Блогер публикует видео:

```text
“Регистрируйся по ссылке, вводи промокод, получай бонус.
Я сам поднял 500 000 ₸. Вывод работает.”
```

На видео могут быть:

- сайт казино;
- промокод;
- QR-код;
- Telegram-канал;
- скрин “выигрыша”;
- инструкция по регистрации;
- призыв пополнить депозит.

## 1.2. Что должна сделать система

```text
Видео блогера
  ↓
Извлечь аудио
  ↓
Whisper → transcript
  ↓
Разбить видео на кадры
  ↓
PaddleOCR → текст с кадров
  ↓
Entity extraction:
  - casino domain
  - promo code
  - Telegram username
  - money amounts
  - call-to-action phrases
  ↓
Scenario detection:
  illegal_gambling_promo
  ↓
Shadow Graph:
  blogger → video → casino_domain → promo_code → telegram
  ↓
Risk report
```

## 1.3. Как собрать датасет

### Способ A — YouTube Data API

Использовать `search.list`.

Сохранять:

```csv
source,platform,query,video_id,url,title,description,channel_title,published_at,thumbnail_url
```

Поисковые запросы:

```text
онлайн казино промокод
казино бонус промокод
слоты промокод
выигрыш казино промокод
депозит бонус казино
вывод денег казино
ставки промокод
казино ссылка в описании
заработок казино
```

### Способ B — ручной сбор

Если API не успели подключить:

1. Найти 10–20 публичных видео вручную.
2. Сохранить URL, title, description.
3. Вручную записать, что видно на экране: сайт, промокод, Telegram.
4. Для демо можно сделать 5 синтетических учебных роликов.

## 1.4. Risk-signals

```text
illegal_gambling_promo
casino_domain_found
promo_code_found
deposit_bonus
registration_instruction
fake_winner_claim
easy_money_claim
telegram_contact
financial_call_to_action
```

## 1.5. Разметка

| Поле | Значение |
|---|---|
| `label` | `scam` / `spam` / `legit` / `unclear` |
| `fraud_type` | `illegal_gambling_promo` |
| `risk_level` | `medium` / `high` / `critical` |
| `evidence_spans` | конкретные фразы: “вводи промокод”, “получи бонус”, “выводи деньги” |

## 1.6. Пример JSON

```json
{
  "id": "gambling_video_001",
  "source": "youtube_api",
  "platform": "youtube",
  "modality": "video",
  "case_type": "illegal_gambling_promo",
  "url": "https://youtube.com/watch?v=demo",
  "title": "Бонус по промокоду",
  "description": "Ссылка в описании",
  "transcript": "Регистрируйся и получи бонус...",
  "ocr_text": "PROMO777 casino-example.com",
  "combined_text": "Регистрируйся... PROMO777 casino-example.com",
  "entities": {
    "urls": ["https://casino-example.com"],
    "domains": ["casino-example.com"],
    "telegram_usernames": ["@casino_manager"],
    "promo_codes": ["PROMO777"],
    "money_amounts": ["500 000 ₸"]
  },
  "risk_signals": [
    "illegal_gambling_promo",
    "promo_code_found",
    "casino_domain_found",
    "financial_call_to_action"
  ],
  "evidence_spans": [
    "получи бонус",
    "введи промокод",
    "ссылка в описании"
  ],
  "label": "scam",
  "fraud_type": "illegal_gambling_promo",
  "risk_level": "high",
  "risk_score": 82
}
```

---

# Кейс 2. Звонок: eGov / доставка / SMS-код / КНБ

## 2.1. Сценарий

Мошенники звонят и говорят:

```text
“Вам пришла доставка от госоргана/eGov.
Чтобы получить, скажите код из SMS.”
```

После передачи кода начинается второй этап:

```text
“Мы сотрудники КНБ / полиции / службы безопасности.
Ваши данные скомпрометированы.
На вас оформляют кредит.
Мы поможем защитить деньги.
Не кладите трубку, никому не говорите.
Переведите деньги на безопасный счёт.”
```

## 2.2. Что должна сделать система

```text
Аудиозвонок
  ↓
Whisper → transcript
  ↓
Разделение на этапы:
  1. eGov/доставка
  2. SMS-код
  3. КНБ/полиция/Нацбанк
  4. кредит/угроза
  5. безопасный счёт/перевод
  ↓
Entity extraction:
  - claimed organization
  - requested secret
  - pressure phrase
  - financial action
  ↓
Scenario detection:
  fake_egov_delivery_call
  fake_government_escalation
  safe_account_fraud
  ↓
Risk report
```

## 2.3. Как собрать датасет

Реальные записи звонков не используем.

### Способ A — синтетические звонки

1. Взять официальный сценарий из предупреждений eGov / Нацбанка.
2. Написать 30–50 коротких диалогов.
3. Озвучить добровольцами или TTS.
4. Сохранить `.wav`.
5. Прогнать через Whisper.
6. Разметить transcript.

### Способ B — текстовые сценарии

Если нет времени на аудио:

1. Подготовить 50 текстовых сценариев.
2. Разметить как `text`.
3. Позже добавить аудио.

## 2.4. Ключевые слова

```text
доставка от eGov
доставка от госоргана
код из SMS
код 1414
сотрудник КНБ
сотрудник полиции
сотрудник Нацбанка
служба безопасности
на вас оформляют кредит
подозрительная операция
безопасный счёт
страховой счёт
не кладите трубку
никому не говорите
спецоперация
удалённый доступ
AnyDesk
TeamViewer
RustDesk
```

Казахские варианты:

```text
қауіпсіз шот
несие рәсімделді
банк қызметкері
полиция қызметкері
ұлттық банк
SMS кодын айтыңыз
қосымшаны орнатыңыз
ешкімге айтпаңыз
шұғыл
```

## 2.5. Risk-signals

```text
fake_egov_call
sms_code_request
egov_1414_code
fake_government_employee
fake_authority
loan_fear
safe_account
do_not_tell_anyone
psychological_pressure
remote_access_request
```

## 2.6. Пример JSON

```json
{
  "id": "kz_call_001",
  "source": "synthetic_based_on_official_warning",
  "platform": "phone",
  "modality": "audio",
  "case_type": "fake_egov_delivery_call",
  "language": "ru",
  "transcript": "Здравствуйте, вам пришла доставка от eGov. Назовите код из SMS. Теперь с вами говорит сотрудник КНБ...",
  "combined_text": "Здравствуйте, вам пришла доставка от eGov. Назовите код из SMS. Теперь с вами говорит сотрудник КНБ...",
  "entities": {
    "organizations": ["eGov", "КНБ"],
    "requested_secrets": ["SMS-код"],
    "financial_actions": ["перевод на безопасный счёт"]
  },
  "risk_signals": [
    "fake_egov_call",
    "sms_code_request",
    "fake_government_employee",
    "safe_account",
    "do_not_tell_anyone"
  ],
  "evidence_spans": [
    "назовите код из SMS",
    "сотрудник КНБ",
    "безопасный счёт",
    "никому не говорите"
  ],
  "label": "scam",
  "fraud_type": "fake_egov_delivery_call",
  "risk_level": "critical",
  "risk_score": 95
}
```

---

# Кейс 3. Финансовая пирамида / быстрый доход

## 3.1. Сценарий

```text
“Инвестируй 10 000 ₸ и получай 20% в неделю.
Пригласи друзей и повышай уровень.
Чем больше команда, тем выше доход.”
```

## 3.2. Что искать

```text
гарантированный доход
доход без риска
доход 20% в неделю
пассивный доход
инвестиции от 10000
реферальный доход
пригласи друга
команда
уровень
пакет
статус
быстрый заработок
```

## 3.3. Как собрать датасет

| Метод | Что делать |
|---|---|
| Готовый датасет | ScamSpot |
| Telegram | Telegram Spam or Ham + ручная фильтрация финансовых примеров |
| Ручной сбор | 50 примеров постов/видео |
| Синтетика | 30 fake-постов + 30 legit-финансовых постов |

## 3.4. Risk-signals

```text
guaranteed_income
unrealistic_profit
no_risk_claim
referral_scheme
telegram_contact
direct_message_request
financial_call_to_action
```

---

# Кейс 4. Фейковая инвестиционная платформа / крипта

## 4.1. Сценарий

```text
“Вложи в майнинг / крипту / цифровой актив.
Минимальный депозит 50 000 ₸.
Менеджер поможет вывести прибыль.”
```

## 4.2. Что искать

```text
крипта доход
заработок USDT
майнинг инвестиции
арбитраж крипты
связки арбитраж
трейдинг без риска
USDT депозит
бот для арбитража
менеджер поможет вывести
```

## 4.3. Как собрать датасет

| Метод | Что делать |
|---|---|
| CryptoScamDB | Взять примеры crypto scam URL |
| Chainabuse | Проверить примеры reported wallet/URL |
| YouTube/Telegram | Искать посты про USDT/майнинг/арбитраж |
| Синтетика | Создать 30 учебных fake landing descriptions |

## 4.4. Risk-signals

```text
crypto_payment
crypto_wallet_found
guaranteed_income
unknown_investment_platform
telegram_contact
suspicious_domain
financial_call_to_action
```

---

# Кейс 5. Фишинг / fake login / SMS-коды

## 5.1. Сценарий

```text
“Ваш аккаунт заблокирован.
Перейдите по ссылке и подтвердите данные.
Введите карту и SMS-код.”
```

## 5.2. Что искать

```text
подтвердите аккаунт
аккаунт заблокирован
введите код
SMS-код
код 1414
подтвердите карту
получить выплату
компенсация
штраф
egov
kaspi
halyk
```

## 5.3. Как собрать датасет

| Метод | Что делать |
|---|---|
| ealvaradob/phishing-dataset | Использовать phishing/legit examples |
| PhishTank | Проверять URL через API |
| Синтетика | Написать fake SMS / fake Telegram messages |
| Ручной сбор | Только warning-публикации, не переходить на опасные сайты |

## 5.4. Risk-signals

```text
phishing_url
suspicious_domain
sms_code_request
card_data_request
personal_data_request
egov_1414_code
digital_signature_request
```

---

# Кейс 6. Дропперство / карты / платежи на третьих лиц

## 6.1. Сценарий

```text
“Нужны карты для переводов.
Оплата каждый день.
Просто принимай деньги и переводи дальше.”
```

Или:

```text
“Пополните депозит переводом на карту физлица.
Если не проходит — дадим другую карту.”
```

## 6.2. Что искать

```text
дроп
дроппер
карта для переводов
принимать платежи
P2P
перевод на физлицо
пополнение через карту
новые реквизиты
счёт третьего лица
```

## 6.3. Как собрать датасет

| Метод | Что делать |
|---|---|
| Синтетика | 30–50 примеров без реальных карт |
| Telegram demo | Только свои/открытые тестовые каналы |
| Stop-Piramida | Использовать как описание признаков |
| Shadow Graph | Сохранять только маску/хэш реквизитов |

## 6.4. Важно

Нельзя хранить реальные карты и телефоны.

Правильно:

```json
{
  "card_mask": "4400****1234",
  "phone_hash": "sha256_hash_here"
}
```

## 6.5. Risk-signals

```text
money_mule_request
third_party_payment
p2p_payment
frequent_requisites_change
card_data_found
phone_found
```

---

# Кейс 7. Лжепродавцы / недоставка товара

## 7.1. Сценарий

```text
“Оплатите сейчас, доставка завтра.
Возврата нет.
После оплаты продавец пропадает.”
```

## 7.2. Что искать

```text
только предоплата
без возврата
доставка после оплаты
скидка только сегодня
оплата на карту
нет самовывоза
```

## 7.3. Как собрать датасет

| Метод | Что делать |
|---|---|
| Синтетика | 30 fake объявлений |
| Ручной сбор | Только открытые примеры без персональных данных |
| Stop-Piramida | Использовать признаки лжепродавцов |
| Разметка | `fake_seller`, `high_risk_seller`, `legit_seller` |

## 7.4. Risk-signals

```text
only_prepayment
no_return_policy
third_party_payment
no_merchant_identity
urgency
suspicious_discount
```

---

# Кейс 8. Лжекредиты / кредитное давление

## 8.1. Сценарий

```text
“На вас оформляют кредит.
Чтобы отменить операцию, нужно подтвердить личность.
Назовите код / установите приложение / переведите деньги.”
```

Или:

```text
“Поможем получить кредит без проверки.
Нужна предоплата за страховку.”
```

## 8.2. Что искать

```text
на вас оформляют кредит
отменить кредит
страховка
кредитная история
проверка личности
код из SMS
удалённый доступ
предоплата за кредит
```

## 8.3. Как собрать датасет

| Метод | Что делать |
|---|---|
| Синтетика | 30 call scripts |
| Ручной сбор | 20 warning-постов |
| ASR | Озвучить и прогнать через Whisper |
| Разметка | `fake_credit`, `fake_bank_call` |

## 8.4. Risk-signals

```text
loan_fear
fake_bank_employee
sms_code_request
remote_access_request
safe_account
advance_fee
```

---

# Кейс 9. Deepfake-реклама инвестиций / казино / фондов

## 9.1. Сценарий

Видео, где “известный человек” якобы говорит:

```text
“Я инвестировал в эту платформу.
Переходите по ссылке и получите доход.”
```

Или голос/лицо выглядят синтетически.

## 9.2. Что должна сделать система

```text
Видео
  ↓
Face detection
  ↓
Voice extraction
  ↓
Lip-sync/anomaly check
  ↓
ASR/OCR:
  - что рекламируется?
  - есть ли финансовый призыв?
  ↓
Entity extraction:
  - сайт
  - Telegram
  - проект
  ↓
FakeFace score + Fraud score
  ↓
Risk report
```

## 9.3. Как собрать датасет

| Метод | Что делать |
|---|---|
| FaceForensics++ | Взять примеры real/fake video |
| DFDC | Взять небольшую выборку для demo |
| FakeAVCeleb | Взять audio-video multimodal examples |
| Синтетика | Сделать учебные видео без реальных публичных лиц |
| Ручная разметка | 20 real / 20 fake examples |

## 9.4. Risk-signals

```text
possible_deepfake
synthetic_voice_suspected
lip_sync_anomaly
financial_call_to_action
unknown_investment_platform
telegram_contact
casino_domain_found
```

---

## 5. Единая структура итогового датасета

Все студенты должны привести свои данные к одному формату.

Файл:

```text
data/processed/ai_media_watch_dataset.jsonl
```

Одна строка JSONL:

```json
{
  "id": "case_0001",
  "source": "youtube_api / telegram_export / synthetic_call / manual_demo / ready_dataset",
  "platform": "youtube / telegram / phone / website / dataset",
  "modality": "video / audio / text / url / image",
  "case_type": "illegal_gambling_promo",
  "language": "ru",
  "url": "https://...",
  "title": "Бонус по промокоду",
  "description": "Ссылка в описании",
  "transcript": "Регистрируйся и получи бонус...",
  "ocr_text": "PROMO777 casino-example.com",
  "combined_text": "Регистрируйся... PROMO777 casino-example.com",
  "entities": {
    "urls": ["https://casino-example.com"],
    "domains": ["casino-example.com"],
    "telegram_usernames": ["@casino_manager"],
    "phones": [],
    "promo_codes": ["PROMO777"],
    "crypto_wallets": [],
    "money_amounts": ["500 000 ₸"],
    "organizations": []
  },
  "media_anomalies": {
    "has_face": true,
    "possible_deepfake": false,
    "synthetic_voice_suspected": false,
    "lip_sync_anomaly": false
  },
  "risk_signals": [
    "illegal_gambling_promo",
    "promo_code_found",
    "casino_domain_found",
    "financial_call_to_action"
  ],
  "evidence_spans": [
    "получи бонус",
    "введи промокод",
    "ссылка в описании"
  ],
  "label": "scam",
  "fraud_type": "illegal_gambling_promo",
  "risk_level": "high",
  "risk_score": 82,
  "annotator": "student_01",
  "review_status": "approved"
}
```

---

## 6. Основные labels

| label | Когда ставить |
|---|---|
| `legit` | Нормальный контент, официальное предупреждение, образовательное видео |
| `spam` | Массовая реклама без явного мошенничества |
| `scam` | Есть признаки обмана, давления, фишинга, пирамиды, fake authority |
| `unclear` | Недостаточно данных, нужна ручная проверка |

---

## 7. fraud_type

```text
illegal_gambling_promo
fake_egov_delivery_call
fake_bank_call
fake_government_call
investment_scam
crypto_scam
phishing
money_mule_or_drop
fake_seller
fake_credit
deepfake_financial_promo
legit_finance
anti_fraud_education
ordinary_spam
```

---

## 8. risk_level

| risk_level | Правило |
|---|---|
| `low` | 1 слабый сигнал, нет денег/ссылки/контакта |
| `medium` | 2–3 сигнала, есть контакт или ссылка |
| `high` | Деньги + давление + контакт/ссылка |
| `critical` | SMS-код, ЭЦП, удалённый доступ, “безопасный счёт”, crypto transfer, deepfake + финансовый призыв |

---

## 9. Полный список risk_signals

```text
guaranteed_income
unrealistic_profit
no_risk_claim
urgency
limited_slots
telegram_contact
whatsapp_contact
direct_message_request
referral_scheme
crypto_payment
crypto_wallet_found
phishing_url
suspicious_domain
fake_authority
fake_bank_employee
fake_government_employee
fake_egov_call
safe_account
sms_code_request
remote_access_request
do_not_tell_anyone
loan_fear
account_blocking_fear
personal_data_request
card_data_request
egov_1414_code
digital_signature_request
possible_deepfake
synthetic_voice_suspected
lip_sync_anomaly
financial_call_to_action
illegal_gambling_promo
casino_domain_found
promo_code_found
deposit_bonus
registration_instruction
fake_winner_claim
money_mule_request
third_party_payment
p2p_payment
frequent_requisites_change
only_prepayment
no_return_policy
no_merchant_identity
advance_fee
```

---

## 10. Regex для извлечения сущностей

### Telegram username

```regex
@[A-Za-z0-9_]{5,32}
```

### URL

```regex
https?:\/\/[^\s]+|www\.[^\s]+
```

### Телефон Казахстан

```regex
(\+7|8)\s?\(?7\d{2}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}
```

### Суммы

```regex
\d[\d\s]{2,}\s?(₸|тг|тенге|KZT|USDT|\$)
```

### Promo code

```regex
(?i)(промокод|promo|код)\s*[:\-]?\s*([A-Z0-9]{4,20})
```

### Crypto keywords

```regex
USDT|BTC|ETH|TRC20|ERC20|BEP20|крипта|биткоин|эфир|майнинг
```

### BTC address

```regex
\b(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b
```

### Ethereum address

```regex
0x[a-fA-F0-9]{40}
```

---

## 11. Risk scoring

Простая формула MVP:

```text
risk_score =
  text_signal_score
+ entity_score
+ media_anomaly_score
+ osint_score
+ graph_score
```

Баллы:

| Сигнал | Баллы |
|---|---:|
| `casino_domain_found` | +25 |
| `promo_code_found` | +20 |
| `registration_instruction` | +20 |
| `fake_winner_claim` | +20 |
| `sms_code_request` | +45 |
| `fake_government_employee` | +30 |
| `safe_account` | +45 |
| `do_not_tell_anyone` | +30 |
| `remote_access_request` | +45 |
| `guaranteed_income` | +25 |
| `referral_scheme` | +25 |
| `phishing_url` | +40 |
| `crypto_wallet_found` | +20 |
| `possible_deepfake` | +25 |
| `synthetic_voice_suspected` | +25 |
| `lip_sync_anomaly` | +20 |
| `graph_entity_reuse` | +25 |

Порог:

```text
0–24      low
25–49     medium
50–79     high
80–100    critical
```

Если сумма больше 100, обрезаем до 100.

---

## 12. Shadow Graph

### 12.1. Узлы

```text
(:Video)
(:Post)
(:Call)
(:Account)
(:Blogger)
(:TelegramUsername)
(:PhoneHash)
(:Wallet)
(:URL)
(:Domain)
(:PromoCode)
(:Organization)
(:RiskSignal)
(:DatasetSource)
```

### 12.2. Связи

```text
(:Blogger)-[:PUBLISHED]->(:Video)
(:Video)-[:MENTIONS]->(:Domain)
(:Video)-[:MENTIONS]->(:TelegramUsername)
(:Video)-[:HAS_PROMO]->(:PromoCode)
(:Video)-[:HAS_SIGNAL]->(:RiskSignal)

(:Call)-[:CLAIMS_AUTHORITY]->(:Organization)
(:Call)-[:REQUESTS]->(:Secret)
(:Call)-[:HAS_SIGNAL]->(:RiskSignal)

(:Post)-[:MENTIONS]->(:URL)
(:URL)-[:HAS_DOMAIN]->(:Domain)
(:Wallet)-[:REPORTED_IN]->(:ThreatIntel)
```

### 12.3. Что должен уметь граф

```text
1. Найти один и тот же домен в разных видео.
2. Найти один Telegram-ник в разных постах.
3. Найти один промокод у разных блогеров.
4. Найти один кошелёк в разных источниках.
5. Показать кластер:
   блогер → видео → сайт → Telegram → risk_signal
```

---

## 13. Распределение студентов

| Студент | Зона | Что делает | Итоговые файлы |
|---|---|---|---|
| Студент 1 | YouTube / Shorts | Собирает metadata видео по gambling/investment/crypto запросам | `youtube_candidates.csv`, `youtube_candidates_clean.jsonl` |
| Студент 2 | Telegram / posts | Собирает Telegram export или готовый Telegram dataset | `telegram_messages.jsonl` |
| Студент 3 | Ready datasets | ScamSpot, phishing, CryptoScamDB, Telegram Spam | `ready_dataset_examples.jsonl`, `dataset_examples.md` |
| Студент 4 | ASR/OCR | Whisper transcript, OCR кадров, объединение текста | `audio_transcripts.jsonl`, `video_ocr.jsonl` |
| Студент 5 | KZ calls | Синтетические звонки eGov/КНБ/банк | `kz_call_scripts.csv`, `kz_call_transcripts.jsonl` |
| Студент 6 | FakeFace | Deepfake/video/voice anomaly fields | `deepfake_examples.jsonl`, `fakeface_findings.md` |
| Студент 7 | Entity + Risk | Regex extraction, risk_signals, scoring | `entities_extracted.jsonl`, `risk_engine.py` |
| Студент 8 | Shadow Graph + UI | Nodes/edges, graph demo, dashboard | `entities_nodes.csv`, `entities_edges.csv`, `streamlit_app.py` |

---

## 14. Deliverables от каждого студента

Каждый студент должен сдать:

```text
1. Сырой файл в data/raw/
2. Обработанный файл в data/processed/
3. Короткое описание в docs/
4. Минимум 20 размеченных примеров
5. Список проблем/ограничений
```

---

## 15. Минимальный объём данных

Для MVP достаточно:

| Тип | Количество |
|---|---:|
| Видео/посты про онлайн-казино | 20 |
| Синтетические звонки eGov/КНБ/банк | 30 |
| Финансовые пирамиды / investment scam | 40 |
| Phishing examples | 30 |
| Crypto scam examples | 20 |
| Deepfake/fakeface examples | 20 |
| Legit / anti-fraud education | 40 |

Итого:

```text
200 размеченных примеров достаточно для хакатона.
```

---

## 16. Структура проекта

```text
fakeface-finguard/
│
├── data/
│   ├── raw/
│   │   ├── youtube/
│   │   ├── telegram/
│   │   ├── scamspot/
│   │   ├── phishing/
│   │   ├── crypto/
│   │   ├── deepfake/
│   │   └── kz_calls/
│   │
│   ├── processed/
│   │   ├── youtube_candidates_clean.jsonl
│   │   ├── telegram_messages.jsonl
│   │   ├── ready_dataset_examples.jsonl
│   │   ├── deepfake_examples.jsonl
│   │   ├── kz_call_transcripts.jsonl
│   │   ├── ai_media_watch_dataset.jsonl
│   │   ├── entities_nodes.csv
│   │   └── entities_edges.csv
│
├── src/
│   ├── parsers/
│   │   ├── parse_youtube.py
│   │   ├── parse_telegram_export.py
│   │   ├── parse_ready_datasets.py
│   │   └── parse_kz_calls.py
│   │
│   ├── media/
│   │   ├── asr_whisper.py
│   │   ├── ocr_paddle.py
│   │   └── fakeface_detector_stub.py
│   │
│   ├── extraction/
│   │   ├── regex_extractors.py
│   │   └── signal_extractor.py
│   │
│   ├── risk/
│   │   └── risk_engine.py
│   │
│   ├── graph/
│   │   ├── graph_schema.cypher
│   │   └── build_graph.py
│   │
│   └── app/
│       └── streamlit_app.py
│
├── docs/
│   ├── annotation_guideline.md
│   ├── dataset_sources.md
│   ├── youtube_search_queries.md
│   ├── kz_call_scenarios.md
│   ├── fakeface_findings.md
│   └── shadow_graph_demo.md
│
└── README.md
```

---

## 17. План на хакатон

### Первые 2 часа

```text
1. Создать repo.
2. Создать структуру папок.
3. Раздать роли.
4. Согласовать JSONL-схему.
5. Согласовать список risk_signals.
```

### Часы 2–6

```text
Студент 1: YouTube metadata.
Студент 2: Telegram / posts.
Студент 3: ready datasets.
Студент 4: ASR/OCR.
Студент 5: KZ synthetic calls.
Студент 6: FakeFace examples.
Студент 7: entity extraction.
Студент 8: graph schema.
```

### Часы 6–10

```text
1. Объединить всё в unified JSONL.
2. Разметить минимум 200 примеров.
3. Подключить regex extraction.
4. Подключить risk scoring.
5. Сделать первый UI.
```

### Часы 10–24

```text
1. Подготовить 2–3 demo scenarios.
2. Показать video → transcript/OCR → entities → risk.
3. Показать call → transcript → scam stage detection.
4. Показать Shadow Graph.
5. Подготовить презентацию.
```

---

## 18. Демо-сценарии для защиты

### Демо 1 — блогер рекламирует онлайн-казино

```text
Загружаем видео
  ↓
Whisper достаёт речь
  ↓
OCR находит промокод и сайт
  ↓
Entity Agent извлекает domain, promo_code, Telegram
  ↓
Risk Engine ставит HIGH/CRITICAL
  ↓
Shadow Graph показывает:
  blogger → video → casino domain → promo code
```

### Демо 2 — звонок eGov → КНБ → безопасный счёт

```text
Загружаем аудио
  ↓
Whisper делает transcript
  ↓
Scenario Agent делит звонок на этапы:
  доставка/eGov → SMS-код → КНБ → кредит → безопасный счёт
  ↓
Risk Engine находит:
  sms_code_request
  fake_authority
  safe_account
  do_not_tell_anyone
  ↓
Risk level: critical
```

### Демо 3 — deepfake financial promo

```text
Загружаем видео
  ↓
FakeFace Agent ставит possible_deepfake
  ↓
ASR/OCR находит финансовый призыв
  ↓
Entity Agent находит сайт/Telegram
  ↓
Risk Engine:
  possible_deepfake + financial_call_to_action = high/critical
```

---

## 19. Итоговая формулировка проекта

**FakeFace FinGuard** — это мультимодальная аналитическая платформа для выявления риск-сигналов в видео, постах и звонках: реклама нелегальных азартных онлайн-игр, финансовые пирамиды, фишинг, fake eGov/КНБ-звонки, deepfake-реклама и связанные цифровые следы.

Система работает как аналитический фильтр:

```text
контент
→ ASR/OCR
→ сущности
→ риск-сигналы
→ Shadow Graph
→ explainable risk report
```

Главная ценность проекта:

```text
Не просто “AI сказал scam”,
а объяснимая цепочка доказательств:
видео → сайт → промокод → Telegram → повторяемость → высокий риск.
```
