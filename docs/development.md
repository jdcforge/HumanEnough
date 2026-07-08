# Development Guide

Practical, worked-example documentation for extending Human Enough. For philosophy and
full module specs, see `architecture.md`; for what each deterministic feature actually
measures and where it breaks, see `docs/heuristics.md`.

## a) Running the test suite

```
poetry run pytest
```

A passing run currently looks like:

```
32 passed in ~3s
```

Run one file with `poetry run pytest tests/test_normaliser.py`, or one test with
`-k <substring>`. Add `-v` for per-test output.

**What each file covers, and what it needs:**

| File | Needs | Notes |
|---|---|---|
| `test_extractor.py` | Nothing external | Builds a minimal valid PDF by hand at test time (no `reportlab` dependency) to exercise the PDF path without a fixture file. |
| `test_preprocessor.py` | Nothing external | Uses small inline story strings, not the sample story. |
| `test_normaliser.py` | Nothing external | Pure function tests against `modules/profiles.py` data. |
| `test_llm_scorer.py` | Nothing external -- **mocked** | Every test injects `llm_scorer.score()`'s `_call_fn` parameter with a fake function instead of making a real API call. This is the seam that makes retry/validation logic testable without an API key -- see `modules/llm_scorer.py`'s `score()` docstring. |
| `test_visualiser.py` | Nothing external | Placement-geometry tests. A few use `pytest`'s `monkeypatch` fixture to temporarily override `profiles.LLM_MAP_COORDS` with synthetic points, so edge cases (the equidistant-centroid fallback, clamping) can be constructed exactly rather than hoped for. |

**None of the automated tests currently read `sample/sample_story.txt`.** It exists for the
app's "Try with sample story" button and for manual/exploratory testing during development
(e.g. `poetry run python -m modules.deterministic` against real prose), not as a pytest
fixture -- the suite favors small, fast, deterministic inline strings instead. If you add an
integration test that exercises the full pipeline end-to-end, the sample story is the right
fixture for it; just be aware no such test exists yet.

The LLM-scored half of the pipeline cannot be tested end-to-end without a real Anthropic or
OpenAI API key (by design -- see `architecture.md` > Security). `test_llm_scorer.py`
verifies the code around the API call; it does not verify that a real model actually returns
sensible scores for a given story.

## b) Adding a new feature

Deciding **deterministic vs. LLM-scored** first: if it's a measurable count, density, or
structural pattern (no interpretation required), it belongs in `deterministic.py`. If it
requires reading and judging the text, it belongs in `llm_scorer.py`. See
`architecture.md` > Feature Assignment for the existing 30-feature split as a guide.

Touch files in this order:

1. **`modules/deterministic.py` or `modules/llm_scorer.py`** -- implement the scorer.
   - Deterministic: write a `_your_feature_name(...)` function following the existing
     pattern (lexicon density + `_bin()`, or a spaCy NER/dependency-parse check), then add
     it to the dict `score()` returns.
   - LLM-scored: add an entry to the `LLM_FEATURES` list with `name`, `question`, and
     `type` (`"scale_1_5"`, `"ordinal_1_4"`, or `"binary"`). It's automatically included in
     the next bundled prompt and validated against `_VALID_VALUES[type]`.
2. **`modules/profiles.py`** -- register the feature in three places:
   - Add a row to `_PROFILE_TABLE` with the feature name and its 7 reference values
     (`HUMAN, AI_AVG, CLAUDE, GPT, GEMINI, DEEPSEEK, KIMI`). This alone updates
     `FEATURE_NAMES`, `HUMAN`, `AI_AVG`, and each per-model profile dict automatically,
     since they're all derived from `_PROFILE_TABLE`.
   - Add an entry to `FEATURE_SCALE_TYPES` (must match the `type` used in step 1).
   - Add an entry to `FEATURE_DESCRIPTIONS` (a short plain-English description for the UI).
3. **`modules/normaliser.py`** -- only touch this if you're introducing a *new scale type*
   (e.g. a genuinely new response format beyond `scale_1_5` / `ordinal_1_4` / `ordinal_1_3`
   / `binary` / `prevalence`). Add it to `profiles.SCALE_MAXIMA`; `normalise()` picks it up
   automatically via `FEATURE_SCALE_TYPES`. If you're reusing an existing scale type,
   there's nothing to do here.
4. **`architecture.md`** -- update the relevant feature table (Deterministic or
   LLM-scored), the Reference Profile Values table, and the Feature Provenance table so the
   spec doesn't drift from the code. If it's a deterministic feature, add a section to
   `docs/heuristics.md` describing what it measures, its failure modes, and what improving
   it would look like -- see `docs/contributing.md`.

**Verify:**

```
poetry run python -m modules.profiles      # assertion checks: feature counts, [0,1] bounds
poetry run pytest                          # nothing else broke
poetry run python -m modules.deterministic # or modules.llm_scorer -- smoke test scores it
```

Then run the app (`poetry run streamlit run app.py`) and confirm the new feature shows up
correctly in the "Full feature breakdown" expander.

## c) Updating pricing

Already covered briefly in `architecture.md` and `docs/contributing.md`; concretely:

1. Edit the rate(s) in `PRICING` in `modules/pricing.py`. Keys are `provider -> model ->
   {"input": ..., "output": ...}`, in USD per 1,000 tokens.
2. Add a `CHANGELOG.md` entry noting the date and which prices changed, e.g.:

   ```markdown
   ## [Unreleased]
   ### Changed
   - Updated Anthropic Haiku pricing (input $0.0008 -> $0.0006 per 1K tokens).
     Pricing verified 2026-08-01.
   ```

3. `poetry run python -m modules.pricing` runs `pricing.py`'s own smoke assertions.

## d) Updating the lexicons

Covered in `docs/contributing.md` in full (format, minimum 30 entries per category, the
verification one-liner, and style guidance for new entries). In short: edit the relevant
`lexicons/*.json` file, keep entries lowercase, then run the count-check snippet in
`docs/contributing.md` followed by `poetry run python -m modules.deterministic` and
`poetry run pytest`.

## e) Updating reference profiles

Two situations: the paper is revised (values change but the model set stays the same), or a
new AI model is added (a new profile is added to the model set).

**Paper revision (values change):**

1. Update the affected value(s) directly in `_PROFILE_TABLE` in `modules/profiles.py`.
2. Update the matching row(s) in the "Reference Profile Values" table in `architecture.md`
   so the two stay in sync.
3. If a per-model fingerprint description changed, update the "Derivation rationale by
   model" prose in `architecture.md` too -- it documents *why* each per-model delta exists,
   not just the numbers.

**New model added:**

1. Add a new profile dict in `modules/profiles.py` (follow the `CLAUDE`/`GPT`/etc. pattern:
   a full 30-value row in `_PROFILE_TABLE`), and add it to the `LLM_PROFILES` dict so it
   participates in manuscript placement.
2. Give it fixed map coordinates in `LLM_MAP_COORDS` and a colour in `PROFILE_COLORS` /
   `PROFILE_COLORS_DARK`. For the colour, follow the dataviz skill's fixed categorical slot
   order (see the comment above `PROFILE_COLORS` in `modules/profiles.py`) -- don't pick an
   arbitrary hex value; use the next unused slot in the validated palette.
3. Update `architecture.md`: the per-model profile table, the "Fixed LLM reference points"
   table (map coordinates and rationale), and the six-way references throughout the doc
   ("five AI models" becomes "six", etc.).
4. Update `docs/development.md` and `docs/heuristics.md` only if the new model's addition
   changes anything about the *heuristics themselves* -- normally it won't, since the
   deterministic/LLM scoring pipeline is model-agnostic; only the reference profiles change.

**Verify (both cases):**

```
poetry run python -m modules.profiles   # re-checks [0,1] bounds and feature-set consistency
poetry run pytest                       # placement tests re-run against the updated profiles
```

If you added a new model, also re-read `tests/test_visualiser.py` -- the "equidistant from
all five" test name and assertions assume five LLM profiles and will need updating to match
the new count.
