"""API cost estimation constants and helper.

Live pricing is pulled from the LiteLLM open-source project's community-maintained price
matrix (LITELLM_PRICING_URL), which tracks official provider pricing and is typically
updated within hours of a pricing change or model release. The fetched result is cached
in-process for CACHE_TTL_SECONDS so a Streamlit rerun does not trigger a network call every
time.

If the fetch fails (offline, timeout, GitHub outage) or a specific model is missing from the
live data, cost estimation falls back to FALLBACK_PRICING below for that model. Update
FALLBACK_PRICING when it drifts too far from reality, and record the update date in
CHANGELOG.md (see docs/architecture.md > pricing.py).

The token estimate itself tracks what llm_scorer.py actually sends, not just the raw
manuscript word count:
- Input is capped at MAX_STORY_WORDS, matching llm_scorer._build_prompt's truncation --
  manuscripts longer than that never bill for more than the truncated amount.
- PROMPT_SCAFFOLDING_WORDS accounts for the fixed instructions/feature-questions/
  deterministic-score lines that surround the story text in every prompt.
- estimate_cost() returns a (low, high) range rather than one number: llm_scorer.score()
  retries once (resending the full prompt) on malformed JSON or an invalid field value, which
  roughly doubles the tokens actually billed for that run.
"""

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from modules.llm_scorer import MAX_STORY_WORDS
from modules.logging_config import get_logger

logger = get_logger("pricing")

LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
FETCH_TIMEOUT_SECONDS = 5
CACHE_TTL_SECONDS = 6 * 60 * 60  # Re-fetch at most once per 6 hours per server process.

# USD per 1,000 tokens. Used only when live pricing is unavailable for a model.
# Last verified: see CHANGELOG.md [0.1.0] entry.
FALLBACK_PRICING: dict[str, dict[str, dict[str, float]]] = {
    "anthropic": {
        "claude-haiku-4-5-20251001": {"input": 0.0008, "output": 0.004},
        "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    },
    "openai": {
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4o": {"input": 0.005, "output": 0.015},
    },
}

WORDS_TO_TOKENS_RATIO = 1.35  # Approximate; used for cost estimation only.
ESTIMATED_OUTPUT_TOKENS = 200  # Approximate LLM response length for the 16 scored features.

# Fixed instructions + 16 feature questions + 15 deterministic-score lines that
# llm_scorer._build_prompt wraps every story in, regardless of manuscript length. Measured
# at ~365 words for the current LLM_FEATURES set; rounded up for a safety margin. Update if
# LLM_FEATURES grows/shrinks meaningfully.
PROMPT_SCAFFOLDING_WORDS = 400

# llm_scorer.score() makes at most one retry (malformed JSON or an invalid field value),
# which resends the full prompt. Used as a multiplier for the high end of the cost estimate.
RETRY_COST_MULTIPLIER = 2

_cache: dict[str, dict[str, dict[str, float]]] | None = None
_cache_live_models: set[tuple[str, str]] = set()
_cache_fetched_at: float = 0.0


def _fetch_live_pricing() -> dict | None:
    """Fetch the LiteLLM master price matrix. Returns None on any failure (network, timeout,
    malformed JSON) -- this is a best-effort enhancement, never a hard requirement."""
    try:
        with urllib.request.urlopen(LITELLM_PRICING_URL, timeout=FETCH_TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Live pricing fetch failed (%s) -- using bundled fallback pricing.", type(exc).__name__)
        return None


def _build_pricing(_fetch_fn=None) -> tuple[dict[str, dict[str, dict[str, float]]], set[tuple[str, str]]]:
    """Return (pricing dict, set of (provider, model) pairs sourced from live data).

    Only ever prices the (provider, model) pairs already known via FALLBACK_PRICING -- this
    does not surface arbitrary models from the LiteLLM matrix, just refreshes rates for the
    ones this app already supports. Each model falls back independently, so a live fetch that
    is missing one model doesn't discard live data for the others.

    _fetch_fn defaults to the module-level _fetch_live_pricing, resolved at call time (not
    bound as a parameter default) so tests can monkeypatch it via `pricing._fetch_live_pricing`.
    """
    remote = (_fetch_fn or _fetch_live_pricing)()
    pricing: dict[str, dict[str, dict[str, float]]] = {}
    live_models: set[tuple[str, str]] = set()

    for provider, models in FALLBACK_PRICING.items():
        pricing[provider] = {}
        for model, fallback_rates in models.items():
            entry = (remote or {}).get(model)
            has_rates = entry and "input_cost_per_token" in entry and "output_cost_per_token" in entry
            if has_rates and entry.get("litellm_provider") == provider:
                pricing[provider][model] = {
                    "input": entry["input_cost_per_token"] * 1000,
                    "output": entry["output_cost_per_token"] * 1000,
                }
                live_models.add((provider, model))
            else:
                pricing[provider][model] = fallback_rates

    return pricing, live_models


def get_pricing() -> tuple[dict[str, dict[str, dict[str, float]]], set[tuple[str, str]]]:
    """Return (pricing dict, live (provider, model) pairs), refreshed at most every
    CACHE_TTL_SECONDS. Safe to call on every Streamlit rerun."""
    global _cache, _cache_live_models, _cache_fetched_at
    now = time.monotonic()
    if _cache is None or (now - _cache_fetched_at) > CACHE_TTL_SECONDS:
        _cache, _cache_live_models = _build_pricing()
        _cache_fetched_at = now
    return _cache, _cache_live_models


@dataclass
class CostEstimate:
    low: float  # Cost if llm_scorer.score() succeeds on the first call.
    high: float  # Cost if it needs its one retry (full prompt resent).
    is_live_pricing: bool


def estimate_cost(word_count: int, provider: str, model: str) -> CostEstimate | None:
    """Return a CostEstimate for one llm_scorer.score() call, or None if the provider/model
    pair is unknown. `word_count` is the raw manuscript word count (pre-truncation) -- this
    caps it at MAX_STORY_WORDS and adds prompt scaffolding to mirror what's actually sent."""
    pricing, live_models = get_pricing()
    rates = pricing.get(provider, {}).get(model)
    if rates is None:
        return None
    billed_words = min(word_count, MAX_STORY_WORDS) + PROMPT_SCAFFOLDING_WORDS
    input_tokens = billed_words * WORDS_TO_TOKENS_RATIO
    single_call_cost = (input_tokens / 1000) * rates["input"] + (ESTIMATED_OUTPUT_TOKENS / 1000) * rates["output"]
    return CostEstimate(
        low=round(single_call_cost, 4),
        high=round(single_call_cost * RETRY_COST_MULTIPLIER, 4),
        is_live_pricing=(provider, model) in live_models,
    )


if __name__ == "__main__":
    assert estimate_cost(5000, "anthropic", "claude-haiku-4-5-20251001") is not None
    assert estimate_cost(5000, "anthropic", "nonexistent-model") is None
    assert estimate_cost(5000, "nonexistent-provider", "x") is None
    assert estimate_cost(500_000, "anthropic", "claude-haiku-4-5-20251001").low == estimate_cost(
        MAX_STORY_WORDS, "anthropic", "claude-haiku-4-5-20251001"
    ).low, "cost must be capped at MAX_STORY_WORDS regardless of manuscript length"
    result = estimate_cost(5000, "anthropic", "claude-haiku-4-5-20251001")
    print(
        "OK --", result.low, "-", result.high,
        "USD for a 5,000-word story on Haiku (live pricing:", result.is_live_pricing, ")",
    )
