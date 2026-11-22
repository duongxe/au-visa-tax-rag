"""Prompt for grounded, cited answers in the asker's language."""
from __future__ import annotations

import re

NOT_FOUND = {
    "vi": "Tôi không tìm thấy thông tin này trong tài liệu hiện có.",
    "en": "I don't know: the available documents do not cover this.",
}

SYSTEM = f"""You answer questions about Australian visas, tax and workplace rights for people living or planning to live in Australia (many are Vietnamese).

Rules:
1. Use ONLY the numbered sources given with the question. Do not use outside knowledge, even if you know the answer.
2. After every sentence that states a fact, cite the source number(s) in square brackets, e.g. [1] or [2][3]. Only cite sources that actually say it.
3. If the sources do not contain the answer, reply with exactly one sentence and no citations:
   - Vietnamese question: "{NOT_FOUND['vi']}"
   - otherwise: "{NOT_FOUND['en']}"
   If they answer only part of the question, answer that part and say what is not covered.
4. Reply in the language of the question. For a Vietnamese question, write natural Vietnamese but keep official English names (visa names, subclass numbers, form and payment names) as they are, e.g. "visa Student (subclass 500)".
5. Be concise and practical: short paragraphs or bullet points, exact numbers, dates and conditions as written in the sources. If a figure may change (rates, thresholds, fees), mention the period the source gives.
6. Do not give personal legal, migration or tax advice and do not guess."""


def format_context(hits: list[dict]) -> str:
    blocks = []
    for n, h in enumerate(hits, start=1):
        where = h["title"]
        if h["headings"]:
            where += " > " + h["headings"][0]
        if h.get("page"):
            where += f" (page {h['page']})"
        blocks.append(f"[{n}] {where}\nURL: {h['url']}\n{h['text']}")
    return "\n\n---\n\n".join(blocks)


def build_prompt(question: str, hits: list[dict]) -> str:
    return f"Sources:\n\n{format_context(hits)}\n\n===\n\nQuestion: {question}"


VI_CHARS = re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", re.I)


def detect_lang(text: str) -> str:
    return "vi" if VI_CHARS.search(text) else "en"


CITE_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def cited_numbers(answer: str) -> list[int]:
    """Source numbers cited in the answer, in order of first appearance."""
    seen: dict[int, None] = {}
    for group in CITE_RE.findall(answer):
        for n in group.split(","):
            seen[int(n)] = None
    return list(seen)
