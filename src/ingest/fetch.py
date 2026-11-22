"""Download every source in sources.csv into data/raw/ and record the download date.

Usage:
    python -m src.ingest.fetch              # download missing files only
    python -m src.ingest.fetch --force      # re-download everything
    python -m src.ingest.fetch --only ato-dasp fw-pay-slips
"""
from __future__ import annotations

import argparse
import time
from datetime import date

import requests

from .common import RAW_DIR, raw_path, read_sources, write_sources

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 Safari/537.36 au-visa-tax-rag",
    "Accept-Language": "en-AU,en;q=0.9",
}
DELAY_SECONDS = 1.5
RETRIES = 3


def download(url: str) -> bytes:
    last_err: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 * attempt)
    raise RuntimeError(f"failed after {RETRIES} attempts: {last_err}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    ap.add_argument("--only", nargs="*", help="doc_ids to download")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_sources()
    ok = failed = skipped = 0
    for row in rows:
        if args.only and row["doc_id"] not in args.only:
            continue
        path = raw_path(row)
        if path.exists() and not args.force:
            skipped += 1
            continue
        try:
            content = download(row["url"])
        except RuntimeError as e:
            print(f"FAIL  {row['doc_id']}: {e}")
            failed += 1
            continue
        if row["doc_type"] == "pdf" and not content.startswith(b"%PDF"):
            print(f"FAIL  {row['doc_id']}: response is not a PDF")
            failed += 1
            continue
        path.write_bytes(content)
        row["downloaded_at"] = date.today().isoformat()
        print(f"OK    {row['doc_id']:40s} {len(content) / 1024:8.0f} KB")
        ok += 1
        time.sleep(DELAY_SECONDS)

    write_sources(rows)
    print(f"\ndownloaded={ok} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
