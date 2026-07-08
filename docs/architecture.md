# Human Enough — Architecture Document

## Purpose

Human Enough is a narrative analysis tool for fiction writers. It scores a story across 30
discourse-level narrative features derived from the StoryScope research paper (Russell et al.,
2026) and plots the result against reference profiles for human authors and five AI models
(Claude, GPT, Gemini, DeepSeek, Kimi). The goal is to give writers an interpretable,
evidence-based picture of how their narrative choices compare to human and AI writing patterns.

---

## Reference

All feature definitions, reference profiles, and normalisation values are drawn from:

> Russell, J. et al. (2026). *StoryScope: Investigating idiosyncrasies in AI fiction.*
> arXiv:2604.03136v4. University of Maryland / Google DeepMind.

Specifically:
- **Table 15** — 30 core features with human vs. AI mean values and gaps
- **Table 13** — 20 AI-characterising features with definitions
- **Table 14** — 13 human-characterising features with definitions
- **Section 4.1** — Qualitative descriptions of core human/AI narrative differences
- **Section 5** — Per-model fingerprint descriptions
- **Figure 2** — Per-model cluster positions in narrative feature space
- **Table 16** — Per-model fingerprint features and uniqueness ratios

---

## Deployment

- **Framework:** Streamlit
- **Python:** 3.14 (`>=3.14,<3.15`). No compatibility guarantees for other versions.
- **Distribution:** GitHub repository. Users clone locally and run with `streamlit run app.py`.
- **No hosted deployment.** There is no server to maintain and no accounts to manage.
- **LLM backend:** User-supplied API key, entered per session in the UI. Key is held in
  Streamlit session state only — never written to disk or logged.
- **Supported providers:** Anthropic (Claude), OpenAI (GPT)

---

## Package Structure

```
human-enough/
├── app.py                  # Streamlit application entry point
├── pyproject.toml          # Poetry project definition and dependencies
├── poetry.lock             # Locked dependency graph (committed to repo)
├── LICENSE                 # MIT
├── NOTICE                  # Attribution to StoryScope paper
├── CHANGELOG.md            # Version history
├── README.md               # Setup, usage, and citation instructions
├── docs/
│   ├── architecture.md     # This document
│   ├── contributing.md     # Contributor guide: setup, tests, lexicon/pricing conventions
│   ├── development.md      # How to add features, update pricing/lexicons/profiles
│   └── heuristics.md       # Plain-English explanation of each deterministic feature
├── .gitignore
├── .streamlit/
│   └── config.toml         # Streamlit theme and local server config
├── modules/
│   ├── __init__.py
│   ├── extractor.py        # File ingestion: PDF, MD, TXT → plain text
│   ├── preprocessor.py     # Segment text into narration vs. dialogue
│   ├── deterministic.py    # spaCy + lexicon scoring (15 raw outputs, 14 mapped)
│   ├── llm_scorer.py       # LLM call for remaining 16 mapped features
│   ├── normaliser.py       # Raw scores → 0–1, cosine similarity, divergence
│   ├── profiles.py         # Reference profiles from the paper
│   ├── pricing.py          # API cost estimates per provider and model
│   ├── visualiser.py       # Similarity Map (Plotly) + text report
│   └── logging_config.py   # Console-only diagnostic logging setup
├── lexicons/
│   ├── sensory.json         # Five-sense word lists
│   ├── body_sensation.json  # Embodied emotion words
│   ├── causal.json          # Causal connectives
│   └── temporal.json        # Anachrony markers
├── sample/
│   └── sample_story.txt    # Short public-domain text for testing and demo
└── tests/
    ├── __init__.py
    ├── test_extractor.py
    ├── test_preprocessor.py
    ├── test_normaliser.py
    ├── test_llm_scorer.py
    └── test_visualiser.py
```

---

## README Requirements

The README must allow a non-technical user to get the tool running. It should cover:

1. Prerequisites: Python 3.14, git, Poetry (`pip install poetry`)
2. Clone the repository
3. `poetry install` — installs all dependencies including dev tools into an isolated environment
4. `python -m spacy download en_core_web_lg`
5. `poetry run streamlit run app.py`
6. Where to get an Anthropic or OpenAI API key
7. How to use the UI (upload a file, enter key, click Analyse)

Instructions should use plain language. Assume the user has never used a terminal before
but is willing to follow steps carefully. Explain what each command does in one plain
sentence before showing it.

---

## Feature Assignment

The 30 core features are split across two scoring modules. The hybrid category has been
eliminated — features with a measurable deterministic signal but requiring semantic
confirmation are handled entirely within the LLM call, which receives the deterministic
scores as context.

### Deterministic features (15 raw outputs, 14 mapped) — `deterministic.py`

These features are fully measurable by spaCy and lexicon matching without semantic
interpretation.

| Feature | Implementation |
|---|---|
| Direct Reader Address | 2nd-person pronoun count in narration / narration word count |
| Fourth-Wall Permeability | Same signal + "dear reader" / "the reader" patterns; binned to 1–4 ordinal |
| Dialogue Ratio | dialogue word count / total word count; mapped to 1–5 scale. **Context-only — see note below.** |
| Chronological Discontinuity | temporal marker density (from `temporal.json`) + pluperfect verb frequency; 1–5 scale |
| Anachrony Intensity | pluperfect density + flashback/flash-forward lexicon match rate; 1–5 scale |
| Nonlinear Disclosure Framing | anachrony markers weighted by position (earlier in text = higher weight); 1–5 scale |
| Location Variety | count distinct GPE + LOC entities via spaCy NER; binned to 1–4 ordinal |
| Named Intertextuality | count WORK_OF_ART + PERSON entities not in `named_characters`; binary |
| Olfactory Imagery | olfactory lexicon matches / total words; binary threshold |
| Sensory Density | all-sense lexicon matches / total words; 1–5 scale |
| Embodied Emotion Expression | `body_sensation.json` match rate in narration; binary threshold |
| Causal Chain Continuity | `causal.json` connective density; 1–5 scale (inverted — high density = high continuity) |
| Protagonist-Driven Resolution | agency verb count (subject = protagonist) in final 15% of text; binary |
| Moral Ambivalence | hedging language (perhaps, seemed, might, as if) co-occurring with protagonist in dependency parse; binary |
| No Subplots | named characters who appear in first 50% but not final 20% of text; binary |

**Note — `Dialogue Ratio` is context-only, not a profile feature.** `deterministic.score()`
returns all 15 keys above, but `Dialogue Ratio` is **not** one of the 30 profile features — it
is absent from both the "Reference Profile Values" table and the Feature Provenance table
below. Its sole purpose is to be passed into the `llm_scorer.py` prompt as context, informing
the `Narrator Thematic Commentary` and `Dialogue as Philosophy` judgments. The pipeline glue
code (in `app.py`) must strip `Dialogue Ratio` from the deterministic dict before merging it
with the LLM scores and calling `normaliser.normalise()`.

**Accounting: 14 deterministic + 16 LLM-scored (see below) = 30 profile features.**

### LLM-scored features (16) — `llm_scorer.py`

These features require semantic interpretation. They include features that have a
measurable deterministic signal but require LLM confirmation (formerly "hybrid"), and
features that are fully semantic. All 16 are scored in a single bundled API call.
The deterministic scores (including the context-only `Dialogue Ratio`) are passed as context
to inform judgment on the hybrid-origin features.

| Feature | Question asked | Response type | Notes |
|---|---|---|---|
| Thematic Explicitness | How explicitly does the story articulate its themes or morals? | 1–5 scale | |
| Moral/Philosophical Weight | How heavily does the story foreground moral or philosophical questions? | 1–5 scale | Added to close a gap: present in the paper's Table 15 / Feature Provenance list but missing from the original module tables. Distinct from Thematic Explicitness — see paper Table 13 §15/§1. |
| Thematic Unity | To what extent do subplots and flourishes serve a central thematic concern? | 1–5 scale | |
| Narrator Thematic Commentary | Does the narrator explicitly comment on themes beyond characters' perspectives? | binary (0/1) | Hybrid — use Dialogue Ratio and narration patterns as context |
| Setting as Psychological Mirror | To what degree does the physical environment mirror characters' inner states? | 1–5 scale | |
| Interior Access Depth | How deep into characters' inner life does the narration go? | 1–5 scale | |
| Dialogue as Philosophy | Does dialogue primarily serve philosophical debate rather than plot or character? | binary (0/1) | Hybrid — use Dialogue Ratio as context |
| External Character Introduction | Are central characters primarily introduced via external physical description? | binary (0/1) | |
| Pre-Threat Character Investment | How much does the story build reader investment before major jeopardy? | 1–5 scale | |
| Revelation Recontextualisation | How extensively does a late revelation force reinterpretation of earlier scenes? | 1–5 scale | Hybrid — use Chronological Discontinuity and Anachrony scores as context |
| Vague Intertextual Allusion | Are intertextual references vague/implicit rather than specific and named? | binary (0/1) | Hybrid — use Named Intertextuality score as context |
| Environmental Emphasis | How prominent is the natural environment or ecology in the narrative? | 1–5 scale | |
| Spatial Granularity | How fine-grained is the story's depiction of physical space? | 1–4 ordinal | |
| Internal Resolution Mode | Is the story resolved through internal understanding/acceptance rather than external action? | binary (0/1) | Hybrid — use Protagonist-Driven Resolution as context |
| Clear Opening Setting | How clearly does the opening ground the reader in a specific physical setting? | 1–4 ordinal | |
| Balanced Intertextual Mix | Does the story balance explicit and implicit cultural references evenly? | binary (0/1) | Hybrid — use Named Intertextuality score as context |

---

## Module Specifications

### `extractor.py`

Accepts an in-memory file object from Streamlit's file uploader.
Returns a named tuple or dataclass with three fields:

```python
@dataclass
class ExtractionResult:
    text: str         # Plain UTF-8 story text
    word_count: int   # Word count of extracted text
    char_count: int   # Character count of extracted text
```

Supported formats:
- `.pdf` — extract via `pdfplumber`; fall back to `pypdf` if pdfplumber fails
- `.md` — strip YAML front matter (lines between `---` delimiters), return body
- `.txt` — return as-is

Expose a single public function:
```python
def extract(file) -> ExtractionResult:
    """Accept a Streamlit UploadedFile. Return text, word count, and character count."""
```

---

### `preprocessor.py`

Splits the extracted text into two parallel representations:
- `narration` — everything outside quotation marks
- `dialogue` — everything inside quotation marks

Both are returned as strings. Some features are scored against narration only (e.g. direct
reader address, narrator thematic commentary); others against the full text; others against
dialogue only (e.g. dialogue as philosophy).

Also identifies:
- The **protagonist** — the named character most frequently referenced as a subject of
  action verbs in the narration. Fallback: if no clear protagonist can be determined
  (e.g. first-person narrator with no named subject), use the most frequently occurring
  PERSON entity instead. If no PERSON entities exist, set protagonist to `None` and
  skip protagonist-dependent features gracefully.
- **Named characters** — all PERSON entities from spaCy NER. Used to exclude characters
  from intertextuality detection.
- The **final 15% of text** — used for resolution features.

Note: dialogue detection is heuristic and assumes standard English double quotation marks.
Manuscripts using em dashes, single quotes, or no quotation marks (e.g. Cormac McCarthy
style) will produce unreliable dialogue/narration splits. This is a known limitation and
is noted in Constraints and Assumptions.

```python
@dataclass
class PreprocessResult:
    full_text: str
    narration: str
    dialogue: str
    protagonist: str
    named_characters: list[str]
    final_segment: str

def preprocess(text: str) -> PreprocessResult:
    """Segment text into narration and dialogue; identify protagonist and named characters."""
```

---

### `deterministic.py`

Scores 15 features using spaCy (`en_core_web_lg`) and lexicon matching.
Takes a `PreprocessResult` as input. Returns a dict of 15 raw scores keyed by feature name
(see the Feature Assignment section above for the `Dialogue Ratio` context-only caveat).

spaCy model required: `en_core_web_lg`. If not installed, raise a clear error with the
install command: `python -m spacy download en_core_web_lg`

```python
def score(preprocessed: PreprocessResult) -> dict[str, float]:
    """Returns raw scores for the 15 deterministic features (14 profile + 1 context-only)."""
```

---

### `llm_scorer.py`

Scores 16 features requiring semantic interpretation. Makes a single API call with:
- The full story text (truncated to 60,000 words if longer, with a note to the LLM)
- The 15 deterministic scores already computed (including `Dialogue Ratio`), as context
- All 16 feature questions in one prompt, requesting JSON output

**Prompt structure:**
```
You are a literary analyst scoring a story on specific narrative dimensions.
Return ONLY a valid JSON object. No preamble, no explanation, no markdown fences.

The following features have already been measured automatically from the text.
Use them as context where relevant:
{deterministic_scores_as_readable_list}

Now read the story and answer these questions. For each, return only the
score value — no explanation.

{feature definitions with discrete answer options, one per line}

Story:
{story_text}

Return: {"Feature Name": value, ...}
```

**Output schema validation**

After parsing the JSON response, validate every field before accepting scores.
Invalid values must become `None` rather than propagating incorrect data.

| Response type | Valid values | Invalid → |
|---|---|---|
| 1–5 scale | integer 1, 2, 3, 4, or 5 | `None` |
| 1–4 ordinal | integer 1, 2, 3, or 4 | `None` |
| binary | integer 0 or 1 | `None` |

If any field is `None` after validation, include it in the retry payload with an explicit
instruction: "The following fields had invalid values. Return only integers within the
specified range: {field list}."

If the retry still produces invalid values for a field, set that field to `None` and
surface a warning in the UI listing which features could not be scored.

**Error handling:**
- If JSON is malformed: one automatic retry with explicit instruction to return only JSON
- If retry still fails: return `None` for all 16 LLM features and surface a warning
- If individual fields are invalid after retry: return `None` for those fields only
- API errors (invalid key, rate limit, network): surface as user-facing error messages in UI

**Provider abstraction:**
```python
def score(
    preprocessed: PreprocessResult,
    deterministic_scores: dict,
    provider: str,        # "anthropic" or "openai"
    api_key: str,
    model: str,
) -> dict[str, float]:
    """Returns raw scores for the 16 LLM-scored features."""
```

Supported models:
- Anthropic: `claude-haiku-4-5-20251001` (default), `claude-sonnet-4-6`
- OpenAI: `gpt-4o-mini` (default), `gpt-4o`

---

### `normaliser.py`

Converts all 30 raw scores to [0, 1] using the scale maxima from the paper.
Also exposes similarity and divergence functions used by `visualiser.py` and `app.py`.

Scale maxima:
- 1–5 Likert scales — divide by 5
- 1–4 ordinal — divide by 4
- 1–3 ordinal — divide by 3
- Binary (0/1) — already normalised
- Prevalence (0.0–1.0) — already normalised

**Key validation**

`normalise()` must validate every incoming key against `profiles.FEATURE_NAMES` and **raise a
clear error on any key it does not recognise**, rather than silently passing it through. This
is the guard that catches a stray context-only key (e.g. `Dialogue Ratio` not having been
stripped by the caller) before it can silently corrupt the cosine similarity calculation.

**Missing score handling**

Some features may be `None` after LLM scoring fails validation. The normaliser must
handle this explicitly.

```python
def normalise(raw_scores: dict[str, float | None]) -> dict[str, float | None]:
    """Normalise scores to [0, 1]. None values pass through unchanged.
    Raises ValueError if raw_scores contains a key not in profiles.FEATURE_NAMES."""

def count_valid(normalised_scores: dict) -> int:
    """Return count of non-None scores."""

def is_sufficient(normalised_scores: dict, threshold: int = 24) -> bool:
    """Return True if at least `threshold` of 30 features are non-None.
    Default threshold: 24/30. Below this, map generation is blocked."""
```

If `is_sufficient()` returns `False`:
- Block Similarity Map generation
- Display a user-facing error: "Too many features could not be scored (fewer than 24/30).
  Try again or switch to a different model."
- Still display the feature breakdown table, with missing features marked clearly.

If `is_sufficient()` returns `True` but some features are `None`:
- Cosine similarity is computed over the subset of features that are non-None,
  using only dimensions present in both the manuscript vector and the reference profile.
- Missing features are excluded from the cosine calculation, not treated as zero.
- A note appears below the map: "X features could not be scored and were excluded
  from similarity calculations."

```python
def similarity(your_scores: dict, profile: dict) -> float:
    """Cosine similarity between a manuscript's normalised scores and a reference profile."""

def rank_profiles(your_scores: dict) -> list[tuple[str, float]]:
    """Return the five LLM profiles ranked by cosine similarity, descending.
    HUMAN and AI_AVG are excluded — they are used for reporting only, not placement."""

def top_divergences(your_scores: dict, baseline: str = "Human", n: int = 6
) -> list[tuple[str, float]]:
    """Return the n features where the manuscript diverges most from the baseline.
    Baseline defaults to HUMAN profile for text report purposes."""
```

---

### `profiles.py`

Contains all reference profiles as Python constants. All values are pre-normalised to [0, 1].

**Profile inventory**

- `HUMAN` — mean values from Table 15. Used for scoring comparison and text report only.
  Has no map coordinates. Does not participate in manuscript placement.
- `AI_AVG` — pooled mean across all five AI models from Table 15. Used for scoring
  comparison and text report only. Has no map coordinates.
- `CLAUDE`, `GPT`, `GEMINI`, `DEEPSEEK`, `KIMI` — per-model profiles derived from
  Table 15 AI_AVG values adjusted by per-model fingerprint deltas from Section 5 and
  Table 16. These five profiles drive the manuscript placement algorithm.

Each profile is a `dict[str, float]` mapping feature name → normalised value.

**Additional constants:**
```python
FEATURE_NAMES: list[str]          # Ordered list of all 30 feature names
FEATURE_DESCRIPTIONS: dict        # Feature name → plain English description for UI
FEATURE_SCALE_TYPES: dict         # Feature name → scale type, used by normaliser.py
AI_ELEVATED: list[str]            # Features where AI scores higher than human baseline
HUMAN_ELEVATED: list[str]         # Features where human scores higher than AI baseline
PROFILE_COLORS: dict[str, str]    # Profile label → hex colour for map rendering
LLM_MAP_COORDS: dict[str, tuple]  # Model name → (x, y) fixed map coordinates
AI_ZONE_CENTRE: tuple             # (38, 26)
HUMAN_ZONE_CENTRE: tuple          # (68, 72)
```

---

### `pricing.py`

Contains API cost estimation logic for estimating analysis cost before a run.

Pricing is fetched live from the LiteLLM open-source project's community-maintained price
matrix (`LITELLM_PRICING_URL`, a JSON file updated within hours of most provider pricing
changes), cached in-process for `CACHE_TTL_SECONDS` (6 hours) so a Streamlit rerun doesn't
trigger a network call every time. Only the (provider, model) pairs already known via
`FALLBACK_PRICING` are priced — this never surfaces arbitrary models from the LiteLLM
matrix, just refreshes rates for the models this app already supports.

If the live fetch fails (offline, timeout, GitHub outage) or a specific model is missing
from the live data, cost estimation falls back to `FALLBACK_PRICING` for that model only —
each model degrades independently. `FALLBACK_PRICING` will still drift over time; update it
when it's too far from reality, and note the date of last verification in `CHANGELOG.md`
when updating.

All rate values are in USD per 1,000 tokens.

The token estimate mirrors what `llm_scorer.py` actually sends, not just the raw manuscript
word count:
- Input is capped at `MAX_STORY_WORDS` (imported from `llm_scorer.py`), matching
  `_build_prompt`'s truncation -- manuscripts longer than that never bill for more than the
  truncated amount.
- `PROMPT_SCAFFOLDING_WORDS` accounts for the fixed instructions/feature-questions/
  deterministic-score lines every prompt is wrapped in, on top of the story text.
- `llm_scorer.score()` retries once (resending the full prompt) on malformed JSON or an
  invalid field value, roughly doubling the tokens actually billed for that run. Rather than
  pretend that never happens, `estimate_cost()` returns a `(low, high)` range.

```python
LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
FETCH_TIMEOUT_SECONDS = 5
CACHE_TTL_SECONDS = 6 * 60 * 60

# Used only when live pricing is unavailable for a model.
# Update these when provider pricing changes and this drifts too far.
# Record the update date in CHANGELOG.md.

FALLBACK_PRICING = {
    "anthropic": {
        "claude-haiku-4-5-20251001": {"input": 0.0008,  "output": 0.004},
        "claude-sonnet-4-6":         {"input": 0.003,   "output": 0.015},
    },
    "openai": {
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4o":      {"input": 0.005,   "output": 0.015},
    },
}

WORDS_TO_TOKENS_RATIO = 1.35      # Approximate; used for cost estimation only
ESTIMATED_OUTPUT_TOKENS = 200     # Approximate LLM response length for 16 features
PROMPT_SCAFFOLDING_WORDS = 400    # Fixed prompt text wrapped around the story, see above
RETRY_COST_MULTIPLIER = 2         # llm_scorer.score() retries at most once

@dataclass
class CostEstimate:
    low: float             # Cost if the first LLM call succeeds
    high: float             # Cost if llm_scorer.score()'s one retry fires
    is_live_pricing: bool

def estimate_cost(word_count: int, provider: str, model: str) -> CostEstimate | None:
    """Return a CostEstimate. None if provider/model not found."""
```

The cost estimate displayed in the UI must always be labelled as an estimate, and show the
range: "Estimated API cost: ~$X.XX (up to ~$Y.YY if a retry is needed). Actual cost may
vary." When live pricing was unavailable and the estimate used `FALLBACK_PRICING` instead,
the UI appends a note that bundled pricing was used.

---

### `visualiser.py`

Produces two outputs: a Similarity Map (Plotly figure) and a text report (dict).

**1. Similarity Map (Plotly)**

A territory map — not a statistical projection. Positions are manually defined and
conceptually derived from the paper. The map must never be described as a classifier,
embedding, latent space, UMAP, PCA, or evidence of authorship.

*Coordinate system*

0–100 on both axes. No axis labels, no tick marks, no grid lines. Pure territory.

*Zones*

Two soft regions rendered as Gaussian blobs — no hard edges, opacity falls off from
centre outward. Zones are fixed and never change between manuscripts.

| Zone | Centre | Radius | Character |
|---|---|---|---|
| AI | (38, 26) | 20 | Tight, dense — reflects paper finding that AI stories cluster closely |
| Human | (68, 72) | 30 | Diffuse, wide — reflects paper finding that human stories are more dispersed |

The map has three kinds of territory: AI zone, Human zone, and undetermined territory
(everywhere else, rendered as empty space). A manuscript landing in undetermined territory
is a valid and meaningful result — it means the story is not narratively typical of any
known AI model, but cannot therefore be described as human-like.

*Fixed LLM reference points*

Positions informed by Figure 2, Table 16, and Section 5 of the paper. They never move.
Defined in `profiles.LLM_MAP_COORDS`.

| Model | X | Y | Rationale |
|---|---|---|---|
| Claude | 28 | 38 | Most distinct AI model. Restrained, continuist — upper edge of AI cluster. |
| GPT | 38 | 22 | Social, gossip-driven. Expansive but deep in AI territory. |
| Gemini | 44 | 24 | Nearest neighbour to DeepSeek. Tidiest endings, most streamlined. |
| DeepSeek | 46 | 26 | Nearest neighbour to Gemini. Front-loads context, slightly expansive. |
| Kimi | 40 | 20 | Fewest fingerprints. Generic centre of AI distribution. |

*Manuscript placement algorithm*

**Prerequisite — `normaliser.py` ↔ `visualiser.py` gate:** `similarity_map()` must never run
against an insufficient score set. `app.py` checks `normaliser.is_sufficient()` before calling
`similarity_map()` at all (per the "Block Similarity Map generation" requirement in the
`normaliser.py` spec above); `similarity_map()` itself also returns `None` if called with
fewer than 24/30 valid features, as a defensive second check rather than assuming the caller
always checks first.

Step 1 — Weighted centroid:
Compute the weighted centroid of the five LLM reference points. Each model's weight is
the cosine similarity between the manuscript's normalised 30-feature vector and that
model's reference profile. HUMAN and AI_AVG do not participate.

Step 2 — Repulsion magnitude:
```
mean_llm_similarity = mean of the five cosine similarity scores
repulsion_magnitude = (1 - mean_llm_similarity) * 35
```
A manuscript very similar to AI profiles (mean similarity ≈ 1.0) receives almost no
repulsion. One dissimilar to all AI profiles (mean similarity ≈ 0.0) is pushed up to
35 units away from the AI cluster.

Step 3 — Repulsion direction:
The direction vector runs from the AI zone centre (38, 26) through the weighted centroid
computed in Step 1. Normalise to a unit vector.

Fallback: if the weighted centroid is exactly equal to the AI zone centre (manuscript is
perfectly equidistant from all five LLM profiles), use the direction from (38, 26) toward
the Human zone centre (68, 72).

Step 4 — Final position:
```
manuscript_position = weighted_centroid + (repulsion_unit_vector * repulsion_magnitude)
```
Clamp final coordinates to map bounds [0, 100] on both axes.

*Zone membership*

After placement, determine which zone the manuscript falls in:
- If within radius 20 of AI zone centre (38, 26): AI zone
- If within radius 30 of Human zone centre (68, 72): Human zone
- Otherwise: Undetermined

*Required UI copy*

The following statement must appear verbatim below the Similarity Map as a caption.
It must not be paraphrased or omitted:

> Entering the Human zone does not imply human authorship; it indicates the manuscript
> is comparatively dissimilar to known AI narrative profiles and lies within the region
> associated with human narrative variability.

*Rendering*

- Zones as soft Gaussian blobs (no hard edges, Gaussian opacity falloff from centre)
- LLM reference points as small labelled circle markers
- Manuscript as a distinct highlighted marker, differentiated from LLM points by shape and colour
- A thin line connecting the manuscript to its nearest LLM reference point
- Hover tooltips showing cosine similarity values for each reference point
- No axes, no grid, no tick marks
- `displayModeBar=False` in Plotly config — removes the toolbar for a cleaner UI
- Library: **Plotly** (required for hover interaction)

```python
def similarity_map(
    your_scores: dict,
    story_title: str,
    llm_similarities: dict[str, float],
    manuscript_xy: tuple[float, float],
) -> plotly.graph_objects.Figure | None:
    """Returns None if the underlying score set is insufficient (see gate above)."""
```

---

**2. Text report**

Returns a structured dict for Streamlit to render as labelled sections.

```python
def text_report(your_scores: dict, story_title: str) -> dict:
    """
    Returns:
    {
      "nearest":        (profile_name, similarity_score),
      "second_nearest": (profile_name, similarity_score),
      "zone":           "AI zone" | "Human zone" | "Undetermined",
      "human_distance": float,   # 1 - cosine_similarity(your_scores, HUMAN)
      "divergences":    list of (feature_name, delta, plain_english_note)
    }
    """
```

---

### `app.py` — Streamlit Interface

**Layout:** Single-page, top-to-bottom flow. No tabs.

**Caching**

spaCy model loading is expensive and must be cached across sessions:

```python
@st.cache_resource
def load_spacy_model():
    import spacy
    return spacy.load("en_core_web_lg")
```

LLM scoring results must be cached within a session to avoid re-running if the user
changes display options without changing the file or configuration. Use
`st.session_state` keyed on a hash of (file content + provider + model). If the file
or config changes, invalidate the cache and re-run the full pipeline.

**1. Header**
- Title: Human Enough
- One-sentence description: "Analyses the narrative structure of your manuscript and
  maps it against known human and AI writing profiles."
- Link to the source paper (arXiv:2604.03136)

**2. Configuration sidebar**
- Provider dropdown: Anthropic / OpenAI
- Model dropdown (updates based on provider: Haiku/Sonnet or gpt-4o-mini/gpt-4o)
- API key input (password masked)
- Notice: "Your key is used only for this session and is never stored."

**3. File upload**
- `st.file_uploader` accepting .pdf, .md, .txt
- Word count displayed after upload (from `ExtractionResult.word_count`)
- Warning if story is under 2,000 words: "Short texts may produce unreliable scores."
- Warning if story is over 60,000 words: "Long manuscripts will be truncated for
  semantic analysis. Structural analysis runs on the full text."

**4. Run button**
- Disabled until a file is uploaded and an API key is entered
- Before running, display an estimated API cost using `pricing.estimate_cost()`:
  "Estimated API cost: ~$X.XX. Actual cost may vary."
  If the model is not found in `pricing.PRICING`, omit the estimate rather than showing
  an error.
- On click: runs the full pipeline with `st.progress` indicator
  - "Extracting text…"
  - "Running structural analysis…"
  - "Running semantic analysis…"
  - "Generating map…"

**5. Results**
- Similarity Map (full width, `st.plotly_chart`)
- Required interpretation caption (verbatim, see `visualiser.py`)
- Zone verdict (bold): AI zone / Human zone / Undetermined
- Nearest and second-nearest LLM profiles with cosine similarity scores
- Cosine distance from Human profile
- Six top divergences from Human profile (plain English, not a table)
- Feature breakdown in a `st.expander`: all 30 features with your score / human mean /
  AI avg mean / delta

**6. Footer**
- Citation: Russell, J. et al. (2026). StoryScope. arXiv:2604.03136
- Disclaimer: "Reference profiles are approximated from published aggregate statistics,
  not the paper's trained classifier weights."

---

## Data Flow

```
UploadedFile
    │
    ▼
extractor.extract()
    │  ExtractionResult (text, word_count, char_count)
    ▼
preprocessor.preprocess()
    │  PreprocessResult (full_text, narration, dialogue,
    │                    protagonist, named_characters, final_segment)
    ▼
deterministic.score()
    │  15 raw scores (14 profile + Dialogue Ratio context-only)
    ▼
llm_scorer.score()          ← receives all 15 deterministic scores as context
    │  16 raw scores
    ▼
app.py: strip Dialogue Ratio, merge 14 + 16 = 30 raw scores
    ▼
normaliser.normalise()      ← 30 normalised scores; raises on any unrecognised key
    │
    ├──────────────────────────────────────────┐
    ▼                                           ▼
normaliser.rank_profiles()         normaliser.top_divergences()
    │  LLM similarity rankings     │  key divergences vs Human
    ▼                                           ▼
visualiser.similarity_map()        visualiser.text_report()
    │  Plotly Figure (or None if insufficient)  │  sections dict
    ▼                                           ▼
app.py: st.plotly_chart()          app.py: st.markdown() per section
```

---

## Reference Profile Values

All values normalised to [0, 1]. Source: Table 15, StoryScope paper (Russell et al., 2026).

Features listed in order: AI-elevated first (0–19), human-elevated second (20–29).

### HUMAN and AI_AVG profiles

| Feature | HUMAN | AI_AVG |
|---|---|---|
| Thematic Explicitness | 0.656 | 0.788 |
| Moral/Philosophical Weight | 0.652 | 0.736 |
| Thematic Unity | 0.882 | 0.948 |
| Narrator Thematic Commentary | 0.520 | 0.770 |
| Dialogue as Philosophy | 0.340 | 0.590 |
| Vague Intertextual Allusion | 0.500 | 0.720 |
| Embodied Emotion Expression | 0.380 | 0.810 |
| Setting as Psychological Mirror | 0.716 | 0.814 |
| Environmental Emphasis | 0.566 | 0.642 |
| Olfactory Imagery | 0.570 | 0.820 |
| Sensory Density | 0.732 | 0.786 |
| Interior Access Depth | 0.734 | 0.786 |
| Causal Chain Continuity | 0.784 | 0.840 |
| Spatial Granularity | 0.568 | 0.633 |
| Protagonist-Driven Resolution | 0.460 | 0.690 |
| External Character Introduction | 0.300 | 0.520 |
| No Subplots | 0.570 | 0.790 |
| Internal Resolution Mode | 0.270 | 0.470 |
| Clear Opening Setting | 0.530 | 0.583 |
| Pre-Threat Character Investment | 0.552 | 0.598 |
| Named Intertextuality | 0.470 | 0.240 |
| Balanced Intertextual Mix | 0.370 | 0.160 |
| Fourth-Wall Permeability | 0.168 | 0.098 |
| Direct Reader Address | 0.093 | 0.023 |
| Revelation Recontextualisation | 0.656 | 0.590 |
| Chronological Discontinuity | 0.480 | 0.424 |
| Nonlinear Disclosure Framing | 0.392 | 0.336 |
| Anachrony Intensity | 0.516 | 0.462 |
| Location Variety | 0.335 | 0.270 |
| Moral Ambivalence | 0.590 | 0.380 |

### Per-model profiles

Derived from AI_AVG as baseline, with per-model deltas applied from Section 5 fingerprint
descriptions and Table 16 uniqueness ratios. Features not mentioned in a model's fingerprint
retain the AI_AVG value. All values normalised to [0, 1].

**Derivation rationale by model:**

*Claude* — "most distinct AI model", "defined by restraint", "flat event escalation",
"most uniform narrative voice", "reverent/continuist", "favours epilogues", "avoids dream
sequences", "quiet endings". Fingerprint features with highest uniqueness: event escalation
strength (22.4), event-type diversity (10.7), epilogue/flash-forward endings (8.9).
Key adjustments from AI_AVG: lower Causal Chain Continuity (restrained escalation),
lower Chronological Discontinuity (avoids nonlinearity), higher Revelation
Recontextualisation (epilogue structure implies looking back), lower Thematic Explicitness
(restraint relative to other AI models).

*GPT* — "gossip and rumor as plot mechanism" (64%), "reflections on events from years ago",
"ensemble-heavy social networks", "subverts expectations more than other AI" (41%),
"leaves reconciliations ambiguous". Key adjustments: higher Chronological Discontinuity
(distant retrospective narration), lower Internal Resolution Mode (ambiguous
reconciliations), higher Moral Ambivalence relative to AI_AVG.

*Gemini* — "tidiest endings", "extended denouements", "bleakest settings" (88% bleak),
nearest neighbour to DeepSeek. Key adjustments: higher Thematic Unity (tidiest, most
streamlined), lower Moral Ambivalence, higher Clear Opening Setting (grounds reader
immediately in bleak setting).

*DeepSeek* — "front-loads crucial context", nearest neighbour to Gemini, otherwise
generic. Key adjustments: higher Clear Opening Setting (front-loading context implies
strong early grounding), higher Pre-Threat Character Investment (establishes context
before jeopardy). Otherwise close to AI_AVG.

*Kimi* — "fewest fingerprints", "lowest F1", "sits at generic centre of AI distribution",
"no distinctive narrative choices". Values stay closest to AI_AVG across all features.

| Feature | CLAUDE | GPT | GEMINI | DEEPSEEK | KIMI |
|---|---|---|---|---|---|
| Thematic Explicitness | 0.750 | 0.790 | 0.800 | 0.785 | 0.788 |
| Moral/Philosophical Weight | 0.710 | 0.740 | 0.745 | 0.735 | 0.736 |
| Thematic Unity | 0.940 | 0.945 | 0.965 | 0.948 | 0.948 |
| Narrator Thematic Commentary | 0.780 | 0.765 | 0.775 | 0.770 | 0.770 |
| Dialogue as Philosophy | 0.600 | 0.620 | 0.575 | 0.590 | 0.590 |
| Vague Intertextual Allusion | 0.730 | 0.705 | 0.725 | 0.720 | 0.720 |
| Embodied Emotion Expression | 0.820 | 0.815 | 0.805 | 0.810 | 0.810 |
| Setting as Psychological Mirror | 0.810 | 0.810 | 0.830 | 0.812 | 0.814 |
| Environmental Emphasis | 0.630 | 0.638 | 0.660 | 0.642 | 0.642 |
| Olfactory Imagery | 0.800 | 0.825 | 0.830 | 0.818 | 0.820 |
| Sensory Density | 0.780 | 0.790 | 0.795 | 0.785 | 0.786 |
| Interior Access Depth | 0.790 | 0.785 | 0.788 | 0.786 | 0.786 |
| Causal Chain Continuity | 0.800 | 0.835 | 0.850 | 0.840 | 0.840 |
| Spatial Granularity | 0.625 | 0.630 | 0.640 | 0.635 | 0.633 |
| Protagonist-Driven Resolution | 0.670 | 0.695 | 0.700 | 0.690 | 0.690 |
| External Character Introduction | 0.510 | 0.525 | 0.530 | 0.520 | 0.520 |
| No Subplots | 0.800 | 0.775 | 0.810 | 0.790 | 0.790 |
| Internal Resolution Mode | 0.480 | 0.440 | 0.475 | 0.470 | 0.470 |
| Clear Opening Setting | 0.575 | 0.578 | 0.610 | 0.620 | 0.583 |
| Pre-Threat Character Investment | 0.590 | 0.598 | 0.600 | 0.625 | 0.598 |
| Named Intertextuality | 0.220 | 0.260 | 0.235 | 0.240 | 0.240 |
| Balanced Intertextual Mix | 0.150 | 0.175 | 0.155 | 0.160 | 0.160 |
| Fourth-Wall Permeability | 0.090 | 0.108 | 0.095 | 0.098 | 0.098 |
| Direct Reader Address | 0.020 | 0.028 | 0.022 | 0.023 | 0.023 |
| Revelation Recontextualisation | 0.620 | 0.580 | 0.585 | 0.590 | 0.590 |
| Chronological Discontinuity | 0.390 | 0.460 | 0.415 | 0.424 | 0.424 |
| Nonlinear Disclosure Framing | 0.310 | 0.360 | 0.330 | 0.336 | 0.336 |
| Anachrony Intensity | 0.420 | 0.490 | 0.455 | 0.462 | 0.462 |
| Location Variety | 0.260 | 0.295 | 0.265 | 0.270 | 0.270 |
| Moral Ambivalence | 0.360 | 0.420 | 0.370 | 0.378 | 0.380 |

---

## Lexicon Files

All lexicons are JSON arrays of lowercase strings. Matching is case-insensitive, whole-word.
Each category must contain a minimum of 30 entries before deterministic scoring is tested.

**`sensory.json`**
```json
{
  "olfactory": ["smell", "scent", "reek", "fragrance", "stench", "aroma", "whiff", ...],
  "auditory":  ["heard", "sound", "noise", "whisper", "clatter", "silence", ...],
  "tactile":   ["rough", "smooth", "cold", "warm", "sharp", "soft", "pressure", ...],
  "gustatory": ["taste", "bitter", "sweet", "sour", "flavour", "swallowed", ...],
  "visual":    ["saw", "light", "shadow", "colour", "glance", "dark", "bright", ...]
}
```

**`body_sensation.json`**
```json
["chest", "throat", "stomach", "pulse", "breath", "heartbeat", "skin", "hands",
 "jaw", "shoulders", "gut", "lungs", "temples", "spine", "fingers", ...]
```

**`causal.json`**
```json
["because", "therefore", "thus", "hence", "consequently", "as a result",
 "which caused", "which meant", "so that", "in order to", "leading to", ...]
```

**`temporal.json`**
```json
["years earlier", "the night before", "she remembered", "he recalled",
 "had been", "had known", "had thought", "long ago", "in those days",
 "the following morning", "three weeks later", "decades before", ...]
```

---

## Error States

All error states must surface as user-facing messages in the Streamlit UI.
Python tracebacks must never be shown to the user.

| Error | User-facing message |
|---|---|
| Invalid API key | "API key was rejected. Check that you've entered it correctly." |
| Rate limit hit | "API rate limit reached. Wait a moment and try again." |
| File too large | "File exceeds the 10MB limit. Try splitting the manuscript." |
| spaCy model missing | "Language model not found. Run: python -m spacy download en_core_web_lg" |
| LLM returns malformed JSON | "Semantic scoring failed after retry. Results show structural features only." |
| PDF has no text layer | "This PDF appears to be scanned. Text extraction requires a PDF with a text layer." |
| Unsupported file type | "Please upload a .pdf, .md, or .txt file." |

---

## Constraints and Assumptions

- Stories under 2,000 words will produce unreliable scores. Warn the user; do not block.
- Stories over 60,000 words are truncated to 60,000 words for the LLM call only.
  Deterministic scoring runs on the full text.
- The per-model reference profiles are approximations derived from aggregate statistics
  and fingerprint descriptions in the paper. They are not the paper's trained classifier
  weights and should not be represented as such.
- Dialogue detection is heuristic and assumes standard English double quotation marks.
  Manuscripts using em dashes, single quotes, or no quotation marks will produce
  unreliable dialogue/narration splits, affecting Dialogue Ratio, Dialogue as Philosophy,
  and narrator-only features.
- spaCy NER is imperfect for fantasy or historical fiction with unusual proper nouns.
  This affects Location Variety and Named Intertextuality most.
- Protagonist detection may fail on first-person narratives with unnamed narrators.
  The fallback (most frequent PERSON entity) is used in these cases; if no PERSON
  entities are found, protagonist-dependent features are skipped.
- The tool does not store any user data, story text, or API keys.
- The Similarity Map is a conceptual visualisation. Zone membership is an indication of
  narrative similarity patterns, not a determination of authorship.

---

## Security

- API keys must never appear in logs, console output, error messages, or tracebacks.
- Story text must never be logged or printed to console.
- LLM prompts (which contain story text) must never be logged.
- If an exception occurs during the LLM call, catch it and log only the exception type
  and a sanitised message — never the prompt or response body.
- In Streamlit, do not use `st.write()` or `st.code()` to display raw prompts or
  API responses at any point in the production code path.

### Diagnostic logging

`modules/logging_config.py` provides console-only (stderr) diagnostic logging under the
shared `human_enough` logger namespace, one child logger per module (e.g.
`human_enough.llm_scorer`). Nothing is ever written to disk, so this introduces no new
persistence mechanism and the "the tool does not store any user data" guarantee in
Constraints and Assumptions holds without a retention or rotation policy.

Level is controlled by the `HUMAN_ENOUGH_LOG_LEVEL` environment variable (default `INFO`),
set before launching the app -- there is no in-app UI control for it, by design (see
`docs/development.md`). Valid values are Python's standard `logging` level names
(case-insensitive): `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` -- see
`logging_config.LEVEL_NAMES_TO_VALUES` for the single source of truth. An unrecognised value
falls back to `INFO` and logs a one-line warning naming the invalid value, rather than
failing silently.

**What is logged:** pipeline stage transitions and their durations, word/character counts,
booleans (e.g. whether a protagonist was found), computed numeric scores (raw and
normalised feature values, cosine similarities, map coordinates), retry/validation outcomes
from `llm_scorer.py` (by *feature name*, e.g. which of the 16 fields were invalid), and the
already-sanitised message from this codebase's `*Error` exception classes
(`ExtractionError`, `PreprocessError`, `DeterministicScoringError`, `LLMScoringError`) on
failure.

**What is never logged**, enforced at every call site that logs an exception (always
`str(exc)` from one of the classes above, never the raw exception or its arguments):

- Story text, in whole or in part, at any pipeline stage.
- Uploaded filenames (a filename can itself be revealing about an unpublished
  manuscript's title or contents).
- Character names, or any other named-entity text extracted from the manuscript.
- LLM prompts or raw LLM responses.
- API keys, or any other request/response body that could contain one.

Every module that logs numeric scores does so because those values are our own closed
taxonomy of feature names and floats — not excerpted text — so they carry no more
information about the manuscript's content than the Similarity Map itself already shows
in the UI.

---

## Licensing and Attribution

**`LICENSE`** — MIT licence. Standard MIT text with copyright holder as the repository owner.

**`NOTICE`** — Must include the following attribution verbatim:

```
This software uses narrative feature definitions and reference profile statistics
derived from:

  Russell, J., Rajendhran, R., Pham, C. M., Iyyer, M., & Wieting, J. (2026).
  StoryScope: Investigating idiosyncrasies in AI fiction.
  arXiv:2604.03136. University of Maryland / Google DeepMind.

The StoryScope paper is used strictly for academic and research reference purposes.
No model weights, datasets, or copyrighted story text from that work are included
in this software.
```

**`README.md`** must include a Citation section containing the same reference in both
plain text and BibTeX format.

---

## Sample Data

**`sample/sample_story.txt`**

Selected story: Ambrose Bierce, *An Occurrence at Owl Creek Bridge* (1890, ~4,000 words).
Nonlinear structure, a late revelation that recontextualises the whole narrative, and strong
temporal complexity — exercises exactly the human-elevated features (Chronological
Discontinuity, Anachrony Intensity, Revelation Recontextualisation) that most differentiate
human from AI writing per the paper. Public domain in all major jurisdictions (pre-1928
publication).

The file must include a header comment:
```
# Title: [Story Title]
# Author: [Author Name]
# Published: [Year]
# Public domain status: [Jurisdiction and basis]
```

The sample file is used for:
1. Automated tests (deterministic and integration)
2. A "Try with sample" button in the UI that bypasses file upload
3. Developer testing during module development

---

## Versioning

Current version: `0.1.0`

**`CHANGELOG.md`** must exist from the first commit. Format:

```markdown
# Changelog

## [0.1.0] — YYYY-MM-DD
### Initial release
- Core pipeline: extraction, preprocessing, deterministic scoring, LLM scoring
- Similarity Map with five LLM reference profiles
- Streamlit UI with Anthropic and OpenAI provider support
- API pricing last verified: YYYY-MM-DD
```

When updating `pricing.py` constants, add a changelog entry noting the date of
verification and which prices changed.

---

## Packaging

This project is **clone-and-run only**. It is not designed to be installed as a Python
package. Poetry is used solely for dependency management and reproducible environments,
not for building or publishing a distribution. Users should not run `poetry build` or
`pip install .`

---

## Feature Provenance

Source table reference for each of the 30 core features, for future maintenance.
Table 13 = AI-characterising features. Table 14 = human-characterising features.
Table 15 = full core feature set with human/AI mean values.

| Feature | Source | Direction |
|---|---|---|
| Thematic Explicitness | Table 13, Table 15 | AI-elevated |
| Moral/Philosophical Weight | Table 13, Table 15 | AI-elevated |
| Thematic Unity | Table 13, Table 15 | AI-elevated |
| Narrator Thematic Commentary | Table 13, Table 15 | AI-elevated |
| Dialogue as Philosophy | Table 13, Table 15 | AI-elevated |
| Vague Intertextual Allusion | Table 13, Table 15 | AI-elevated |
| Embodied Emotion Expression | Table 13, Table 15 | AI-elevated |
| Setting as Psychological Mirror | Table 13, Table 15 | AI-elevated |
| Environmental Emphasis | Table 13, Table 15 | AI-elevated |
| Olfactory Imagery | Table 13, Table 15 | AI-elevated |
| Sensory Density | Table 13, Table 15 | AI-elevated |
| Interior Access Depth | Table 13, Table 15 | AI-elevated |
| Causal Chain Continuity | Table 13, Table 15 | AI-elevated |
| Spatial Granularity | Table 13, Table 15 | AI-elevated |
| Protagonist-Driven Resolution | Table 13, Table 15 | AI-elevated |
| External Character Introduction | Table 13, Table 15 | AI-elevated |
| No Subplots | Table 13, Table 15 | AI-elevated |
| Internal Resolution Mode | Table 13, Table 15 | AI-elevated |
| Clear Opening Setting | Table 13, Table 15 | AI-elevated |
| Pre-Threat Character Investment | Table 13, Table 15 | AI-elevated |
| Named Intertextuality | Table 14, Table 15 | Human-elevated |
| Balanced Intertextual Mix | Table 14, Table 15 | Human-elevated |
| Fourth-Wall Permeability | Table 14, Table 15 | Human-elevated |
| Direct Reader Address | Table 14, Table 15 | Human-elevated |
| Revelation Recontextualisation | Table 14, Table 15 | Human-elevated |
| Chronological Discontinuity | Table 14, Table 15 | Human-elevated |
| Nonlinear Disclosure Framing | Table 14, Table 15 | Human-elevated |
| Anachrony Intensity | Table 14, Table 15 | Human-elevated |
| Location Variety | Table 14, Table 15 | Human-elevated |
| Moral Ambivalence | Table 14, Table 15 | Human-elevated |

---

## Dependencies

Managed with **Poetry**. All dependencies are defined in `pyproject.toml` and pinned in
`poetry.lock`. The lock file must be committed to the repository so all users get an
identical environment.

**`pyproject.toml`:**

```toml
[tool.poetry]
name = "human-enough"
version = "0.1.0"
description = "Narrative analysis tool for fiction writers"
authors = ["David Caldwell"]
license = "MIT"
readme = "README.md"
package-mode = false

[tool.poetry.dependencies]
python = ">=3.14,<3.15"
streamlit = "^1.59.0"
spacy = "3.8.13"
anthropic = "^0.116.0"
openai = "^2.44.0"
plotly = "^6.8.0"
numpy = "^2.5.1"
pdfplumber = "^0.11.10"
pypdf = "^6.14.2"

[tool.poetry.group.dev.dependencies]
pytest = "^9.1.1"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

`package-mode = false` is used because this project is clone-and-run only (see Packaging
section) and does not follow a `src/human_enough/` importable-package layout — modules live
directly under `modules/`.

`spacy` is pinned exactly to `3.8.13` (not `3.8.14`, and not a caret range) because `3.8.14`
has no installable distribution on PyPI (confirmed via `pip download`, which enumerates all
real releases and does not list it, unlike Poetry's PyPI JSON API lookup which surfaced it
anyway) — an unpinned caret range would let the resolver pick it again and fail at install
time with "no candidate wheels for this ABI". `3.8.13` is the latest version with a published
`cp314-win_amd64` wheel.

The spaCy model (`en_core_web_lg`) is not a PyPI package and cannot be managed by
Poetry directly. Install it after `poetry install`:

```
poetry run python -m spacy download en_core_web_lg
```

This should also be noted clearly in the README setup steps.

---

## Tests

All tests live in `tests/`. Run with `pytest`. The sample story in `sample/sample_story.txt`
is used as the primary test fixture for integration tests.

### `test_extractor.py`
- PDF extraction returns non-empty string and correct word count
- Markdown extraction strips YAML front matter correctly
- TXT extraction returns text unchanged
- Unsupported file type raises a clear error
- Empty file raises a clear error

### `test_preprocessor.py`
- Narration and dialogue segments are non-overlapping and together cover the full text
- Protagonist is a string present in `named_characters`
- `final_segment` is approximately 15% of full text length
- First-person narrator story (no named protagonist) is handled without error

### `test_normaliser.py`
- All 30 features normalise to [0, 1] given valid raw inputs
- Scale features (1–5) normalise correctly: 1 → 0.2, 5 → 1.0
- Binary features pass through unchanged
- `None` values pass through unchanged
- `count_valid()` returns correct count for mixed None/float dicts
- `is_sufficient()` returns True at exactly 24 valid features, False at 23
- Cosine similarity computed correctly over subset when some features are None
- Cosine similarity of identical vectors = 1.0
- `normalise()` raises a clear error when given a key not in `profiles.FEATURE_NAMES`
  (e.g. a stray `Dialogue Ratio` that the caller failed to strip)

### `test_llm_scorer.py`
- Malformed JSON response triggers one retry
- Second malformed JSON response returns None for all 16 features
- Scale field with value 6 (out of range) → None
- Binary field with value 2 (out of range) → None
- Valid response parses correctly and passes schema validation
- Invalid API key raises user-facing error, not a traceback

### `test_visualiser.py`
- Placement: manuscript identical to Claude profile lands nearest Claude's map coordinates
  and within the AI zone radius
- Placement: manuscript equidistant from all five profiles lands near AI cluster centre
- Placement: manuscript with uniformly low similarity (all scores 0.1) lands outside AI zone
- Fallback direction used when weighted centroid equals AI zone centre exactly
- Final coordinates clamped to [0, 100] on both axes
- `is_sufficient()` returning False blocks map generation and `similarity_map()` returns None

---

## Known Heuristic Limitations

The architecture is sound, but the deterministic scoring heuristics are approximations.
These are acceptable for v0.1.0 but represent where future refinement will be concentrated.
Expect to spend the majority of post-launch iteration on these four areas:

**Protagonist detection**
The action-verb-subject heuristic fails on ensemble casts (no clear dominant subject),
frame narratives (narrator distinct from protagonist), and first-person stories where
the narrator is unnamed. The PERSON entity fallback partially covers these but is not
reliable for all literary fiction structures.

**Subplot detection**
Named entity thread analysis catches character-driven subplots — a secondary character
who appears and disappears. It misses thematic subplots that don't introduce new
characters, and setting- or object-driven secondary threads. A story can have rich
subplot structure that scores as "no subplots" under this heuristic.

**Embodied emotion**
Lexicon matching on body-sensation words cannot distinguish a character *experiencing*
a tightening chest from a character *observing* someone else's tight chest, or from
a figurative use of the same language. False positives are likely in stories with
frequent physical description that is not emotionally motivated.

**Causal continuity**
Connective density (because, therefore, thus, etc.) measures explicit causation language,
not actual narrative causality. A story can be highly causal in structure without using
connective words, and can use many connectives in dialogue or argument without having a
tight causal chain. This feature is the most likely to require replacement with a
dependency-parse or discourse-relation approach in a future version.

---

## Notes for Claude Code

- Build modules in dependency order: `profiles.py` → `pricing.py` → `lexicons/` →
  `extractor.py` → `preprocessor.py` → `deterministic.py` → `llm_scorer.py` →
  `normaliser.py` → `visualiser.py` → `app.py`
- Each module should be independently testable with a simple `if __name__ == "__main__"`
  block using a sample text string
- `PreprocessResult` and `ExtractionResult` dataclasses must be importable by downstream
  modules without circular imports — define them in their respective modules and import
  explicitly
- Lexicon JSON files must be populated with a minimum of 30 entries per category before
  deterministic scoring is tested
- Do not use `st.experimental_*` APIs — use only stable Streamlit APIs
- The Similarity Map must render correctly on both light and dark Streamlit themes.
  Use explicit background colours in the Plotly figure layout; do not rely on theme defaults
- The Similarity Map is a conceptual visualisation, not a statistical projection. Do not
  use language in comments, docstrings, or UI strings that implies otherwise
- Add a `.gitignore` excluding: `__pycache__/`, `*.pyc`, `.env`, `.venv/`, `.DS_Store`
  Poetry creates its virtual environment outside the project directory by default, but
  if configured locally it may appear as `.venv/` — exclude it either way
- Test manuscript placement with three synthetic edge cases:
  1. A vector identical to one LLM profile — should land nearest that model's map point
     and within the AI zone (exact placement will differ due to repulsion term)
  2. A vector equidistant from all five LLM profiles — should land near AI cluster centre
  3. A synthetic profile with uniformly low cosine similarity to all five LLM profiles —
     should be pushed well clear of the AI cluster, toward or into undetermined territory
