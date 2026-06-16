"""Проверка ЖИВОГО LLM-слоя через пайплайн: /analyze/text с ENABLE_LLM=true против vLLM.

Сам определяет имя модели из /v1/models (чтобы запрос совпадал с тем, что отдаёт vLLM).
Запуск (когда vLLM поднят на :8100):
    PYTHONPATH=. .venv/bin/python scripts/test_llm_pipeline.py
"""

import os

import httpx

BASE = os.getenv("LLM_BASE_URL", "http://localhost:8100/v1")
model_id = httpx.get(f"{BASE}/models", timeout=10).json()["data"][0]["id"]
print(f"vLLM модель: {model_id}\n")

# env до импорта backend (get_settings кешируется)
os.environ.update({
    "ENABLE_LLM": "true", "LLM_BASE_URL": BASE, "LLM_MODEL": model_id,
    "ENABLE_SIMILARITY": "true", "ENABLE_GRAPH": "true",
    "QDRANT_URL": os.getenv("QDRANT_URL", "http://localhost:6333"),
    "NEO4J_URI": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    "NEO4J_USER": "neo4j", "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD", "finguard_pass"),
})

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402

EXAMPLES = [
    ("казино/ru", "Регистрируйся на casino-x.com промокод PROMO777, бонус на депозит! Я поднял 500 000 ₸, вывод работает. Пиши @bonus_manager"),
    ("eGov-звонок/ru", "Здравствуйте, вам доставка от eGov. Назовите код из SMS. Теперь с вами сотрудник КНБ, на вас оформляют кредит, переведите деньги на безопасный счёт, никому не говорите."),
    ("eGov-звонок/kk", "Сәлеметсіз бе, сізге eGov жеткізілімі келді. SMS кодын айтыңыз. Ұлттық банк қызметкері, ақшаны қауіпсіз шотқа аударыңыз, ешкімге айтпаңыз."),
    ("пирамида/ru", "Инвестируй 10 000 ₸ и получай 20% в неделю. Пригласи друзей, повышай уровень. Пиши @invest_guru_kz"),
    ("фишинг/ru", "Ваш аккаунт заблокирован. Перейдите на kaspi-bonus.click и подтвердите данные карты и код из SMS."),
    ("deepfake-промо/ru", "Известный банкир рассказал, как он инвестировал в эту платформу. Переходите по ссылке invest-pro.top и получите гарантированный доход."),
    ("legit/ru", "Депозит в Halyk Bank под 14% годовых, страхование вкладов до 20 млн ₸. Оформление в приложении."),
]

with TestClient(app) as c:
    h = c.get("/health").json()
    print("health:", h, "\n")
    for tag, text in EXAMPLES:
        r = c.post("/analyze/text", json={"id": f"llm_{tag}", "text": text}).json()
        sigs = [s["signal"] for s in r["triggered_signals"]]
        print(f"[{tag}]")
        print(f"   fraud_type : {r.get('fraud_type')}")
        print(f"   risk       : {r['risk_level']} ({r['risk_score']})")
        print(f"   signals    : {sigs}")
        print(f"   evidence   : {r.get('evidence_spans')}")
        print()
print("LLM_PIPELINE_OK")
