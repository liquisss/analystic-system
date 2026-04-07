import os
import numpy as np
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


def get_text_embedding_with_window(text: str, model, window: int = 256, stride: int = 128) -> np.ndarray:
    """
    Скользящее окно по словам — каждый чанк кодируется отдельно,
    итоговый embedding = среднее по всем чанкам.
    Это позволяет не терять смысл длинных документов.
    """
    words  = text.split()
    if not words:
        # Возвращаем нулевой вектор размерности модели
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


def run_bertopic(settings: dict, natasha_data: dict) -> dict:
    documents = natasha_data.get('documents', [])
    if not documents:
        raise ValueError("Нет документов для анализа")

    texts = [d['text_clean'] for d in documents]
    names = [d['name'] for d in documents]

    # Фильтруем пустые
    valid = [(t, n) for t, n in zip(texts, names) if t.strip()]
    if not valid:
        raise ValueError("Все документы пустые после предобработки")

    texts, names = zip(*valid)
    texts = list(texts)
    names = list(names)

    if len(texts) < 2:
        raise ValueError("Нужно минимум 2 документа для анализа")

    if len(texts) < 10:
        print(f"[BERTopic] внимание: малый корпус ({len(texts)} документов)")

    print(f"[BERTopic] документов: {len(texts)}")

    # ── Embedding модель (CPU) ──
    model_key       = settings.get('model', 'rubert-tiny2')
    model_name      = MODEL_MAP.get(model_key, MODEL_MAP['rubert-tiny2'])
    embedding_model = get_embedding_model(model_name)

    # ── Скользящее окно для embeddings ──
    print("[BERTopic] вычисление embeddings со скользящим окном...")
    doc_embeddings = []
    for i, text in enumerate(texts):
        print(f"[BERTopic] embedding {i+1}/{len(texts)}: {names[i]}")
        emb = get_text_embedding_with_window(text, embedding_model)
        doc_embeddings.append(emb)
    doc_embeddings = np.array(doc_embeddings)

    # ── UMAP ──
    n_comp = settings.get('umapComp', 5)
    if len(texts) < 10:
        from bertopic.dimensionality import BaseDimensionalityReduction
        umap_model = BaseDimensionalityReduction()
    else:
        umap_model = UMAP(
            n_components=min(n_comp, len(texts) - 2),
            n_neighbors=max(2, min(15, len(texts) - 1)),
            min_dist=0.0,
            metric='cosine',
            random_state=42,
            low_memory=True,
        )

    # ── HDBSCAN ──
    hdbscan_model = HDBSCAN(
        min_cluster_size=2,
        min_samples=1,
        cluster_selection_epsilon=0.0,
        metric='euclidean',
        prediction_data=True,
        cluster_selection_method='eom'
    )

    # ── Vectorizer ──
    vectorizer = CountVectorizer(
        min_df=1,
        ngram_range=(1, 2),
        max_features=10000,
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
    # Передаём предвычисленные embeddings — модель не будет их пересчитывать
    topics, _ = topic_model.fit_transform(texts, embeddings=doc_embeddings)

    # ── Снижение шума ──
    if settings.get('outlierReduce', True) and len(texts) >= 10:
        try:
            print("[BERTopic] снижение шума...")
            topics = topic_model.reduce_outliers(
                texts, topics,
                strategy="embeddings",
                embeddings=doc_embeddings,
            )
        except ValueError as e:
            print(f"[BERTopic] снижение шума пропущено: {e}")

    # ── Сбор результатов ──
    topic_info    = topic_model.get_topic_info()
    result_topics = []

    for _, row in topic_info.iterrows():
        tid = int(row['Topic'])
        if tid == -1:
            continue

        words_scores = topic_model.get_topic(tid)

        # ---- НОВОЕ: генерация названия темы ----
        top_words = [w for w, _ in words_scores[:3]]  # можно взять 2 или 3 слова
        if top_words:
            label = ' '.join(top_words).capitalize()
            # Если название слишком длинное, обрежем до 50 символов (опционально)
            if len(label) > 50:
                label = label[:47] + '...'
        else:
            label = f"Тема {tid}"

        result_topics.append({
            'id':     tid,
            'label':  label,
            'count':  int(row['Count']),
            'words':  [w for w, _ in words_scores[:10]],
            'scores': [round(float(s), 4) for _, s in words_scores[:10]],
        })

    # ── Embeddings тем для реальных связей ──
    topic_embeddings = None
    try:
        all_embeddings = topic_model.topic_embeddings_
        if all_embeddings is not None:
            # Берём embeddings только для найденных тем по их реальным id
            valid_embeddings = []
            for t in result_topics:
                tid = t['id']
                # В topic_embeddings_ индекс = topic_id + 1 (так как -1 идёт первым)
                idx = tid + 1
                if idx < len(all_embeddings):
                    valid_embeddings.append(all_embeddings[idx])
                else:
                    print(f"[BERTopic] нет embedding для темы {tid}, пропускаем")

            if len(valid_embeddings) == len(result_topics):
                topic_embeddings = np.array(valid_embeddings)
                print(f"[BERTopic] embeddings тем: {topic_embeddings.shape}")
            else:
                print(
                    f"[BERTopic] несовпадение embeddings ({len(valid_embeddings)}) и тем ({len(result_topics)}), пропускаем")
                topic_embeddings = None
    except Exception as e:
        print(f"[BERTopic] embeddings тем недоступны: {e}")
        topic_embeddings = None

    doc_topics  = [{'name': n, 'topic': int(t)} for n, t in zip(names, topics)]
    noise_count = sum(1 for t in topics if t == -1)
    noise_pct   = round(noise_count / len(topics) * 100, 1)

    coherence = 0.0
    if result_topics:
        avg_scores = [np.mean(t['scores']) if t['scores'] else 0 for t in result_topics]
        coherence  = round(float(np.mean(avg_scores)) * 100, 1)

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


def build_vosviewer_json(bertopic_result: dict) -> dict:
    topics           = bertopic_result.get('topics', [])
    topic_embeddings = bertopic_result.get('topic_embeddings', None)

    if not topics:
        return {}

    # ── Items (без x/y — VOSviewer рассчитает сам) ──
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

    # ── Реальные связи через косинусное сходство embeddings ──
    if topic_embeddings is not None and len(topic_embeddings) >= 2:
        emb_matrix = np.array(topic_embeddings)
        # Проверяем что размеры совпадают
        if len(emb_matrix) != len(topics):
            print(f"[VOSviewer] несовпадение размеров, используем fallback")
            topic_embeddings = None
        else:
            sim_matrix = cosine_similarity(emb_matrix)

        n = len(topics)

        for i in range(n):
            for j in range(i + 1, n):
                sim = float(sim_matrix[i][j])
                if sim > 0.05:  # порог значимости
                    links.append({
                        "source_id": topics[i]['id'] + 1,
                        "target_id": topics[j]['id'] + 1,
                        "strength":  round(sim, 4),
                    })

        print(f"[VOSviewer] реальных связей по cosine similarity: {len(links)}")

    # ── Fallback — пересечение слов ──
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

    # Темы без связей всё равно остаются в items — VOSviewer их покажет
    print(f"[VOSviewer] итого узлов: {len(items)}, связей: {len(links)}")

    return {
        "network": {
            "items": items,
            "links": links,
        }
    }