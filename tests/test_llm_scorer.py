import json

import pytest

from modules import llm_scorer
from modules.preprocessor import preprocess

_PREPROCESSED = preprocess('Alice walked home. "It is late," she said. Bob nodded and left.')
_DET_SCORES = {"Direct Reader Address": 0.0, "Dialogue Ratio": 2}
_VALID_VALUE_BY_TYPE = {"scale_1_5": 3, "ordinal_1_4": 3, "binary": 1}
_VALID_RESPONSE = json.dumps(
    {f["name"]: _VALID_VALUE_BY_TYPE[f["type"]] for f in llm_scorer.LLM_FEATURES}
)


def _score(call_fn):
    return llm_scorer.score(_PREPROCESSED, _DET_SCORES, "anthropic", "fake-key", "fake-model", _call_fn=call_fn)


def test_malformed_json_triggers_one_retry_then_succeeds():
    calls = []

    def call_fn(prompt):
        calls.append(prompt)
        return "not json" if len(calls) == 1 else _VALID_RESPONSE

    result = _score(call_fn)
    assert len(calls) == 2
    for f in llm_scorer.LLM_FEATURES:
        assert result[f["name"]] == float(_VALID_VALUE_BY_TYPE[f["type"]])


def test_second_malformed_json_returns_none_for_all_16_features():
    calls = []

    def call_fn(prompt):
        calls.append(prompt)
        return "still not json"

    result = _score(call_fn)
    assert len(calls) == 2
    assert set(result.keys()) == {f["name"] for f in llm_scorer.LLM_FEATURES}
    assert all(v is None for v in result.values())


def test_scale_field_out_of_range_becomes_none():
    payload = {f["name"]: 3 for f in llm_scorer.LLM_FEATURES}
    payload["Thematic Explicitness"] = 6  # out of range for a 1-5 scale
    calls = []

    def call_fn(prompt):
        calls.append(prompt)
        return json.dumps(payload)  # retry gets the same invalid payload back

    result = _score(call_fn)
    assert result["Thematic Explicitness"] is None
    assert result["Moral/Philosophical Weight"] == 3.0
    assert len(calls) == 2  # initial call + retry for the one invalid field


def test_binary_field_out_of_range_becomes_none():
    payload = {f["name"]: 1 for f in llm_scorer.LLM_FEATURES}
    payload["Narrator Thematic Commentary"] = 2  # out of range for binary

    def call_fn(prompt):
        return json.dumps(payload)

    result = _score(call_fn)
    assert result["Narrator Thematic Commentary"] is None
    assert result["Dialogue as Philosophy"] == 1.0


def test_valid_response_parses_and_passes_schema_validation():
    calls = []

    def call_fn(prompt):
        calls.append(prompt)
        return _VALID_RESPONSE

    result = _score(call_fn)
    assert len(calls) == 1  # no retry needed
    for f in llm_scorer.LLM_FEATURES:
        assert result[f["name"]] == float(_VALID_VALUE_BY_TYPE[f["type"]])
    assert set(result.keys()) == {f["name"] for f in llm_scorer.LLM_FEATURES}


@pytest.mark.parametrize(
    "exc_type_name,expected_substring",
    [
        ("AuthenticationError", "rejected"),
        ("RateLimitError", "rate limit"),
        ("APIConnectionError", "returned an error"),
    ],
)
def test_invalid_api_key_and_rate_limit_produce_user_facing_messages_not_tracebacks(
    exc_type_name, expected_substring
):
    fake_exc_type = type(exc_type_name, (Exception,), {})
    message = llm_scorer._sanitize_error(fake_exc_type("some raw provider-internal detail"))
    assert expected_substring in message.lower()
    assert "raw provider-internal detail" not in message
