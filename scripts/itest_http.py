"""Проверка HTTP-слоя (роутеры + CORS) в процессе через TestClient — без привязки
к порту (раннер песочницы убивает сетевые серверы). Прогоняет реальный ASGI-app и
lifespan против Qdrant/Neo4j на localhost. Это то, что дёргает фронт frontend/index.html.
"""

from fastapi.testclient import TestClient

from backend.app.main import app

with TestClient(app) as c:
    print("### /health");             print(" ", c.get("/health").json())

    r = c.post("/analyze/text", json={"id": "ui",
        "text": "Регистрируйся на casino-x.com промокод PROMO777, бонус! Пиши @bonus_manager"})
    j = r.json()
    print("### POST /analyze/text →", r.status_code)
    print("  risk:", j["risk_level"], j["risk_score"], "| domains:", j["entities"]["domains"])
    print("  signals:", [s["signal"] for s in j["triggered_signals"]])

    pre = c.options("/analyze/text", headers={
        "Origin": "http://localhost:8090", "Access-Control-Request-Method": "POST"})
    print("### CORS preflight →", pre.status_code,
          "| allow-origin:", pre.headers.get("access-control-allow-origin"))

    print("### GET /graph/entity/casino-x.com →", c.get("/graph/entity/casino-x.com").json())

    s = c.get("/search/similar", params={"text": "инвестиции доход в неделю", "limit": 3}).json()
    print("### GET /search/similar → similar_to_known_scam:", s["similar_to_known_scam"],
          "| neighbors:", len(s["neighbors"]))

print("\nHTTP_OK")
