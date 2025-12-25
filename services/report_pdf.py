import io
from datetime import datetime
from typing import Dict, List, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY


def _register_fonts():
    """Register fonts with Cyrillic support."""
    # Try to register DejaVu fonts (commonly available on Linux)
    font_paths = [
        # Linux paths
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        # Windows paths
        "C:/Windows/Fonts/arial.ttf",
        # Mac paths
        "/Library/Fonts/Arial.ttf",
    ]

    font_registered = False
    for font_path in font_paths:
        try:
            pdfmetrics.registerFont(TTFont('CustomFont', font_path))
            font_registered = True
            break
        except:
            continue

    if not font_registered:
        # Fallback: try Arial Unicode or system default
        try:
            pdfmetrics.registerFont(TTFont('CustomFont', 'arial.ttf'))
        except:
            pass  # Will use default Helvetica

    return font_registered


def _get_styles(font_registered: bool):
    """Create styles with proper font."""
    styles = getSampleStyleSheet()
    font_name = 'CustomFont' if font_registered else 'Helvetica'

    styles.add(ParagraphStyle(
        name='RussianTitle',
        fontName=font_name,
        fontSize=16,
        leading=20,
        spaceAfter=12,
        alignment=TA_LEFT,
    ))

    styles.add(ParagraphStyle(
        name='RussianHeading',
        fontName=font_name,
        fontSize=12,
        leading=14,
        spaceAfter=6,
        spaceBefore=12,
        textColor='#2c5282',
    ))

    styles.add(ParagraphStyle(
        name='RussianBody',
        fontName=font_name,
        fontSize=10,
        leading=14,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
    ))

    styles.add(ParagraphStyle(
        name='RussianQuote',
        fontName=font_name,
        fontSize=10,
        leading=14,
        leftIndent=20,
        spaceAfter=6,
        textColor='#4a5568',
        fontStyle='italic',
    ))

    styles.add(ParagraphStyle(
        name='RussianBullet',
        fontName=font_name,
        fontSize=10,
        leading=14,
        leftIndent=15,
        spaceAfter=4,
    ))

    return styles


def build_pdf(report: Dict, title: str = "Отчет по анализу отзывов") -> bytes:
    """Build PDF report from analysis results."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    font_registered = _register_fonts()
    styles = _get_styles(font_registered)

    story = []

    # Title
    story.append(Paragraph(title, styles['RussianTitle']))
    story.append(Paragraph(
        f"Дата создания: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC",
        styles['RussianBody']
    ))
    story.append(Spacer(1, 12))

    # Executive Summary
    _add_section(
        story, styles,
        "📋 Краткое резюме",
        report.get("executive_summary", "")
    )

    # Quotes section
    quotes = report.get("quotes", {})
    if quotes:
        story.append(Paragraph("💬 Примеры отзывов", styles['RussianHeading']))
        story.append(Spacer(1, 6))

        if quotes.get("wow_effect"):
            story.append(Paragraph("⭐ Вау-эффект:", styles['RussianBody']))
            story.append(Paragraph(f'"{quotes["wow_effect"]}"', styles['RussianQuote']))

        if quotes.get("typical_positive"):
            story.append(Paragraph("✅ Типичный позитив:", styles['RussianBody']))
            story.append(Paragraph(f'"{quotes["typical_positive"]}"', styles['RussianQuote']))

        if quotes.get("typical_negatives"):
            story.append(Paragraph("❌ Типичный негатив:", styles['RussianBody']))
            for neg in quotes["typical_negatives"]:
                story.append(Paragraph(f'"{neg}"', styles['RussianQuote']))

        story.append(Spacer(1, 12))

    # Positives
    _add_list_section(
        story, styles,
        "✅ Сильные стороны",
        report.get("positives", [])
    )

    # Negatives
    _add_list_section(
        story, styles,
        "❌ Слабые стороны",
        report.get("negatives", [])
    )

    # Risk Flags
    _add_list_section(
        story, styles,
        "🚨 Красные флаги",
        report.get("risk_flags", []),
        is_critical=True
    )

    # Action Plan
    _add_list_section(
        story, styles,
        "📌 План действий",
        report.get("action_plan", report.get("actionable_recommendations", []))
    )

    # Best Practices
    _add_list_section(
        story, styles,
        "💡 Системные улучшения",
        report.get("best_practices", [])
    )

    # Key themes (legacy support)
    if "key_themes" in report:
        _add_list_section(
            story, styles,
            "🔑 Ключевые темы",
            report.get("key_themes", [])
        )

    # Raw output fallback
    if "raw_output" in report:
        story.append(Paragraph("📄 Необработанный вывод модели", styles['RussianHeading']))
        story.append(Spacer(1, 6))
        raw_text = str(report["raw_output"])
        # Split long text into paragraphs
        for para in raw_text.split('\n'):
            if para.strip():
                story.append(Paragraph(para, styles['RussianBody']))
        story.append(Spacer(1, 12))

    doc.build(story)
    return buffer.getvalue()


def _add_section(story: List, styles, header: str, text: str):
    """Add a text section to the story."""
    story.append(Paragraph(header, styles['RussianHeading']))
    story.append(Spacer(1, 6))
    if text:
        story.append(Paragraph(str(text), styles['RussianBody']))
    else:
        story.append(Paragraph("—", styles['RussianBody']))
    story.append(Spacer(1, 12))


def _add_list_section(story: List, styles, header: str, items: Any, is_critical: bool = False):
    """Add a list section to the story."""
    story.append(Paragraph(header, styles['RussianHeading']))
    story.append(Spacer(1, 6))

    if not items:
        story.append(Paragraph("—", styles['RussianBody']))
        story.append(Spacer(1, 12))
        return

    # Handle case where items is not a list
    if isinstance(items, str):
        items = [items]
    elif not isinstance(items, list):
        items = [str(items)]

    for item in items:
        bullet = "• "
        if is_critical and item != "Критических проблем не выявлено":
            bullet = "⚠️ "
        story.append(Paragraph(f"{bullet}{str(item)}", styles['RussianBullet']))

    story.append(Spacer(1, 12))
