"""FastAPI service: POST /ask -> answer with cited sources."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the embedding model and the index once, not on the first request.
    from ..retrieval.search import load_index, search

    load_index()
    search("warm up", 1)
    yield


app = FastAPI(title="au-visa-tax-rag", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(5, ge=1, le=20)


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
    model: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    from ..generation.answer import answer

    try:
        res = answer(req.question, req.top_k)
    except RuntimeError as e:  # e.g. missing API key
        raise HTTPException(status_code=503, detail=str(e))
    return AskResponse(answer=res["answer"], found=res["found"],
                       sources=[Source(**s) for s in res["sources"]], model=res["model"])
