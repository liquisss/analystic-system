from __future__ import annotations
import re
from typing import Optional
from natasha import (
    Segmenter, MorphVocab, NewsEmbedding,
    NewsMorphTagger, NewsNERTagger,
    DatesExtractor, Doc
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
    'конечно','всю','между','рис','который','Рис',
}

segmenter       = Segmenter()
morph_vocab     = MorphVocab()
emb             = NewsEmbedding()
morph_tagger    = NewsMorphTagger(emb)
ner_tagger      = NewsNERTagger(emb)
dates_extractor = DatesExtractor(morph_vocab)

CHUNK_SIZE    = 3000
CHUNK_OVERLAP = 200


# ─────────────────────────────────────────────────────────────────────────────
# ТЕЗАУРУС
# ─────────────────────────────────────────────────────────────────────────────

def _lemmatize_single_word(word: str) -> str:
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
    single: dict = {}
    multi:  list = []

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


def _run_morph_chunk(text: str, settings: dict) -> tuple[list, list]:
    """Морфология одного чанка → (tokens, lemmas)."""
    doc = Doc(text)
    doc.segment(segmenter)
    doc.tag_morph(morph_tagger)
    for token in doc.tokens:
        token.lemmatize(morph_vocab)

    min_len       = settings.get('minTokenLen', 2)
    use_stopwords = settings.get('stopwords', True)
    stop_custom   = set(
        w.strip() for w in settings.get('customStop', '').split('\n') if w.strip()
    )

    tokens, lemmas = [], []
    for token in doc.tokens:
        lemma = (token.lemma or token.text).lower()
        if len(lemma) < min_len:                        continue
        if token.pos in ('PUNCT', 'NUM', 'SYM', 'X'):  continue
        if use_stopwords and lemma in STOPWORDS_RU:     continue
        if lemma in stop_custom:                        continue
        tokens.append(token.text)
        lemmas.append(lemma)
    return tokens, lemmas


def _run_ner_chunk(text: str, do_ner: bool, do_dates: bool) -> tuple[list, list]:
    """NER + даты одного чанка → (entities, dates)."""
    doc = Doc(text)
    doc.segment(segmenter)

    entities, dates = [], []

    if do_ner:
        doc.tag_ner(ner_tagger)
        for span in doc.spans:
            entities.append({'text': span.text, 'type': span.type})

    if do_dates:
        for match in dates_extractor(text):
            dates.append({
                'text':  match.fact.as_json
                         if hasattr(match.fact, 'as_json') else str(match.fact),
                'start': match.start,
                'stop':  match.stop,
            })
    return entities, dates


def _dedup_entities(entities: list) -> list:
    seen = set()
    out  = []
    for e in entities:
        key = (e['text'], e['type'])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# ОБРАБОТКА ДОКУМЕНТА
# ─────────────────────────────────────────────────────────────────────────────

def process_document(raw: dict, settings: dict,
                     thesaurus_lookup: Optional[dict] = None) -> dict:
    """
    Два режима определяются флагом fast_mode в raw:

    fast_mode=False (PDF/DOCX/TXT — обычный файл):
      - Морфология на полном тексте → text_clean (леммы)
      - NER + даты на полном тексте
      - Полное качество

    fast_mode=True (CSV/XLSX датасет):
      - Морфология ПРОПУСКАЕТСЯ → text_clean = ''
      - NER + даты только на ner_text (наименование + исполнитель + сроки)
      - BERTopic будет использовать text_raw напрямую через CountVectorizer
      - В 5-10 раз быстрее
    """
    is_fast  = raw.get('fast_mode', False)
    text_raw = clean_text(raw['text'])

    # Источник для NER: короткий текст для датасета, полный для обычного файла
    ner_source = clean_text(raw['ner_text']) \
        if is_fast and raw.get('ner_text') \
        else text_raw

    all_tokens:   list = []
    all_lemmas:   list = []
    all_entities: list = []
    all_dates:    list = []

    morph_chunks = split_into_chunks(text_raw)

    if not is_fast:
        # ── Полный режим: морфология на всём тексте ──────────────────────
        print(f"[Natasha] обработка: {raw['name']} ({len(morph_chunks)} чанков)")
        for chunk in morph_chunks:
            t, l = _run_morph_chunk(chunk, settings)
            all_tokens.extend(t)
            all_lemmas.extend(l)

        if thesaurus_lookup:
            all_lemmas = apply_thesaurus_to_lemmas(all_lemmas, thesaurus_lookup)

        # NER на полном тексте
        do_ner   = settings.get('ner',   True)
        do_dates = settings.get('dates', True)
        if do_ner or do_dates:
            for chunk in morph_chunks:
                e, d = _run_ner_chunk(chunk, do_ner, do_dates)
                all_entities.extend(e)
                all_dates.extend(d)

    else:
        # ── Fast mode: только NER на коротком тексте ─────────────────────
        # Морфология пропускается — text_clean будет пустым
        # BERTopic сам токенизирует text_raw через CountVectorizer
        do_ner   = settings.get('ner',   True)
        do_dates = settings.get('dates', True)
        if do_ner or do_dates:
            ner_chunks = split_into_chunks(ner_source)
            for chunk in ner_chunks:
                e, d = _run_ner_chunk(chunk, do_ner, do_dates)
                all_entities.extend(e)
                all_dates.extend(d)

    all_entities = _dedup_entities(all_entities)

    # Группируем сущности по типу для удобного отображения в UI
    entities_by_type = {}
    for e in all_entities:
        t = e['type']
        if t not in entities_by_type:
            entities_by_type[t] = []
        entities_by_type[t].append(e['text'])

    return {
        'name':             raw['name'],
        'reg_number':       raw.get('reg_number', ''),
        'title':            raw.get('title', raw['name']),

        # Два представления текста для BERTopic
        'text_raw':         text_raw,
        'text_clean':       ' '.join(all_lemmas),  # пусто при fast_mode

        # Для TopicDetailModal и отчётов
        'tokens':           all_tokens,
        'lemmas':           all_lemmas,
        'entities':         all_entities,
        'entities_by_type': entities_by_type,   # PER/ORG/LOC сгруппированы
        'dates':            all_dates,

        # Метрики
        'chunks_count':     len(morph_chunks),
        'tokens_count':     len(all_tokens),
        'entities_count':   len(all_entities),
        'dates_count':      len(all_dates),
        'fast_mode':        is_fast,
    }


def process_all(documents: list, settings: dict,
                thesaurus_raw: Optional[dict] = None) -> dict:
    thesaurus_lookup = None
    if thesaurus_raw and isinstance(thesaurus_raw, dict) and len(thesaurus_raw) > 0:
        print(f"[Thesaurus] инициализация: {len(thesaurus_raw)} записей...")
        thesaurus_lookup = build_thesaurus_lookup(thesaurus_raw)

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
