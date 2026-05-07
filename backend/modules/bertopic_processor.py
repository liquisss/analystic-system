from __future__ import annotations
import re
import gc
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
    "это","этот","эта","эти","тот","та","те","который","которая","которые",
    "которого","которому","свой","своя","свои","своего","своему","весь","вся",
    "все","всё","всего","такой","такая","такие","такого","сам","сама","сами",
    "самого","некоторый","некоторые","никакой","любой","каждый","другой","другие",
    "также","тоже","же","ли","бы","ведь","вот","вон","даже","уже","ещё","ещe",
    "еще","вдруг","лишь","почти","просто","именно","особенно","затем","потом",
    "здесь","там","тут","куда","откуда","где","когда","зачем","почему","чтобы",
    "чтоб","хотя","пока","после","перед","через","между","около","вместе",
    "вместо","среди","против","кроме","внутри","снова","опять","вновь","всегда",
    "никогда","иногда","часто","редко","быстро","медленно","очень","слишком",
    "совсем","абсолютно","быть","является","являются","есть","нет","нету",
    "будет","будут","был","была","были","стать","становится","стал","стала",
    "стали","может","могут","должен","должна","должны","надо","нужно","можно",
    "нельзя","хотеть","хочет","хотят","один","два","три","первый","второй","третий",
    "много","мало","несколько","немного",
}

_GARBAGE_RE = re.compile(
    r'^[^а-яёa-z]+$|^\d+$|^[а-яёa-z]{1,2}$', re.IGNORECASE
)

# Суффиксы прилагательных русского языка
_ADJ_SUFFIXES = (
    'ный','ной','ний','ской','ский','зный','дный','вый','лый','рый','мый','тый',
    'ная','ное','ные','ного','ному',
    'ive','ous','ful','ial','ical',
)


# ─────────────────────────────────────────────────────────────────────────────
# МЕТКИ ТЕМ — существительное + прилагательное
# ─────────────────────────────────────────────────────────────────────────────

def _looks_like_adjective(word: str) -> bool:
    return any(word.lower().endswith(sfx) for sfx in _ADJ_SUFFIXES)


def _make_topic_label(words: list, topic_id: int) -> str:
    """
    Метка из c-TF-IDF слов темы.
    Предпочитает пару прилагательное+существительное,
    иначе два существительных с разными корнями.
    """
    if not words:
        return f"Тема {topic_id}"

    seen, dedup = [], []
    for w in words[:8]:
        wl = w.lower()
        if wl not in seen and len(w) >= 4:
            seen.append(wl)
            dedup.append(w)

    if not dedup:         return f"Тема {topic_id}"
    if len(dedup) == 1:   return dedup[0].capitalize()

    noun = dedup[0]
    adj  = next(
        (w for w in dedup[1:]
         if _looks_like_adjective(w)
         and not w.lower().startswith(noun.lower()[:4])),
        None
    )

    if adj:
        label = f"{adj} {noun}".capitalize()
    else:
        w2    = next(
            (w for w in dedup[1:] if not w.lower().startswith(noun.lower()[:4])),
            dedup[1]
        )
        label = f"{noun} {w2}".capitalize()

    return label[:47] + '...' if len(label) > 47 else label


# ─────────────────────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────────────────────────────────────

def _is_valid_word(word: str, extra_stop: set) -> bool:
    w = word.lower().strip()
    if _GARBAGE_RE.match(w):    return False
    if w in EXTRA_STOPWORDS_RU: return False
    if w in extra_stop:         return False
    return True


def _mmr_select_words(words_scores, model, n=10, diversity=0.6, extra_stop=None):
    if extra_stop is None: extra_stop = set()
    candidates = [(w, s) for w, s in words_scores if _is_valid_word(w, extra_stop) and s > 0.0]
    if not candidates:        return []
    if len(candidates) <= n:  return candidates

    words  = [w for w, _ in candidates]
    scores = np.array([s for _, s in candidates])
    rel    = scores / scores.max() if scores.max() > 0 else scores

    try:
        embeddings = model.encode(words, show_progress_bar=False)
        sim_matrix = cosine_similarity(embeddings)
    except Exception:
        return candidates[:n]

    selected_idx, remaining = [], list(range(len(words)))
    best = int(np.argmax(rel))
    selected_idx.append(best); remaining.remove(best)

    while len(selected_idx) < n and remaining:
        mmr_scores = [(i, (1-diversity)*rel[i] - diversity*max(sim_matrix[i][j] for j in selected_idx))
                      for i in remaining]
        best_i = max(mmr_scores, key=lambda x: x[1])[0]
        selected_idx.append(best_i); remaining.remove(best_i)

    return sorted([(words[i], float(scores[i])) for i in selected_idx], key=lambda x: -x[1])


def compute_npmi_coherence(topics, texts, top_n=5):
    if not topics or not texts: return 0.0
    n = len(texts)
    tokenized = [set(re.findall(r'[а-яёa-z]+', t.lower())) for t in texts]
    word_freq: Counter = Counter(w for toks in tokenized for w in toks)
    def freq_pair(a, b): return sum(1 for toks in tokenized if a in toks and b in toks)
    all_pairs = []
    for topic in topics:
        words = [w.lower() for w in topic.get('words', [])[:top_n]]
        if len(words) < 2: continue
        for i in range(len(words)):
            for j in range(i+1, len(words)):
                a, b = words[i], words[j]
                fa, fb, fab = word_freq.get(a,0), word_freq.get(b,0), freq_pair(a,b)
                if fa==0 or fb==0: all_pairs.append(0.0); continue
                pa, pb, pab = fa/n, fb/n, (fab+0.5)/n
                pmi = math.log2(pab/(pa*pb)) if pa*pb>0 else 0.0
                pmi_max = -math.log2(max(pa,pb))
                npmi = pmi/pmi_max if pmi_max>0 else 0.0
                all_pairs.append(max(0.0, min(1.0, npmi)))
    return round(float(np.mean(all_pairs))*100, 1) if all_pairs else 0.0


def get_text_embedding_with_window(text, model, window=256, stride=128):
    words = text.split()
    if not words: return np.zeros(model.get_sentence_embedding_dimension())
    chunks, start = [], 0
    while start < len(words):
        chunks.append(' '.join(words[start:start+window]))
        start += stride
        if start >= len(words): break
    return np.mean(model.encode(chunks, show_progress_bar=False), axis=0)


def _encode_in_batches(model, texts, batch_size=32):
    """
    Батчевое кодирование с gc между батчами.
    batch_size=32 → ~20MB пик на батч vs ~160MB при batch=256.
    Потребление памяти снижается в 4-8 раз ценой +20-30% времени.
    """
    all_embeddings = []
    total = len(texts)
    for start in range(0, total, batch_size):
        end   = min(start + batch_size, total)
        batch = texts[start:end]
        if start % (batch_size * 5) == 0:
            print(f"[BERTopic] embedding {start}/{total}...")
        batch_emb = model.encode(batch, batch_size=batch_size,
                                  show_progress_bar=False, convert_to_numpy=True)
        all_embeddings.append(batch_emb)
        del batch, batch_emb
        gc.collect()
    result = np.concatenate(all_embeddings, axis=0)
    del all_embeddings; gc.collect()
    return result


# ─────────────────────────────────────────────────────────────────────────────
# КАРТА КЛЮЧЕВЫХ СЛОВ
# ─────────────────────────────────────────────────────────────────────────────

def build_keywords_vos_data(topics, embedding_model, top_n_words=8):
    if not topics: return {}
    word_meta: dict = {}
    for t_idx, topic in enumerate(topics):
        for w, s in zip(topic['words'][:top_n_words], topic['scores'][:top_n_words]):
            key = w.lower()
            if key not in word_meta or s > word_meta[key]['score']:
                word_meta[key] = {'label':w,'cluster':t_idx+1,'cluster_idx':t_idx,
                                  'score':float(s),'count':topic['count']}
    if len(word_meta) < 2: return {}

    all_words = list(word_meta.keys())
    labels    = [word_meta[w]['label'] for w in all_words]
    n         = len(all_words)

    print(f"[Keywords VOS] кодируем {n} слов...")
    try:
        word_emb   = embedding_model.encode(labels, show_progress_bar=False, batch_size=32)
        sim_matrix = cosine_similarity(word_emb)
    except Exception as e:
        print(f"[Keywords VOS] ошибка: {e}"); return {}

    max_score = max(m['score'] for m in word_meta.values()) or 1.0
    INTRA_THRESHOLD, CROSS_THRESHOLD, INTRA_BOOST, CROSS_TOP_N = 0.25, 0.55, 3.0, 3

    items = [{
        "id": idx+1, "label": word_meta[w]['label'], "cluster": word_meta[w]['cluster'],
        "weights": {"Score": round((word_meta[w]['score']/max_score)*100,2),
                    "Documents": word_meta[w]['count']},
        "scores": {"TF-IDF": round(word_meta[w]['score'],6)},
    } for idx, w in enumerate(all_words)]

    intra_links = []
    for i in range(n):
        for j in range(i+1, n):
            if word_meta[all_words[i]]['cluster_idx'] != word_meta[all_words[j]]['cluster_idx']: continue
            sim = float(sim_matrix[i][j])
            if sim >= INTRA_THRESHOLD:
                intra_links.append({"source_id":i+1,"target_id":j+1,"strength":round(sim*INTRA_BOOST,4)})

    cross_cands: dict = {}
    for i in range(n):
        for j in range(i+1, n):
            ci,cj = word_meta[all_words[i]]['cluster_idx'], word_meta[all_words[j]]['cluster_idx']
            if ci==cj: continue
            sim = float(sim_matrix[i][j])
            if sim < CROSS_THRESHOLD: continue
            cross_cands.setdefault((min(ci,cj),max(ci,cj)),[]).append((sim,i,j))

    cross_links = []
    for cands in cross_cands.values():
        for sim,i,j in sorted(cands,key=lambda x:-x[0])[:CROSS_TOP_N]:
            cross_links.append({"source_id":i+1,"target_id":j+1,"strength":round(sim,4)})

    links = intra_links + cross_links
    if not intra_links:
        print("[Keywords VOS] снижаем порог до 0.15")
        for i in range(n):
            for j in range(i+1, n):
                if word_meta[all_words[i]]['cluster_idx'] != word_meta[all_words[j]]['cluster_idx']: continue
                sim = float(sim_matrix[i][j])
                if sim >= 0.15:
                    links.append({"source_id":i+1,"target_id":j+1,"strength":round(sim*INTRA_BOOST,4)})

    print(f"[Keywords VOS] узлов:{len(items)}, внутри:{len(intra_links)}, мосты:{len(cross_links)}")
    return {"network": {"items": items, "links": links}}


# ─────────────────────────────────────────────────────────────────────────────
# ОСНОВНАЯ ФУНКЦИЯ
# ─────────────────────────────────────────────────────────────────────────────

def run_bertopic(settings: dict, natasha_data: dict) -> dict:
    documents = natasha_data.get('documents', [])
    if not documents: raise ValueError("Нет документов для анализа")

    raw_pairs = [
        (d.get('text_raw') or d.get('text_clean') or d.get('text',''),
         d.get('text_clean') or d.get('text_raw') or d.get('text',''),
         d['name'])
        for d in documents
        if (d.get('text_raw') or d.get('text_clean') or d.get('text','')).strip()
    ]
    if not raw_pairs:   raise ValueError("Все документы пустые")
    if len(raw_pairs)<2: raise ValueError("Нужно минимум 2 документа")

    texts_raw, texts_clean, names = zip(*raw_pairs)
    texts_raw, texts_clean, names = list(texts_raw), list(texts_clean), list(names)
    n = len(texts_raw)
    print(f"[BERTopic] документов: {n}")

    user_stop = {w.strip().lower() for w in settings.get('customStop','').split('\n') if w.strip()}
    all_stop  = EXTRA_STOPWORDS_RU | user_stop

    model_key       = settings.get('model','rubert-tiny2')
    embedding_model = get_embedding_model(MODEL_MAP.get(model_key, MODEL_MAP['rubert-tiny2']))

    # ── Эмбеддинги: batch=32 + gc между батчами ──────────────────────────────
    BATCH_SIZE = 32
    avg_words  = sum(len(t.split()) for t in texts_raw) / max(n,1)
    print(f"[BERTopic] avg={avg_words:.0f} слов, batch={BATCH_SIZE}")

    if avg_words <= 250:
        doc_embeddings = _encode_in_batches(embedding_model, texts_raw, BATCH_SIZE)
    else:
        doc_embeddings = []
        for i, text in enumerate(texts_raw):
            if i % 100 == 0:
                print(f"[BERTopic] embedding {i}/{n}..."); gc.collect()
            doc_embeddings.append(get_text_embedding_with_window(text, embedding_model))
        doc_embeddings = np.array(doc_embeddings); gc.collect()

    # ── UMAP ─────────────────────────────────────────────────────────────────
    n_comp = settings.get('umapComp', 5)
    if n < 10:
        from bertopic.dimensionality import BaseDimensionalityReduction
        umap_model = BaseDimensionalityReduction()
    else:
        n_neighbors = max(2, min(50, n//20)) if n>1000 else max(2, min(15, n//8))
        umap_model  = UMAP(n_components=min(n_comp,n-2), n_neighbors=n_neighbors,
                           min_dist=0.0, metric='cosine', random_state=42, low_memory=True)
        print(f"[BERTopic] UMAP: n_neighbors={n_neighbors}")

    # ── HDBSCAN ──────────────────────────────────────────────────────────────
    min_cs = 2 if n<15 else (max(2,n//10) if n<40 else max(2,n//15))
    user_min_cs = settings.get('minTopic') or settings.get('minClusterSize')
    if user_min_cs: min_cs = int(user_min_cs)
    cluster_method = 'leaf' if n < 100 else 'eom'
    print(f"[BERTopic] HDBSCAN: min_cluster_size={min_cs}, method={cluster_method}")

    hdbscan_model = HDBSCAN(min_cluster_size=min_cs, min_samples=1,
                             cluster_selection_epsilon=0.0, metric='euclidean',
                             prediction_data=True, cluster_selection_method=cluster_method)

    # ── CountVectorizer ───────────────────────────────────────────────────────
    vectorizer = CountVectorizer(
        min_df=max(1, min(2, n//5)), max_df=0.85, ngram_range=(1,2),
        max_features=8000, stop_words=list(all_stop),
        token_pattern=r'(?u)\b[а-яёa-zA-Z]{3,}\b',
    )

    num_topics_raw = settings.get('numTopics','auto')
    nr_topics      = None if num_topics_raw=='auto' else int(num_topics_raw)

    topic_model = BERTopic(
        embedding_model=embedding_model, umap_model=umap_model,
        hdbscan_model=hdbscan_model, vectorizer_model=vectorizer,
        nr_topics=nr_topics, calculate_probabilities=False, verbose=True,
    )

    print("[BERTopic] обучение модели...")
    topics, _ = topic_model.fit_transform(texts_clean, embeddings=doc_embeddings)
    gc.collect()

    if settings.get('outlierReduce',True) and n>=10:
        try:
            print("[BERTopic] снижение шума...")
            topics = topic_model.reduce_outliers(texts_clean, topics,
                                                  strategy="embeddings", embeddings=doc_embeddings)
        except ValueError as e:
            print(f"[BERTopic] снижение шума пропущено: {e}")

    # ── Формирование тем ──────────────────────────────────────────────────────
    topic_info    = topic_model.get_topic_info()
    result_topics = []
    used_labels   = set()
    diversity     = float(settings.get('diversity', 0.6))

    for _, row in topic_info.iterrows():
        tid = int(row['Topic'])
        if tid == -1: continue
        raw_ws = topic_model.get_topic(tid) or []
        selected = _mmr_select_words(raw_ws, embedding_model, 10, diversity, all_stop)
        if not selected:
            selected = [(w,s) for w,s in raw_ws[:10] if _is_valid_word(w,all_stop)]
        words  = [w for w,_ in selected]
        scores = [round(float(s),4) for _,s in selected]
        label  = _make_topic_label(words, tid)
        if label.lower() in used_labels:
            label = _make_topic_label([words[0]]+(words[2:] if len(words)>2 else words[1:]), tid)
        if label.lower() in used_labels:
            label = f"{label} ({tid})"
        used_labels.add(label.lower())
        result_topics.append({'id':tid,'label':label,'count':int(row['Count']),'words':words,'scores':scores})

    # ── Embeddings тем ────────────────────────────────────────────────────────
    topic_embeddings = None
    try:
        all_emb = topic_model.topic_embeddings_
        if all_emb is not None:
            valid = [all_emb[t['id']+1] for t in result_topics if t['id']+1 < len(all_emb)]
            if len(valid)==len(result_topics):
                topic_embeddings = np.array(valid)
    except Exception as e:
        print(f"[BERTopic] embeddings тем недоступны: {e}")

    # ── 2D UMAP ───────────────────────────────────────────────────────────────
    doc_positions = None
    try:
        umap_2d = UMAP(n_components=2, n_neighbors=max(2,min(15,n//5)),
                       min_dist=0.1, metric='cosine', random_state=42, low_memory=True)
        pos2d = umap_2d.fit_transform(doc_embeddings)
        doc_positions = [{'x':round(float(p[0]),4),'y':round(float(p[1]),4)} for p in pos2d]
        del pos2d; gc.collect()
    except Exception as e:
        print(f"[BERTopic] 2D UMAP ошибка: {e}")

    doc_topics  = [{'name':nm,'topic':int(t)} for nm,t in zip(names,topics)]
    noise_count = sum(1 for t in topics if t==-1)
    noise_pct   = round(noise_count/len(topics)*100, 1)

    coherence = compute_npmi_coherence(result_topics, texts_clean, top_n=5)
    print(f"[BERTopic] когерентность:{coherence}%, тем:{len(result_topics)}, шум:{noise_pct}%")

    keywords_vos_data = build_keywords_vos_data(result_topics, embedding_model, 8)

    del doc_embeddings; gc.collect()

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
# VOSviewer
# ─────────────────────────────────────────────────────────────────────────────

def build_vosviewer_json(bertopic_result: dict) -> dict:
    topics           = bertopic_result.get('topics', [])
    topic_embeddings = bertopic_result.get('topic_embeddings', None)
    if not topics: return {}

    items = [{
        "id": t['id']+1, "label": t['label'], "cluster": i+1,
        "weights": {"Documents": t['count']},
        "scores":  {"Avg. score": round(float(sum(t['scores'])/len(t['scores'])),4) if t['scores'] else 0.0},
    } for i,t in enumerate(topics)]

    links = []
    if topic_embeddings is not None and len(topic_embeddings)>=2:
        emb = np.array(topic_embeddings)
        if len(emb)==len(topics):
            sim = cosine_similarity(emb)
            nt  = len(topics)
            for i in range(nt):
                for j in range(i+1,nt):
                    if sim[i][j]>0.1:
                        links.append({"source_id":topics[i]['id']+1,"target_id":topics[j]['id']+1,
                                      "strength":round(float(sim[i][j]),4)})
            print(f"[VOSviewer] реальных связей: {len(links)}")

    if not links:
        for i,t1 in enumerate(topics):
            for j,t2 in enumerate(topics):
                if j<=i: continue
                shared = set(t1['words'])&set(t2['words'])
                if shared:
                    links.append({"source_id":t1['id']+1,"target_id":t2['id']+1,
                                  "strength":round(len(shared)/max(len(t1['words']),len(t2['words'])),4)})

    print(f"[VOSviewer] узлов:{len(items)}, связей:{len(links)}")
    return {"network": {"items": items, "links": links}}
