"""Step 2 of the evaluation: score the in-corpus answers with RAGAS.

Metrics (each 0..1):
    faithfulness       share of the answer's claims supported by the retrieved contexts
    answer_relevancy   how well the answer addresses the question (questions generated
                       back from the answer, compared to the real one with bge-m3)
    context_precision  are the relevant contexts ranked high (judged against the reference)
    context_recall     share of the reference answer's claims found in the contexts

The judge LLM goes through the same fallback chain as the app (src/generation/llm.py),
set with EVAL_CHAIN in .env; the embeddings are the app's bge-m3. Judge calls are cached
in eval/runs/.ragas_cache, so a rerun after rate-limit errors only redoes what failed.

Usage:
    python -X utf8 -m src.evaluation.ragas_eval
    python -X utf8 -m src.evaluation.ragas_eval --workers 2 --limit 5
"""
from __future__ import annotations

import argparse
import asyncio
import os
import typing as t

from langchain_core.outputs import Generation, LLMResult
from ragas import EvaluationDataset, RunConfig, evaluate
from ragas.cache import DiskCacheBackend
from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.llms.base import BaseRagasLLM
from ragas.metrics._answer_relevance import ResponseRelevancy
from ragas.metrics._context_precision import LLMContextPrecisionWithReference
from ragas.metrics._context_recall import LLMContextRecall
from ragas.metrics._faithfulness import Faithfulness

from ..generation.llm import generate, parse_chain
from ..retrieval.embed import encode
from .run_answers import RUNS, load_answers, load_questions

SCORES = RUNS / "ragas_scores.csv"
DEFAULT_EVAL_CHAIN = (
    "gemini:gemini-3.5-flash-lite,"
    "gemini:gemini-3.5-flash,"
    "groq:openai/gpt-oss-120b,"
    "mistral:ministral-14b-latest,"
    "openrouter:google/gemma-4-31b-it:free,"
    "deepseek:deepseek-chat,"
    "openai:gpt-5-mini,"
    "anthropic:claude-haiku-5-5"
)
JUDGE_SYSTEM = ("You are a careful evaluator of question-answering systems. Follow the "
                "instructions exactly and return only the requested JSON.")


class ChainJudge(BaseRagasLLM):
    """RAGAS judge that calls the app's LLM fallback chain."""

    def __init__(self, steps: list[tuple[str, str]], cache=None):
        self.steps = steps
        self.used: dict[str, int] = {}
        super().__init__(cache=cache)

    def _one(self, text: str) -> str:
        out, model = generate(JUDGE_SYSTEM, text, steps=list(self.steps))
        self.used[model] = self.used.get(model, 0) + 1
        return out

    def generate_text(self, prompt, n: int = 1, temperature: float = 0.01, stop=None,
                      callbacks=None) -> LLMResult:
        text = prompt.to_string()
        return LLMResult(generations=[[Generation(text=self._one(text)) for _ in range(n)]])

    async def agenerate_text(self, prompt, n: int = 1, temperature: float | None = 0.01,
                             stop=None, callbacks=None) -> LLMResult:
        return await asyncio.to_thread(self.generate_text, prompt, n, temperature or 0.01, stop)

    def is_finished(self, response: LLMResult) -> bool:
        return True


class Bge(BaseRagasEmbeddings):
    """bge-m3 from the retrieval module (multilingual, so Vietnamese works)."""

    def embed_query(self, text: str) -> t.List[float]:
        return encode([text])[0].tolist()

    def embed_documents(self, texts: t.List[str]) -> t.List[t.List[float]]:
        return encode(texts).tolist()

    async def aembed_query(self, text: str) -> t.List[float]:
        return self.embed_query(text)

    async def aembed_documents(self, texts: t.List[str]) -> t.List[t.List[float]]:
        return self.embed_documents(texts)


METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3, help="parallel judge calls (rate limits)")
    ap.add_argument("--limit", type=int, default=0, help="only score the first N questions (smoke test)")
    args = ap.parse_args()

    questions = {q["id"]: q for q in load_questions()}
    answers = load_answers()
    # Only questions the corpus can answer, that the pipeline did answer: the
    # "I don't know" behaviour and the out-of-corpus questions are scored in report.py.
    rows = [a for i, a in sorted(answers.items())
            if questions[i]["in_corpus"] and a["found"] and not a["error"]]
    if args.limit:
        rows = rows[: args.limit]
    print(f"scoring {len(rows)} answers with RAGAS")

    dataset = EvaluationDataset.from_list([
        {"user_input": a["question"], "response": a["answer"], "retrieved_contexts": a["contexts"],
         "reference": questions[a["id"]]["ground_truth"]}
        for a in rows
    ])
    judge = ChainJudge(parse_chain(os.getenv("EVAL_CHAIN") or DEFAULT_EVAL_CHAIN),
                       cache=DiskCacheBackend(cache_dir=str(RUNS / ".ragas_cache")))
    metrics = [
        Faithfulness(),
        # strictness=1: one generated question per answer instead of 3, a third of the
        # judge calls; enough for a 42-question set on free tiers.
        ResponseRelevancy(strictness=1),
        LLMContextPrecisionWithReference(),
        LLMContextRecall(),
    ]
    result = evaluate(dataset, metrics=metrics, llm=judge, embeddings=Bge(),
                      run_config=RunConfig(max_workers=args.workers, max_retries=4, max_wait=60,
                                           timeout=600),
                      show_progress=True)
    df = result.to_pandas().rename(columns={"llm_context_precision_with_reference": "context_precision"})
    df.insert(0, "id", [a["id"] for a in rows])
    df = df[["id"] + [m for m in METRICS if m in df.columns]]
    df.to_csv(SCORES, index=False)
    print(df[[m for m in METRICS if m in df.columns]].mean().round(3).to_string())
    print("judge calls:", judge.used)
    print("saved", SCORES)


if __name__ == "__main__":
    main()
