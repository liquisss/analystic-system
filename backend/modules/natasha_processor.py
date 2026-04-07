import re
from natasha import (
    Segmenter, MorphVocab, NewsEmbedding,
    NewsMorphTagger, NewsSyntaxParser, NewsNERTagger,
    NamesExtractor, DatesExtractor, Doc
)

STOPWORDS_RU = {
    'и','в','во','не','что','он','на','я','с','со','как','а','то','все','она',
    'так','его','но','да','ты','к','у','же','вы','за','бы','по','только','ее',
    'мне','было','вот','от','меня','еще','нет','о','из','ему','теперь','когда',
    'даже','ну','вдруг','ли','если','уже','или','ни','быть','был','него','до',
    'вас','нибудь','опять','уж','вам','ведь','там','потом','себя','ничего','ей',
    'может','они','тут','где','есть','надо','ней','для','мы','тебя','их','чем',
    'была','сам','чтоб','без','будто','чего','раз','тоже','себе','под','будет',
    'ж','тогда','кто','этот','того','потому','этого','какой','совсем','ним',
    'здесь','этом','один','почти','мой','тем','чтобы','нее','сейчас','были',
    'куда','зачем','всех','никогда','можно','при','наконец','два','об','другой',
    'хоть','после','над','больше','тот','через','эти','нас','про','всего','них',
    'какая','много','разве','три','эту','моя','впрочем','хорошо','свою','этой',
    'перед','иногда','лучше','чуть','том','нельзя','такой','им','более','всегда',
    'конечно','всю','между', 'рис', 'который',
}

# ── Инициализация один раз при импорте ──
segmenter   = Segmenter()
morph_vocab = MorphVocab()
emb         = NewsEmbedding()
morph_tagger  = NewsMorphTagger(emb)
syntax_parser = NewsSyntaxParser(emb)
ner_tagger    = NewsNERTagger(emb)
names_extractor = NamesExtractor(morph_vocab)
dates_extractor = DatesExtractor(morph_vocab)

CHUNK_SIZE    = 3000   # символов на чанк
CHUNK_OVERLAP = 200    # перекрытие между чанками

def split_into_chunks(text: str) -> list[str]:
    """Делит текст на чанки с перекрытием"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def clean_text(text: str) -> str:
    """Базовая очистка текста"""
    text = re.sub(r'\s+', ' ', text)           # лишние пробелы
    text = re.sub(r'[^\w\s\.\,\!\?\-]', '', text)  # спецсимволы
    return text.strip()


def process_chunk(text: str, settings: dict) -> dict:
    """Обрабатывает один чанк через Natasha"""
    doc = Doc(text)

    # Сегментация всегда включена
    doc.segment(segmenter)

    tokens     = []
    lemmas     = []
    entities   = []
    dates      = []

    # Морфология + лемматизация
    if settings.get('morph', True):
        doc.tag_morph(morph_tagger)
        if settings.get('lemmatize', True):
            for token in doc.tokens:
                token.lemmatize(morph_vocab)

        min_len = settings.get('minTokenLen', 2)
        use_stopwords = settings.get('stopwords', True)
        stop_custom = set(
            w.strip() for w in settings.get('customStop', '').split('\n')
            if w.strip()
        )

        for token in doc.tokens:
            lemma = (token.lemma or token.text).lower()

            # Фильтр по длине
            if len(lemma) < min_len:
                continue
            # Фильтр по части речи
            if token.pos in ('PUNCT', 'NUM', 'SYM', 'X'):
                continue
            # Встроенные стоп-слова
            if use_stopwords and lemma in STOPWORDS_RU:
                continue
            # Пользовательские стоп-слова
            if lemma in stop_custom:
                continue

            tokens.append(token.text)
            lemmas.append(lemma)

    # NER
    if settings.get('ner', True):
        doc.tag_ner(ner_tagger)
        for span in doc.spans:
            entities.append({
                'text': span.text,
                'type': span.type,   # PER, ORG, LOC
            })

    # Даты
    if settings.get('dates', True):
        for match in dates_extractor(text):
            dates.append({
                'text': match.fact.as_json if hasattr(match.fact, 'as_json') else str(match.fact),
                'start': match.start,
                'stop':  match.stop,
            })

    return {
        'tokens':   tokens,
        'lemmas':   lemmas,
        'entities': entities,
        'dates':    dates,
        'text_clean': ' '.join(lemmas),  # для BERTopic
    }


def process_document(raw: dict, settings: dict) -> dict:
    """
    Обрабатывает один документ (из session raw/).
    raw = { name, ext, text, error }
    """
    print(f"[Natasha] обработка: {raw['name']}")

    text = clean_text(raw['text'])
    chunks = split_into_chunks(text)
    print(f"[Natasha] чанков: {len(chunks)}")

    all_tokens   = []
    all_lemmas   = []
    all_entities = []
    all_dates    = []

    for i, chunk in enumerate(chunks):
        print(f"[Natasha] чанк {i+1}/{len(chunks)}...")
        result = process_chunk(chunk, settings)
        all_tokens.extend(result['tokens'])
        all_lemmas.extend(result['lemmas'])
        all_entities.extend(result['entities'])
        all_dates.extend(result['dates'])

    # Убираем дубли в сущностях
    seen = set()
    unique_entities = []
    for e in all_entities:
        key = (e['text'], e['type'])
        if key not in seen:
            seen.add(key)
            unique_entities.append(e)

    return {
        'name':       raw['name'],
        'tokens':     all_tokens,
        'lemmas':     all_lemmas,
        'entities':   unique_entities,
        'dates':      all_dates,
        'text_clean': ' '.join(all_lemmas),  # готово для BERTopic
        'chunks_count': len(chunks),
        'tokens_count': len(all_tokens),
    }


def process_all(documents: list[dict], settings: dict) -> dict:
    """Обрабатывает все документы сессии"""
    results = []
    for raw in documents:
        if raw.get('error'):
            print(f"[Natasha] пропуск {raw['name']} — ошибка загрузки")
            continue
        result = process_document(raw, settings)
        results.append(result)

    return {
        'documents': results,
        'total_tokens': sum(r['tokens_count'] for r in results),
        'total_docs':   len(results),
    }