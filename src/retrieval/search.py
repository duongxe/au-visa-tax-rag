"""Dense retrieval over the FAISS index (no LLM).

Usage:
    python -X utf8 -m src.retrieval.search "Visa 482 cần bao nhiêu năm kinh nghiệm?"
    python -X utf8 -m src.retrieval.search -k 10 "Do I pay tax on a working holiday visa?"
"""
from __future__ import annotations

import argparse
import json
import textwrap
from functools import lru_cache

import faiss

from .chunk import CHUNKS_FILE
from .build_index import INDEX_FILE
from .embed import encode


@lru_cache(maxsize=1)
def load_index():
    index = faiss.read_index(str(INDEX_FILE))
    chunks = [json.loads(line) for line in CHUNKS_FILE.open(encoding="utf-8")]
    if index.ntotal != len(chunks):
        raise RuntimeError("faiss.index and chunks.jsonl are out of sync; rebuild the index")
    return index, chunks


def search(query: str, k: int = 5) -> list[dict]:
    index, chunks = load_index()
    scores, ids = index.search(encode([query]), k)
    return [{**chunks[i], "score": float(s)} for s, i in zip(scores[0], ids[0]) if i >= 0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+")
    ap.add_argument("-k", type=int, default=5)
    args = ap.parse_args()
    query = " ".join(args.query)

    print(f"Q: {query}\n")
    for rank, hit in enumerate(search(query, args.k), start=1):
        where = " > ".join(hit["headings"][:1]) or "-"
        page = f" (p.{hit['page']})" if hit["page"] else ""
        print(f"[{rank}] {hit['score']:.3f}  {hit['title']}  |  {where}{page}")
        print(f"    {hit['url']}")
        body = " ".join(hit["text"].split())
        print(textwrap.indent(textwrap.shorten(body, 400, placeholder=" …"), "    "))
        print()


if __name__ == "__main__":
    main()
