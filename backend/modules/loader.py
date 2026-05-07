from __future__ import annotations
import os
import chardet
import pandas as pd
import PyPDF2
from docx import Document

_NAME_COLS = {'наименование', 'название', 'name', 'title', 'заголовок', 'тема'}
_TEXT_COLS = {'аннотация', 'анатация', 'описание', 'abstract', 'text',
              'текст', 'содержание', 'annotation', 'реферат'}
_NER_COLS = {
    'сведения об исполнителе', 'исполнитель', 'executor',
    'организация', 'author', 'сроки выполнения работ',
    'сроки выполнения работ (дата начала, дата окончания) ',
    'сроки'
}
_REG_COLS = {'регистрационный номер', 'рег. номер', 'id', 'reg_number', 'номер'}


def _detect_columns(df: pd.DataFrame):
    cols_lower = {c.lower().strip(): c for c in df.columns}
    name_col = next((cols_lower[k] for k in _NAME_COLS if k in cols_lower), None)
    text_col = next((cols_lower[k] for k in _TEXT_COLS if k in cols_lower), None)
    reg_col = next((cols_lower[k] for k in _REG_COLS if k in cols_lower), None)
    ner_cols = [cols_lower[k] for k in _NER_COLS if k in cols_lower]
    return name_col, text_col, reg_col, ner_cols


def load_file(path: str) -> dict:
    name = os.path.basename(path)
    ext = name.split('.')[-1].lower()
    try:
        if ext == 'pdf':
            text = _load_pdf(path)
            return {'name': name, 'ext': ext, 'text': text, 'error': None,
                    'is_dataset': False, 'ner_text': None, 'reg_number': '',
                    'title': name, 'fast_mode': False}
        elif ext == 'docx':
            text = _load_docx(path)
            return {'name': name, 'ext': ext, 'text': text, 'error': None,
                    'is_dataset': False, 'ner_text': None, 'reg_number': '',
                    'title': name, 'fast_mode': False}
        elif ext == 'txt':
            text = _load_txt(path)
            return {'name': name, 'ext': ext, 'text': text, 'error': None,
                    'is_dataset': False, 'ner_text': None, 'reg_number': '',
                    'title': name, 'fast_mode': False}
        elif ext in ('csv', 'xlsx'):
            return _load_tabular(path, name, ext)
        else:
            return {'name': name, 'ext': ext, 'text': '', 'error': f'Формат .{ext} не поддерживается',
                    'is_dataset': False}
    except Exception as e:
        return {'name': name, 'ext': ext, 'text': '', 'error': str(e), 'is_dataset': False}


def _load_tabular(path: str, name: str, ext: str) -> dict:
    try:
        if ext == 'csv':
            with open(path, 'rb') as f:
                raw = f.read()
            encoding = chardet.detect(raw)['encoding'] or 'utf-8'
            df = None
            for sep in (';', ',', '\t'):
                try:
                    _df = pd.read_csv(path, encoding=encoding, sep=sep,
                                      engine='python', on_bad_lines='skip',
                                      dtype=str, keep_default_na=False)
                    if len(_df.columns) > 1:
                        df = _df
                        break
                except Exception:
                    continue
            if df is None:
                df = pd.read_csv(path, encoding=encoding,
                                 engine='python', on_bad_lines='skip',
                                 dtype=str, keep_default_na=False)
        else:  # xlsx
            df = pd.read_excel(path, dtype=str, keep_default_na=False, engine='openpyxl')
            # Удаляем строки, где все ячейки пусты
            df = df.dropna(how='all')

        if df.empty:
            return {'name': name, 'ext': ext, 'text': '', 'error': 'Файл не содержит данных',
                    'is_dataset': False}

        name_col, text_col, reg_col, ner_cols = _detect_columns(df)

        # Нет текстовой колонки — возвращаем missing_cols для фронта
        if not text_col:
            return {
                'name': name, 'ext': ext, 'text': '', 'error': None,
                'is_dataset': True, 'missing_cols': True,
                'columns': list(df.columns), 'documents': []
            }

        documents = []
        for i, row in df.iterrows():
            # Рег. номер
            reg_number = ''
            if reg_col and pd.notna(row.get(reg_col)) and str(row[reg_col]).strip():
                reg_number = str(row[reg_col]).strip()

            # Название
            title = ''
            if name_col and pd.notna(row.get(name_col)):
                title = str(row[name_col]).strip()
            if not title:
                title = f"Документ {i+1}"
            doc_name = reg_number if reg_number else f"{i+1}_{title[:40]}"

            # Полный текст = название + аннотация
            parts = []
            if name_col and pd.notna(row.get(name_col)):
                parts.append(str(row[name_col]).strip())
            if pd.notna(row[text_col]):
                parts.append(str(row[text_col]).strip())
            full_text = ' '.join(parts).strip()

            # Пропускаем строки без текста (пустые)
            if not full_text:
                continue

            # Короткий текст для NER
            ner_parts = []
            if name_col and pd.notna(row.get(name_col)):
                ner_parts.append(str(row[name_col]).strip())
            for col in ner_cols:
                if pd.notna(row.get(col)) and str(row[col]).strip():
                    ner_parts.append(str(row[col]).strip())
            ner_text = ' '.join(ner_parts).strip()
            if not ner_text:
                ner_text = full_text[:300]

            documents.append({
                'name': doc_name, 'ext': ext, 'text': full_text,
                'ner_text': ner_text, 'reg_number': reg_number,
                'title': title, 'error': None, 'is_dataset': False,
                'fast_mode': True
            })

        if not documents:
            return {
                'name': name, 'ext': ext, 'text': '', 'error': None,
                'is_dataset': True, 'missing_cols': False,
                'columns': list(df.columns), 'documents': [],
                'total': 0, 'warning': 'Нет строк с непустым текстом'
            }

        return {
            'name': name, 'ext': ext, 'text': '', 'error': None,
            'is_dataset': True, 'missing_cols': False,
            'columns': list(df.columns), 'documents': documents,
            'total': len(documents)
        }

    except Exception as e:
        return {'name': name, 'ext': ext, 'text': '', 'error': str(e), 'is_dataset': False}


def _load_pdf(path: str) -> str:
    parts = []
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
    return '\n'.join(parts)


def _load_docx(path: str) -> str:
    doc = Document(path)
    return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())


def _load_txt(path: str) -> str:
    with open(path, 'rb') as f:
        raw = f.read()
    encoding = chardet.detect(raw)['encoding'] or 'utf-8'
    return raw.decode(encoding)
