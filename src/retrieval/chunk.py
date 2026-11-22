"""Split cleaned documents (data/processed/*.json) into retrieval chunks.

Rules:
  * Chunks follow the section structure: small sections of the same document are
    merged up to MAX_TOKENS, long sections are split on paragraph / sentence
    boundaries with OVERLAP_TOKENS of overlap.
  * Every chunk keeps doc_id, title, url, site, the section heading(s) and the PDF
    page, so answers can cite their source.
  * Sections whose text appears word-for-word in an earlier document (visa page
    boilerplate about documents, translations, agents...) are dropped, so the
    index keeps a single copy.

Token counts use the bge-m3 tokenizer, the same one used for embedding.

Usage:
    python -m src.retrieval.chunk          # writes data/index/chunks.jsonl
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

from ..ingest.common import PROCESSED_DIR, ROOT
from .config import EMBEDDING_MODEL, INDEX_DIR

MAX_TOKENS = 550      # chunk body size limit
MIN_TOKENS = 400      # keep merging sections until at least this size
OVERLAP_TOKENS = 80   # carried over when a long section is split

CHUNKS_FILE = INDEX_DIR / "chunks.jsonl"

_tokenizer = None


def n_tokens(text: str) -> int:
    global _tokenizer
    if _tokenizer is None:
        from transformers import AutoTokenizer
        _tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)
    return len(_tokenizer.encode(text, add_special_tokens=False))


def _norm_key(text: str) -> str:
    return hashlib.md5(re.sub(r"\W+", " ", text.lower()).strip().encode()).hexdigest()


SENT_RE = re.compile(r"(?<=[.!?;:])\s+")


def _pieces(text: str, limit: int) -> list[tuple[str, int]]:
    """Paragraphs (or sentences / word windows for very long ones) with token counts."""
    out = []
    for para in [p.strip() for p in text.split("\n") if p.strip()]:
        n = n_tokens(para)
        if n <= limit:
            out.append((para, n))
            continue
        for sent in SENT_RE.split(para):
            n = n_tokens(sent)
            if n <= limit:
                out.append((sent, n))
                continue
            words = sent.split()
            step = 200  # ~300-400 tokens for English words
            for i in range(0, len(words), step):
                w = " ".join(words[i:i + step])
                out.append((w, n_tokens(w)))
    return out


def split_long(text: str, limit: int = MAX_TOKENS) -> list[str]:
    """Split text longer than `limit` tokens into overlapping windows of paragraphs."""
    pieces = _pieces(text, limit)
    chunks, cur, cur_n = [], [], 0
    for piece, n in pieces:
        if cur and cur_n + n > limit:
            chunks.append("\n".join(p for p, _ in cur))
            # overlap: keep trailing pieces up to OVERLAP_TOKENS
            keep, keep_n = [], 0
            for p, pn in reversed(cur):
                if keep_n + pn > OVERLAP_TOKENS:
                    break
                keep.insert(0, (p, pn))
                keep_n += pn
            cur, cur_n = keep, keep_n
        cur.append((piece, n))
        cur_n += n
    if cur:
        chunks.append("\n".join(p for p, _ in cur))
    return chunks


def chunk_doc(doc: dict, seen: set[str], stats: Counter) -> list[dict]:
    chunks: list[dict] = []
    buf: list[dict] = []   # sections waiting to be merged
    buf_n = 0

    def make(text: str, secs: list[dict]) -> dict:
        headings = list(dict.fromkeys(s["heading"] for s in secs if s["heading"]))
        return {
            "chunk_id": f"{doc['doc_id']}#{len(chunks)}",
            "doc_id": doc["doc_id"],
            "title": doc["title"],
            "url": doc["url"],
            "site": doc["site"],
            "headings": headings,
            "page": secs[0]["page"],
            "text": text,
        }

    def flush():
        nonlocal buf, buf_n
        if buf:
            text = "\n\n".join(_section_text(s) for s in buf)
            chunks.append(make(text, buf))
        buf, buf_n = [], 0

    for sec in doc["sections"]:
        key = _norm_key(sec["text"])
        if key in seen:
            stats["dup_sections"] += 1
            continue
        seen.add(key)
        stats["sections"] += 1

        text = _section_text(sec)
        n = n_tokens(text)
        if n > MAX_TOKENS:
            flush()
            head = f"{sec['heading']}\n" if sec["heading"] else ""
            for part in split_long(sec["text"], MAX_TOKENS - n_tokens(head) - 2):
                chunks.append(make(head + part, [sec]))
            continue
        # PDF pages: do not merge across pages, otherwise the page citation is wrong.
        if buf and (buf_n + n > MAX_TOKENS or buf[0]["page"] != sec["page"]):
            flush()
        buf.append(sec)
        buf_n += n
        if buf_n >= MIN_TOKENS:
            flush()
    flush()
    return chunks


def _section_text(sec: dict) -> str:
    leaf = sec["heading"].split(" > ")[-1] if sec["heading"] else ""
    if leaf and not sec["text"].startswith(leaf):
        return f"{leaf}\n{sec['text']}"
    return sec["text"]


def embed_text(chunk: dict) -> str:
    """Text given to the embedding model: document title + section path + body."""
    head = chunk["title"]
    if chunk["headings"]:
        head += " > " + chunk["headings"][0]
    return f"{head}\n\n{chunk['text']}"


def load_docs() -> list[dict]:
    # Fair Work and ATO first, then Home Affairs: when sections repeat across sites,
    # the copy kept is the one on the agency that owns the topic. Inside a site,
    # sorted by doc_id so a visa's main page comes before its streams.
    order = {"fairwork.gov.au": 0, "ato.gov.au": 1, "immi.homeaffairs.gov.au": 2}
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in PROCESSED_DIR.glob("*.json")]
    return sorted(docs, key=lambda d: (order.get(d["site"], 9), d["doc_id"]))


def main() -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    docs = load_docs()
    seen: set[str] = set()
    stats: Counter = Counter()
    per_site: Counter = Counter()
    sizes = []
    with CHUNKS_FILE.open("w", encoding="utf-8") as f:
        for doc in docs:
            for c in chunk_doc(doc, seen, stats):
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
                per_site[c["site"]] += 1
                sizes.append(n_tokens(c["text"]))
    sizes.sort()
    total = len(sizes)
    print(f"docs={len(docs)} sections kept={stats['sections']} duplicate sections dropped={stats['dup_sections']}")
    print(f"chunks={total}  " + "  ".join(f"{k}={v}" for k, v in per_site.items()))
    print(f"tokens per chunk: min={sizes[0]} p10={sizes[total // 10]} median={sizes[total // 2]} "
          f"p90={sizes[total * 9 // 10]} max={sizes[-1]}")
    print(f"-> {CHUNKS_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
