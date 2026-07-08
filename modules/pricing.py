"""API cost estimation constants and helper.

Pricing drifts over time -- update these constants when provider pricing changes, and
record the update date in CHANGELOG.md (see docs/architecture.md > pricing.py).
"""

# USD per 1,000 tokens. Last verified: see CHANGELOG.md [0.1.0] entry.
PRICING: dict[str, dict[str, dict[str, float]]] = {
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


def estimate_cost(word_count: int, provider: str, model: str) -> float | None:
    """Return estimated cost in USD for one llm_scorer.score() call. None if unknown model."""
    rates = PRICING.get(provider, {}).get(model)
    if rates is None:
        return None
    input_tokens = word_count * WORDS_TO_TOKENS_RATIO
    cost = (input_tokens / 1000) * rates["input"] + (ESTIMATED_OUTPUT_TOKENS / 1000) * rates["output"]
    return round(cost, 4)


if __name__ == "__main__":
    assert estimate_cost(5000, "anthropic", "claude-haiku-4-5-20251001") is not None
    assert estimate_cost(5000, "anthropic", "nonexistent-model") is None
    assert estimate_cost(5000, "nonexistent-provider", "x") is None
    print("OK --", estimate_cost(5000, "anthropic", "claude-haiku-4-5-20251001"), "USD for a 5,000-word story on Haiku")
