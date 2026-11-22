"""Embed every chunk with bge-m3 and save a FAISS index.

Outputs (data/index/):
    chunks.jsonl     chunk text + metadata (row i = vector i)
    faiss.index      IndexFlatIP over normalised vectors (= cosine similarity)
    meta.json        model name, dimension, chunk count, build date

Usage:
    python -m src.retrieval.build_index            # chunk + embed
    python -m src.retrieval.build_index --skip-chunk
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date

import faiss

from . import chunk
from .config import EMBEDDING_MODEL, INDEX_DIR
from .embed import encode

INDEX_FILE = INDEX_DIR / "faiss.index"
META_FILE = INDEX_DIR / "meta.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-chunk", action="store_true", help="reuse existing chunks.jsonl")
    ap.add_argument("--batch-size", type=int, default=16)
    args = ap.parse_args()

    if not args.skip_chunk:
        chunk.main()
    chunks = [json.loads(line) for line in chunk.CHUNKS_FILE.open(encoding="utf-8")]
    texts = [chunk.embed_text(c) for c in chunks]

    # Longest first: batches of similar length waste less padding.
    order = sorted(range(len(texts)), key=lambda i: -len(texts[i]))
    t0 = time.time()
    vecs_sorted = encode([texts[i] for i in order], batch_size=args.batch_size, progress=True)
    vecs = vecs_sorted.copy()
    vecs[order] = vecs_sorted
    secs = time.time() - t0

    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    faiss.write_index(index, str(INDEX_FILE))
    META_FILE.write_text(json.dumps({
        "embedding_model": EMBEDDING_MODEL,
        "dim": int(vecs.shape[1]),
        "chunks": len(chunks),
        "built_at": date.today().isoformat(),
    }, indent=2), encoding="utf-8")
    print(f"embedded {len(chunks)} chunks in {secs:.0f}s -> {INDEX_FILE} ({INDEX_FILE.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
