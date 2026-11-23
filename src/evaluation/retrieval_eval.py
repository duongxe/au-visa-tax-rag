"""Compare retrieval modes on the evaluation questions, without any LLM call.

Replays the queries (question + LLM rewrites) saved in eval/runs/answers.jsonl, so
every mode searches with exactly the same queries, and checks where the first chunk
from an expected source page lands (questions.csv, source_urls).

    hit@1 / hit@5 / hit@10   an expected page is among the first 1 / 5 / 10 chunks
    MRR@10                   mean of 1/rank of the first expected page (0 if not in top 10)

Usage:
    python -X utf8 -m src.evaluation.retrieval_eval
    python -X utf8 -m src.evaluation.retrieval_eval --no-rewrite   # original question only
"""
from __future__ import annotations

import argparse
import time

from ..retrieval.query import MODES, retrieve
from .run_answers import RUNS, load_answers, load_questions

OUT = RUNS / "retrieval_compare.md"
DEPTH = 10


def first_rank(hits: list[dict], expected: set[str]) -> int | None:
    return next((r for r, h in enumerate(hits, start=1) if h["url"] in expected), None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-rewrite", action="store_true", help="search with the question only")
    args = ap.parse_args()

    answers = load_answers()
    qs = [q for q in load_questions() if q["in_corpus"]]
    ranks: dict[str, dict[int, int | None]] = {m: {} for m in MODES}
    secs: dict[str, float] = {}
    for mode in MODES:
        t0 = time.time()
        for q in qs:
            queries = [q["question"]] if args.no_rewrite else (answers[q["id"]]["queries"] or [q["question"]])
            hits, _ = retrieve(q["question"], DEPTH, mode=mode, queries=queries)
            ranks[mode][q["id"]] = first_rank(hits, set(q["source_urls"]))
        secs[mode] = (time.time() - t0) / len(qs)

    n = len(qs)
    out = [f"# So sánh retrieval ({n} câu có trong tài liệu, "
           f"{'chỉ câu hỏi gốc' if args.no_rewrite else 'câu hỏi gốc + câu viết lại đã lưu'})", "",
           "| Chế độ | hit@1 | hit@5 | hit@10 | MRR@10 | giây/câu |", "|---|---|---|---|---|---|"]
    for m in MODES:
        r = ranks[m]
        hit = lambda d: sum(1 for x in r.values() if x and x <= d)
        mrr = sum(1 / x for x in r.values() if x) / n
        out.append(f"| {m} | {hit(1)}/{n} | {hit(5)}/{n} | {hit(10)}/{n} | {mrr:.3f} | {secs[m]:.2f} |")
    changed = [q for q in qs if len({ranks[m][q["id"]] for m in MODES}) > 1]
    out += ["", "## Câu có thứ hạng thay đổi (hạng của trang nguồn đúng đầu tiên, - = ngoài top 10)", "",
            "| # | câu hỏi | " + " | ".join(MODES) + " |", "|---|---|" + "---|" * len(MODES)]
    for q in changed:
        out.append(f"| {q['id']} | {q['question']} | "
                   + " | ".join(str(ranks[m][q['id']] or "-") for m in MODES) + " |")
    text = "\n".join(out) + "\n"
    if not args.no_rewrite:
        OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
