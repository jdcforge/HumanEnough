# Contributing

Thanks for looking at Human Enough. Most contributions fall into one of three categories:
a bug fix, a lexicon update, or a pricing update. This guide covers all three.

## Setup

Install dependencies, including dev tools (pytest):

```
poetry install
```

If you haven't already, download the spaCy language model the app depends on:

```
poetry run python -m spacy download en_core_web_lg
```

## Running tests

```
poetry run pytest
```

A passing run looks like `32 passed in ~3s`. Run a single file with
`poetry run pytest tests/test_normaliser.py`, or a single test with `-k <name>`.

See `docs/development.md` for what each test file covers and how to add a new feature.

## Updating a lexicon

The four lexicon files in `lexicons/` are plain JSON, matched case-insensitively and
whole-word (so multi-word phrases like `"as a result"` still match correctly, but `"ash"`
won't match inside `"ashamed"`).

- `sensory.json` is a JSON object with five keys (`olfactory`, `auditory`, `tactile`,
  `gustatory`, `visual`), each an array of lowercase strings.
- `body_sensation.json`, `causal.json`, and `temporal.json` are each a flat JSON array of
  lowercase strings.

**Every category needs at least 30 entries.** After editing a lexicon file, verify the
counts and that it's still valid JSON:

```
poetry run python -c "
import json
with open('lexicons/sensory.json') as f:
    for k, v in json.load(f).items():
        assert len(v) >= 30, k
for name in ['body_sensation', 'causal', 'temporal']:
    with open(f'lexicons/{name}.json') as f:
        assert len(json.load(f)) >= 30, name
print('OK')
"
```

Then run `poetry run python -m modules.deterministic` to confirm the module still scores a
sample string without error, and `poetry run pytest` to make sure nothing else broke.

Keep new entries lowercase and avoid words so short or common they'll false-positive inside
unrelated words (whole-word matching handles most of this, but short entries like `"ax"`
still surface a lot of noise).

## Updating pricing

Provider pricing drifts. When it changes:

1. Edit the relevant rate(s) in `PRICING` in `modules/pricing.py`.
2. Add an entry to `CHANGELOG.md` noting the date and which prices changed.

That's the whole convention -- see `docs/development.md` for a worked example.

## Submitting a change

- Keep the change focused -- a lexicon PR shouldn't also touch scoring logic.
- Run the full test suite before submitting.
- If you touch a deterministic feature's scoring logic, also update the relevant entry in
  `docs/heuristics.md` so the documentation doesn't drift from the code.
