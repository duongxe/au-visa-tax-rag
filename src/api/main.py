"""FastAPI service. /ask hiện là stub; nối với retrieval + generation ở giai đoạn 3."""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="au-visa-tax-rag")


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


class Source(BaseModel):
    id: int
    title: str
    url: str
    page: int | None = None
    snippet: str


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    # TODO (giai đoạn 3): retrieve -> build prompt -> call LLM
    return AskResponse(answer=f"(stub) Chưa có pipeline. Câu hỏi: {req.question}", sources=[])
