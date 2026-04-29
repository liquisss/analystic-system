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


def _is_valid_word(word: str, extra_stop: set) -> bool:
    w = word.lower().strip()
    if _GARBAGE_RE.match(w):      return False
    if w in EXTRA_STOPWORDS_RU:   return False
    if w in extra_stop:           return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# MMR — без изменений
# ─────────────────────────────────────────────────────────────────────────────

def _mmr_select_words(
    words_scores: list,
    model,
    n: int = 10,
    diversity: float = 0.6,
    extra_stop: set = None,
) -> list:
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

    if scores.max() > 0:
        rel = scores / scores.max()
    else:
        rel = scores

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


# ─────────────────────────────────────────────────────────────────────────────
# Название темы — без изменений
# ─────────────────────────────────────────────────────────────────────────────

def _make_topic_label(words: list, topic_id: int) -> str:
    if not words:
        return f"Тема {topic_id}"

    seen, dedup = [], []
    for w in words[:5]:
        wl = w.lower()
        if wl not in seen:
            seen.append(wl)
            dedup.append(w)

    if not dedup:
        return f"Тема {topic_id}"
    if len(dedup) == 1:
        return dedup[0].capitalize()

    w1, w2 = dedup[0], dedup[1]
    common  = os.path.commonprefix([w1.lower(), w2.lower()])
    if len(common) > 4 and len(dedup) > 2:
        label = f"{w1} {dedup[2]}".capitalize()
    else:
        label = f"{w1} {w2}".capitalize()

    return label[:47] + "..." if len(label) > 50 else label


# ─────────────────────────────────────────────────────────────────────────────
# NPMI когерентность — без изменений
# ─────────────────────────────────────────────────────────────────────────────

def compute_npmi_coherence(topics: list, texts: list, top_n: int = 5) -> float:
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


# ─────────────────────────────────────────────────────────────────────────────
# СКОЛЬЗЯЩЕЕ ОКНО
# ─────────────────────────────────────────────────────────────────────────────

def get_text_embedding_with_window(
    text: str, model, window: int = 256, stride: int = 128
) -> np.ndarray:
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
# РАЗБИВКА КРУПНЫХ ТЕМ — без изменений
# ─────────────────────────────────────────────────────────────────────────────

def _maybe_split_large_topics(result_topics, doc_topics, doc_embeddings,
                               split_threshold=0.20):
    total_docs = len(doc_topics)
    if total_docs == 0:
        return result_topics, doc_topics

    topic_to_doc_idx = {}
    for i, dt in enumerate(doc_topics):
        tid = dt["topic"]
        if tid == -1:
            continue
        topic_to_doc_idx.setdefault(tid, []).append(i)

    new_topics     = []
    new_doc_topics = list(doc_topics)
    max_id         = max((t["id"] for t in result_topics), default=0)
    next_id        = max_id + 100
    split_happened = False

    for topic in result_topics:
        tid       = topic["id"]
        doc_idxs  = topic_to_doc_idx.get(tid, [])
        doc_count = len(doc_idxs)

        if doc_count / total_docs <= split_threshold or doc_count < 6:
            new_topics.append(topic)
            continue

        lbl = topic.get('label', str(tid))
        print(f'[Split] тема {tid} ({lbl}) {doc_count} документов — пробуем разбить')
        cluster_embs = doc_embeddings[doc_idxs]
        sub_min_cs   = max(2, doc_count // 5)

        try:
            sub_hdb = HDBSCAN(
                min_cluster_size=sub_min_cs, min_samples=1,
                cluster_selection_epsilon=0.0, metric="euclidean",
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
            sub_lbl_int = int(sub_lbl)
            new_tid      = next_id + sub_lbl_int
            sub_doc_idxs = [doc_idxs[li] for li, sl in enumerate(sub_labels) if sl == sub_lbl]
            suffix       = chr(65 + int(sub_lbl))
            new_topics.append({
                "id":     new_tid,
                "label":  topic.get("label", f"Тема {tid}") + f" / {suffix}",
                "count":  len(sub_doc_idxs),
                "words":  topic["words"],
                "scores": topic["scores"],
            })

        next_id += len(real_sub) + 10

    if split_happened:
        print(f"[Split] тем после разбивки: {len(new_topics)}")
    return new_topics, new_doc_topics


# ─────────────────────────────────────────────────────────────────────────────
# ОСНОВНАЯ ФУНКЦИЯ
# ─────────────────────────────────────────────────────────────────────────────

def run_bertopic(settings: dict, natasha_data: dict) -> dict:
    """
    Hybrid representation:
      text_raw   → скользящее окно → эмбеддинги → UMAP + HDBSCAN (кластеризация)
      text_clean → CountVectorizer → c-TF-IDF (ключевые слова и названия тем)

    Это даёт:
      - точную кластеризацию (BERT видит живой язык, пунктуацию, контекст)
      - читаемые ключевые слова (только леммы + синонимы из тезауруса, без мусора)
    """
    documents = natasha_data.get('documents', [])
    if not documents:
        raise ValueError("Нет документов для анализа")

    # ── Два представления текста ──────────────────────────────────────────────
    # text_raw   — исходный текст (clean_text без лемматизации) → для эмбеддингов
    # text_clean — леммы + тезаурус → для c-TF-IDF
    #
    # Если text_raw отсутствует (старые сессии без обновления natasha_processor)
    # — используем text_clean как fallback для обратной совместимости.
    # ─────────────────────────────────────────────────────────────────────────
    raw_pairs = [
        (d.get('text_raw') or d['text_clean'], d['text_clean'], d['name'])
        for d in documents
        if (d.get('text_raw') or d.get('text_clean', '')).strip()
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
    print(f"[BERTopic] hybrid mode: эмбеддинги на text_raw, c-TF-IDF на text_clean")

    # ── Стоп-слова ────────────────────────────────────────────────────────────
    custom_stop_raw = settings.get('customStop', '')
    user_stop = {
        w.strip().lower()
        for w in custom_stop_raw.split('\n') if w.strip()
    }
    all_stop = EXTRA_STOPWORDS_RU | user_stop

    # ── Embedding модель ──────────────────────────────────────────────────────
    model_key       = settings.get('model', 'rubert-tiny2')
    model_name      = MODEL_MAP.get(model_key, MODEL_MAP['rubert-tiny2'])
    embedding_model = get_embedding_model(model_name)

    # ── Эмбеддинги на ИСХОДНОМ тексте (text_raw) ─────────────────────────────
    # BERT видит живой язык → точная кластеризация смысловых групп
    print("[BERTopic] вычисление embeddings на исходном тексте (text_raw)...")
    doc_embeddings = []
    for i, text in enumerate(texts_raw):
        print(f"[BERTopic] embedding {i+1}/{n}: {names[i]}")
        emb = get_text_embedding_with_window(text, embedding_model)
        doc_embeddings.append(emb)
    doc_embeddings = np.array(doc_embeddings)

    # ── UMAP ──────────────────────────────────────────────────────────────────
    n_comp = settings.get('umapComp', 5)
    if n < 10:
        from bertopic.dimensionality import BaseDimensionalityReduction
        umap_model = BaseDimensionalityReduction()
    else:
        n_neighbors = max(2, min(8, n // 8))
        umap_model  = UMAP(
            n_components=min(n_comp, n - 2),
            n_neighbors=n_neighbors,
            min_dist=0.0,
            metric='cosine',
            random_state=42,
            low_memory=True,
        )
        print(f"[BERTopic] UMAP: n_neighbors={n_neighbors}, n_components={min(n_comp, n-2)}")

    # ── HDBSCAN ───────────────────────────────────────────────────────────────
    if n < 15:
        min_cs = 2
    elif n < 40:
        min_cs = max(2, n // 10)
    else:
        min_cs = max(2, n // 15)

    user_min_cs = settings.get('minClusterSize')
    if user_min_cs:
        min_cs = int(user_min_cs)

    print(f"[BERTopic] HDBSCAN: min_cluster_size={min_cs}, method=leaf")

    hdbscan_model = HDBSCAN(
        min_cluster_size=min_cs,
        min_samples=1,
        cluster_selection_epsilon=0.0,
        metric='euclidean',
        prediction_data=True,
        cluster_selection_method='leaf',
    )

    # ── CountVectorizer на text_clean ─────────────────────────────────────────
    # c-TF-IDF строится на леммах + тезаурус → ключевые слова без мусора
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

    # ── fit_transform: КЛЮЧЕВОЙ МОМЕНТ HYBRID APPROACH ────────────────────────
    #
    # texts_clean → CountVectorizer / c-TF-IDF (ключевые слова тем)
    # embeddings= → doc_embeddings уже посчитаны на texts_raw (исходный текст)
    #
    # BERTopic НЕ будет пересчитывать эмбеддинги сам — использует наши.
    # Это и есть разделение: кластеризация на живом тексте,
    # ключевые слова на чистых леммах.
    # ─────────────────────────────────────────────────────────────────────────
    print("[BERTopic] обучение модели (hybrid: raw embeddings + clean c-TF-IDF)...")
    topics, _ = topic_model.fit_transform(
        texts_clean,               # ← c-TF-IDF строится на леммах
        embeddings=doc_embeddings  # ← кластеризация на исходном тексте
    )

    # ── Снижение шума ─────────────────────────────────────────────────────────
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

    # ── Сбор результатов с MMR ────────────────────────────────────────────────
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

        label = _make_topic_label(words, tid)
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

    # ── Embeddings тем для VOSviewer ──────────────────────────────────────────
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

    doc_topics  = [{'name': nm, 'topic': int(t)} for nm, t in zip(names, topics)]
    noise_count = sum(1 for t in topics if t == -1)
    noise_pct   = round(noise_count / len(topics) * 100, 1)

    # ── Разбивка крупных тем ──────────────────────────────────────────────────
    if settings.get('splitLargeTopics', True) and len(result_topics) > 0:
        result_topics, doc_topics = _maybe_split_large_topics(
            result_topics=result_topics,
            doc_topics=doc_topics,
            doc_embeddings=doc_embeddings,
            split_threshold=float(settings.get('splitThreshold', 0.20)),
        )
        noise_count = sum(1 for dt in doc_topics if dt['topic'] == -1)
        noise_pct   = round(noise_count / len(doc_topics) * 100, 1)

    # ── NPMI когерентность на text_clean ─────────────────────────────────────
    # Считаем на text_clean — именно по нему строились ключевые слова
    print("[BERTopic] вычисление NPMI когерентности...")
    coherence = compute_npmi_coherence(result_topics, texts_clean, top_n=5)
    print(f"[BERTopic] NPMI когерентность: {coherence}%")
    print(f"[BERTopic] тем: {len(result_topics)}, шум: {noise_pct}%")

    return {
        'topics':           result_topics,
        'doc_topics':       doc_topics,
        'total_docs':       len(texts_raw),
        'noise_count':      noise_count,
        'noise_pct':        noise_pct,
        'coherence':        coherence,
        'topic_embeddings': topic_embeddings.tolist() if topic_embeddings is not None else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# VOSviewer — без изменений
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
