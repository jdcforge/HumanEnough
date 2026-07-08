"""Deterministic scoring: 15 raw feature outputs from spaCy + lexicon matching.

No semantic interpretation -- every feature here is a measurable count, density, or
structural pattern. See docs/architecture.md > Feature Assignment for the full table and the
`Dialogue Ratio` context-only caveat (14 of these 15 outputs feed the 30-feature profile
vector; `Dialogue Ratio` is passed to llm_scorer.py as context only).
"""

import json
import re
import time
from collections import Counter
from pathlib import Path

from modules import preprocessor
from modules.logging_config import get_logger
from modules.preprocessor import PreprocessResult

LEXICON_DIR = Path(__file__).resolve().parent.parent / "lexicons"

_lexicons: dict | None = None
logger = get_logger("deterministic")


class DeterministicScoringError(Exception):
    """Raised for any deterministic-scoring failure. Safe to show directly to the user."""


def _get_nlp():
    # Reuses preprocessor's module-level singleton so the ~500MB en_core_web_lg model is
    # loaded exactly once per process, not once per module that happens to need spaCy.
    try:
        return preprocessor._get_nlp()
    except preprocessor.PreprocessError as exc:
        raise DeterministicScoringError(str(exc)) from exc


def _load_lexicons() -> dict:
    global _lexicons
    if _lexicons is None:
        with open(LEXICON_DIR / "sensory.json", encoding="utf-8") as f:
            sensory = json.load(f)
        with open(LEXICON_DIR / "body_sensation.json", encoding="utf-8") as f:
            body_sensation = json.load(f)
        with open(LEXICON_DIR / "causal.json", encoding="utf-8") as f:
            causal = json.load(f)
        with open(LEXICON_DIR / "temporal.json", encoding="utf-8") as f:
            temporal = json.load(f)
        _lexicons = {
            "sensory": sensory,
            "body_sensation": body_sensation,
            "causal": causal,
            "temporal": temporal,
        }
    return _lexicons


def _compile_pattern(terms: list[str]) -> re.Pattern:
    # Longest terms first so multi-word phrases match before their sub-strings would.
    escaped = sorted((re.escape(t) for t in terms), key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)


_pattern_cache: dict[str, re.Pattern] = {}


def _match_count(text: str, terms: list[str], cache_key: str) -> int:
    if cache_key not in _pattern_cache:
        _pattern_cache[cache_key] = _compile_pattern(terms)
    return len(_pattern_cache[cache_key].findall(text))


def _word_count(text: str) -> int:
    return max(len(text.split()), 1)  # Avoid division by zero on empty segments.


def _bin(value: float, thresholds: tuple[float, ...]) -> int:
    """Map a value to an ordinal 1..len(thresholds)+1 using ascending thresholds."""
    for i, t in enumerate(thresholds, start=1):
        if value < t:
            return i
    return len(thresholds) + 1


def _pluperfect_density(doc) -> float:
    """'had' (VBD, lemma 'have') immediately followed by a past participle (VBN)."""
    count = 0
    tokens = list(doc)
    for i, token in enumerate(tokens[:-1]):
        if token.lemma_ == "have" and token.tag_ == "VBD" and tokens[i + 1].tag_ == "VBN":
            count += 1
    return count / _word_count(doc.text)


# --- Individual feature scorers -------------------------------------------------------


def _direct_reader_address(narration: str) -> float:
    pronouns = ["you", "your", "yours", "yourself"]
    count = _match_count(narration, pronouns, "2nd_person_pronouns")
    return count / _word_count(narration)


def _fourth_wall_permeability(narration: str, direct_address_density: float) -> int:
    phrases = ["dear reader", "the reader", "gentle reader", "my reader"]
    phrase_count = _match_count(narration, phrases, "reader_address_phrases")
    combined = direct_address_density + (phrase_count * 3 / _word_count(narration))
    # Thresholds are a documented approximation (see docs/architecture.md > Known Heuristic
    # Limitations) -- there is no exact binning formula given in the source paper.
    bin_value = _bin(combined, (0.0005, 0.002, 0.006))
    if phrase_count > 0:
        bin_value = max(bin_value, 3)
    return bin_value


def _dialogue_ratio(dialogue: str, full_text: str) -> int:
    ratio = _word_count(dialogue) / _word_count(full_text) if dialogue.strip() else 0.0
    return _bin(ratio, (0.05, 0.15, 0.30, 0.50))


def _chronological_discontinuity(full_doc) -> int:
    lexicons = _load_lexicons()
    temporal_density = _match_count(full_doc.text, lexicons["temporal"], "temporal") / _word_count(
        full_doc.text
    )
    pluperfect = _pluperfect_density(full_doc)
    combined = temporal_density + pluperfect
    return _bin(combined, (0.005, 0.015, 0.035, 0.07))


def _anachrony_intensity(full_doc) -> int:
    lexicons = _load_lexicons()
    temporal_density = _match_count(full_doc.text, lexicons["temporal"], "temporal") / _word_count(
        full_doc.text
    )
    pluperfect = _pluperfect_density(full_doc)
    combined = (pluperfect * 2) + temporal_density
    return _bin(combined, (0.006, 0.02, 0.05, 0.1))


def _nonlinear_disclosure_framing(full_text: str) -> int:
    lexicons = _load_lexicons()
    pattern = _pattern_cache.get("temporal") or _compile_pattern(lexicons["temporal"])
    _pattern_cache.setdefault("temporal", pattern)
    matches = list(pattern.finditer(full_text))
    if not matches or len(full_text) == 0:
        return 1
    weights = [1 - (m.start() / len(full_text)) for m in matches]
    score = sum(weights) / _word_count(full_text) * 100
    return _bin(score, (0.5, 1.5, 3.5, 7.0))


def _location_variety(full_doc) -> int:
    locations = {
        ent.text.lower() for ent in full_doc.ents if ent.label_ in ("GPE", "LOC")
    }
    return _bin(len(locations), (2, 4, 7))


def _named_intertextuality(full_doc, named_characters: list[str]) -> int:
    named_set = set(named_characters)
    work_of_art_count = sum(1 for ent in full_doc.ents if ent.label_ == "WORK_OF_ART")
    external_person_count = sum(
        1 for ent in full_doc.ents if ent.label_ == "PERSON" and ent.text not in named_set
    )
    return 1 if (work_of_art_count + external_person_count) >= 1 else 0


def _olfactory_imagery(full_text: str) -> int:
    lexicons = _load_lexicons()
    density = _match_count(full_text, lexicons["sensory"]["olfactory"], "olfactory") / _word_count(
        full_text
    )
    return 1 if density >= 0.0005 else 0


def _sensory_density(full_text: str) -> int:
    lexicons = _load_lexicons()["sensory"]
    total = sum(
        _match_count(full_text, terms, f"sensory_{name}") for name, terms in lexicons.items()
    )
    density = total / _word_count(full_text)
    return _bin(density, (0.01, 0.02, 0.035, 0.055))


def _embodied_emotion_expression(narration: str) -> int:
    lexicons = _load_lexicons()
    density = _match_count(
        narration, lexicons["body_sensation"], "body_sensation"
    ) / _word_count(narration)
    return 1 if density >= 0.006 else 0


def _causal_chain_continuity(full_text: str) -> int:
    lexicons = _load_lexicons()
    density = _match_count(full_text, lexicons["causal"], "causal") / _word_count(full_text)
    # High density = high continuity (the paper's "inversion" note just clarifies this
    # is the natural direction, not a formula inversion).
    return _bin(density, (0.003, 0.008, 0.016, 0.03))


def _protagonist_driven_resolution(final_doc, protagonist: str | None) -> int:
    if protagonist is None:
        return 0
    person_token_index = {
        i: ent.text
        for ent in final_doc.ents
        if ent.label_ == "PERSON"
        for i in range(ent.start, ent.end)
    }
    for token in final_doc:
        if token.dep_ in ("nsubj", "nsubjpass") and token.head.pos_ == "VERB":
            name = person_token_index.get(token.i)
            if name == protagonist or token.pos_ == "PRON":
                return 1
    return 0


_HEDGE_TERMS = [
    "perhaps", "seemed", "seemed to", "might", "may have", "as if", "as though",
    "it seemed", "apparently", "possibly", "maybe", "could have been", "appeared to",
]


def _moral_ambivalence(narration_doc, protagonist: str | None) -> int:
    if protagonist is None:
        return 0
    for sent in narration_doc.sents:
        sent_text = sent.text
        has_hedge = _match_count(sent_text, _HEDGE_TERMS, "hedge_terms") > 0
        has_protagonist = protagonist in sent_text or any(
            tok.pos_ == "PRON" for tok in sent
        )
        if has_hedge and has_protagonist:
            return 1
    return 0


def _no_subplots(full_text: str, named_characters: list[str], protagonist: str | None) -> int:
    if len(full_text) == 0:
        return 1
    first_half = full_text[: int(len(full_text) * 0.5)]
    final_20 = full_text[int(len(full_text) * 0.8) :]
    for name in named_characters:
        if name == protagonist:
            continue
        if name in first_half and name not in final_20:
            return 0  # A secondary character thread was dropped -- a subplot existed.
    return 1


# --- Public API -------------------------------------------------------------------------


def score(preprocessed: PreprocessResult) -> dict[str, float]:
    """Returns raw scores for the 15 deterministic features (14 profile + Dialogue Ratio,
    which is context-only -- see the module docstring and docs/architecture.md)."""
    started = time.perf_counter()
    nlp = _get_nlp()

    full_doc = nlp(preprocessed.full_text)
    narration_doc = nlp(preprocessed.narration)
    final_doc = nlp(preprocessed.final_segment)

    direct_address_density = _direct_reader_address(preprocessed.narration)

    result = {
        "Direct Reader Address": direct_address_density,
        "Fourth-Wall Permeability": _fourth_wall_permeability(
            preprocessed.narration, direct_address_density
        ),
        "Dialogue Ratio": _dialogue_ratio(preprocessed.dialogue, preprocessed.full_text),
        "Chronological Discontinuity": _chronological_discontinuity(full_doc),
        "Anachrony Intensity": _anachrony_intensity(full_doc),
        "Nonlinear Disclosure Framing": _nonlinear_disclosure_framing(preprocessed.full_text),
        "Location Variety": _location_variety(full_doc),
        "Named Intertextuality": _named_intertextuality(full_doc, preprocessed.named_characters),
        "Olfactory Imagery": _olfactory_imagery(preprocessed.full_text),
        "Sensory Density": _sensory_density(preprocessed.full_text),
        "Embodied Emotion Expression": _embodied_emotion_expression(preprocessed.narration),
        "Causal Chain Continuity": _causal_chain_continuity(preprocessed.full_text),
        "Protagonist-Driven Resolution": _protagonist_driven_resolution(
            final_doc, preprocessed.protagonist
        ),
        "Moral Ambivalence": _moral_ambivalence(narration_doc, preprocessed.protagonist),
        "No Subplots": _no_subplots(
            preprocessed.full_text, preprocessed.named_characters, preprocessed.protagonist
        ),
    }

    # Feature values are numbers, not text -- safe to log in full (see logging_config.py).
    elapsed = time.perf_counter() - started
    logger.info("Deterministic scoring complete in %.3fs: %s", elapsed, result)
    return result


if __name__ == "__main__":
    from modules.preprocessor import preprocess

    sample = (
        'Years earlier, Alice had walked this same road, though she had never told anyone. '
        '"I have been waiting for you," she said, her voice trembling as if she doubted herself. '
        "The scent of rain drifted through the open window while thunder rolled over the hills. "
        "Because the storm had passed, Bob decided to leave the old house behind, and so, "
        "in the end, Alice chose to stay behind and rebuild what remained. "
        '"You always know when to arrive," Bob said, before he vanished into the fog and was '
        "never mentioned again. Alice looked at the mountains in the distance, then at the "
        "river below, then at the village beyond the hills."
    )
    result = score(preprocess(sample))
    assert set(result.keys()) == {
        "Direct Reader Address", "Fourth-Wall Permeability", "Dialogue Ratio",
        "Chronological Discontinuity", "Anachrony Intensity", "Nonlinear Disclosure Framing",
        "Location Variety", "Named Intertextuality", "Olfactory Imagery", "Sensory Density",
        "Embodied Emotion Expression", "Causal Chain Continuity",
        "Protagonist-Driven Resolution", "Moral Ambivalence", "No Subplots",
    }
    print("OK --", result)
