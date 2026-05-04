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
    '#e8413b', '#177dbe', '#0ea54b', '#fc8c00',
    '#8e409a', '#cc0e74', '#b8b008', '#00aba5',
    '#6d3f1f', '#5b5b5b',
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


def _get_cluster_links(vos_data: dict, top_n: int = 6) -> list:
    if not vos_data:
        return []
    links = vos_data.get('network', {}).get('links', [])
    items = vos_data.get('network', {}).get('items', [])
    if not links or not items:
        return []

    id_to_label = {item['id']: item['label'] for item in items}
    id_to_cluster = {item['id']: (item['cluster'] - 1) for item in items}

    sorted_links = sorted(links, key=lambda x: x['strength'], reverse=True)

    result = []
    for lnk in sorted_links[:top_n]:
        sid = lnk['source_id']
        tid = lnk['target_id']
        result.append({
            'a':        id_to_label.get(sid, f'Тема {sid}'),
            'b':        id_to_label.get(tid, f'Тема {tid}'),
            'strength': round(float(lnk['strength']), 3),
            'color':    TOPIC_COLORS[id_to_cluster.get(sid, 0) % len(TOPIC_COLORS)],
        })
    return result

def _get_topic_ner_summary(topic: dict, doc_topics: list,
                            natasha_docs: list, top_n: int = 10) -> dict:
    """
    Возвращает топ NER-сущностей по теме.
    Структура: { 'PER': [(text, count), ...], 'ORG': [...], 'LOC': [...] }
    """
    topic_id = topic['id']

    # Имена документов принадлежащих теме
    topic_doc_names = {dt['name'] for dt in doc_topics if dt['topic'] == topic_id}
    if not topic_doc_names:
        return {}

    # Индекс natasha по имени
    natasha_index = {d['name']: d for d in natasha_docs}

    # Считаем частоту сущностей (уникальные на документ)
    freq: dict = {}
    for name in topic_doc_names:
        nd = natasha_index.get(name)
        if not nd:
            continue
        seen = set()
        for e in nd.get('entities', []):
            key = f"{e['type']}::{e['text']}"
            if key in seen:
                continue
            seen.add(key)
            if key not in freq:
                freq[key] = {'text': e['text'], 'type': e['type'], 'count': 0}
            freq[key]['count'] += 1

    # Группируем по типу, сортируем по частоте
    result: dict = {}
    for item in sorted(freq.values(), key=lambda x: -x['count']):
        t = item['type']
        if t not in result:
            result[t] = []
        if len(result[t]) < top_n:
            result[t].append((item['text'], item['count']))

    return result

def generate_report(bertopic_data: dict, natasha_data: dict,
                    sections: dict, output_path: str) -> str:
    _register_fonts()

    topics      = bertopic_data.get('topics', [])
    total_docs  = bertopic_data.get('total_docs', 0)
    coherence   = bertopic_data.get('coherence', 0)
    noise_pct   = bertopic_data.get('noise_pct', 0)
    noise_count = bertopic_data.get('noise_count', 0)

    dominant_topic = topics[0] if topics else None
    dominant_pct   = round((dominant_topic['count'] / total_docs) * 100) if dominant_topic and total_docs else 0

    doc_topics = bertopic_data.get('doc_topics', [])
    natasha_docs = natasha_data.get('documents', [])

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

    style_note = ParagraphStyle('note',
                                fontSize=9, textColor=GRAY, fontName='Arial',
                                leading=14, spaceAfter=4,
                                leftIndent=8,
                                )

    story = []

    # ── Шапка ──
    story.append(Paragraph('Аналитический отчёт · SemanticAnalyzer', style_title))
    story.append(Paragraph(
        f"Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M')} · v1.0.0 · Лебедева Елизавета · гр. ИДБ-22-12",
        style_meta
    ))
    story.append(HRFlowable(width='100%', thickness=2, color=CYAN, spaceAfter=16))

    story.append(Paragraph(
        '<i>Примечание: анализируется только текстовое содержимое документов. '
        'Изображения, таблицы, графики и прочие нетекстовые элементы игнорируются.</i>',
        style_body,
    ))
    story.append(Spacer(1, 8))

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

        style_cell = ParagraphStyle('cell',
                                    fontSize=8, fontName='Arial', leading=12,
                                    wordWrap='CJK', textColor=DARK,
                                    )
        style_cell_hdr = ParagraphStyle('cell_hdr',
                                        fontSize=8, fontName='Arial-Bold', leading=12, textColor=CYAN,
                                        )

        topic_rows = [[
            Paragraph('№', style_cell_hdr),
            Paragraph('Тема', style_cell_hdr),
            Paragraph('Ключевые слова', style_cell_hdr),
            Paragraph('Документов', style_cell_hdr),
        ]]

        for i, t in enumerate(topics):
            words_str = '\n'.join(
                ' · '.join(t['words'][k:k + 3])
                for k in range(0, min(len(t['words']), 9), 3)
            )
            topic_rows.append([
                Paragraph(str(i + 1), style_cell),
                Paragraph(t['label'], style_cell),
                Paragraph(words_str, style_cell),
                Paragraph(str(t['count']), ParagraphStyle('cnt',
                                                          fontSize=8, fontName='Arial-Bold', leading=12,
                                                          textColor=colors.HexColor(
                                                              TOPIC_COLORS[i % len(TOPIC_COLORS)]),
                                                          )),
            ])

        topic_table = Table(topic_rows, colWidths=[1 * cm, 4.5 * cm, 9 * cm, 2 * cm], repeatRows=1)
        topic_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), LIGHT),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
            ('BOX', (0, 0), (-1, -1), 1, BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(topic_table)
        story.append(Spacer(1, 12))

    # ── Сущности по темам (NER) ──
    if sections.get('topics') and topics and natasha_docs:
        story.append(Paragraph('4. Именованные сущности по темам', style_section))
        story.append(Paragraph(
            'Топ именованных сущностей (Natasha NER) по каждой теме. '
            'Число в скобках — количество документов темы содержащих сущность.',
            style_note,
        ))

        NER_COLORS = {
            'PER': colors.HexColor('#a78bfa'),
            'ORG': colors.HexColor('#00aba5'),
            'LOC': colors.HexColor('#0ea54b'),
        }

        for i, t in enumerate(topics):
            ner = _get_topic_ner_summary(t, doc_topics, natasha_docs, top_n=8)
            if not ner:
                continue

            topic_color = colors.HexColor(TOPIC_COLORS[i % len(TOPIC_COLORS)])

            # Заголовок темы
            topic_header = Table(
                [[Paragraph(f"● {t['label']}", ParagraphStyle(
                    'th', fontSize=9, fontName='Arial-Bold',
                    textColor=topic_color, leading=12,
                ))]],
                colWidths=[16.5 * cm],
            )
            topic_header.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f9ff')),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
            ]))
            story.append(topic_header)

            # Строки по типам PER / ORG / LOC
            for ner_type in ['PER', 'ORG', 'LOC']:
                items = ner.get(ner_type, [])
                if not items:
                    continue

                ner_color = NER_COLORS.get(ner_type, GRAY)
                # Формируем строку: тип | сущности через запятую
                entities_str = ',  '.join(
                    f"{text} (×{count})" if count > 1 else text
                    for text, count in items
                )
                row_data = [[
                    Paragraph(ner_type, ParagraphStyle(
                        'ntype', fontSize=8, fontName='Arial-Bold',
                        textColor=ner_color, leading=11,
                    )),
                    Paragraph(entities_str, ParagraphStyle(
                        'nval', fontSize=8, fontName='Arial',
                        textColor=DARK, leading=11, wordWrap='CJK',
                    )),
                ]]
                row_table = Table(row_data, colWidths=[1.8 * cm, 14.7 * cm])
                row_table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('INNERGRID', (0, 0), (-1, -1), 0.3, BORDER),
                    ('BOX', (0, 0), (-1, -1), 0.3, BORDER),
                ]))
                story.append(row_table)

            story.append(Spacer(1, 8))

        story.append(Spacer(1, 4))

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

        vos_data = bertopic_data.get('vos_data', {})
        cluster_links = _get_cluster_links(vos_data, top_n=6)

        if cluster_links:
            link_rows = [[
                Paragraph('Тема A', style_cell_hdr),
                Paragraph('Тема B', style_cell_hdr),
                Paragraph('Сила связи', style_cell_hdr),
            ]]
            for lnk in cluster_links:
                filled = round(lnk['strength'] * 20)
                bar = '█' * filled + '░' * (20 - filled)
                link_rows.append([
                    Paragraph(lnk['a'], style_cell),
                    Paragraph(lnk['b'], style_cell),
                    Paragraph(
                        f"{lnk['strength']:.3f}  {bar}",
                        ParagraphStyle('bar', fontSize=8, fontName='Arial',
                                       leading=12, textColor=colors.HexColor(lnk['color'])),
                    ),
                ])

            link_table = Table(link_rows, colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm], repeatRows=1)
            link_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), LIGHT),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
                ('BOX', (0, 0), (-1, -1), 1, BORDER),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(link_table)
        else:
            story.append(Paragraph(
                'Данные о связях отсутствуют — запустите анализ повторно.',
                style_body,
            ))

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
