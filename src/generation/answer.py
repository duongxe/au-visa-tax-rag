"""Rewrite query -> retrieve -> prompt -> LLM (with fallback) -> answer with [n] citations.

Usage:
    python -X utf8 -m src.generation.answer "Du học sinh visa 500 được làm thêm bao nhiêu giờ?"
    python -X utf8 -m src.generation.answer -k 8 --show-context "Do working holiday makers pay tax?"
    python -X utf8 -m src.generation.answer --no-rewrite "..."   # search with the question only
"""
from __future__ import annotations

import argparse
import textwrap

from ..retrieval.query import retrieve
from .llm import generate
from .prompt import NOT_FOUND, SYSTEM, build_prompt, cited_numbers, detect_lang


def answer(question: str, k: int = 5, use_rewrite: bool = True) -> dict:
    """Returns {answer, found, sources, contexts, queries, model}.

    sources  = the retrieved chunks the answer cites, keeping their [n] number
    contexts = all k retrieved chunks (used by the evaluation in phase 4)
    """
    hits, queries = retrieve(question, k, use_rewrite)
    if not hits:
        return {"answer": NOT_FOUND[detect_lang(question)], "found": False,
                "sources": [], "contexts": [], "context_urls": [], "queries": queries, "model": ""}

    text, model = generate(SYSTEM, build_prompt(question, hits))
    cited = [n for n in cited_numbers(text) if 1 <= n <= len(hits)]
    sources = [
        {
            "id": n,
            "title": hits[n - 1]["title"],
            "url": hits[n - 1]["url"],
            "heading": (hits[n - 1]["headings"] or [""])[0],
            "page": hits[n - 1]["page"],
            "snippet": textwrap.shorten(" ".join(hits[n - 1]["text"].split()), 300, placeholder=" …"),
        }
        for n in cited
    ]
    return {
        "answer": text,
        "found": bool(cited),  # an answer without citations is the "I don't know" reply
        "sources": sources,
        "contexts": [h["text"] for h in hits],
        "context_urls": [h["url"] for h in hits],
        "queries": queries,
        "model": model,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="+")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--show-context", action="store_true", help="also print the retrieved chunks")
    ap.add_argument("--no-rewrite", action="store_true", help="do not rewrite the question with the LLM")
    args = ap.parse_args()
    question = " ".join(args.question)

    res = answer(question, args.k, use_rewrite=not args.no_rewrite)
    print(f"Q: {question}")
    for q in res["queries"][1:]:
        print(f"   + {q}")
    print(f"   model: {res['model']}\n")
    print(res["answer"])
    if res["sources"]:
        print("\nNguồn / Sources:")
        for s in res["sources"]:
            where = f" › {s['heading']}" if s["heading"] else ""
            page = f" (p.{s['page']})" if s["page"] else ""
            print(f"  [{s['id']}] {s['title']}{where}{page}\n      {s['url']}")
    if args.show_context:
        print("\n--- retrieved ---")
        for n, c in enumerate(res["contexts"], start=1):
            print(f"[{n}] {textwrap.shorten(' '.join(c.split()), 300)}")


if __name__ == "__main__":
    main()
