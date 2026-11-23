"""
local embeddings with sentence-transformers.
model all-MiniLM-L6-v2 (apache 2.0) ~90MB, downloaded once into ~/.cache/huggingface
after that it works offline.
"""
import math
import config

_model = None
_failed = False


def load():
    global _model, _failed
    if _model is not None or _failed:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(config.EMBED_MODEL)
        print("embedding model loaded:", config.EMBED_MODEL)
    except Exception as e:
        print("could not load sentence-transformers model, using word overlap instead.", e)
        _failed = True
    return _model


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def word_overlap(a, b):
    # backup method if model not available
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def similarity(text1, text2):
    m = load()
    if m is None:
        return round(word_overlap(text1, text2), 3), "word_overlap"
    v = m.encode([text1, text2])
    return round(float(cosine(v[0], v[1])), 3), "sentence_transformers"


def top_chunks(query, text, k=4, chunk_size=400):
    """split page text in chunks and return most relevant ones for the query.
    used so we don't send whole website to small model (context is limited)"""
    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    if len(chunks) <= k:
        return chunks
    m = load()
    if m is None:
        scored = [(word_overlap(query, c), c) for c in chunks]
    else:
        vecs = m.encode([query] + chunks)
        q = vecs[0]
        scored = [(cosine(q, vecs[i + 1]), chunks[i]) for i in range(len(chunks))]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for s, c in scored[:k]]
