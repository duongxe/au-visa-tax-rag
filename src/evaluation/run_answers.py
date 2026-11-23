"""Step 1 of the evaluation: run the RAG pipeline on every question in eval/questions.csv.

Writes one JSON line per question to eval/runs/answers.jsonl. Questions already in
the file are skipped, so the run can be stopped and resumed (useful when the free
LLM tiers hit their rate limits). Use --fresh to start over.

Usage:
    python -X utf8 -m src.evaluation.run_answers
    python -X utf8 -m src.evaluation.run_answers --fresh --sleep 4
"""
from __future__ import annotations

import argparse
import csv
import json
import time

from ..generation.answer import answer
from ..ingest.common import ROOT

QUESTIONS = ROOT / "eval" / "questions.csv"
RUNS = ROOT / "eval" / "runs"
ANSWERS = RUNS / "answers.jsonl"


def load_questions() -> list[dict]:
    with QUESTIONS.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["id"] = int(r["id"])
        r["in_corpus"] = r["in_corpus"] == "1"
        r["source_urls"] = [u.strip() for u in r["source_urls"].split("|") if u.strip()]
    return rows


def load_answers(path=ANSWERS) -> dict[int, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {(d := json.loads(line))["id"]: d for line in f if line.strip()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true", help="delete previous answers first")
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between questions (rate limits)")
    ap.add_argument("-k", type=int, default=5)
    args = ap.parse_args()

    RUNS.mkdir(parents=True, exist_ok=True)
    if args.fresh and ANSWERS.exists():
        ANSWERS.unlink()
    # Later lines win, so a question that failed earlier is simply answered again.
    done = {i: r for i, r in load_answers().items() if not r["error"]}
    todo = [q for q in load_questions() if q["id"] not in done]
    print(f"{len(done)} already answered, {len(todo)} to go")

    for i, q in enumerate(todo, start=1):
        t0 = time.time()
        try:
            res = answer(q["question"], args.k)
            error = ""
        except RuntimeError as e:  # every LLM failed: record it and carry on
            res = {"answer": "", "found": False, "sources": [], "contexts": [], "context_urls": [],
                   "queries": [], "model": ""}
            error = str(e)
        row = {
            "id": q["id"],
            "question": q["question"],
            "answer": res["answer"],
            "found": res["found"],
            "model": res["model"],
            "queries": res["queries"],
            "cited_urls": [s["url"] for s in res["sources"]],
            "context_urls": res["context_urls"],
            "contexts": res["contexts"],
            "seconds": round(time.time() - t0, 1),
            "error": error,
        }
        with ANSWERS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        status = "ERROR" if error else ("found" if res["found"] else "not found")
        print(f"[{i}/{len(todo)}] #{q['id']} {row['seconds']}s {res['model'] or '-'} {status}")
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
