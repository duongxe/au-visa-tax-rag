"""LLM calls with automatic fallback across models and providers.

The chain is a comma-separated list of `provider:model`, tried in order. A step is
skipped when its provider has no API key in .env. When a call fails (overloaded,
rate limited, out of credit, invalid key, timeout...), the next step is tried and
the failed one is put on cooldown so later requests skip it straight away.

Settings (.env):
    LLM_CHAIN        chain for answers
    LLM_FAST_CHAIN   chain for small tasks (query rewriting); cheap/fast models first
    GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, DEEPSEEK_API_KEY,
    OPENAI_API_KEY, ANTHROPIC_API_KEY

Providers: gemini, openai, anthropic, and the OpenAI-compatible groq, openrouter,
deepseek.
"""
from __future__ import annotations

import logging
import os
import time
from functools import lru_cache

from dotenv import load_dotenv

from ..ingest.common import ROOT

load_dotenv(ROOT / ".env")
log = logging.getLogger(__name__)

DEFAULT_CHAIN = (
    "gemini:gemini-3.5-flash,"
    "gemini:gemini-3.5-flash-lite,"
    "gemini:gemini-3.8-flash,"
    "groq:openai/gpt-oss-120b,"
    "openrouter:openai/gpt-oss-120b,"
    "deepseek:deepseek-chat,"
    "openai:gpt-5-mini,"
    "anthropic:claude-haiku-5-5"
)
DEFAULT_FAST_CHAIN = (
    "gemini:gemini-3.5-flash-lite,"
    "gemini:gemini-3.5-flash,"
    "groq:qwen/qwen3.8-27b,"
    "groq:openai/gpt-oss-20b,"
    "openrouter:openai/gpt-oss-20b,"
    "deepseek:deepseek-chat,"
    "openai:gpt-5-nano,"
    "anthropic:claude-haiku-5-5"
)

# provider -> (env vars holding the key, base_url for OpenAI-compatible APIs)
PROVIDERS: dict[str, tuple[tuple[str, ...], str | None]] = {
    "gemini": (("GEMINI_API_KEY", "GOOGLE_API_KEY"), None),
    "openai": (("OPENAI_API_KEY",), None),
    "anthropic": (("ANTHROPIC_API_KEY",), None),
    "groq": (("GROQ_API_KEY",), "https://api.groq.com/openai/v1"),
    "openrouter": (("OPENROUTER_API_KEY",), "https://openrouter.ai/api/v1"),
    "deepseek": (("DEEPSEEK_API_KEY",), "https://api.deepseek.com"),
}

TEMPERATURE = 0.1
MAX_OUTPUT_TOKENS = 2048
TIMEOUT_S = 45
COOLDOWN_BUSY_S = 300      # overloaded / timeout
COOLDOWN_MINUTE_S = 60     # per-minute rate limit (e.g. Groq free tier tokens per minute)
COOLDOWN_ACCOUNT_S = 3600  # out of credit, billing, invalid key

_cooldown_until: dict[str, float] = {}


def parse_chain(spec: str) -> list[tuple[str, str]]:
    steps = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        provider, sep, model = item.partition(":")
        if not sep or provider not in PROVIDERS:
            raise ValueError(f"bad chain step {item!r}; use provider:model with provider in {list(PROVIDERS)}")
        steps.append((provider, model))
    return steps


def chain(fast: bool = False) -> list[tuple[str, str]]:
    if fast:
        return parse_chain(os.getenv("LLM_FAST_CHAIN") or DEFAULT_FAST_CHAIN)
    return parse_chain(os.getenv("LLM_CHAIN") or DEFAULT_CHAIN)


def api_key(provider: str) -> str | None:
    for var in PROVIDERS[provider][0]:
        if os.getenv(var):
            return os.getenv(var)
    return None


def available(steps: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [s for s in steps if api_key(s[0])]


@lru_cache(maxsize=None)
def _client(provider: str):
    key = api_key(provider)
    if provider == "gemini":
        from google import genai
        from google.genai import types

        return genai.Client(api_key=key, http_options=types.HttpOptions(
            timeout=TIMEOUT_S * 1000, retry_options=types.HttpRetryOptions(attempts=1)))
    if provider == "anthropic":
        import anthropic

        return anthropic.Anthropic(api_key=key, timeout=TIMEOUT_S, max_retries=0)
    import openai

    return openai.OpenAI(api_key=key, base_url=PROVIDERS[provider][1], timeout=TIMEOUT_S, max_retries=0)


def _call(provider: str, model: str, system: str, prompt: str) -> str:
    client = _client(provider)
    if provider == "gemini":
        from google.genai import types

        resp = client.models.generate_content(model=model, contents=prompt, config=types.GenerateContentConfig(
            system_instruction=system, temperature=TEMPERATURE, max_output_tokens=MAX_OUTPUT_TOKENS))
        return resp.text or ""
    if provider == "anthropic":
        resp = client.messages.create(model=model, max_tokens=MAX_OUTPUT_TOKENS, system=system,
                                      messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in resp.content if b.type == "text")
    kwargs = {}
    if provider != "openai":
        # OpenAI reasoning models only accept the default temperature and use
        # max_completion_tokens; the OpenAI-compatible providers take these.
        # Groq counts max_tokens against the per-minute output quota, so keep it bounded.
        kwargs["temperature"] = TEMPERATURE
        kwargs["max_tokens"] = MAX_OUTPUT_TOKENS
    if provider == "groq" and model == "openai/gpt-oss-20b":
        # Used for short tasks (query rewriting). With the default effort it sometimes
        # spends all max_tokens on reasoning and returns empty content. Not applied to
        # gpt-oss-120b: low effort made its Vietnamese answers noticeably worse.
        kwargs["reasoning_effort"] = "low"
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        **kwargs,
    )
    return resp.choices[0].message.content or ""


ACCOUNT_HINTS = ("quota", "credit", "billing", "balance", "insufficient", "api key", "api_key",
                 "unauthorized", "permission", "payment")


def _cooldown_for(err: Exception) -> int:
    code = getattr(err, "code", None) or getattr(err, "status_code", None)
    msg = str(err).lower()
    if code in (401, 402, 403) or any(h in msg for h in ACCOUNT_HINTS):
        return COOLDOWN_ACCOUNT_S
    if "per min" in msg or "per minute" in msg:
        return COOLDOWN_MINUTE_S
    return COOLDOWN_BUSY_S


def generate(system: str, prompt: str, fast: bool = False,
             steps: list[tuple[str, str]] | None = None) -> tuple[str, str]:
    """Run the chain. Returns (text, "provider:model" that answered)."""
    steps = available(steps or chain(fast))
    if not steps:
        raise RuntimeError("no LLM API key set: add GEMINI_API_KEY (or another provider's key) to .env")
    now = time.time()
    # Steps on cooldown go last (still tried if everything else fails).
    steps.sort(key=lambda s: _cooldown_until.get(f"{s[0]}:{s[1]}", 0) > now)
    errors = []
    for provider, model in steps:
        name = f"{provider}:{model}"
        try:
            text = _call(provider, model, system, prompt).strip()
        except Exception as e:  # any provider failure -> next step
            _cooldown_until[name] = time.time() + _cooldown_for(e)
            short = " ".join(str(e).split())[:160]
            log.warning("LLM %s failed: %s", name, short)
            errors.append(f"{name}: {short}")
            continue
        if not text:
            errors.append(f"{name}: empty response")
            continue
        _cooldown_until.pop(name, None)
        return text, name
    raise RuntimeError("all LLM providers failed:\n  " + "\n  ".join(errors))
