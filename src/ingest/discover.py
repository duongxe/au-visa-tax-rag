"""Build sources.csv automatically for the full visa + ATO (individuals) corpus.

Scope:
  * Home Affairs: every page under /visas/getting-a-visa/visa-listing/ (visa + stream
    pages), discovered from the site-wide visa menu embedded in every visa page.
  * ATO: every page under /individuals-and-families/ from the ATO sitemap, minus
    year-specific pages (old myTax instructions etc.), plus a few rate pages.
  * Rows from other sites already in sources.csv (Fair Work) are kept as they are.

Rows whose URL was already in sources.csv keep their download date, and their raw
file is renamed to the new doc_id so it is not downloaded again.

Usage:
    python -m src.ingest.discover            # rewrite sources.csv
    python -m src.ingest.discover --dry-run  # only print counts
"""
from __future__ import annotations

import argparse
import hashlib
import re
from urllib.parse import urlparse

import requests

from .common import raw_path, read_sources, write_sources
from .fetch import HEADERS

HA_BASE = "https://immi.homeaffairs.gov.au"
HA_SEED = f"{HA_BASE}/visas/getting-a-visa/visa-listing/student-500"
HA_PREFIX = "/visas/getting-a-visa/visa-listing/"

ATO_SITEMAP = "https://www.ato.gov.au/sitemap.xml"
ATO_PREFIX = "/individuals-and-families/"
# Pages for a specific year (e.g. .../mytax-instructions/2019/...) are mostly old copies.
YEAR_RE = re.compile(r"(?:^|[/\-])(?:19|20)\d\d(?:[\-/]|$)")
ATO_EXTRA_RE = re.compile(
    r"/tax-rates-and-codes/(tax-rates-australian-residents|tax-rates-foreign-residents"
    r"|tax-rates-working-holiday-makers|key-superannuation-rates-and-thresholds)(/|$)"
)

# From robots.txt (Disallow) on immi.homeaffairs.gov.au / ato.gov.au
ROBOTS_DISALLOW = ["/help-text/", "/sitesearch?", "/workarea/", "/widgets/", "/misc/"]

MAX_ID_LEN = 120


def make_id(prefix: str, path: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower().strip("/").replace("/", "--")).strip("-")
    doc_id = f"{prefix}-{slug}"
    if len(doc_id) > MAX_ID_LEN:
        digest = hashlib.md5(path.encode()).hexdigest()[:8]
        doc_id = f"{doc_id[: MAX_ID_LEN - 9]}-{digest}"
    return doc_id


def allowed(path: str) -> bool:
    return not any(path.startswith(p) for p in ROBOTS_DISALLOW)


def discover_homeaffairs() -> list[dict]:
    html = requests.get(HA_SEED, headers=HEADERS, timeout=60).text
    paths = sorted(set(re.findall(r"/visas/getting-a-visa/visa-listing/[a-z0-9\-]+(?:/[a-z0-9\-]+)*", html)))
    rows = []
    for path in paths:
        if not allowed(path):
            continue
        rows.append({
            "doc_id": make_id("ha", path[len(HA_PREFIX):]),
            "url": HA_BASE + path,
            "title": "",
            "site": "immi.homeaffairs.gov.au",
            "doc_type": "html",
            "downloaded_at": "",
            "notes": "",
        })
    return rows


def discover_ato() -> list[dict]:
    xml = requests.get(ATO_SITEMAP, headers=HEADERS, timeout=120).text
    urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
    rows = []
    for url in sorted(set(urls)):
        path = urlparse(url).path
        if path.startswith(ATO_PREFIX):
            if YEAR_RE.search(path):
                continue
            doc_id = make_id("ato", path[len(ATO_PREFIX):])
        elif ATO_EXTRA_RE.search(path):
            doc_id = make_id("ato-rates", path.split("/tax-rates-and-codes/", 1)[1])
        else:
            continue
        if not allowed(path):
            continue
        rows.append({
            "doc_id": doc_id,
            "url": url,
            "title": "",
            "site": "ato.gov.au",
            "doc_type": "html",
            "downloaded_at": "",
            "notes": "",
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    old = read_sources()
    old_by_url = {r["url"]: r for r in old}
    keep = [r for r in old if r["site"] not in ("immi.homeaffairs.gov.au", "ato.gov.au")]

    ha = discover_homeaffairs()
    ato = discover_ato()
    new_rows = ha + ato

    # Carry over download date / title / notes; rename raw files to the new doc_id.
    renamed = 0
    for row in new_rows:
        prev = old_by_url.get(row["url"])
        if not prev:
            continue
        row["title"] = prev["title"]
        row["notes"] = prev["notes"]
        src = raw_path(prev)
        if src.exists():
            row["downloaded_at"] = prev["downloaded_at"]
            dst = raw_path(row)
            if src != dst and not args.dry_run:
                src.replace(dst)
                renamed += 1

    ids = [r["doc_id"] for r in new_rows + keep]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"duplicate doc_ids: {sorted(dupes)[:10]}")

    print(f"Home Affairs: {len(ha)}  ATO: {len(ato)}  kept (other sites): {len(keep)}  "
          f"total: {len(ids)}  raw files renamed: {renamed}")
    if not args.dry_run:
        write_sources(ha + ato + keep)


if __name__ == "__main__":
    main()
