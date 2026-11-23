"""FastAPI service.

    GET  /health   index and model status (no secrets)
    POST /ask      question -> answer with [n] citations and the cited sources

Usage:
    uvicorn src.api.main:app --port 8000          # docs: http://localhost:8000/docs
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("uvicorn.error")
# One request at a time on the GPU/CPU models (bge-m3, reranker): concurrent
# forward passes would fight for the 4 GB of GPU memory. The LLM call is outside
# the lock, so requests still overlap while waiting for the provider.
_models_lock = threading.Lock()

# Public deployments: cap /ask calls so a crawler cannot burn the free LLM quotas
# (or the cloud bill). 0 = unlimited (local default).
MAX_ASKS_PER_DAY = int(os.getenv("MAX_ASKS_PER_DAY", "0"))
MAX_ASKS_PER_MINUTE = int(os.getenv("MAX_ASKS_PER_MINUTE", "0"))
_calls: list[float] = []
_calls_lock = threading.Lock()


def _take_slot() -> bool:
    """True if this call is within both caps (and records it)."""
    now = time.time()
    with _calls_lock:
        _calls[:] = [t for t in _calls if now - t < 86400]
        if MAX_ASKS_PER_DAY and len(_calls) >= MAX_ASKS_PER_DAY:
            return False
        if MAX_ASKS_PER_MINUTE and sum(now - t < 60 for t in _calls) >= MAX_ASKS_PER_MINUTE:
            return False
        _calls.append(now)
        return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the index, BM25 and both models at startup, not on the first request.
    from ..retrieval.query import DEFAULT_MODE, retrieve

    t0 = time.time()
    retrieve("warm up", 1, use_rewrite=False, mode=DEFAULT_MODE)
    log.info("retrieval ready (%s) in %.1fs", DEFAULT_MODE, time.time() - t0)
    yield


app = FastAPI(
    title="au-visa-tax-rag",
    description="Hỏi đáp visa, thuế, super và quyền lợi lao động Úc (tiếng Việt / English), "
                "trả lời có trích nguồn từ immi.homeaffairs.gov.au, ato.gov.au, fairwork.gov.au. "
                "Không phải tư vấn pháp lý / not legal or tax advice.",
    version="0.6.0",
    lifespan=lifespan,
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000,
                          examples=["Du học sinh visa 500 được đi làm bao nhiêu giờ?"])
    top_k: int = Field(5, ge=1, le=10, description="number of chunks given to the LLM")
    rewrite: bool = Field(True, description="rewrite the question into English search queries")
    mode: Literal["vector", "hybrid", "hybrid_rerank"] | None = Field(
        None, description="retrieval mode; default RETRIEVAL_MODE")


class Source(BaseModel):
    id: int
    title: str
    url: str
    heading: str = ""
    page: int | None = None
    snippet: str


class AskResponse(BaseModel):
    answer: str
    found: bool
    sources: list[Source]
    queries: list[str]
    model: str
    seconds: float


@app.get("/health")
def health() -> dict:
    from ..generation.llm import available, chain
    from ..retrieval.build_index import META_FILE
    from ..retrieval.query import DEFAULT_MODE, ENABLED_MODES

    meta = json.loads(META_FILE.read_text(encoding="utf-8")) if META_FILE.exists() else {}
    fmt = lambda steps: [f"{p}:{m}" for p, m in steps]
    return {
        "status": "ok",
        "index": {"chunks": meta.get("chunks"), "built_at": meta.get("built_at"),
                  "embedding_model": meta.get("embedding_model")},
        "retrieval_mode": DEFAULT_MODE,
        "modes": list(ENABLED_MODES),
        # Only steps whose provider has a key; never the keys themselves.
        "llm_chain": fmt(available(chain())),
        "llm_fast_chain": fmt(available(chain(fast=True))),
    }


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    from ..generation.answer import answer

    if not _take_slot():
        raise HTTPException(status_code=429,
                            detail="Bản demo đã hết lượt hỏi cho hôm nay/phút này, vui lòng thử lại sau. "
                                   "/ The demo has reached its request limit, please try again later.")
    t0 = time.time()
    try:
        res = answer(req.question.strip(), req.top_k, use_rewrite=req.rewrite, mode=req.mode,
                     lock=_models_lock)
    except RuntimeError as e:
        # Every LLM in the chain failed (no key, quota, overloaded). The provider
        # errors can contain account ids, so they go to the log, not the client.
        log.error("all LLMs failed: %s", e)
        raise HTTPException(status_code=503,
                            detail="Các dịch vụ AI đang quá tải hoặc hết lượt, vui lòng thử lại sau. "
                                   "/ The AI providers are busy or out of quota, please try again later.")
    return AskResponse(answer=res["answer"], found=res["found"],
                       sources=[Source(**s) for s in res["sources"]],
                       queries=res["queries"], model=res["model"],
                       seconds=round(time.time() - t0, 2))
