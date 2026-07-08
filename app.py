"""Human Enough -- Streamlit entry point.

Single-page, top-to-bottom flow. See docs/architecture.md > app.py for the full UI spec.
"""

import hashlib
import time
from io import BytesIO

import streamlit as st

from modules import deterministic, llm_scorer, normaliser, pricing, profiles, visualiser
from modules.deterministic import DeterministicScoringError
from modules.extractor import ExtractionError, extract
from modules.llm_scorer import LLMScoringError
from modules.logging_config import get_logger
from modules.preprocessor import PreprocessError, preprocess

SAMPLE_STORY_PATH = "sample/sample_story.txt"
PAPER_URL = "https://arxiv.org/abs/2604.03136"

logger = get_logger("app")

PROVIDER_MODELS = {
    "Anthropic": {
        "provider_key": "anthropic",
        "models": {
            "Haiku (default, cheaper)": "claude-haiku-4-5-20251001",
            "Sonnet (higher quality)": "claude-sonnet-4-6",
        },
    },
    "OpenAI": {
        "provider_key": "openai",
        "models": {
            "gpt-4o-mini (default, cheaper)": "gpt-4o-mini",
            "gpt-4o (higher quality)": "gpt-4o",
        },
    },
}


@st.cache_resource
def load_spacy_model():
    """Pre-warms the shared spaCy singleton (see modules/preprocessor.py) once per server
    process, so it is not reloaded on every Streamlit rerun."""
    from modules.preprocessor import _get_nlp

    return _get_nlp()


class _BytesUpload:
    """Minimal file-like wrapper so extractor.extract() can treat the sample story the same
    way it treats a real st.file_uploader result."""

    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def _cache_key(file_bytes: bytes, provider: str, model: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    hasher.update(provider.encode())
    hasher.update(model.encode())
    return hasher.hexdigest()


def _run_pipeline(file_bytes: bytes, file_name: str, provider: str, api_key: str, model: str) -> dict:
    """Runs extraction -> preprocessing -> deterministic -> LLM -> normalisation -> map/report.

    Returns a dict of everything the Results section needs to render. Raises ExtractionError /
    PreprocessError / DeterministicScoringError / LLMScoringError with a user-safe message.
    """
    started = time.perf_counter()
    logger.info("Pipeline started (provider=%s, model=%s)", provider, model)

    progress = st.progress(0, text="Extracting text...")
    extraction = extract(_BytesUpload(file_name, file_bytes))

    progress.progress(25, text="Running structural analysis...")
    preprocessed = preprocess(extraction.text)
    deterministic_scores = deterministic.score(preprocessed)

    progress.progress(50, text="Running semantic analysis...")
    llm_scores = llm_scorer.score(preprocessed, deterministic_scores, provider, api_key, model)

    progress.progress(75, text="Generating map...")
    # Dialogue Ratio is context-only -- strip it before the 30-feature profile vector.
    profile_raw_scores = {
        name: value for name, value in deterministic_scores.items() if name != "Dialogue Ratio"
    }
    profile_raw_scores.update(llm_scores)
    normalised = normaliser.normalise(profile_raw_scores)

    result = {
        "extraction": extraction,
        "preprocessed": preprocessed,
        "deterministic_scores": deterministic_scores,
        "llm_scores": llm_scores,
        "normalised": normalised,
        "sufficient": normaliser.is_sufficient(normalised),
    }

    if result["sufficient"]:
        position, llm_similarities = visualiser.place_manuscript(normalised)
        result["position"] = position
        result["llm_similarities"] = llm_similarities
        result["figure"] = visualiser.similarity_map(normalised, file_name, llm_similarities, position)
        result["report"] = visualiser.text_report(normalised, file_name)

    progress.progress(100, text="Done.")
    progress.empty()

    elapsed = time.perf_counter() - started
    logger.info("Pipeline finished in %.3fs (sufficient=%s)", elapsed, result["sufficient"])
    return result


# --- 1. Header ---------------------------------------------------------------------------

st.set_page_config(page_title="Human Enough", layout="wide")
st.title("Human Enough")
st.write(
    "Analyses the narrative structure of your manuscript and maps it against known human "
    "and AI writing profiles."
)
st.caption(f"Based on the StoryScope paper: [arXiv:2604.03136]({PAPER_URL})")

# --- 2. Configuration sidebar --------------------------------------------------------------

with st.sidebar:
    st.header("Configuration")
    provider_label = st.selectbox("Provider", list(PROVIDER_MODELS.keys()))
    provider_info = PROVIDER_MODELS[provider_label]
    model_label = st.selectbox("Model", list(provider_info["models"].keys()))
    model = provider_info["models"][model_label]
    provider = provider_info["provider_key"]
    api_key = st.text_input("API key", type="password")
    st.caption("Your key is used only for this session and is never stored.")

# --- 3. File upload ------------------------------------------------------------------------

st.header("1. Upload your manuscript")
uploaded_file = st.file_uploader("Manuscript", type=["pdf", "md", "txt"], label_visibility="collapsed")
use_sample = st.button("Try with sample story")

file_bytes: bytes | None = None
file_name: str | None = None
word_count: int | None = None

if use_sample:
    with open(SAMPLE_STORY_PATH, "rb") as f:
        file_bytes = f.read()
    file_name = "sample_story.txt"
    st.session_state["active_file_bytes"] = file_bytes
    st.session_state["active_file_name"] = file_name
elif uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name
    st.session_state["active_file_bytes"] = file_bytes
    st.session_state["active_file_name"] = file_name
elif "active_file_bytes" in st.session_state:
    file_bytes = st.session_state["active_file_bytes"]
    file_name = st.session_state["active_file_name"]

if file_bytes is not None:
    try:
        preview = extract(_BytesUpload(file_name, file_bytes))
        word_count = preview.word_count
        st.write(f"**{file_name}** -- {word_count:,} words")
        if word_count < 2000:
            st.warning("Short texts may produce unreliable scores.")
        if word_count > 60000:
            st.warning(
                "Long manuscripts will be truncated for semantic analysis. "
                "Structural analysis runs on the full text."
            )
    except ExtractionError as exc:
        st.error(str(exc))
        file_bytes = None

# --- 4. Run button -------------------------------------------------------------------------

st.header("2. Run analysis")

if file_bytes is not None and word_count is not None:
    cost_estimate = pricing.estimate_cost(word_count, provider, model)
    if cost_estimate is not None:
        caption = (
            f"Estimated API cost: ~${cost_estimate.low:.2f} "
            f"(up to ~${cost_estimate.high:.2f} if a retry is needed). Actual cost may vary."
        )
        if not cost_estimate.is_live_pricing:
            caption += " (using bundled pricing -- live pricing lookup unavailable)"
        st.caption(caption)

run_disabled = file_bytes is None or not api_key
run_clicked = st.button("Analyse", disabled=run_disabled, type="primary")

if run_clicked:
    cache_key = _cache_key(file_bytes, provider, model)
    if st.session_state.get("results_cache_key") != cache_key:
        try:
            load_spacy_model()
            results = _run_pipeline(file_bytes, file_name, provider, api_key, model)
            st.session_state["results_cache_key"] = cache_key
            st.session_state["results"] = results
        except (ExtractionError, PreprocessError, DeterministicScoringError, LLMScoringError) as exc:
            # str(exc) here is always the already-sanitised, user-safe message these
            # exception classes carry -- never a raw traceback or provider response body.
            logger.error("Pipeline failed (%s): %s", type(exc).__name__, exc)
            st.error(str(exc))
            st.session_state.pop("results", None)

# --- 5. Results ----------------------------------------------------------------------------

results = st.session_state.get("results")
if results is not None:
    st.header("3. Results")

    if not results["sufficient"]:
        valid = normaliser.count_valid(results["normalised"])
        st.error(
            f"Too many features could not be scored ({valid}/30, fewer than 24/30). "
            "Try again or switch to a different model."
        )
    else:
        st.plotly_chart(results["figure"], config={"displayModeBar": False}, use_container_width=True)
        st.caption(visualiser.REQUIRED_CAPTION)

        report = results["report"]
        st.markdown(f"**Zone: {report['zone']}**")

        col1, col2 = st.columns(2)
        with col1:
            nearest_name, nearest_sim = report["nearest"]
            st.metric(f"Nearest profile: {nearest_name}", f"{nearest_sim:.3f} similarity")
        with col2:
            second_name, second_sim = report["second_nearest"]
            st.metric(f"Second nearest: {second_name}", f"{second_sim:.3f} similarity")

        st.write(f"Cosine distance from Human profile: **{report['human_distance']:.3f}**")

        st.subheader("Top divergences from human writing")
        for name, delta, note in report["divergences"]:
            st.write(f"- **{name}** ({delta:+.3f}): {note}")

    with st.expander("Full feature breakdown (all 30 features)"):
        rows = []
        for name in profiles.FEATURE_NAMES:
            your_score = results["normalised"].get(name)
            human_mean = profiles.HUMAN[name]
            ai_avg_mean = profiles.AI_AVG[name]
            delta = your_score - human_mean if your_score is not None else None
            rows.append(
                {
                    "Feature": name,
                    "Your score": "Not scored" if your_score is None else round(your_score, 3),
                    "Human mean": round(human_mean, 3),
                    "AI avg mean": round(ai_avg_mean, 3),
                    "Delta vs. Human": "--" if delta is None else round(delta, 3),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)

    missing = normaliser.count_valid(results["normalised"])
    total = len(profiles.FEATURE_NAMES)
    if missing < total:
        st.caption(
            f"{total - missing} feature(s) could not be scored and were excluded from "
            "similarity calculations."
        )

# --- 6. Footer -----------------------------------------------------------------------------

st.divider()
st.caption("Citation: Russell, J. et al. (2026). StoryScope. arXiv:2604.03136")
st.caption(
    "Reference profiles are approximated from published aggregate statistics, not the "
    "paper's trained classifier weights."
)
