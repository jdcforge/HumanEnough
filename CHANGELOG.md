# Changelog

## [Unreleased]
### Changed
- `pricing.py` now fetches live model pricing from the LiteLLM project's price matrix
  (cached 6h in-process), falling back per-model to the bundled static rates if the fetch
  fails or a model is missing from the live data. UI notes when bundled pricing was used.
- Cost estimate now mirrors what's actually sent to the LLM: input is capped at
  `MAX_STORY_WORDS` (matching `llm_scorer.py`'s truncation), fixed prompt scaffolding is
  included, and the UI shows a `(low, high)` range accounting for `llm_scorer.score()`'s one
  possible retry (which resends the full prompt).

## [0.1.0] -- 2026-07-07
### Initial release
- Core pipeline: extraction, preprocessing, deterministic scoring, LLM scoring
- Similarity Map with five LLM reference profiles
- Streamlit UI with Anthropic and OpenAI provider support
- API pricing last verified: 2026-07-07
