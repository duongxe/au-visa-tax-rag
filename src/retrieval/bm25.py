"""Keyword search (BM25) over the same chunks as the FAISS index.

Dense search (bge-m3) misses exact tokens such as subclass numbers ("482") or
"1 year"; BM25 scores documents by the query words they contain, so it catches
those. The index is built in memory from chunks.jsonl on first use (~5k chunks,
a few seconds), so there is nothing extra to keep in sync on disk.

Usage:
    python -X utf8 -m src.retrieval.bm25 "subclass 482 work experience"
"""
from __future__ import annotations

import re
import sys
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi

from .search import load_index

TOKEN = re.compile(r"\w+", re.UNICODE)
# Very common English words: dropping them keeps the BM25 scores focused on the
# content words (the corpus is English; Vietnamese questions reach BM25 through
# the English rewrites).
STOPWORDS = set(
    "a an and are as at be by can do does for from has have how i if in is it its my of on or "
    "that the their this to was what when where which who will with you your".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS]


def doc_text(chunk: dict) -> str:
    # Title and headings carry the visa name / topic, which the body may not repeat.
    return " ".join([chunk["title"], *(chunk["headings"][:1]), chunk["text"]])


@lru_cache(maxsize=1)
def load_bm25() -> BM25Okapi:
    _, chunks = load_index()
    return BM25Okapi([tokenize(doc_text(c)) for c in chunks])


def bm25_search(query: str, k: int = 5) -> list[dict]:
    tokens = tokenize(query)
    if not tokens:
        return []
    _, chunks = load_index()
    scores = load_bm25().get_scores(tokens)
    top = np.argsort(-scores)[:k]
    return [{**chunks[i], "score": float(scores[i])} for i in top if scores[i] > 0]


if __name__ == "__main__":
    q = " ".join(sys.argv[1:])
    for r, h in enumerate(bm25_search(q, 10), start=1):
        print(f"[{r}] {h['score']:.2f}  {h['title']}  |  {(h['headings'] or ['-'])[0]}\n    {h['url']}")
