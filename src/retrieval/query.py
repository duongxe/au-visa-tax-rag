"""Query rewriting + multi-query retrieval.

Dense search on a short Vietnamese question can miss the right page: in
"Bố mẹ tôi muốn sang Úc thăm tôi thì xin visa gì?" the word "parents" pulls the
search towards the Parent (migration) visas, while the answer is the Visitor visa
(subclass 600). A fast LLM first rewrites the question into 1-3 English search
queries with official terms; the original question and the rewrites are searched
separately and the rankings are merged with Reciprocal Rank Fusion (RRF).

Each query is searched twice, dense (bge-m3) and keyword (BM25), and all the
rankings are fused with RRF; the top 30 are then reordered by a cross-encoder
reranker (best score over the question and its rewrites) (RETRIEVAL_MODE, see MODES).

The rewrite only steers retrieval: the answer is still written from the retrieved
documents only. If every LLM fails, retrieval falls back to the original question.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from .bm25 import bm25_search
from .rerank import rerank
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
RERANK_CANDIDATES = 30
# vector         dense search only (phase 3 baseline)
# hybrid         dense for every query + BM25 for the English ones, fused with RRF
# hybrid_rerank  hybrid top 30 scored by bge-reranker-v2-m3, reranked order and hybrid
#                order fused again with RRF (default)
MODES = ("vector", "hybrid", "hybrid_rerank")
# RERANK_ENABLED=0 (small cloud instances, image built without the reranker):
# hybrid_rerank requests fall back to hybrid instead of loading the model.
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "1").lower() not in ("0", "false", "no")
ENABLED_MODES = MODES if RERANK_ENABLED else tuple(m for m in MODES if m != "hybrid_rerank")
DEFAULT_MODE = os.getenv("RETRIEVAL_MODE", "hybrid_rerank")
if DEFAULT_MODE not in ENABLED_MODES:
    DEFAULT_MODE = "hybrid"


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


def rrf(lists: list[list[dict]], n: int) -> list[dict]:
    """Reciprocal Rank Fusion: sum of 1/(60 + rank) over the ranked lists; the n best chunks."""
    fused: dict[str, float] = {}
    by_id: dict[str, dict] = {}
    for hits in lists:
        for rank, hit in enumerate(hits):
            cid = hit["chunk_id"]
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
            by_id.setdefault(cid, hit)
    top = sorted(fused, key=fused.get, reverse=True)[:n]
    return [{**by_id[c], "score": fused[c]} for c in top]


def first_stage(queries: list[str], mode: str, n: int) -> list[dict]:
    """Dense search for every query, plus BM25 for the English ones, fused with RRF.

    BM25 skips Vietnamese queries: the corpus is English, so their words only match
    noise ("visa", numbers aside); the English rewrites carry the keywords instead.
    """
    from ..generation.prompt import detect_lang

    lists = [search(q, CANDIDATES_PER_QUERY) for q in queries]
    if mode != "vector":
        lists += [bm25_search(q, CANDIDATES_PER_QUERY) for q in queries if detect_lang(q) == "en"]
    return rrf(lists, n)


def retrieve(question: str, k: int = 5, use_rewrite: bool = True, mode: str | None = None,
             queries: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Returns (top-k chunks, the queries used).

    queries: search with these instead of rewriting (the evaluation replays the
    rewrites saved from an earlier run, so retrieval modes are compared on the same queries).
    """
    mode = mode or DEFAULT_MODE
    if mode not in MODES:
        raise ValueError(f"unknown retrieval mode {mode!r}, expected one of {MODES}")
    if mode not in ENABLED_MODES:
        mode = "hybrid"
    if queries is None:
        queries = [question] + (list(rewrite(question)) if use_rewrite else [])
    if mode == "hybrid_rerank":
        pool = first_stage(queries, mode, RERANK_CANDIDATES)
        reranked = rerank(queries, pool, len(pool))
        # Blend the two orders with RRF instead of trusting the reranker alone: on the
        # evaluation set this beat both (MRR@10 0.89 vs 0.82 reranker only, 0.80 hybrid).
        return rrf([pool, reranked], k), queries
    return first_stage(queries, mode, k), queries
