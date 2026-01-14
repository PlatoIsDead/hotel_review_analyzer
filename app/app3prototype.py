import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import os
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from services.parser import parse_reviews_file
from services.llm_client import analyze_reviews_with_llm
from services.report_pdf import build_pdf


st.set_page_config(
    page_title="Анализатор отзывов отеля",
    page_icon="🏨",
    layout="centered"
)

st.title("🏨 Анализатор отзывов отеля")
st.caption("Загрузите отзывы → AI-анализ (Gemini) → скачайте PDF-отчет")

# File upload
uploaded = st.file_uploader(
    "📁 Загрузите файл с отзывами",
    type=["xlsx", "xls", "csv", "txt"],
    help="Поддерживаемые форматы: Excel (.xlsx, .xls), CSV, TXT"
)

# Custom prompt (optional)
with st.expander("⚙️ Дополнительные настройки"):
    custom_prompt = st.text_area(
        "Собственный промпт (необязательно)",
        height=150,
        placeholder="Оставьте пустым для использования промпта по умолчанию...",
        help="Если вы хотите изменить формат анализа, введите свой промпт здесь"
    )

    max_reviews = st.number_input(
        "Максимум отзывов для анализа",
        min_value=10,
        max_value=500,
        value=200,
        help="Ограничение для экономии токенов API"
    )

# Analyze button
run = st.button("🔍 Анализировать", type="primary", use_container_width=True)

if run:
    if uploaded is None:
        st.error("❌ Сначала загрузите файл с отзывами.")
        st.stop()

    # Parse file
    with st.spinner("📖 Читаем файл..."):
        try:
            reviews = parse_reviews_file(uploaded.name, uploaded.getvalue())
        except Exception as e:
            st.error(f"❌ Ошибка при чтении файла: {str(e)}")
            st.stop()

    if not reviews:
        st.error("❌ Не удалось найти отзывы в файле. Проверьте формат данных.")
        st.stop()

    st.info(f"📊 Найдено отзывов: **{len(reviews)}**")

    # Limit reviews if needed
    reviews_for_llm = reviews[:max_reviews]
    if len(reviews) > max_reviews:
        st.warning(f"⚠️ Для анализа взято первые {max_reviews} отзывов из {len(reviews)}")

    # Send to LLM
    with st.spinner("🤖 Отправляем в Gemini для анализа... (это может занять минуту)"):
        try:
            report = analyze_reviews_with_llm(
                reviews=reviews_for_llm,
                custom_prompt=custom_prompt if custom_prompt else ""
            )
        except Exception as e:
            st.error(f"❌ Ошибка API: {str(e)}")
            st.stop()

    st.success("✅ Анализ завершен!")

    # Display results
    st.divider()

    # Executive Summary
    st.subheader("📋 Краткое резюме")
    summary = report.get("executive_summary", "")
    if summary:
        st.write(summary)
    elif "raw_output" in report:
        st.warning("⚠️ Модель вернула нестандартный формат. Проверьте PDF для полных данных.")
        with st.expander("Показать сырой вывод"):
            st.text(str(report.get("raw_output", ""))[:2000])

    # Key findings in columns
    col1, col2 = st.columns(2)

    with col1:
        positives = report.get("positives", [])
        if positives:
            st.subheader("✅ Плюсы")
            for p in positives[:5]:
                st.write(f"• {p}")

    with col2:
        negatives = report.get("negatives", [])
        if negatives:
            st.subheader("❌ Минусы")
            for n in negatives[:5]:
                st.write(f"• {n}")

    # Risk flags
    risk_flags = report.get("risk_flags", [])
    if risk_flags and risk_flags != ["Критических проблем не выявлено"]:
        st.subheader("🚨 Красные флаги")
        for flag in risk_flags:
            if flag != "Критических проблем не выявлено":
                st.error(f"⚠️ {flag}")

    st.divider()

    # Generate and offer PDF download
    with st.spinner("📄 Генерируем PDF-отчет..."):
        try:
            pdf_bytes = build_pdf(report, title="Отчет по анализу отзывов гостей")
        except Exception as e:
            st.error(f"❌ Ошибка при создании PDF: {str(e)}")
            st.stop()

    st.download_button(
        label="📥 Скачать PDF-отчет",
        data=pdf_bytes,
        file_name="hotel_reviews_report.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )

# Footer
st.divider()
st.caption("💡 Powered by Gemini AI | © 2025")
