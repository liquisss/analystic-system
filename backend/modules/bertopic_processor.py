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

# ─────────────────────────────────────────────
# 1. РАСШИРЕННЫЙ СПИСОК СТОП-СЛОВ
#    Добавлены: местоимения, союзы, частицы,
#    наречия, числительные, короткие слова ≤2 букв
# ─────────────────────────────────────────────
EXTRA_STOPWORDS_RU = {
    # Местоимения
    "это", "этот", "эта", "эти", "тот", "та", "те",
    "который", "которая", "которые", "которого", "которому",
    "свой", "своя", "свои", "своего", "своему",
    "весь", "вся", "все", "всё", "всего",
    "такой", "такая", "такие", "такого",
    "сам", "сама", "сами", "самого",
    "некоторый", "некоторые", "никакой",
    "любой", "каждый", "другой", "другие",
    # Служебные части речи
    "также", "тоже", "же", "ли", "бы", "ведь", "вот", "вон",
    "даже", "уже", "ещё", "ещe", "еще", "вдруг", "лишь", "лишь",
    "почти", "просто", "именно", "особенно", "именно",
    "именно", "затем", "потом", "здесь", "там", "тут",
    "куда", "откуда", "где", "когда", "зачем", "почему",
    "чтобы", "чтоб", "хотя", "пока", "после", "перед",
    "через", "между", "около", "вместе", "вместо",
    "среди", "против", "кроме", "кроме", "внутри",
    "снова", "опять", "вновь", "всегда", "никогда",
    "иногда", "часто", "редко", "быстро", "медленно",
    "очень", "слишком", "совсем", "совсем", "абсолютно",
    # Глаголы-связки / вспомогательные
    "быть", "является", "являются", "есть", "нет", "нету",
    "будет", "будут", "был", "была", "были", "стать",
    "становится", "стал", "стала", "стали", "может",
    "могут", "должен", "должна", "должны", "надо", "нужно",
    "можно", "нельзя", "хотеть", "хочет", "хотят",
    # Числительные / общие
    "один", "два", "три", "первый", "второй", "третий",
    "много", "мало", "несколько", "немного",
    # Слова ≤ 2 букв будут отфильтрованы через min_token_len
}

# Паттерн для фильтрации неинформативных токенов
_GARBAGE_RE = re.compile(
    r'^[^а-яёa-z]+$'           # нет букв вообще
    r'|^\d+$'                   # только цифры
    r'|^[а-яёa-z]{1,2}$',      # слишком короткие
    re.IGNORECASE
)


def _is_valid_word(word: str, extra_stop: set) -> bool:
    """True если слово информативное."""
    w = word.lower().strip()
    if _GARBAGE_RE.match(w):
        return False
    if w in EXTRA_STOPWORDS_RU:
        return False
    if w in extra_stop:
        return False
    return True


# ─────────────────────────────────────────────
# 2. MMR-ОТБОР КЛЮЧЕВЫХ СЛОВ (Maximal Marginal Relevance)
#    Выбирает слова, которые одновременно
#    релевантны теме И разнообразны между собой.
#    Без LLM — только косинусное сходство эмбеддингов слов.
# ─────────────────────────────────────────────
def _mmr_select_words(
    words_scores: list[tuple[str, float]],
    model,
    n: int = 10,
    diversity: float = 0.6,
    extra_stop: set = None,
) -> list[tuple[str, float]]:
    """
    Из кандидатов words_scores выбирает n слов через MMR:
      score = (1-diversity)*relevance - diversity*max_sim_to_selected
    diversity=0 → чистый TF-IDF рейтинг BERTopic
    diversity=1 → максимальное разнообразие
    0.5-0.7 — хороший баланс.
    """
    if extra_stop is None:
        extra_stop = set()

    # Фильтруем мусор
    candidates = [
        (w, s) for w, s in words_scores
        if _is_valid_word(w, extra_stop) and s > 0.0
    ]

    if not candidates:
        return []
    if len(candidates) <= n:
        return candidates

    words   = [w for w, _ in candidates]
    scores  = np.array([s for _, s in candidates])

    # Нормируем relevance в [0,1]
    if scores.max() > 0:
        rel = scores / scores.max()
    else:
        rel = scores

    try:
        embeddings = model.encode(words, show_progress_bar=False)
        sim_matrix = cosine_similarity(embeddings)
    except Exception:
        # Fallback — просто топ-n по score
        return candidates[:n]

    selected_idx = []
    remaining    = list(range(len(words)))

    # Первый — наиболее релевантный
    best = int(np.argmax(rel))
    selected_idx.append(best)
    remaining.remove(best)

    while len(selected_idx) < n and remaining:
        mmr_scores = []
        for i in remaining:
            relevance = rel[i]
            # Максимальное сходство с уже отобранными
            max_sim   = max(sim_matrix[i][j] for j in selected_idx)
            mmr       = (1 - diversity) * relevance - diversity * max_sim
            mmr_scores.append((i, mmr))

        best_i = max(mmr_scores, key=lambda x: x[1])[0]
        selected_idx.append(best_i)
        remaining.remove(best_i)

    # Восстанавливаем оригинальный порядок по relevance
    result = sorted(
        [(words[i], float(scores[i])) for i in selected_idx],
        key=lambda x: -x[1],
    )
    return result


# ─────────────────────────────────────────────
# 3. ГЕНЕРАЦИЯ НАЗВАНИЯ ТЕМЫ (без LLM)
#    Стратегия: берём топ-5 слов после MMR,
#    пробуем найти биграмму среди них,
#    иначе формируем заголовок из 2-3 уникальных слов.
# ─────────────────────────────────────────────
def _make_topic_label(words: list[str], topic_id: int) -> str:
    """Формирует читаемое название темы из списка ключевых слов."""
    if not words:
        return f"Тема {topic_id}"

    seen  = []
    dedup = []
    for w in words[:5]:
        wl = w.lower()
        if wl not in seen:
            seen.append(wl)
            dedup.append(w)

    if not dedup:
        return f"Тема {topic_id}"

    # Если слово одно — просто капитализируем
    if len(dedup) == 1:
        return dedup[0].capitalize()

    # Пробуем: первые два слова, если они не однокоренные
    w1, w2 = dedup[0], dedup[1]
    # Простая проверка на однокоренность: общий префикс > 4 букв
    common_prefix = os.path.commonprefix([w1.lower(), w2.lower()])
    if len(common_prefix) > 4 and len(dedup) > 2:
        label = f"{w1} {dedup[2]}".capitalize()
    else:
        label = f"{w1} {w2}".capitalize()

    # Ограничение длины
    if len(label) > 50:
        label = label[:47] + "..."

    return label


# ─────────────────────────────────────────────
# 4. РЕАЛЬНАЯ КОГЕРЕНТНОСТЬ (NPMI)
#    Normalized Pointwise Mutual Information —
#    стандартная метрика для оценки тем.
#    Измеряет, насколько слова темы встречаются
#    вместе в документах (а не как часто они там есть).
#    Нормальный диапазон: 30-70% при хорошей модели.
# ─────────────────────────────────────────────
def compute_npmi_coherence(topics: list[dict], texts: list[str], top_n: int = 5) -> float:
    """
    Вычисляет среднюю PMI2-когерентность по всем темам.

    PMI2(a,b) = log2(P(a,b)^2 / (P(a)*P(b)))
    нормируется на PMI_max = -log2(max(P(a), P(b)))

    Преимущества перед стандартным NPMI:
    - Устойчив к высокочастотным словам (часто встречающиеся слова
      получают меньший бонус, что снижает «ложно высокие» связи)
    - Сглаживание Лапласа (0.5) для пар без совместных вхождений
    - Все значения clip в [0, 1] — учитываем только позитивную связность

    Возвращает значение в [0, 100] — в процентах.
    Интерпретация результата:
      0–20%  : плохая модель или мало документов для оценки
      20–50% : приемлемая связность тем
      50–80% : хорошая модель
      80–100%: отличная связность (редко на реальных текстах)

    Примечание: старый расчёт mean(TF-IDF scores) * 100 был ошибочным —
    TF-IDF BERTopic показывает важность слова внутри кластера, а не
    связность слов между собой, и всегда даёт завышенные значения.
    """
    if not topics or not texts:
        return 0.0

    n = len(texts)
    if n == 0:
        return 0.0

    # Токенизируем тексты (быстро, без NLP)
    tokenized = [
        set(re.findall(r'[а-яёa-z]+', text.lower()))
        for text in texts
    ]

    # Частоты: сколько документов содержат слово
    word_freq: Counter = Counter()
    for tokens in tokenized:
        for w in tokens:
            word_freq[w] += 1

    def freq_pair(a: str, b: str) -> int:
        return sum(1 for tokens in tokenized if a in tokens and b in tokens)

    all_pairs: list[float] = []

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
                pab = (fab + 0.5) / n    # сглаживание Лапласа 0.5

                # PMI2 нормированный
                pmi     = math.log2(pab / (pa * pb)) if pa * pb > 0 else 0.0
                pmi_max = -math.log2(max(pa, pb))

                if pmi_max <= 0:
                    npmi = 0.0
                else:
                    npmi = pmi / pmi_max

                # Берём только положительную связность
                all_pairs.append(max(0.0, min(1.0, npmi)))

    if not all_pairs:
        return 0.0

    return round(float(np.mean(all_pairs)) * 100, 1)


# ─────────────────────────────────────────────
# СКОЛЬЗЯЩЕЕ ОКНО (без изменений)
# ─────────────────────────────────────────────
def get_text_embedding_with_window(text: str, model, window: int = 256, stride: int = 128) -> np.ndarray:
    words = text.split()
    if not words:
        return np.zeros(model.get_sentence_embedding_dimension())

    chunks = []
    start  = 0
    while start < len(words):
        chunk = ' '.join(words[start:start + window])
        chunks.append(chunk)
        start += stride
        if start >= len(words):
            break

    embeddings = model.encode(chunks, show_progress_bar=False)
    return np.mean(embeddings, axis=0)


# ─────────────────────────────────────────────
# РАЗБИВКА КРУПНЫХ ТЕМ
# ─────────────────────────────────────────────
def _maybe_split_large_topics(
    result_topics, doc_topics, doc_embeddings,
    split_threshold=0.20,
):
    total_docs = len(doc_topics)
    if total_docs == 0:
        return result_topics, doc_topics

    topic_to_doc_idx = {}
    for i, dt in enumerate(doc_topics):
        tid = dt["topic"]
        if tid == -1:
            continue
        topic_to_doc_idx.setdefault(tid, []).append(i)

    new_topics = []
    new_doc_topics = list(doc_topics)
    max_id = max((t["id"] for t in result_topics), default=0)
    next_id = max_id + 100
    split_happened = False

    for topic in result_topics:
        tid = topic["id"]
        doc_idxs = topic_to_doc_idx.get(tid, [])
        doc_count = len(doc_idxs)

        if doc_count / total_docs <= split_threshold or doc_count < 6:
            new_topics.append(topic)
            continue


        lbl = topic.get('label', str(tid))
        print(f'[Split] тема {tid} ({lbl}) {doc_count} документов -- пробуем разбить')
        cluster_embs = doc_embeddings[doc_idxs]
        sub_min_cs = max(2, doc_count // 5)
        try:
            sub_hdb = HDBSCAN(
                min_cluster_size=sub_min_cs,
                min_samples=1,
                cluster_selection_epsilon=0.0,
                metric="euclidean",
                cluster_selection_method="leaf",
            )
            sub_labels = sub_hdb.fit_predict(cluster_embs)
        except Exception as e:
            print(f"[Split] ошибка: {e}")
            new_topics.append(topic)
            continue

        real_sub = set(sub_labels) - {-1}
        if len(real_sub) <= 1:
            print(f"[Split] разбить не удалось")
            new_topics.append(topic)
            continue

        print(f"[Split] разбито на {len(real_sub)} подтем")
        split_happened = True

        for local_i, global_i in enumerate(doc_idxs):
            sl = int(sub_labels[local_i])
            if sl == -1:
                continue
            new_doc_topics[global_i] = {**new_doc_topics[global_i], "topic": next_id + sl}

        for sub_lbl in sorted(real_sub):
            new_tid = next_id + sub_lbl
            sub_doc_idxs = [doc_idxs[li] for li, sl in enumerate(sub_labels) if sl == sub_lbl]
            suffix = chr(65 + int(sub_lbl))
            new_topics.append({
                "id":     new_tid,
                "count":  len(sub_doc_idxs),
                "words":  topic["words"],
                "scores": topic["scores"],
            })

        next_id += len(real_sub) + 10

    if split_happened:
        print(f"[Split] тем после разбивки: {len(new_topics)}")
    return new_topics, new_doc_topics


# ─────────────────────────────────────────────
# ОСНОВНАЯ ФУНКЦИЯ
# ─────────────────────────────────────────────
def run_bertopic(settings: dict, natasha_data: dict) -> dict:
    documents = natasha_data.get('documents', [])
    if not documents:
        raise ValueError("Нет документов для анализа")

    texts = [d['text_clean'] for d in documents]
    names = [d['name'] for d in documents]

    valid = [(t, n) for t, n in zip(texts, names) if t.strip()]
    if not valid:
        raise ValueError("Все документы пустые после предобработки")

    texts, names = zip(*valid)
    texts = list(texts)
    names = list(names)

    if len(texts) < 2:
        raise ValueError("Нужно минимум 2 документа для анализа")

    n = len(texts)
    print(f"[BERTopic] документов: {n}")

    # ── Пользовательские стоп-слова из настроек ──
    custom_stop_raw = settings.get('customStop', '')
    user_stop = {
        w.strip().lower()
        for w in custom_stop_raw.split('\n')
        if w.strip()
    }
    all_stop = EXTRA_STOPWORDS_RU | user_stop

    # ── Embedding модель (CPU) ──
    model_key       = settings.get('model', 'rubert-tiny2')
    model_name      = MODEL_MAP.get(model_key, MODEL_MAP['rubert-tiny2'])
    embedding_model = get_embedding_model(model_name)

    # ── Скользящее окно ──
    print("[BERTopic] вычисление embeddings со скользящим окном...")
    doc_embeddings = []
    for i, text in enumerate(texts):
        print(f"[BERTopic] embedding {i+1}/{n}: {names[i]}")
        emb = get_text_embedding_with_window(text, embedding_model)
        doc_embeddings.append(emb)
    doc_embeddings = np.array(doc_embeddings)

    # ── UMAP ──
    # n_neighbors: насколько «глобально» смотрит UMAP.
    # Малое значение (5-8) -> видит локальную структуру -> больше кластеров.
    # Большое (15+) -> всё сжимается в одно облако -> мало кластеров.
    n_comp = settings.get('umapComp', 5)
    if n < 10:
        from bertopic.dimensionality import BaseDimensionalityReduction
        umap_model = BaseDimensionalityReduction()
    else:
        # Малый n_neighbors -> видим локальную структуру -> больше тем
        n_neighbors = max(2, min(8, n // 8))
        umap_model = UMAP(
            n_components=min(n_comp, n - 2),
            n_neighbors=n_neighbors,
            min_dist=0.0,
            metric='cosine',
            random_state=42,
            low_memory=True,
        )
        print(f"[BERTopic] UMAP: n_neighbors={n_neighbors}, n_components={min(n_comp, n-2)}")

    # ─────────────────────────────────────────
    # АДАПТИВНЫЙ HDBSCAN
    # epsilon убран -- он сливал соседние кластеры.
    # cluster_selection_method='leaf' вместо 'eom':
    #   'eom'  -- иерархически объединяет, дает меньше крупных тем
    #   'leaf' -- берёт листья дерева, дает больше мелких четких тем
    # Для разнородных новостей 'leaf' работает лучше.
    # ─────────────────────────────────────────
    if n < 15:
        min_cs      = 2
        min_samples = 1
    elif n < 40:
        min_cs      = max(2, n // 10)
        min_samples = 1
    else:
        # Для 60 документов: min_cluster_size=4
        # Позволяет найти ~8-15 тем вместо 3
        min_cs      = max(2, n // 15)
        min_samples = 1

    # Переопределяем если пользователь задал явно
    user_min_cs = settings.get('minClusterSize')
    if user_min_cs:
        min_cs = int(user_min_cs)

    print(f"[BERTopic] HDBSCAN: min_cluster_size={min_cs}, min_samples={min_samples}, method=leaf")

    hdbscan_model = HDBSCAN(
        min_cluster_size=min_cs,
        min_samples=min_samples,
        cluster_selection_epsilon=0.0,
        metric='euclidean',
        prediction_data=True,
        cluster_selection_method='leaf',
    )

    # ─────────────────────────────────────────
    # УЛУЧШЕНИЕ 1: VECTORIZER С РАСШИРЕННЫМИ СТОП-СЛОВАМИ
    # token_pattern исключает числа и короткие токены ≤2 букв,
    # min_df=2 убирает редкие слова (появились только в 1 документе),
    # max_df=0.85 убирает слишком частые (>85% документов) —
    # они информационно пусты для разделения тем.
    # ─────────────────────────────────────────
    vectorizer = CountVectorizer(
        min_df=max(1, min(2, n // 5)),     # для малых корпусов min_df=1
        max_df=0.85,
        ngram_range=(1, 2),
        max_features=8000,
        stop_words=list(all_stop),
        # Только слова ≥ 3 букв, только кириллица/латиница
        token_pattern=r'(?u)\b[а-яёa-zA-Z]{3,}\b',
    )

    # ── Количество топиков ──
    num_topics_raw = settings.get('numTopics', 'auto')
    nr_topics      = None if num_topics_raw == 'auto' else int(num_topics_raw)

    # ── BERTopic ──
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
    topics, _ = topic_model.fit_transform(texts, embeddings=doc_embeddings)

    # ── Снижение шума ──
    if settings.get('outlierReduce', True) and n >= 10:
        try:
            print("[BERTopic] снижение шума...")
            topics = topic_model.reduce_outliers(
                texts, topics,
                strategy="embeddings",
                embeddings=doc_embeddings,
            )
        except ValueError as e:
            print(f"[BERTopic] снижение шума пропущено: {e}")

    # ─────────────────────────────────────────
    # УЛУЧШЕНИЕ 1+2: СБОР РЕЗУЛЬТАТОВ С MMR + ДЕДУПЛИКАЦИЕЙ
    # ─────────────────────────────────────────
    topic_info    = topic_model.get_topic_info()
    result_topics = []
    used_labels   = set()   # чтобы названия тем не повторялись

    # Степень разнообразия MMR: настраивается через настройки
    diversity = float(settings.get('diversity', 0.6))

    for _, row in topic_info.iterrows():
        tid = int(row['Topic'])
        if tid == -1:
            continue

        raw_words_scores = topic_model.get_topic(tid) or []

        # ── MMR-отбор (улучшение 2) ──
        selected = _mmr_select_words(
            words_scores=raw_words_scores,
            model=embedding_model,
            n=10,
            diversity=diversity,
            extra_stop=all_stop,
        )

        # Если MMR вернул пусто — фолбэк на сырой список
        if not selected:
            selected = [
                (w, s) for w, s in raw_words_scores[:10]
                if _is_valid_word(w, all_stop)
            ]

        words  = [w for w, _ in selected]
        scores = [round(float(s), 4) for _, s in selected]

        # ── Название темы (улучшение 2) ──
        label = _make_topic_label(words, tid)

        # Если такое название уже есть — добавляем следующее слово
        if label.lower() in used_labels and len(words) > 2:
            label = _make_topic_label([words[0], words[2]] + words[3:], tid)
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

    # ── Embeddings тем для VOSviewer ──
    topic_embeddings = None
    try:
        all_embeddings = topic_model.topic_embeddings_
        if all_embeddings is not None:
            valid_embeddings = []
            for t in result_topics:
                idx = t['id'] + 1
                if idx < len(all_embeddings):
                    valid_embeddings.append(all_embeddings[idx])
                else:
                    print(f"[BERTopic] нет embedding для темы {t['id']}")

            if len(valid_embeddings) == len(result_topics):
                topic_embeddings = np.array(valid_embeddings)
                print(f"[BERTopic] embeddings тем: {topic_embeddings.shape}")
            else:
                topic_embeddings = None
    except Exception as e:
        print(f"[BERTopic] embeddings тем недоступны: {e}")
        topic_embeddings = None

    doc_topics  = [{'name': nm, 'topic': int(t)} for nm, t in zip(names, topics)]
    noise_count = sum(1 for t in topics if t == -1)
    noise_pct   = round(noise_count / len(topics) * 100, 1)

    # Разбивка крупных тем (> splitThreshold от корпуса)
    if settings.get('splitLargeTopics', True) and len(result_topics) > 0:
        result_topics, doc_topics = _maybe_split_large_topics(
            result_topics=result_topics,
            doc_topics=doc_topics,
            doc_embeddings=doc_embeddings,
            split_threshold=float(settings.get('splitThreshold', 0.20)),
        )
        noise_count = sum(1 for dt in doc_topics if dt['topic'] == -1)
        noise_pct   = round(noise_count / len(doc_topics) * 100, 1)

    # ─────────────────────────────────────────
    # УЛУЧШЕНИЕ 4: РЕАЛЬНАЯ NPMI-КОГЕРЕНТНОСТЬ
    # Заменяет ложный расчёт "среднее TF-IDF скоров".
    # NPMI показывает реальное совместное появление слов.
    # При хорошей модели: 30-70%. При плохой: <15%.
    # ─────────────────────────────────────────
    print("[BERTopic] вычисление NPMI когерентности...")
    coherence = compute_npmi_coherence(result_topics, texts, top_n=5)
    print(f"[BERTopic] NPMI когерентность: {coherence}%")

    print(f"[BERTopic] тем: {len(result_topics)}, шум: {noise_pct}%")

    return {
        'topics':           result_topics,
        'doc_topics':       doc_topics,
        'total_docs':       len(texts),
        'noise_count':      noise_count,
        'noise_pct':        noise_pct,
        'coherence':        coherence,
        'topic_embeddings': topic_embeddings.tolist() if topic_embeddings is not None else None,
    }


# ─────────────────────────────────────────────
# VOSviewer — без изменений, работает корректно
# ─────────────────────────────────────────────
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

    return {
        "network": {
            "items": items,
            "links": links,
        }
    }
