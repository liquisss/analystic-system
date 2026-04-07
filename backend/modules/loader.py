import os
import chardet
import pandas as pd
import PyPDF2
from docx import Document

def load_file(path: str) -> dict:
    """
    Загружает файл по пути и возвращает словарь:
    { name, ext, text, error }
    """
    name = os.path.basename(path)
    ext = name.split('.')[-1].lower()

    try:
        if ext == 'pdf':
            text = _load_pdf(path)
        elif ext == 'docx':
            text = _load_docx(path)
        elif ext == 'txt':
            text = _load_txt(path)
        elif ext == 'csv':
            text = _load_csv(path)
        else:
            return { 'name': name, 'ext': ext, 'text': '', 'error': f'Формат .{ext} не поддерживается' }

        return { 'name': name, 'ext': ext, 'text': text, 'error': None }

    except Exception as e:
        return { 'name': name, 'ext': ext, 'text': '', 'error': str(e) }


def _load_pdf(path: str) -> str:
    text_parts = []
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            part = page.extract_text()
            if part:
                text_parts.append(part)
    return '\n'.join(text_parts)


def _load_docx(path: str) -> str:
    doc = Document(path)
    return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())


def _load_txt(path: str) -> str:
    # Автоопределение кодировки через chardet
    with open(path, 'rb') as f:
        raw = f.read()
    encoding = chardet.detect(raw)['encoding'] or 'utf-8'
    return raw.decode(encoding)


def _load_csv(path: str) -> str:
    # Читаем CSV и склеиваем все строки в текст
    with open(path, 'rb') as f:
        raw = f.read()
    encoding = chardet.detect(raw)['encoding'] or 'utf-8'
    df = pd.read_csv(path, encoding=encoding)
    # Склеиваем все текстовые колонки через пробел
    return '\n'.join(
        ' '.join(str(v) for v in row if pd.notna(v))
        for _, row in df.iterrows()
    )


def load_files(paths: list[str]) -> list[dict]:
    """Загружает список файлов, возвращает список результатов"""
    return [load_file(p) for p in paths]