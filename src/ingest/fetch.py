"""Download every source in sources.csv into data/raw/ and record the download date.

Usage:
    python -m src.ingest.fetch              # download missing files only
    python -m src.ingest.fetch --force      # re-download everything
    python -m src.ingest.fetch --only ato-dasp fw-pay-slips
"""
from __future__ import annotations

import argparse
import html
import re
import time
from datetime import date

import requests

from .common import RAW_DIR, raw_path, read_sources, write_sources

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 Safari/537.36 au-visa-tax-rag",
    "Accept-Language": "en-AU,en;q=0.9",
}
DELAY_SECONDS = 1.0
RETRIES = 3


class NotFound(Exception):
    pass


def download(url: str) -> bytes:
    last_err: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            # 401/403: access-restricted pages linked from the public menu; not retryable.
            if r.status_code in (401, 403, 404, 410):
                raise NotFound(f"http {r.status_code}")
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 * attempt)
    raise RuntimeError(f"failed after {RETRIES} attempts: {last_err}")


TITLE_SUFFIXES = (" | Australian Taxation Office", " - Fair Work Ombudsman")


def page_title(content: bytes) -> str:
    m = re.search(rb"<title[^>]*>(.*?)</title>", content, re.S | re.I)
    if not m:
        return ""
    title = html.unescape(m.group(1).decode("utf-8", "replace"))
    title = re.sub(r"\s+", " ", title).strip()
    for suffix in TITLE_SUFFIXES:
        title = title.removesuffix(suffix)
    return title


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    ap.add_argument("--only", nargs="*", help="doc_ids to download")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_sources()
    todo = [
        r for r in rows
        if (not args.only or r["doc_id"] in args.only)
        and (args.force or not raw_path(r).exists())
        and (args.force or r["notes"] != "not found")
    ]
    print(f"{len(rows)} sources, {len(todo)} to download")
    ok = failed = 0
    for i, row in enumerate(todo, start=1):
        path = raw_path(row)
        try:
            content = download(row["url"])
        except NotFound as e:
            print(f"[{i}/{len(todo)}] 404   {row['doc_id']}: {e}")
            row["notes"] = "not found"
            failed += 1
            continue
        except RuntimeError as e:
            print(f"[{i}/{len(todo)}] FAIL  {row['doc_id']}: {e}")
            failed += 1
            continue
        if row["doc_type"] == "pdf" and not content.startswith(b"%PDF"):
            print(f"[{i}/{len(todo)}] FAIL  {row['doc_id']}: response is not a PDF")
            failed += 1
            continue
        path.write_bytes(content)
        row["downloaded_at"] = date.today().isoformat()
        if not row["title"] and row["doc_type"] == "html":
            row["title"] = page_title(content)
        ok += 1
        if i % 25 == 0 or i == len(todo):
            print(f"[{i}/{len(todo)}] ok={ok} failed={failed}", flush=True)
            write_sources(rows)  # checkpoint so an interrupted run can resume
        time.sleep(DELAY_SECONDS)

    write_sources(rows)
    print(f"\ndownloaded={ok} failed={failed}")


if __name__ == "__main__":
    main()
