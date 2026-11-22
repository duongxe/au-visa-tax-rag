"""Gemini client (Google GenAI SDK).

Settings (.env):
    GEMINI_API_KEY        key from https://aistudio.google.com/apikey
    LLM_MODEL             main Gemini model id
    LLM_FALLBACK_MODELS   comma-separated models tried when the main one is
                          overloaded (503) or rate limited (429)
"""
from __future__ import annotations

import os
import time
from functools import lru_cache

from dotenv import load_dotenv

from ..ingest.common import ROOT

load_dotenv(ROOT / ".env")

LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash")
FALLBACK_MODELS = [m.strip() for m in os.getenv(
    "LLM_FALLBACK_MODELS", "gemini-3.5-flash-lite,gemini-3.8-flash").split(",") if m.strip()]
TEMPERATURE = 0.1
TIMEOUT_MS = 45_000
RETRYABLE = (429, 500, 502, 503, 504)
COOLDOWN_SECONDS = 300  # skip a model for 5 minutes after it was busy

_busy_until: dict[str, float] = {}


@lru_cache(maxsize=1)
def get_client():
    from google import genai
    from google.genai import types

    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set (put it in .env)")
    # Retries are handled here (with model fallback), not by the SDK.
    return genai.Client(api_key=key, http_options=types.HttpOptions(
        timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)))


def generate(system: str, prompt: str, model: str | None = None) -> tuple[str, str]:
    """Returns (text, model actually used)."""
    from google.genai import errors, types

    config = types.GenerateContentConfig(system_instruction=system, temperature=TEMPERATURE)
    models = [model] if model else list(dict.fromkeys([LLM_MODEL, *FALLBACK_MODELS]))
    now = time.time()
    # Models that failed recently go last instead of being tried first again.
    models.sort(key=lambda m: _busy_until.get(m, 0) > now)
    last: Exception | None = None
    for m in models:
        try:
            resp = get_client().models.generate_content(model=m, contents=prompt, config=config)
            _busy_until.pop(m, None)
            return (resp.text or "").strip(), m
        except errors.APIError as e:
            if e.code not in RETRYABLE:
                raise
            _busy_until[m] = time.time() + COOLDOWN_SECONDS
            last = e
    raise RuntimeError(f"all Gemini models busy or rate limited ({', '.join(models)}): {last}")
