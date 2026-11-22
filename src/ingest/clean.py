"""Turn raw HTML/PDF files into clean JSON documents with section + page metadata.

Output: data/processed/<doc_id>.json
{
  "doc_id", "title", "url", "site", "doc_type", "downloaded_at",
  "sections": [{"heading": str, "page": int | None, "text": str}, ...]
}

Usage:
    python -m src.ingest.clean
    python -m src.ingest.clean --only ha-student-500
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata

import pymupdf
import trafilatura
from bs4 import BeautifulSoup, NavigableString, Tag

from .common import PROCESSED_DIR, raw_path, read_sources

MIN_SECTION_CHARS = 40
MIN_DOC_CHARS = 1000   # warn below this
MIN_KEEP_CHARS = 300   # drop below this (landing pages that only link elsewhere)

# Lines that are UI chrome rather than content.
JUNK_LINE_PATTERNS = [
    r"^QC \d+$",
    r"^Last (updated|modified)\b.*$",
    r"^(Print|Share|Back to top|Was this page helpful\??)$",
    r"^Page \d+ of \d+$",
    r"^fairwork\.gov\.au$",
    r"^Fair Work Ombudsman\s*$",
]
JUNK_INLINE = [
    "External Link",
    "Opens in a new window",
    "(opens in a new window)",
]


# ---------------------------------------------------------------- text utils
def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace(" ", " ").replace("​", "").replace("�", "")
    # Control chars (except newline/tab) and private-use glyphs (PDF icon fonts).
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f-]", "", text)
    for junk in JUNK_INLINE:
        text = text.replace(junk, "")
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if any(re.match(p, line, re.I) for p in JUNK_LINE_PATTERNS):
            continue
        lines.append(line)
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def html_fragment_to_text(fragment: str, md_headings: bool = False) -> str:
    """Convert an HTML fragment to plain text that keeps lists, tables and sub-headings.

    With md_headings=True, headings are emitted as markdown ('## ...') so the text
    can later be split into sections with split_markdown().
    """
    soup = BeautifulSoup(fragment or "", "html.parser")
    for el in soup.select("a.btn, script, style"):
        el.decompose()

    out: list[str] = []

    def walk(node, list_depth: int = 0) -> None:
        for child in node.children:
            if isinstance(child, NavigableString):
                s = str(child)
                if s.strip():
                    out.append(s)
                continue
            if not isinstance(child, Tag):
                continue
            name = child.name
            if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                marker = "#" * int(name[1]) + " " if md_headings else ""
                out.append(f"\n\n{marker}{child.get_text(' ', strip=True)}\n")
            elif name in ("ul", "ol"):
                out.append("\n")
                walk(child, list_depth + 1)
                out.append("\n")
            elif name == "li":
                out.append("\n" + "  " * max(list_depth - 1, 0) + "- ")
                walk(child, list_depth)
            elif name in ("p", "div", "table", "section"):
                out.append("\n\n")
                walk(child, list_depth)
                out.append("\n")
            elif name == "tr":
                cells = [c.get_text(" ", strip=True) for c in child.find_all(["td", "th"])]
                out.append("\n" + " | ".join(cells))
            elif name == "br":
                out.append("\n")
            else:
                walk(child, list_depth)

    walk(soup)
    return normalize("".join(out))


def section(heading: str, text: str, page: int | None = None) -> dict | None:
    text = normalize(text)
    if len(text) < MIN_SECTION_CHARS:
        return None
    return {"heading": normalize(heading) or None, "page": page, "text": text}


def split_markdown(md: str, base: str | None = None) -> list[dict]:
    """Split markdown into sections; heading = breadcrumb of the heading stack."""
    sections: list[dict] = []
    path: list[tuple[int, str]] = []
    buf: list[str] = []

    def flush() -> None:
        crumbs = ([base] if base else []) + [h for _, h in path]
        s = section(" > ".join(crumbs) or "Introduction", "\n".join(buf))
        if s:
            sections.append(s)
        buf.clear()

    for line in md.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if m:
            flush()
            level, text = len(m.group(1)), m.group(2).strip().strip("*").strip()
            while path and path[-1][0] >= level:
                path.pop()
            path.append((level, text))
        else:
            buf.append(line)
    flush()
    return sections


# ------------------------------------------------- immi.homeaffairs.gov.au
HA_TABS = [
    ("overview", "Overview"),
    ("aboutVisa", "About this visa"),
    ("eligibility", "Eligibility"),
    ("stepGuide", "Step by step"),
    ("haveThisVisa", "When you have this visa"),
]
HA_OVERVIEW_FIELDS = [
    ("notes", "notesHeading", "You must"),
    ("withThisVisa", "withThisVisaHeading", "With this visa you can"),
    ("visaStay", None, "How long you can stay"),
    ("visaCost", None, "Cost"),
    ("visaProcessingTime", None, "Processing time"),
]


def parse_homeaffairs(raw: bytes) -> tuple[str | None, list[dict]]:
    """immi.homeaffairs.gov.au is SharePoint + Angular. Content lives in one of:

    1. visa pages:    JSON in the PageSchemaHiddenField input (applicant/sponsor tabs)
    2. topic pages:   JSON in the same input shaped {"content": [{"text", "block"}]}
    3. article pages: plain HTML inside div#...RichHtmlField
    """
    soup = BeautifulSoup(raw, "html.parser")
    sections: list[dict] = []
    add = lambda s: s and sections.append(s)  # noqa: E731
    title = None

    holder = soup.find("input", id=re.compile(r"PageSchemaHiddenField_Input$"))
    data = json.loads(holder["value"]) if holder is not None and holder.get("value") else {}

    if data.get("applicant") or data.get("sponsor"):
        title = _parse_ha_visa(data, add)
    elif data.get("subClass"):
        # Stream-chooser page: short summary + eligibility; details live on stream pages.
        title = f"{(data.get('title') or '').strip()} ({data['subClass']})"
        add(section("Overview", html_fragment_to_text(data.get("description", ""))))
        add(section("Overview > Eligibility", html_fragment_to_text(data.get("eligibility", ""))))
    for item in data.get("content") or []:
        add(section(item.get("text", ""), html_fragment_to_text(item.get("block", ""))))
    for div in soup.find_all("div", id=re.compile(r"RichHtmlField$")):
        for s in split_markdown(html_fragment_to_text(str(div), md_headings=True)):
            add(s)

    if not sections:
        raise ValueError("no content found in any known Home Affairs layout")
    return title, sections


def _parse_ha_visa(data: dict, add) -> str | None:
    title = data.get("title")
    if data.get("visaSubclassHeading"):
        title = f"{title} ({data['visaSubclassHeading']})"

    add(section("Overview", data.get("description", "")))

    for actor_key, actor_label in (("applicant", None), ("sponsor", "Sponsor")):
        actor = data.get(actor_key) or {}
        prefix = f"{actor_label} > " if actor_label else ""
        for key, tab_label in HA_TABS:
            tab = actor.get(key)
            if not tab:
                continue
            base = prefix + tab_label
            if key == "overview":
                for field, heading_field, default in HA_OVERVIEW_FIELDS:
                    heading = tab.get(heading_field) if heading_field else None
                    add(section(f"{base} > {heading or default}", html_fragment_to_text(tab.get(field, ""))))
                continue
            cta = (tab.get("callToAction") or {}).get("body")
            if cta:
                add(section(base, html_fragment_to_text(cta)))
            for item in tab.get("content") or []:
                add(section(f"{base} > {item.get('text', '')}", html_fragment_to_text(item.get("block", ""))))
            for item in tab.get("criteria") or []:
                _ha_nested(item, base, "criteria", add)
            for item in tab.get("steps") or []:
                _ha_nested(item, base, "steps", add)
    return title


def _ha_nested(item: dict, base: str, child_key: str, add) -> None:
    heading = f"{base} > {item.get('title', '')}"
    body = "\n\n".join(
        html_fragment_to_text(item.get(k, "")) for k in ("subTitle", "description") if item.get(k)
    )
    add(section(heading, body))
    for child in item.get(child_key) or []:
        _ha_nested(child, heading, child_key, add)


# ------------------------------------------------- generic HTML (ATO, Fair Work)
TITLE_SUFFIXES = [" | Australian Taxation Office", " - Fair Work Ombudsman"]


def parse_html(raw: bytes) -> tuple[str | None, list[dict]]:
    md = trafilatura.extract(
        raw,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_comments=False,
        favor_recall=True,  # precision mode drops the headings we need for sections
    )
    if not md:
        raise ValueError("trafilatura returned no content")
    meta = trafilatura.extract_metadata(raw)
    title = meta.title if meta else None
    for suffix in TITLE_SUFFIXES:
        if title and title.endswith(suffix):
            title = title[: -len(suffix)]
    return title, split_markdown(md)


# ------------------------------------------------- PDF
def parse_pdf(raw: bytes) -> tuple[str | None, list[dict]]:
    """Sections split on large-font headings; a new section also starts on each page
    so every section has exactly one page number for citations."""
    doc = pymupdf.open(stream=raw, filetype="pdf")
    blocks = []  # (page_no, paragraph_text, max_font_size)
    for page_no, page in enumerate(doc, start=1):
        for block in page.get_text("dict")["blocks"]:
            lines, size = [], 0.0
            for line in block.get("lines", []):
                text = normalize("".join(s["text"] for s in line["spans"]))
                if text:
                    lines.append(text)
                    size = max([size] + [s["size"] for s in line["spans"] if s["text"].strip()])
            if lines:
                # Re-join hard-wrapped lines into one paragraph; keep bullets on their own line.
                para = ""
                for ln in lines:
                    if para and not re.match(r"^[-•●▪]\s*", ln):
                        para += ("" if para.endswith("-") else " ") + ln
                    else:
                        para += ("\n" if para else "") + ln
                blocks.append((page_no, para, size))
    if not blocks:
        raise ValueError("PDF has no extractable text (scanned?)")

    sizes = sorted(b[2] for b in blocks)
    body_size = sizes[len(sizes) // 2]
    title = (doc.metadata or {}).get("title") or None

    def is_heading(text: str, size: float) -> bool:
        return (
            size >= body_size * 1.2
            and len(text) < 120
            and len(re.findall(r"[A-Za-z]", text)) >= 4
        )

    sections: list[dict] = []
    heading, page_start, buf = "Introduction", 1, []

    def flush() -> None:
        s = section(heading, "\n\n".join(buf), page_start)
        if s:
            sections.append(s)
        buf.clear()

    for page_no, text, size in blocks:
        if is_heading(text, size):
            flush()
            heading, page_start = text.replace("\n", " "), page_no
            continue
        if buf and page_no != page_start:
            flush()
        if not buf:
            page_start = page_no
        buf.append(text)
    flush()
    return title, sections


# ------------------------------------------------- driver
def clean_one(row: dict) -> dict:
    raw = raw_path(row).read_bytes()
    if row["doc_type"] == "pdf":
        title, sections = parse_pdf(raw)
    elif row["site"] == "immi.homeaffairs.gov.au":
        title, sections = parse_homeaffairs(raw)
    else:
        title, sections = parse_html(raw)

    # Drop exact duplicate sections (menus repeated on page etc.)
    seen, unique = set(), []
    for s in sections:
        key = s["text"]
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return {
        "doc_id": row["doc_id"],
        "title": row["title"] or title,
        "url": row["url"],
        "site": row["site"],
        "doc_type": row["doc_type"],
        "downloaded_at": row["downloaded_at"],
        "sections": unique,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="doc_ids to clean")
    ap.add_argument("-v", "--verbose", action="store_true", help="print a line per document")
    args = ap.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_sources()

    if not args.only:  # remove output of documents no longer in sources.csv
        wanted = {r["doc_id"] for r in rows}
        for f in PROCESSED_DIR.glob("*.json"):
            if f.stem not in wanted:
                f.unlink()

    stats: dict[str, dict] = {}
    issues: list[str] = []
    for row in rows:
        if args.only and row["doc_id"] not in args.only:
            continue
        st = stats.setdefault(row["site"], {"docs": 0, "sections": 0, "chars": 0, "skipped": 0})
        out = PROCESSED_DIR / f"{row['doc_id']}.json"
        if not raw_path(row).exists():
            if row["notes"] != "not found":
                issues.append(f"MISSING  {row['doc_id']} (run fetch)")
            st["skipped"] += 1
            continue
        try:
            doc = clean_one(row)
        except Exception as e:  # keep going, report at the end
            issues.append(f"ERROR    {row['doc_id']}: {e}")
            st["skipped"] += 1
            out.unlink(missing_ok=True)
            continue
        chars = sum(len(s["text"]) for s in doc["sections"])
        if chars < MIN_KEEP_CHARS:
            # Index/landing pages that only link elsewhere: nothing worth retrieving.
            st["skipped"] += 1
            out.unlink(missing_ok=True)
            if args.verbose:
                print(f"skip  {row['doc_id']} ({chars} chars)")
            continue
        if chars < MIN_DOC_CHARS:
            issues.append(f"SHORT    {row['doc_id']} ({chars} chars)")
        st["docs"] += 1
        st["sections"] += len(doc["sections"])
        st["chars"] += chars
        if args.verbose:
            print(f"{row['doc_id']:60s} {len(doc['sections']):5d} {chars:8d}")
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'site':28s} {'docs':>6s} {'skipped':>8s} {'sections':>9s} {'chars':>11s}")
    for site, st in stats.items():
        print(f"{site:28s} {st['docs']:6d} {st['skipped']:8d} {st['sections']:9d} {st['chars']:11,d}")
    tot = {k: sum(s[k] for s in stats.values()) for k in ("docs", "skipped", "sections", "chars")}
    print(f"{'TOTAL':28s} {tot['docs']:6d} {tot['skipped']:8d} {tot['sections']:9d} {tot['chars']:11,d}")
    errors = [i for i in issues if not i.startswith("SHORT")]
    print(f"\n{len(errors)} errors/missing, {len(issues) - len(errors)} short docs (kept)")
    for line in errors[:30]:
        print("  " + line)


if __name__ == "__main__":
    main()
