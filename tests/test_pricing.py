import pytest

from modules import pricing


def _fake_remote():
    return {
        "claude-haiku-4-5-20251001": {
            "input_cost_per_token": 1e-06,
            "output_cost_per_token": 5e-06,
            "litellm_provider": "anthropic",
        },
        "claude-sonnet-4-6": {
            "input_cost_per_token": 3e-06,
            "output_cost_per_token": 1.5e-05,
            "litellm_provider": "anthropic",
        },
        "gpt-4o-mini": {
            "input_cost_per_token": 1.5e-07,
            "output_cost_per_token": 6e-07,
            "litellm_provider": "openai",
        },
        "gpt-4o": {
            "input_cost_per_token": 2.5e-06,
            "output_cost_per_token": 1e-05,
            "litellm_provider": "openai",
        },
    }


def test_live_fetch_success_uses_live_rates_for_all_known_models():
    pricing_dict, live_models = pricing._build_pricing(_fetch_fn=_fake_remote)
    assert live_models == {
        ("anthropic", "claude-haiku-4-5-20251001"),
        ("anthropic", "claude-sonnet-4-6"),
        ("openai", "gpt-4o-mini"),
        ("openai", "gpt-4o"),
    }
    assert pricing_dict["anthropic"]["claude-haiku-4-5-20251001"] == {"input": 0.001, "output": 0.005}


def test_fetch_failure_falls_back_to_bundled_pricing_for_every_model():
    pricing_dict, live_models = pricing._build_pricing(_fetch_fn=lambda: None)
    assert live_models == set()
    assert pricing_dict == pricing.FALLBACK_PRICING


def test_model_missing_from_live_data_falls_back_only_for_that_model():
    def fetch_missing_sonnet():
        data = _fake_remote()
        del data["claude-sonnet-4-6"]
        return data

    pricing_dict, live_models = pricing._build_pricing(_fetch_fn=fetch_missing_sonnet)
    assert ("anthropic", "claude-sonnet-4-6") not in live_models
    assert ("anthropic", "claude-haiku-4-5-20251001") in live_models
    assert pricing_dict["anthropic"]["claude-sonnet-4-6"] == pricing.FALLBACK_PRICING["anthropic"]["claude-sonnet-4-6"]


def test_provider_mismatch_in_live_data_falls_back_for_that_model():
    def fetch_wrong_provider():
        data = _fake_remote()
        data["gpt-4o"]["litellm_provider"] = "azure"
        return data

    pricing_dict, live_models = pricing._build_pricing(_fetch_fn=fetch_wrong_provider)
    assert ("openai", "gpt-4o") not in live_models
    assert pricing_dict["openai"]["gpt-4o"] == pricing.FALLBACK_PRICING["openai"]["gpt-4o"]


def test_unknown_provider_or_model_is_absent_from_built_pricing():
    pricing_dict, _ = pricing._build_pricing(_fetch_fn=lambda: None)
    assert pricing_dict.get("anthropic", {}).get("nonexistent-model") is None
    assert pricing_dict.get("nonexistent-provider") is None


def test_estimate_cost_reflects_live_status_and_uses_cached_pricing(monkeypatch):
    monkeypatch.setattr(pricing, "_fetch_live_pricing", _fake_remote)
    monkeypatch.setattr(pricing, "_cache", None)
    monkeypatch.setattr(pricing, "_cache_live_models", set())
    monkeypatch.setattr(pricing, "_cache_fetched_at", 0.0)

    result = pricing.estimate_cost(5000, "anthropic", "claude-haiku-4-5-20251001")
    assert result is not None
    assert result.is_live_pricing is True
    assert 0 < result.low < result.high


def test_estimate_cost_falls_back_when_live_fetch_fails(monkeypatch):
    monkeypatch.setattr(pricing, "_fetch_live_pricing", lambda: None)
    monkeypatch.setattr(pricing, "_cache", None)
    monkeypatch.setattr(pricing, "_cache_live_models", set())
    monkeypatch.setattr(pricing, "_cache_fetched_at", 0.0)

    result = pricing.estimate_cost(5000, "anthropic", "claude-haiku-4-5-20251001")
    assert result is not None
    assert result.is_live_pricing is False
    assert 0 < result.low < result.high


def test_estimate_cost_returns_none_for_unknown_model(monkeypatch):
    monkeypatch.setattr(pricing, "_fetch_live_pricing", lambda: None)
    monkeypatch.setattr(pricing, "_cache", None)
    monkeypatch.setattr(pricing, "_cache_live_models", set())
    monkeypatch.setattr(pricing, "_cache_fetched_at", 0.0)

    assert pricing.estimate_cost(5000, "anthropic", "nonexistent-model") is None
    assert pricing.estimate_cost(5000, "nonexistent-provider", "x") is None


def test_estimate_cost_caps_input_at_max_story_words(monkeypatch):
    monkeypatch.setattr(pricing, "_fetch_live_pricing", lambda: None)
    monkeypatch.setattr(pricing, "_cache", None)
    monkeypatch.setattr(pricing, "_cache_live_models", set())
    monkeypatch.setattr(pricing, "_cache_fetched_at", 0.0)

    at_cap = pricing.estimate_cost(pricing.MAX_STORY_WORDS, "anthropic", "claude-haiku-4-5-20251001")
    way_over_cap = pricing.estimate_cost(pricing.MAX_STORY_WORDS * 10, "anthropic", "claude-haiku-4-5-20251001")
    assert at_cap.low == way_over_cap.low


def test_estimate_cost_high_is_retry_multiplier_of_low(monkeypatch):
    monkeypatch.setattr(pricing, "_fetch_live_pricing", lambda: None)
    monkeypatch.setattr(pricing, "_cache", None)
    monkeypatch.setattr(pricing, "_cache_live_models", set())
    monkeypatch.setattr(pricing, "_cache_fetched_at", 0.0)

    result = pricing.estimate_cost(5000, "anthropic", "claude-haiku-4-5-20251001")
    # low/high are each independently rounded from an unrounded per-call cost, so compare
    # with a small tolerance rather than exact equality against round(low * multiplier, 4).
    assert result.high == pytest.approx(result.low * pricing.RETRY_COST_MULTIPLIER, abs=0.001)
