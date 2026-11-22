"""Retrieval settings, read from the environment (.env) with project defaults."""
from __future__ import annotations

import os

from dotenv import load_dotenv

from ..ingest.common import ROOT

load_dotenv(ROOT / ".env")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
INDEX_DIR = ROOT / os.getenv("INDEX_DIR", "data/index")
