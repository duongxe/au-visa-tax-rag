"""Query rewriting + multi-query retrieval.

Dense search on a short Vietnamese question can miss the right page: in
"Bố mẹ tôi muốn sang Úc thăm tôi thì xin visa gì?" the word "parents" pulls the
search towards the Parent (migration) visas, while the answer is the Visitor visa
(subclass 600). A fast LLM first rewrites the question into 1-3 English search
queries with official terms; the original question and the rewrites are searched
separately and the rankings are merged with Reciprocal Rank Fusion (RRF).

The rewrite only steers retrieval: the answer is still written from the retrieved
documents only. If every LLM fails, retrieval falls back to the original question.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from .search import search

log = logging.getLogger(__name__)

REWRITE_SYSTEM = (
    "You turn a user's question about Australian visas, tax, superannuation or workplace rights "
    "into 1 to 3 short English search queries for a search engine over immi.homeaffairs.gov.au, "
    "ato.gov.au and fairwork.gov.au pages. Use the official terms these sites use (visa names with "
    "subclass numbers, ATO and Fair Work terms). Cover the likely intents of the question. "
    "Output one query per line, nothing else."
)
CANDIDATES_PER_QUERY = 20
RRF_K = 60


@lru_cache(maxsize=512)
def rewrite(question: str) -> tuple[str, ...]:
    from ..generation.llm import generate

    try:
        text, _ = generate(REWRITE_SYSTEM, question, fast=True)
    except RuntimeError as e:
        log.warning("query rewrite skipped: %s", e)
        return ()
    lines = [l.strip().lstrip("-•*0123456789.) ").strip().strip('"') for l in text.splitlines()]
    return tuple(l for l in lines if l and l.lower() != question.lower())[:3]


def retrieve(question: str, k: int = 5, use_rewrite: bool = True) -> tuple[list[dict], list[str]]:
    """Returns (top-k chunks fused over all queries, the queries used)."""
    queries = [question] + (list(rewrite(question)) if use_rewrite else [])
    if len(queries) == 1:
        return search(question, k), queries
    fused: dict[str, float] = {}
    by_id: dict[str, dict] = {}
    for q in queries:
        for rank, hit in enumerate(search(q, CANDIDATES_PER_QUERY)):
            cid = hit["chunk_id"]
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
            by_id.setdefault(cid, hit)
    top = sorted(fused, key=fused.get, reverse=True)[:k]
    return [{**by_id[c], "score": fused[c]} for c in top], queries
