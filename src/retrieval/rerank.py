"""Cross-encoder reranking with bge-reranker-v2-m3 (multilingual).

The first stage (dense + BM25, fused with RRF) is tuned for recall; the reranker
reads the question and each candidate chunk together and scores how well the chunk
answers it, which orders the final top k much better than either first-stage score.
"""
from __future__ import annotations

import os
from functools import lru_cache

from .config import RERANKER_MODEL

MAX_LENGTH = 512  # question + chunk tokens; longer chunks are truncated
BATCH_SIZE = int(os.getenv("RERANK_BATCH_SIZE", "8"))  # small: 4 GB GPU


@lru_cache(maxsize=1)
def get_reranker():
    import torch
    from sentence_transformers import CrossEncoder

    device = "cuda" if torch.cuda.is_available() else "cpu"
    kwargs = {"torch_dtype": torch.float16} if device == "cuda" else {}
    return CrossEncoder(RERANKER_MODEL, device=device, max_length=MAX_LENGTH, model_kwargs=kwargs)


def passage(chunk: dict) -> str:
    head = (chunk["headings"] or [""])[0]
    return f"{chunk['title']}\n{head}\n{chunk['text']}" if head else f"{chunk['title']}\n{chunk['text']}"


def rerank(queries: list[str], candidates: list[dict], k: int) -> list[dict]:
    """Returns the k best candidates, scored by the best match over the queries.

    queries = the user's question + the English rewrites. The reranker is multilingual,
    but a Vietnamese question against an English chunk gets low, noisy scores; taking the
    max over the English rewrites as well keeps the ranking stable for Vietnamese questions.
    """
    if not candidates:
        return []
    texts = [passage(c) for c in candidates]
    pairs = [(q, t) for q in queries for t in texts]
    flat = get_reranker().predict(pairs, batch_size=BATCH_SIZE, show_progress_bar=False)
    n = len(candidates)
    scores = [max(float(flat[j * n + i]) for j in range(len(queries))) for i in range(n)]
    order = sorted(range(n), key=lambda i: scores[i], reverse=True)[:k]
    return [{**candidates[i], "score": scores[i]} for i in order]
