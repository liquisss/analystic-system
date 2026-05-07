from __future__ import annotations
import re
import math
import os
import numpy as np
from collections import Counter
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from umap import UMAP
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ── YAKE для извлечения меток тем ──
try:
    import yake as _yake
    _YAKE_AVAILABLE = True
    print("[BERTopic] YAKE загружен — используем умные метки тем")
except ImportError:
    _YAKE_AVAILABLE = False
    print("[BERTopic] yake не установлен — pip install yake (используем fallback метки)")

# ── Модель загружается один раз ──
_model_cache: dict = {}


def get_embedding_model(model_name: str):
    if model_name not in _model_cache:
        print(f"[BERTopic] загрузка модели: {model_name}")
        _model_cache[model_name] = SentenceTransformer(model_name, device='cpu')
    return _model_cache[model_name]


MODEL_MAP = {
    'rubert-tiny2':    'cointegrated/rubert-tiny2',
    'multilingual-e5': 'intfloat/multilingual-e5-small',
    'labse':           'sentence-transformers/LaBSE',
}

EXTRA_STOPWORDS_RU = {
    "это", "этот", "эта", "эти", "тот", "та", "те",
    "который", "которая", "которые", "которого", "которому",
    "свой", "своя", "свои", "своего", "своему",
    "весь", "вся", "все", "всё", "всего",
    "такой", "такая", "такие", "такого",
    "сам", "сама", "сами", "самого",
    "некоторый", "некоторые", "никакой",
    "любой", "каждый", "другой", "другие",
    "также", "тоже", "же", "ли", "бы", "ведь", "вот", "вон",
    "даже", "уже", "ещё", "ещe", "еще", "вдруг", "лишь",
    "почти", "просто", "именно", "особенно",
    "затем", "потом", "здесь", "там", "тут",
    "куда", "откуда", "где", "когда", "зачем", "почему",
    "чтобы", "чтоб", "хотя", "пока", "после", "перед",
    "через", "между", "около", "вместе", "вместо",
    "среди", "против", "кроме", "внутри",
    "снова", "опять", "вновь", "всегда", "никогда",
    "иногда", "часто", "редко", "быстро", "медленно",
    "очень", "слишком", "совсем", "абсолютно",
    "быть", "является", "являются", "есть", "нет", "нету",
    "будет", "будут", "был", "была", "были", "стать",
    "становится", "стал", "стала", "стали", "может",
    "могут", "должен", "должна", "должны", "надо", "нужно",
    "можно", "нельзя", "хотеть", "хочет", "хотят",
    "один", "два", "три", "первый", "второй", "третий",
    "много", "мало", "несколько", "немного",
}

_GARBAGE_RE = re.compile(
    r'^[^а-яёa-z]+$'
    r'|^\d+$'
    r'|^[а-яёa-z]{1,2}$',
    re.IGNORECASE
)


# ─────────────────────────────────────────────────────────────────────────────
# МЕТКИ ТЕМ — YAKE + fallback
# ─────────────────────────────────────────────────────────────────────────────

def _extract_label_yake(texts: list, fallback_words: list, topic_id: int) -> str:
    """
    Извлекает значимое словосочетание из текстов темы через YAKE.
    YAKE — статистический алгоритм без нейросетей, работает для русского.

    Находит фразы которые:
    - часто встречаются в данной теме
    - редки в остальном тексте (специфичны для темы)
    - находятся в значимых позициях (начало предложения)

    Скорость: ~5-15мс на тему — пренебрежимо мало.
    """
    if not _YAKE_AVAILABLE or not texts:
        return _make_topic_label_fallback(fallback_words, topic_id)

    # Берём топ-15 документов темы — YAKE хватает
    combined = ' '.join(t[:1000] for t in texts[:15])
    if len(combined) < 30:
        return _make_topic_label_fallback(fallback_words, topic_id)

    try:
        extractor = _yake.KeywordExtractor(
            lan="ru",
            n=3,            # до 3-словных фраз
            dedupLim=0.7,   # убираем почти-дубли
            dedupFunc='seqm',
            windowsSize=2,
            top=15,
            features=None,
        )
        keywords = extractor.extract_keywords(combined)

        if not keywords:
            return _make_topic_label_fallback(fallback_words, topic_id)

        # Фильтр: хотим 2-3-словные фразы без мусора
        good = []
        for phrase, score in keywords:
            phrase = phrase.strip()
            words_in_phrase = phrase.split()

            if len(words_in_phrase) < 2:
                continue
            if any(w.isdigit() for w in words_in_phrase):
                continue
            if any(len(w) < 3 for w in words_in_phrase):
                continue
            if any(w.lower() in EXTRA_STOPWORDS_RU for w in words_in_phrase):
                continue
            # Нет спецсимволов
            if re.search(r'[^\w\s\-]', phrase):
                continue

            good.append((phrase, score))

        if good:
            # YAKE: меньший score = лучше
            best_phrase = good[0][0]
            label = best_phrase[0].upper() + best_phrase[1:]
            return label[:50] + '...' if len(label) > 50 else label

        return _make_topic_label_fallback(fallback_words, topic_id)

    except Exception as e:
        print(f"[BERTopic] YAKE ошибка для темы {topic_id}: {e}")
        return _make_topic_label_fallback(fallback_words, topic_id)


def _make_topic_label_fallback(words: list, topic_id: int) -> str:
    """
    Fallback метка: берёт два наиболее информативных слова из c-TF-IDF.
    Улучшен по сравнению с оригиналом: избегает коротких слов и
    слов с общим корнем.
    """
    if not words:
        return f"Тема {topic_id}"

    seen, dedup = [], []
    for w in words[:8]:
        wl = w.lower()
        if wl not in seen and len(w) >= 4:
            seen.append(wl)
            dedup.append(w)

    if not dedup:
        return f"Тема {topic_id}"
    if len(dedup) == 1:
        return dedup[0].capitalize()

    w1 = dedup[0]
    # Избегаем слов с общим корнем (первые 4 символа)
    w2 = next(
        (w for w in dedup[1:] if not w.lower().startswith(w1.lower()[:4])),
        dedup[1]
    )
    label = f"{w1} {w2}".capitalize()
    return label[:47] + '...' if len(label) > 47 else label


# Алиас для обратной совместимости
_make_topic_label = _make_topic_label_fallback


# ─────────────────────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────────────────────────────────────

def _is_valid_word(word: str, extra_stop: set) -> bool:
    w = word.lower().strip()
    if _GARBAGE_RE.match(w):    return False
    if w in EXTRA_STOPWORDS_RU: return False
    if w in extra_stop:         return False
    return True


def _mmr_select_words(
    words_scores: list,
    model,
    n: int = 10,
    diversity: float = 0.6,
    extra_stop: set = None,
) -> list:
    """
    Maximal Marginal Relevance — выбирает разнообразные ключевые слова.
    Баланс между релевантностью (высокий c-TF-IDF) и разнообразием
    (не выбирать похожие слова).
    """
    if extra_stop is None:
        extra_stop = set()

    candidates = [
        (w, s) for w, s in words_scores
        if _is_valid_word(w, extra_stop) and s > 0.0
    ]
    if not candidates:
        return []
    if len(candidates) <= n:
        return candidates

    words  = [w for w, _ in candidates]
    scores = np.array([s for _, s in candidates])

    rel = scores / scores.max() if scores.max() > 0 else scores

    try:
        embeddings = model.encode(words, show_progress_bar=False)
        sim_matrix = cosine_similarity(embeddings)
    except Exception:
        return candidates[:n]

    selected_idx = []
    remaining    = list(range(len(words)))

    best = int(np.argmax(rel))
    selected_idx.append(best)
    remaining.remove(best)

    while len(selected_idx) < n and remaining:
        mmr_scores = []
        for i in remaining:
            max_sim = max(sim_matrix[i][j] for j in selected_idx)
            mmr     = (1 - diversity) * rel[i] - diversity * max_sim
            mmr_scores.append((i, mmr))
        best_i = max(mmr_scores, key=lambda x: x[1])[0]
        selected_idx.append(best_i)
        remaining.remove(best_i)

    return sorted(
        [(words[i], float(scores[i])) for i in selected_idx],
        key=lambda x: -x[1],
    )


def compute_npmi_coherence(topics: list, texts: list, top_n: int = 5) -> float:
    """
    Нормализованная попарная взаимная информация (NPMI).
    Измеряет насколько ключевые слова темы встречаются вместе в документах.
    Значение 100% = идеальная когерентность.
    """
    if not topics or not texts:
        return 0.0
    n = len(texts)
    if n == 0:
        return 0.0

    tokenized = [
        set(re.findall(r'[а-яёa-z]+', text.lower()))
        for text in texts
    ]
    word_freq: Counter = Counter()
    for tokens in tokenized:
        for w in tokens:
            word_freq[w] += 1

    def freq_pair(a: str, b: str) -> int:
        return sum(1 for tokens in tokenized if a in tokens and b in tokens)

    all_pairs: list = []

    for topic in topics:
        words = [w.lower() for w in topic.get('words', [])[:top_n]]
        if len(words) < 2:
            continue
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                a, b = words[i], words[j]
                fa   = word_freq.get(a, 0)
                fb   = word_freq.get(b, 0)
                fab  = freq_pair(a, b)
                if fa == 0 or fb == 0:
                    all_pairs.append(0.0)
                    continue
                pa  = fa  / n
                pb  = fb  / n
                pab = (fab + 0.5) / n
                pmi     = math.log2(pab / (pa * pb)) if pa * pb > 0 else 0.0
                pmi_max = -math.log2(max(pa, pb))
                npmi    = pmi / pmi_max if pmi_max > 0 else 0.0
                all_pairs.append(max(0.0, min(1.0, npmi)))

    if not all_pairs:
        return 0.0
    return round(float(np.mean(all_pairs)) * 100, 1)


def get_text_embedding_with_window(
    text: str, model, window: int = 256, stride: int = 128
) -> np.ndarray:
    """Скользящее окно для длинных текстов (> 250 слов)."""
    words = text.split()
    if not words:
        return np.zeros(model.get_sentence_embedding_dimension())

    chunks = []
    start  = 0
    while start < len(words):
        chunks.append(' '.join(words[start:start + window]))
        start += stride
        if start >= len(words):
            break

    embeddings = model.encode(chunks, show_progress_bar=False)
    return np.mean(embeddings, axis=0)


# ─────────────────────────────────────────────────────────────────────────────
# КАРТА КЛЮЧЕВЫХ СЛОВ — реальные эмбеддинги слов
# ─────────────────────────────────────────────────────────────────────────────

def build_keywords_vos_data(topics: list, embedding_model,
                             top_n_words: int = 8) -> dict:
    """
    Строит VOSviewer JSON для карты ключевых слов.

    Стратегия связей:
    - Внутрикластерные: strength = sim * BOOST (3.0) → слова темы держатся вместе
    - Межкластерные: только топ-3 на каждую пару → кластеры расходятся
    - Разные пороги: внутри 0.25 (мягкий), между 0.55 (строгий)
    """
    if not topics:
        return {}

    word_meta: dict = {}
    for t_idx, topic in enumerate(topics):
        words  = topic['words'][:top_n_words]
        scores = topic['scores'][:top_n_words]
        for w, s in zip(words, scores):
            key = w.lower()
            if key not in word_meta or s > word_meta[key]['score']:
                word_meta[key] = {
                    'label':       w,
                    'cluster':     t_idx + 1,
                    'cluster_idx': t_idx,
                    'score':       float(s),
                    'count':       topic['count'],
                }

    if len(word_meta) < 2:
        return {}

    all_words = list(word_meta.keys())
    labels    = [word_meta[w]['label'] for w in all_words]
    n         = len(all_words)

    print(f"[Keywords VOS] кодируем {len(labels)} слов...")
    try:
        word_embeddings = embedding_model.encode(
            labels, show_progress_bar=False, batch_size=64
        )
    except Exception as e:
        print(f"[Keywords VOS] ошибка кодирования: {e}")
        return {}

    sim_matrix = cosine_similarity(word_embeddings)
    max_score  = max(m['score'] for m in word_meta.values()) or 1.0

    INTRA_THRESHOLD = 0.25
    CROSS_THRESHOLD = 0.55
    INTRA_BOOST     = 3.0
    CROSS_TOP_N     = 3

    items = []
    for idx, w in enumerate(all_words):
        meta  = word_meta[w]
        score = meta['score']
        items.append({
            "id":      idx + 1,
            "label":   meta['label'],
            "cluster": meta['cluster'],
            "weights": {
                "Score":     round((score / max_score) * 100, 2),
                "Documents": meta['count'],
            },
            "scores": {"TF-IDF": round(score, 6)},
        })

    intra_links = []
    for i in range(n):
        for j in range(i + 1, n):
            if word_meta[all_words[i]]['cluster_idx'] != word_meta[all_words[j]]['cluster_idx']:
                continue
            sim = float(sim_matrix[i][j])
            if sim >= INTRA_THRESHOLD:
                intra_links.append({
                    "source_id": i + 1,
                    "target_id": j + 1,
                    "strength":  round(sim * INTRA_BOOST, 4),
                })

    cross_candidates: dict = {}
    for i in range(n):
        for j in range(i + 1, n):
            ci = word_meta[all_words[i]]['cluster_idx']
            cj = word_meta[all_words[j]]['cluster_idx']
            if ci == cj:
                continue
            sim = float(sim_matrix[i][j])
            if sim < CROSS_THRESHOLD:
                continue
            key = (min(ci, cj), max(ci, cj))
            cross_candidates.setdefault(key, []).append((sim, i, j))

    cross_links = []
    for key, candidates in cross_candidates.items():
        for sim, i, j in sorted(candidates, key=lambda x: -x[0])[:CROSS_TOP_N]:
            cross_links.append({
                "source_id": i + 1,
                "target_id": j + 1,
                "strength":  round(sim, 4),
            })

    links = intra_links + cross_links
    print(f"[Keywords VOS] узлов: {len(items)}, внутри: {len(intra_links)}, мосты: {len(cross_links)}")

    if not intra_links:
        print("[Keywords VOS] нет внутрикластерных связей, снижаем порог до 0.15")
        for i in range(n):
            for j in range(i + 1, n):
                if word_meta[all_words[i]]['cluster_idx'] != word_meta[all_words[j]]['cluster_idx']:
                    continue
                sim = float(sim_matrix[i][j])
                if sim >= 0.15:
                    links.append({
                        "source_id": i + 1,
                        "target_id": j + 1,
                        "strength":  round(sim * INTRA_BOOST, 4),
                    })

    return {"network": {"items": items, "links": links}}


# ─────────────────────────────────────────────────────────────────────────────
# ОСНОВНАЯ ФУНКЦИЯ
# ─────────────────────────────────────────────────────────────────────────────

def run_bertopic(settings: dict, natasha_data: dict) -> dict:
    """
    Hybrid BERTopic:
      text_raw   → батчевые эмбеддинги → UMAP + HDBSCAN (кластеризация)
      text_clean → CountVectorizer → c-TF-IDF (ключевые слова тем)

    Оптимизации для больших датасетов:
      - Батч 256 для эмбеддингов (в 3-4x быстрее)
      - eom/leaf в зависимости от размера
      - Нет split больших тем (экономия 10-30% времени)
      - YAKE для умных меток тем
    """
    documents = natasha_data.get('documents', [])
    if not documents:
        raise ValueError("Нет документов для анализа")

    raw_pairs = [
        (
            d.get('text_raw') or d.get('text_clean') or d.get('text', ''),
            # text_clean пустой при fast_mode → BERTopic использует text_raw напрямую
            d.get('text_clean') or d.get('text_raw') or d.get('text', ''),
            d['name'],
        )
        for d in documents
        if (d.get('text_raw') or d.get('text_clean') or d.get('text', '')).strip()
    ]

    if not raw_pairs:
        raise ValueError("Все документы пустые после предобработки")
    if len(raw_pairs) < 2:
        raise ValueError("Нужно минимум 2 документа для анализа")

    texts_raw, texts_clean, names = zip(*raw_pairs)
    texts_raw   = list(texts_raw)
    texts_clean = list(texts_clean)
    names       = list(names)

    n = len(texts_raw)
    print(f"[BERTopic] документов: {n}")

    custom_stop_raw = settings.get('customStop', '')
    user_stop = {
        w.strip().lower()
        for w in custom_stop_raw.split('\n') if w.strip()
    }
    all_stop = EXTRA_STOPWORDS_RU | user_stop

    model_key       = settings.get('model', 'rubert-tiny2')
    model_name      = MODEL_MAP.get(model_key, MODEL_MAP['rubert-tiny2'])
    embedding_model = get_embedding_model(model_name)

    # ── Эмбеддинги — батчевые ────────────────────────────────────────────────
    print(f"[BERTopic] эмбеддинги: {n} документов...")
    avg_words = sum(len(t.split()) for t in texts_raw) / max(n, 1)

    # Большой батч = меньше накладных расходов на запуск вычислений
    # 256 на CPU даёт в 3-4x прирост vs 32-64
    BATCH = 256 if n > 500 else 128

    if avg_words <= 250:
        # Короткие тексты (аннотации, заголовки) — прямое батчевое кодирование
        print(f"[BERTopic] батч={BATCH}, avg={avg_words:.0f} слов → прямое кодирование")
        doc_embeddings = embedding_model.encode(
            texts_raw,
            batch_size=BATCH,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=False,
        )
    else:
        # Длинные тексты — скользящее окно + батч внутри
        print(f"[BERTopic] avg={avg_words:.0f} слов → скользящее окно")
        doc_embeddings = []
        for i, text in enumerate(texts_raw):
            if i % 100 == 0:
                print(f"[BERTopic] embedding {i}/{n}...")
            doc_embeddings.append(
                get_text_embedding_with_window(text, embedding_model)
            )
        doc_embeddings = np.array(doc_embeddings)

    # ── UMAP ─────────────────────────────────────────────────────────────────
    n_comp = settings.get('umapComp', 5)
    if n < 10:
        from bertopic.dimensionality import BaseDimensionalityReduction
        umap_model = BaseDimensionalityReduction()
    else:
        # Для больших датасетов больше соседей = лучше глобальная структура
        if n > 1000:
            n_neighbors = max(2, min(50, n // 20))
        else:
            n_neighbors = max(2, min(15, n // 8))

        umap_model = UMAP(
            n_components=min(n_comp, n - 2),
            n_neighbors=n_neighbors,
            min_dist=0.0,
            metric='cosine',
            random_state=42,
            low_memory=True,
        )
        print(f"[BERTopic] UMAP: n_neighbors={n_neighbors}, n_components={min(n_comp, n-2)}")

    # ── HDBSCAN ──────────────────────────────────────────────────────────────
    # min_cs из настроек UI (minTopic) или автоматически
    if n < 15:
        min_cs = 2
    elif n < 40:
        min_cs = max(2, n // 10)
    else:
        min_cs = max(2, n // 15)

    # Читаем из UI — поддерживаем оба варианта названия настройки
    user_min_cs = settings.get('minTopic') or settings.get('minClusterSize')
    if user_min_cs:
        min_cs = int(user_min_cs)

    # leaf лучше на малых датасетах (< 300 docs) — находит мелкие кластеры
    # eom лучше на больших — более стабильные крупные темы
    cluster_method = 'leaf' if n < 100 else 'eom'
    print(f"[BERTopic] HDBSCAN: min_cluster_size={min_cs}, method={cluster_method}")

    hdbscan_model = HDBSCAN(
        min_cluster_size=min_cs,
        min_samples=1,
        cluster_selection_epsilon=0.0,
        metric='euclidean',
        prediction_data=True,
        cluster_selection_method=cluster_method,
    )

    # ── CountVectorizer ───────────────────────────────────────────────────────
    vectorizer = CountVectorizer(
        min_df=max(1, min(2, n // 5)),
        max_df=0.85,
        ngram_range=(1, 2),
        max_features=8000,
        stop_words=list(all_stop),
        token_pattern=r'(?u)\b[а-яёa-zA-Z]{3,}\b',
    )

    num_topics_raw = settings.get('numTopics', 'auto')
    nr_topics      = None if num_topics_raw == 'auto' else int(num_topics_raw)

    topic_model = BERTopic(
        embedding_model=embedding_model,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        nr_topics=nr_topics,
        calculate_probabilities=False,
        verbose=True,
    )

    print("[BERTopic] обучение модели...")
    topics, _ = topic_model.fit_transform(
        texts_clean,
        embeddings=doc_embeddings
    )

    if settings.get('outlierReduce', True) and n >= 10:
        try:
            print("[BERTopic] снижение шума...")
            topics = topic_model.reduce_outliers(
                texts_clean, topics,
                strategy="embeddings",
                embeddings=doc_embeddings,
            )
        except ValueError as e:
            print(f"[BERTopic] снижение шума пропущено: {e}")

    # ── Индекс текстов по теме — для YAKE ────────────────────────────────────
    # Берём не более 15 текстов на тему — YAKE хватает, скорость не страдает
    topic_texts_index: dict = {}
    for idx, topic_id in enumerate(topics):
        if topic_id == -1:
            continue
        if topic_id not in topic_texts_index:
            topic_texts_index[topic_id] = []
        if len(topic_texts_index[topic_id]) < 15:
            topic_texts_index[topic_id].append(texts_raw[idx])

    # ── Формирование тем ──────────────────────────────────────────────────────
    topic_info    = topic_model.get_topic_info()
    result_topics = []
    used_labels   = set()
    diversity     = float(settings.get('diversity', 0.6))

    for _, row in topic_info.iterrows():
        tid = int(row['Topic'])
        if tid == -1:
            continue

        raw_words_scores = topic_model.get_topic(tid) or []

        selected = _mmr_select_words(
            words_scores=raw_words_scores,
            model=embedding_model,
            n=10,
            diversity=diversity,
            extra_stop=all_stop,
        )
        if not selected:
            selected = [
                (w, s) for w, s in raw_words_scores[:10]
                if _is_valid_word(w, all_stop)
            ]

        words  = [w for w, _ in selected]
        scores = [round(float(s), 4) for _, s in selected]

        # YAKE: извлекаем умную метку из реальных текстов темы
        topic_docs_texts = topic_texts_index.get(tid, [])
        label = _extract_label_yake(topic_docs_texts, words, tid)

        # Дедупликация меток
        if label.lower() in used_labels:
            # Пробуем fallback с другими словами
            label = _make_topic_label_fallback(
                [words[0]] + (words[2:] if len(words) > 2 else words[1:]), tid
            )
        if label.lower() in used_labels:
            label = f"{label} ({tid})"
        used_labels.add(label.lower())

        result_topics.append({
            'id':     tid,
            'label':  label,
            'count':  int(row['Count']),
            'words':  words,
            'scores': scores,
        })

    # ── Эмбеддинги тем (для VOSviewer) ───────────────────────────────────────
    topic_embeddings = None
    try:
        all_emb = topic_model.topic_embeddings_
        if all_emb is not None:
            valid = []
            for t in result_topics:
                idx = t['id'] + 1
                if idx < len(all_emb):
                    valid.append(all_emb[idx])
                else:
                    print(f"[BERTopic] нет embedding для темы {t['id']}")
            if len(valid) == len(result_topics):
                topic_embeddings = np.array(valid)
                print(f"[BERTopic] embeddings тем: {topic_embeddings.shape}")
    except Exception as e:
        print(f"[BERTopic] embeddings тем недоступны: {e}")

    # ── 2D UMAP для карты документов ─────────────────────────────────────────
    doc_positions = None
    try:
        print("[BERTopic] 2D позиции для карты документов...")
        umap_2d = UMAP(
            n_components=2,
            n_neighbors=max(2, min(15, n // 5)),
            min_dist=0.1,
            metric='cosine',
            random_state=42,
            low_memory=True,
        )
        positions_2d = umap_2d.fit_transform(doc_embeddings)
        doc_positions = [
            {'x': round(float(p[0]), 4), 'y': round(float(p[1]), 4)}
            for p in positions_2d
        ]
        print(f"[BERTopic] 2D позиции готовы: {len(doc_positions)} документов")
    except Exception as e:
        print(f"[BERTopic] 2D UMAP ошибка: {e}")

    # ── doc_topics + шум ──────────────────────────────────────────────────────
    doc_topics  = [{'name': nm, 'topic': int(t)} for nm, t in zip(names, topics)]
    noise_count = sum(1 for t in topics if t == -1)
    noise_pct   = round(noise_count / len(topics) * 100, 1)

    # ── Когерентность ─────────────────────────────────────────────────────────
    print("[BERTopic] вычисление NPMI когерентности...")
    coherence = compute_npmi_coherence(result_topics, texts_clean, top_n=5)
    print(f"[BERTopic] когерентность: {coherence}%")
    print(f"[BERTopic] тем: {len(result_topics)}, шум: {noise_pct}%")

    # ── Карта ключевых слов ───────────────────────────────────────────────────
    print("[BERTopic] строим карту ключевых слов...")
    keywords_vos_data = build_keywords_vos_data(
        topics=result_topics,
        embedding_model=embedding_model,
        top_n_words=8,
    )

    return {
        'topics':            result_topics,
        'doc_topics':        doc_topics,
        'total_docs':        len(texts_raw),
        'noise_count':       noise_count,
        'noise_pct':         noise_pct,
        'coherence':         coherence,
        'topic_embeddings':  topic_embeddings.tolist() if topic_embeddings is not None else None,
        'keywords_vos_data': keywords_vos_data,
        'doc_positions':     doc_positions,
    }


# ─────────────────────────────────────────────────────────────────────────────
# VOSviewer для кластеров тем
# ─────────────────────────────────────────────────────────────────────────────

def build_vosviewer_json(bertopic_result: dict) -> dict:
    topics           = bertopic_result.get('topics', [])
    topic_embeddings = bertopic_result.get('topic_embeddings', None)

    if not topics:
        return {}

    items = []
    for i, t in enumerate(topics):
        items.append({
            "id":      t['id'] + 1,
            "label":   t['label'],
            "cluster": i + 1,
            "weights": {"Documents": t['count']},
            "scores":  {
                "Avg. score": round(
                    float(sum(t['scores']) / len(t['scores'])), 4
                ) if t['scores'] else 0.0
            },
        })

    links = []

    if topic_embeddings is not None and len(topic_embeddings) >= 2:
        emb_matrix = np.array(topic_embeddings)
        if len(emb_matrix) != len(topics):
            print("[VOSviewer] несовпадение размеров, используем fallback")
            topic_embeddings = None
        else:
            sim_matrix = cosine_similarity(emb_matrix)
            n = len(topics)
            for i in range(n):
                for j in range(i + 1, n):
                    sim = float(sim_matrix[i][j])
                    if sim > 0.1:
                        links.append({
                            "source_id": topics[i]['id'] + 1,
                            "target_id": topics[j]['id'] + 1,
                            "strength":  round(sim, 4),
                        })
            print(f"[VOSviewer] реальных связей: {len(links)}")

    if not links:
        print("[VOSviewer] fallback: связи по пересечению слов")
        for i, t1 in enumerate(topics):
            for j, t2 in enumerate(topics):
                if j <= i:
                    continue
                shared = set(t1['words']) & set(t2['words'])
                if shared:
                    strength = round(
                        len(shared) / max(len(t1['words']), len(t2['words'])), 4
                    )
                    links.append({
                        "source_id": t1['id'] + 1,
                        "target_id": t2['id'] + 1,
                        "strength":  strength,
                    })

    print(f"[VOSviewer] узлов: {len(items)}, связей: {len(links)}")
    return {"network": {"items": items, "links": links}}
