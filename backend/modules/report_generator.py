import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ── Цвета ──
CYAN   = colors.HexColor('#0077b6')
AMBER  = colors.HexColor('#d97706')
GREEN  = colors.HexColor('#16a34a')
RED    = colors.HexColor('#dc2626')
LIGHT  = colors.HexColor('#f0f9ff')
BORDER = colors.HexColor('#bae6fd')
GRAY   = colors.HexColor('#666666')
DARK   = colors.HexColor('#1a1a2e')

TOPIC_COLORS = [
    '#00d4ff', '#f59e0b', '#10b981', '#a78bfa',
    '#f87171', '#34d399', '#60a5fa', '#f472b6',
]

# ── Регистрация шрифтов (один раз) ──
_fonts_registered = False

def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    try:
        pdfmetrics.registerFont(TTFont('Arial',      'C:/Windows/Fonts/arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
        _fonts_registered = True
        print("[Report] шрифты Arial зарегистрированы")
    except Exception as e:
        print(f"[Report] ошибка регистрации шрифтов: {e}")


def generate_report(bertopic_data: dict, sections: dict, output_path: str) -> str:
    _register_fonts()

    topics      = bertopic_data.get('topics', [])
    total_docs  = bertopic_data.get('total_docs', 0)
    coherence   = bertopic_data.get('coherence', 0)
    noise_pct   = bertopic_data.get('noise_pct', 0)
    noise_count = bertopic_data.get('noise_count', 0)

    dominant_topic = topics[0] if topics else None
    dominant_pct   = round((dominant_topic['count'] / total_docs) * 100) if dominant_topic and total_docs else 0

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=2*cm,
    )

    # ── Стили ──
    style_title = ParagraphStyle('title',
        fontSize=20, textColor=CYAN, fontName='Arial-Bold',
        spaceAfter=4, leading=24,
    )
    style_meta = ParagraphStyle('meta',
        fontSize=9, textColor=GRAY, fontName='Arial',
        spaceAfter=16,
    )
    style_section = ParagraphStyle('section',
        fontSize=10, textColor=CYAN, fontName='Arial-Bold',
        spaceBefore=16, spaceAfter=8,
    )
    style_body = ParagraphStyle('body',
        fontSize=10, textColor=DARK, fontName='Arial',
        leading=16, spaceAfter=8,
    )
    style_footer = ParagraphStyle('footer',
        fontSize=8, textColor=GRAY, fontName='Arial',
        alignment=TA_CENTER,
    )

    story = []

    # ── Шапка ──
    story.append(Paragraph('Аналитический отчёт · SemanticAnalyzer', style_title))
    story.append(Paragraph(
        f"Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M')} · v1.0.0 · Лебедева Елизавета · гр. ИДБ-22-12",
        style_meta
    ))
    story.append(HRFlowable(width='100%', thickness=2, color=CYAN, spaceAfter=16))

    # ── 1. Краткое резюме ──
    if sections.get('summary'):
        story.append(Paragraph('1. Краткое резюме', style_section))

        coherence_comment = (
            'высокая — чёткое тематическое разграничение'
            if coherence >= 70 else
            'средняя — темы частично перекрываются'
            if coherence >= 40 else
            'низкая — рекомендуется пересмотреть параметры'
        )

        summary_text = (
            f"Корпус из <b>{total_docs} документов</b> разбит на "
            f"<b>{len(topics)} тематических кластеров</b>. "
        )
        if dominant_topic:
            summary_text += (
                f"Доминирующая тема — <b>«{dominant_topic['label']}»</b> "
                f"({dominant_pct}% документов, {dominant_topic['count']} ед.). "
            )
        summary_text += f"Когерентность {coherence}% — {coherence_comment}. "
        if noise_count > 0:
            summary_text += f"Обнаружено <b>{noise_count} документов шума</b> ({noise_pct}%)."

        story.append(Paragraph(summary_text, style_body))
        story.append(Spacer(1, 8))

    # ── 2. Общая статистика ──
    if sections.get('stats'):
        story.append(Paragraph('2. Общая статистика', style_section))

        stat_data = [
            ['Документов', 'Тем', 'Когерентность', 'Шум'],
            [str(total_docs), str(len(topics)), f'{coherence}%', f'{noise_pct}%'],
        ]
        stat_table = Table(stat_data, colWidths=[4*cm]*4)
        stat_table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), LIGHT),
            ('BACKGROUND',    (0,1), (-1,1), colors.white),
            ('TEXTCOLOR',     (0,0), (-1,0), GRAY),
            ('TEXTCOLOR',     (0,1), (-1,1), CYAN),
            ('FONTNAME',      (0,0), (-1,0), 'Arial'),
            ('FONTNAME',      (0,1), (-1,1), 'Arial-Bold'),
            ('FONTSIZE',      (0,0), (-1,0), 8),
            ('FONTSIZE',      (0,1), (-1,1), 16),
            ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('BOX',           (0,0), (-1,-1), 1, BORDER),
            ('INNERGRID',     (0,0), (-1,-1), 0.5, BORDER),
            ('TOPPADDING',    (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(stat_table)
        story.append(Spacer(1, 12))

    # ── 3. Тематический анализ ──
    if sections.get('topics') and topics:
        story.append(Paragraph('3. Тематический анализ', style_section))

        topic_rows = [['№', 'Тема', 'Ключевые слова', 'Документов']]
        for i, t in enumerate(topics):
            words_str = ' · '.join(t['words'][:6])
            topic_rows.append([
                str(i + 1),
                t['label'],
                words_str,
                str(t['count']),
            ])

        topic_table = Table(topic_rows, colWidths=[1*cm, 4*cm, 9*cm, 2.5*cm])
        topic_table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), LIGHT),
            ('TEXTCOLOR',     (0,0), (-1,0), CYAN),
            ('FONTNAME',      (0,0), (-1,0), 'Arial-Bold'),
            ('FONTNAME',      (0,1), (-1,-1), 'Arial'),
            ('FONTSIZE',      (0,0), (-1,-1), 8),
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
            ('ALIGN',         (3,0), (3,-1), 'CENTER'),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, LIGHT]),
            ('BOX',           (0,0), (-1,-1), 1, BORDER),
            ('INNERGRID',     (0,0), (-1,-1), 0.5, BORDER),
            ('TOPPADDING',    (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ]))
        story.append(topic_table)
        story.append(Spacer(1, 12))

    # ── 4. Аномалии и шум ──
    if sections.get('anomalies'):
        story.append(Paragraph('4. Аномалии и шум', style_section))

        noise_color = RED if noise_pct > 20 else (AMBER if noise_pct > 10 else GREEN)
        anomaly_data = [
            ['Показатель', 'Документов', 'Процент'],
            ['Нераспознанные документы (шум)', str(noise_count), f'{noise_pct}%'],
        ]
        anomaly_table = Table(anomaly_data, colWidths=[8*cm, 3*cm, 5.5*cm])
        anomaly_table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), LIGHT),
            ('TEXTCOLOR',     (0,0), (-1,0), CYAN),
            ('FONTNAME',      (0,0), (-1,0), 'Arial-Bold'),
            ('FONTNAME',      (0,1), (-1,-1), 'Arial'),
            ('FONTSIZE',      (0,0), (-1,-1), 9),
            ('ALIGN',         (1,0), (-1,-1), 'CENTER'),
            ('TEXTCOLOR',     (2,1), (2,-1), noise_color),
            ('FONTNAME',      (2,1), (2,-1), 'Arial-Bold'),
            ('BOX',           (0,0), (-1,-1), 1, BORDER),
            ('INNERGRID',     (0,0), (-1,-1), 0.5, BORDER),
            ('TOPPADDING',    (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ]))
        story.append(anomaly_table)
        story.append(Spacer(1, 12))

    # ── 5. Межкластерные связи ──
    if sections.get('clusters') and len(topics) > 1:
        story.append(Paragraph('5. Межкластерные связи', style_section))

        links = []
        for i, t1 in enumerate(topics[:5]):
            for t2 in topics[i+1:i+2]:
                shared = set(t1['words']) & set(t2['words'])
                w = min(0.99, len(shared) / 10 + 0.3)
                links.append({
                    'a': f"Тема {t1['id']}",
                    'b': f"Тема {t2['id']}",
                    'w': round(w, 2),
                })

        if links:
            link_data = [['Кластер A', 'Кластер B', 'Сила связи']]
            for lnk in links:
                link_data.append([lnk['a'], lnk['b'], str(lnk['w'])])

            link_table = Table(link_data, colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
            link_table.setStyle(TableStyle([
                ('BACKGROUND',    (0,0), (-1,0), LIGHT),
                ('TEXTCOLOR',     (0,0), (-1,0), CYAN),
                ('FONTNAME',      (0,0), (-1,0), 'Arial-Bold'),
                ('FONTNAME',      (0,1), (-1,-1), 'Arial'),
                ('FONTSIZE',      (0,0), (-1,-1), 9),
                ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
                ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, LIGHT]),
                ('BOX',           (0,0), (-1,-1), 1, BORDER),
                ('INNERGRID',     (0,0), (-1,-1), 0.5, BORDER),
                ('TOPPADDING',    (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ]))
            story.append(link_table)

    # ── Футер ──
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width='100%', thickness=1, color=BORDER))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"SemanticAnalyzer v1.0.0 · Выпускная квалификационная работа · гр. ИДБ-22-12 · {datetime.now().strftime('%d.%m.%Y')}",
        style_footer,
    ))

    doc.build(story)
    print(f"[Report] PDF сохранён: {output_path}")
    return output_path