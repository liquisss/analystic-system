from __future__ import annotations
import re
from typing import Optional
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
    'конечно','всю','между', 'рис', 'который', 'Рис',
}

# ── Инициализация один раз при импорте ──
segmenter       = Segmenter()
morph_vocab     = MorphVocab()
emb             = NewsEmbedding()
morph_tagger    = NewsMorphTagger(emb)
syntax_parser   = NewsSyntaxParser(emb)
ner_tagger      = NewsNERTagger(emb)
names_extractor = NamesExtractor(morph_vocab)
dates_extractor = DatesExtractor(morph_vocab)

CHUNK_SIZE    = 3000
CHUNK_OVERLAP = 200


# ─────────────────────────────────────────────────────────────────────────────
# ТЕЗАУРУС
# ─────────────────────────────────────────────────────────────────────────────

def _lemmatize_single_word(word: str) -> str:
    """Лемматизирует одно слово через Natasha MorphVocab."""
    try:
        doc = Doc(word)
        doc.segment(segmenter)
        doc.tag_morph(morph_tagger)
        for token in doc.tokens:
            token.lemmatize(morph_vocab)
            return (token.lemma or word).lower()
    except Exception:
        pass
    return word.lower()


def build_thesaurus_lookup(raw: dict) -> dict:
    """
    Принимает сырой тезаурус из UI:
        { "евросоюз": ["ес", "eu", "европейский союз"], ... }

    Возвращает:
        {
          "single": { лемма_варианта: лемма_канона },
          "multi":  [ (кортеж_лемм_фразы, лемма_канона), ... ]
                    отсортировано по убыванию длины (longest match first)
        }

    Многословный канон ("европейский союз"):
      - сам регистрируется в multi → при встрече в тексте схлопывается
        в один токен "европейский_союз"
      - все варианты тоже регистрируются (однословные → single,
        многословные → multi)
    """
    single: dict = {}
    multi: list  = []

    for canon_raw, variants in (raw or {}).items():
        canon_words = [_lemmatize_single_word(w)
                       for w in canon_raw.strip().lower().split()]
        if not canon_words:
            continue

        canon_key = '_'.join(canon_words) if len(canon_words) > 1 else canon_words[0]

        for variant_raw in (variants or []):
            variant_words = [_lemmatize_single_word(w)
                             for w in variant_raw.strip().lower().split()]
            if not variant_words:
                continue

            if len(variant_words) == 1:
                v = variant_words[0]
                if v != canon_key:
                    single[v] = canon_key
            else:
                vt = tuple(variant_words)
                ct = tuple(canon_words)
                if vt != ct:
                    multi.append((vt, canon_key))

        if len(canon_words) > 1:
            multi.append((tuple(canon_words), canon_key))

    multi.sort(key=lambda x: -len(x[0]))

    print(f"[Thesaurus] lookup: {len(single)} однословных, {len(multi)} фразовых")
    return {'single': single, 'multi': multi}


def apply_thesaurus_to_lemmas(lemmas: list, lookup: dict) -> list:
    """
    Greedy left-to-right, longest match first.

    Почему ПОСЛЕ всех чанков:
      Фраза "европейский союз" может разорваться на границе чанков.
      Собираем все леммы документа — потом один проход тезауруса.
    """
    if not lookup:
        return lemmas

    single = lookup.get('single', {})
    multi  = lookup.get('multi', [])
    n      = len(lemmas)
    result = []
    i      = 0

    while i < n:
        matched = False
        for phrase_tuple, canon_key in multi:
            plen = len(phrase_tuple)
            if i + plen > n:
                continue
            if tuple(lemmas[i:i + plen]) == phrase_tuple:
                result.append(canon_key)
                i += plen
                matched = True
                break
        if not matched:
            result.append(single.get(lemmas[i], lemmas[i]))
            i += 1

    return result


# ─────────────────────────────────────────────────────────────────────────────
# БАЗОВЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────────────────────────────────────

def split_into_chunks(text: str) -> list:
    chunks = []
    start  = 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s\.\,\!\?\-]', '', text)
    return text.strip()


def process_chunk(text: str, settings: dict) -> dict:
    """Обрабатывает один чанк через Natasha. Тезаурус здесь НЕ применяется."""
    doc = Doc(text)
    doc.segment(segmenter)

    tokens   = []
    lemmas   = []
    entities = []
    dates    = []

    if settings.get('morph', True):
        doc.tag_morph(morph_tagger)
        if settings.get('lemmatize', True):
            for token in doc.tokens:
                token.lemmatize(morph_vocab)

        min_len       = settings.get('minTokenLen', 2)
        use_stopwords = settings.get('stopwords', True)
        stop_custom   = set(
            w.strip() for w in settings.get('customStop', '').split('\n') if w.strip()
        )

        for token in doc.tokens:
            lemma = (token.lemma or token.text).lower()
            if len(lemma) < min_len:                        continue
            if token.pos in ('PUNCT', 'NUM', 'SYM', 'X'):  continue
            if use_stopwords and lemma in STOPWORDS_RU:     continue
            if lemma in stop_custom:                        continue
            tokens.append(token.text)
            lemmas.append(lemma)

    if settings.get('ner', True):
        doc.tag_ner(ner_tagger)
        for span in doc.spans:
            entities.append({'text': span.text, 'type': span.type})

    if settings.get('dates', True):
        for match in dates_extractor(text):
            dates.append({
                'text':  match.fact.as_json if hasattr(match.fact, 'as_json') else str(match.fact),
                'start': match.start,
                'stop':  match.stop,
            })

    return {'tokens': tokens, 'lemmas': lemmas, 'entities': entities, 'dates': dates}


# ─────────────────────────────────────────────────────────────────────────────
# ОБРАБОТКА ДОКУМЕНТА
# ─────────────────────────────────────────────────────────────────────────────

def process_document(raw: dict, settings: dict,
                     thesaurus_lookup: Optional[dict] = None) -> dict:
    """
    raw = { name, ext, text, error }

    Возвращает ДВА текстовых представления:
      text_raw   — исходный текст после clean_text()
                   → используется BERTopic для вычисления эмбеддингов
                   → BERT видит живой язык, пунктуацию, контекст
                   → даёт точную кластеризацию

      text_clean — леммы после Natasha + тезаурус
                   → используется BERTopic для c-TF-IDF (ключевые слова тем)
                   → только значимые термины, синонимы объединены
                   → даёт читаемые названия тем без мусора
    """
    print(f"[Natasha] обработка: {raw['name']}")

    # text_raw сохраняем ДО лемматизации — исходный очищенный текст
    text_raw = clean_text(raw['text'])
    chunks   = split_into_chunks(text_raw)
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

    # Тезаурус применяется ПОСЛЕ сборки всех чанков
    # (чтобы многословные фразы не разрывались на границах чанков)
    if thesaurus_lookup:
        before     = len(all_lemmas)
        all_lemmas = apply_thesaurus_to_lemmas(all_lemmas, thesaurus_lookup)
        after      = len(all_lemmas)
        print(f"[Thesaurus] '{raw['name']}': {before} → {after} лемм")

    seen = set()
    unique_entities = []
    for e in all_entities:
        key = (e['text'], e['type'])
        if key not in seen:
            seen.add(key)
            unique_entities.append(e)

    return {
        'name':         raw['name'],
        # ── Два представления текста ──────────────────────────────────────
        'text_raw':     text_raw,               # → эмбеддинги в BERTopic
        'text_clean':   ' '.join(all_lemmas),   # → c-TF-IDF в BERTopic
        # ─────────────────────────────────────────────────────────────────
        'tokens':       all_tokens,
        'lemmas':       all_lemmas,
        'entities':     unique_entities,
        'dates':        all_dates,
        'chunks_count': len(chunks),
        'tokens_count': len(all_tokens),
    }


def process_all(documents: list, settings: dict,
                thesaurus_raw: Optional[dict] = None) -> dict:
    """
    thesaurus_raw — { "канон": ["вариант1", ...] } из UI или None.
    lookup строится один раз для всех документов.
    """
    thesaurus_lookup = None
    if thesaurus_raw and isinstance(thesaurus_raw, dict) and len(thesaurus_raw) > 0:
        print(f"[Thesaurus] инициализация: {len(thesaurus_raw)} записей...")
        thesaurus_lookup = build_thesaurus_lookup(thesaurus_raw)
    else:
        print("[Thesaurus] не задан, пропускаем")

    results = []
    for raw in documents:
        if raw.get('error'):
            print(f"[Natasha] пропуск {raw['name']} — ошибка загрузки")
            continue
        results.append(process_document(raw, settings, thesaurus_lookup))

    return {
        'documents':         results,
        'total_tokens':      sum(r['tokens_count'] for r in results),
        'total_docs':        len(results),
        'thesaurus_applied': thesaurus_lookup is not None,
        'thesaurus_entries': len(thesaurus_raw) if thesaurus_raw else 0,
    }
