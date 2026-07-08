"""LLM-scored features: 16 semantic questions in one bundled API call.

Provider-abstracted over Anthropic and OpenAI. See docs/architecture.md > Feature Assignment for
why this is 16 (not the original 15) -- "Moral/Philosophical Weight" was added to close a
gap in the source doc.

Security: API keys and story text must never be logged. On exception, only the exception
type informs a sanitised, canned user-facing message -- never the raw exception text, prompt,
or response body (see docs/architecture.md > Security).
"""

import json
import re
import time

from modules.logging_config import get_logger
from modules.preprocessor import PreprocessResult

MAX_STORY_WORDS = 60_000

logger = get_logger("llm_scorer")

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
}


class LLMScoringError(Exception):
    """Raised for any LLM API failure. Message is safe to show directly to the user."""


# name, question, response type ("scale_1_5" / "ordinal_1_4" / "binary")
LLM_FEATURES: list[dict[str, str]] = [
    {
        "name": "Thematic Explicitness",
        "question": "How explicitly does the story articulate its themes or morals?",
        "type": "scale_1_5",
    },
    {
        "name": "Moral/Philosophical Weight",
        "question": "How heavily does the story foreground moral or philosophical questions?",
        "type": "scale_1_5",
    },
    {
        "name": "Thematic Unity",
        "question": "To what extent do subplots and flourishes serve a central thematic concern?",
        "type": "scale_1_5",
    },
    {
        "name": "Narrator Thematic Commentary",
        "question": "Does the narrator explicitly comment on themes beyond characters' perspectives?",
        "type": "binary",
    },
    {
        "name": "Setting as Psychological Mirror",
        "question": "To what degree does the physical environment mirror characters' inner states?",
        "type": "scale_1_5",
    },
    {
        "name": "Interior Access Depth",
        "question": "How deep into characters' inner life does the narration go?",
        "type": "scale_1_5",
    },
    {
        "name": "Dialogue as Philosophy",
        "question": "Does dialogue primarily serve philosophical debate rather than plot or character?",
        "type": "binary",
    },
    {
        "name": "External Character Introduction",
        "question": "Are central characters primarily introduced via external physical description?",
        "type": "binary",
    },
    {
        "name": "Pre-Threat Character Investment",
        "question": "How much does the story build reader investment before major jeopardy?",
        "type": "scale_1_5",
    },
    {
        "name": "Revelation Recontextualisation",
        "question": "How extensively does a late revelation force reinterpretation of earlier scenes?",
        "type": "scale_1_5",
    },
    {
        "name": "Vague Intertextual Allusion",
        "question": "Are intertextual references vague/implicit rather than specific and named?",
        "type": "binary",
    },
    {
        "name": "Environmental Emphasis",
        "question": "How prominent is the natural environment or ecology in the narrative?",
        "type": "scale_1_5",
    },
    {
        "name": "Spatial Granularity",
        "question": "How fine-grained is the story's depiction of physical space?",
        "type": "ordinal_1_4",
    },
    {
        "name": "Internal Resolution Mode",
        "question": "Is the story resolved through internal understanding/acceptance rather than external action?",
        "type": "binary",
    },
    {
        "name": "Clear Opening Setting",
        "question": "How clearly does the opening ground the reader in a specific physical setting?",
        "type": "ordinal_1_4",
    },
    {
        "name": "Balanced Intertextual Mix",
        "question": "Does the story balance explicit and implicit cultural references evenly?",
        "type": "binary",
    },
]

_VALID_VALUES: dict[str, set[int]] = {
    "scale_1_5": {1, 2, 3, 4, 5},
    "ordinal_1_4": {1, 2, 3, 4},
    "binary": {0, 1},
}

_RESPONSE_OPTIONS_TEXT: dict[str, str] = {
    "scale_1_5": "integer 1-5",
    "ordinal_1_4": "integer 1-4",
    "binary": "0 or 1",
}


def _build_prompt(preprocessed: PreprocessResult, deterministic_scores: dict) -> str:
    words = preprocessed.full_text.split()
    truncation_note = ""
    if len(words) > MAX_STORY_WORDS:
        story_text = " ".join(words[:MAX_STORY_WORDS])
        truncation_note = "\n\n[Note: story truncated to the first 60,000 words for length.]"
    else:
        story_text = preprocessed.full_text

    det_lines = "\n".join(f"- {name}: {value}" for name, value in deterministic_scores.items())
    feature_lines = "\n".join(
        f"{i}. {f['name']} -- {f['question']} ({_RESPONSE_OPTIONS_TEXT[f['type']]})"
        for i, f in enumerate(LLM_FEATURES, start=1)
    )

    return f"""You are a literary analyst scoring a story on specific narrative dimensions.
Return ONLY a valid JSON object. No preamble, no explanation, no markdown fences.

The following features have already been measured automatically from the text.
Use them as context where relevant:
{det_lines}

Now read the story and answer these questions. For each, return only the
score value -- no explanation.

{feature_lines}

Story:
{story_text}{truncation_note}

Return: {{"Feature Name": value, ...}}"""


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE | re.DOTALL).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _validate(parsed: dict) -> tuple[dict[str, float | None], list[str]]:
    """Returns (validated_scores, names_of_invalid_fields)."""
    validated: dict[str, float | None] = {}
    invalid: list[str] = []
    for feat in LLM_FEATURES:
        name = feat["name"]
        raw = parsed.get(name)
        value: int | None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = None
        if value is not None and value in _VALID_VALUES[feat["type"]]:
            validated[name] = float(value)
        else:
            validated[name] = None
            invalid.append(name)
    return validated, invalid


def _sanitize_error(exc: Exception) -> str:
    """Never echoes the raw exception message (which could contain request/response
    details) -- only the exception type name is used for classification."""
    type_name = type(exc).__name__.lower()
    if "auth" in type_name or "permission" in type_name:
        return "API key was rejected. Check that you've entered it correctly."
    if "ratelimit" in type_name or "rate_limit" in type_name:
        return "API rate limit reached. Wait a moment and try again."
    return "The AI provider returned an error. Please try again."


def _call_anthropic(prompt: str, api_key: str, model: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if hasattr(block, "text"))


def _call_openai(prompt: str, api_key: str, model: str) -> str:
    import openai

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def _call_provider(provider: str, prompt: str, api_key: str, model: str) -> str:
    if provider not in ("anthropic", "openai"):
        raise LLMScoringError(f"Unknown provider: {provider}")
    try:
        if provider == "anthropic":
            return _call_anthropic(prompt, api_key, model)
        return _call_openai(prompt, api_key, model)
    except Exception as exc:
        # Only the exception *type* is logged, same rule _sanitize_error follows -- never
        # the raw exception message, which could echo request/response details or the key.
        logger.error("Provider API call failed (%s): %s", type(exc).__name__, provider)
        raise LLMScoringError(_sanitize_error(exc)) from exc


def score(
    preprocessed: PreprocessResult,
    deterministic_scores: dict,
    provider: str,
    api_key: str,
    model: str,
    _call_fn=None,
) -> dict[str, float | None]:
    """Returns raw scores for the 16 LLM-scored features.

    `_call_fn`, if given, replaces the network call with `_call_fn(prompt) -> str`. It exists
    so this function's retry/validation logic is unit-testable without a live API key.
    """
    call_fn = _call_fn or (lambda prompt: _call_provider(provider, prompt, api_key, model))
    started = time.perf_counter()
    logger.info("LLM scoring requested (provider=%s, model=%s)", provider, model)

    prompt = _build_prompt(preprocessed, deterministic_scores)
    parsed = _parse_json(call_fn(prompt))

    if parsed is None:
        logger.warning("LLM response was not valid JSON, retrying once")
        retry_prompt = (
            prompt
            + "\n\nYour previous response was not valid JSON. Return ONLY a valid JSON "
            "object, nothing else."
        )
        parsed = _parse_json(call_fn(retry_prompt))
        if parsed is None:
            logger.error("LLM response still not valid JSON after retry -- all 16 features None")
            return {f["name"]: None for f in LLM_FEATURES}

    validated, invalid = _validate(parsed)

    if invalid:
        # Field *names* are our own taxonomy, not story content -- safe to log.
        logger.warning("Retrying %d invalid field(s): %s", len(invalid), invalid)
        retry_prompt = (
            prompt
            + "\n\nThe following fields had invalid values. Return only integers within "
            f"the specified range: {', '.join(invalid)}."
        )
        retry_parsed = _parse_json(call_fn(retry_prompt)) or {}
        for feat in LLM_FEATURES:
            name = feat["name"]
            if name not in invalid:
                continue
            raw = retry_parsed.get(name)
            try:
                value = int(raw)
            except (TypeError, ValueError):
                value = None
            if value is not None and value in _VALID_VALUES[feat["type"]]:
                validated[name] = float(value)
            # else: remains None, already set above.

    elapsed = time.perf_counter() - started
    still_invalid = [name for name, value in validated.items() if value is None]
    logger.info(
        "LLM scoring complete in %.3fs: %d/%d features scored%s",
        elapsed, len(LLM_FEATURES) - len(still_invalid), len(LLM_FEATURES),
        f", unscored: {still_invalid}" if still_invalid else "",
    )
    return validated


if __name__ == "__main__":
    from modules.preprocessor import preprocess

    sample = 'Alice walked home. "It is late," she said. Bob nodded and left.'
    preprocessed = preprocess(sample)
    deterministic_scores = {"Direct Reader Address": 0.0, "Dialogue Ratio": 2}

    fake_response = json.dumps({f["name"]: 1 for f in LLM_FEATURES})
    result = score(
        preprocessed, deterministic_scores, "anthropic", "fake-key", "fake-model",
        _call_fn=lambda prompt: fake_response,
    )
    assert all(v == 1.0 for v in result.values())
    assert set(result.keys()) == {f["name"] for f in LLM_FEATURES}

    # Malformed JSON both times -> all None.
    result_bad = score(
        preprocessed, deterministic_scores, "anthropic", "fake-key", "fake-model",
        _call_fn=lambda prompt: "not json at all",
    )
    assert all(v is None for v in result_bad.values())

    print("OK --", len(LLM_FEATURES), "features defined; retry/validation logic verified.")
