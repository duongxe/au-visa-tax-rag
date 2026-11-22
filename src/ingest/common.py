"""Shared paths and helpers for the ingest pipeline."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES_CSV = ROOT / "sources.csv"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

FIELDS = ["doc_id", "url", "title", "site", "doc_type", "downloaded_at", "notes"]


def read_sources() -> list[dict]:
    with SOURCES_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_sources(rows: list[dict]) -> None:
    with SOURCES_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def raw_path(row: dict) -> Path:
    ext = "pdf" if row["doc_type"] == "pdf" else "html"
    return RAW_DIR / f"{row['doc_id']}.{ext}"
