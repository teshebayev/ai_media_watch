"""Streamlit-демо (Студент 8, ТЗ §13, план этап 7).

Ходит в FastAPI: ввод текста/файла → отчёт Risk Engine + сигналы + сущности.
Запуск (когда backend поднят):
    API_URL=http://localhost:8080 streamlit run src/app/streamlit_app.py
"""

from __future__ import annotations

import os

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8080")

LEVEL_COLOR = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}

st.set_page_config(page_title="FakeFace FinGuard", page_icon="🛡️")
st.title("🛡️ FakeFace FinGuard")
st.caption(
    "Система выявляет риск-сигналы и передаёт материал на ручную проверку аналитика. "
    "Она не выносит юридическое обвинение."
)

tab_text, tab_graph = st.tabs(["Анализ текста", "Граф / повторяемость"])

with tab_text:
    text = st.text_area("Текст поста / транскрипт звонка / описание видео", height=180)
    if st.button("Анализировать", type="primary") and text.strip():
        with st.spinner("Анализ..."):
            r = httpx.post(
                f"{API_URL}/analyze/text",
                json={"id": "demo_ui", "text": text},
                timeout=60,
            )
        if r.status_code == 200:
            rep = r.json()
            lvl = rep["risk_level"]
            st.metric("Risk score", rep["risk_score"], help=f"уровень: {lvl}")
            st.subheader(f"{LEVEL_COLOR.get(lvl, '')} risk_level: {lvl}")
            if rep.get("fraud_type"):
                st.write(f"**fraud_type:** `{rep['fraud_type']}`")
            st.write("**Сработавшие сигналы:**")
            for s in rep["triggered_signals"]:
                st.write(f"- `{s['signal']}` (+{s['weight']})")
            with st.expander("Сущности"):
                st.json(rep["entities"])
            st.info(rep["recommendation"])
        else:
            st.error(f"API error {r.status_code}: {r.text}")

with tab_graph:
    value = st.text_input("Домен / Telegram / промокод для проверки повторяемости")
    if st.button("Проверить в Shadow Graph") and value.strip():
        r = httpx.get(f"{API_URL}/graph/entity/{value}", timeout=30)
        st.json(r.json() if r.status_code == 200 else {"error": r.text})
