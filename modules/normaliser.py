"""Raw scores -> [0,1], cosine similarity, and divergence reporting.

See docs/architecture.md > normaliser.py for the None-handling and is_sufficient() contract, and
docs/architecture.md > Feature Assignment for why `normalise()` must reject unrecognised keys
(the guard against a stray context-only key such as `Dialogue Ratio` leaking in).
"""

import numpy as np

from modules import profiles
from modules.logging_config import get_logger

DEFAULT_SUFFICIENCY_THRESHOLD = 24

logger = get_logger("normaliser")


def normalise(raw_scores: dict[str, float | None]) -> dict[str, float | None]:
    """Normalise scores to [0, 1]. None values pass through unchanged.

    Raises ValueError if raw_scores contains a key not in profiles.FEATURE_NAMES.
    """
    unknown = set(raw_scores) - set(profiles.FEATURE_NAMES)
    if unknown:
        raise ValueError(
            f"normalise() received unrecognised feature key(s): {sorted(unknown)}. "
            "Only the 30 features in profiles.FEATURE_NAMES may be passed here -- strip "
            "context-only outputs (e.g. 'Dialogue Ratio') before calling normalise()."
        )
    normalised: dict[str, float | None] = {}
    for name, raw in raw_scores.items():
        if raw is None:
            normalised[name] = None
            continue
        scale_type = profiles.FEATURE_SCALE_TYPES[name]
        maximum = profiles.SCALE_MAXIMA[scale_type]
        normalised[name] = raw / maximum
    logger.info("Normalised %d/%d features", count_valid(normalised), len(normalised))
    return normalised


def count_valid(normalised_scores: dict) -> int:
    """Return count of non-None scores."""
    return sum(1 for v in normalised_scores.values() if v is not None)


def is_sufficient(normalised_scores: dict, threshold: int = DEFAULT_SUFFICIENCY_THRESHOLD) -> bool:
    """Return True if at least `threshold` of 30 features are non-None.

    Default threshold: 24/30. Below this, map generation is blocked (see visualiser.py).
    """
    valid = count_valid(normalised_scores)
    sufficient = valid >= threshold
    if not sufficient:
        logger.warning("Insufficient scores for map generation: %d/%d (threshold %d)",
                        valid, len(normalised_scores), threshold)
    return sufficient


def similarity(your_scores: dict, profile: dict) -> float:
    """Cosine similarity between a manuscript's normalised scores and a reference profile.

    Computed only over dimensions that are non-None in your_scores and present in profile --
    missing features are excluded, not treated as zero.
    """
    shared_names = [
        name for name, value in your_scores.items() if value is not None and name in profile
    ]
    if not shared_names:
        return 0.0
    a = np.array([your_scores[name] for name in shared_names])
    b = np.array([profile[name] for name in shared_names])
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def rank_profiles(your_scores: dict) -> list[tuple[str, float]]:
    """Return the five LLM profiles ranked by cosine similarity, descending.

    HUMAN and AI_AVG are excluded -- they are used for reporting only, not placement.
    """
    ranked = [
        (name, similarity(your_scores, profile))
        for name, profile in profiles.LLM_PROFILES.items()
    ]
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked


_BASELINE_PROFILES = {"Human": profiles.HUMAN, "AI_AVG": profiles.AI_AVG}


def _plain_english_note(feature_name: str, delta: float, baseline: str) -> str:
    direction = "higher" if delta > 0 else "lower"
    elevated_side = "an AI-elevated" if feature_name in profiles.AI_ELEVATED else "a human-elevated"
    return (
        f"{direction.capitalize()} than the {baseline} baseline on {feature_name.lower()}, "
        f"{elevated_side} feature."
    )


def top_divergences(
    your_scores: dict, baseline: str = "Human", n: int = 6
) -> list[tuple[str, float, str]]:
    """Return the n features where the manuscript diverges most from the baseline.

    Baseline defaults to the HUMAN profile for text-report purposes.
    """
    baseline_profile = _BASELINE_PROFILES.get(baseline)
    if baseline_profile is None:
        raise ValueError(f"Unknown baseline: {baseline!r}. Expected one of {list(_BASELINE_PROFILES)}.")

    diffs: list[tuple[str, float, str]] = []
    for name in profiles.FEATURE_NAMES:
        your_val = your_scores.get(name)
        if your_val is None:
            continue
        delta = your_val - baseline_profile[name]
        diffs.append((name, delta, _plain_english_note(name, delta, baseline)))

    diffs.sort(key=lambda item: abs(item[1]), reverse=True)
    return diffs[:n]


if __name__ == "__main__":
    raw = {name: 1.0 for name in profiles.FEATURE_NAMES}  # arbitrary raw scores (all binary/1)
    for name in raw:
        raw[name] = 1 if profiles.FEATURE_SCALE_TYPES[name] == "binary" else profiles.SCALE_MAXIMA[
            profiles.FEATURE_SCALE_TYPES[name]
        ]
    normalised = normalise(raw)
    assert all(v == 1.0 for v in normalised.values())
    assert count_valid(normalised) == 30
    assert is_sufficient(normalised) is True

    normalised_missing = dict(normalised)
    for name in profiles.FEATURE_NAMES[:7]:
        normalised_missing[name] = None
    assert count_valid(normalised_missing) == 23
    assert is_sufficient(normalised_missing) is False

    assert similarity(profiles.CLAUDE, profiles.CLAUDE) > 0.999

    ranked = rank_profiles(profiles.CLAUDE)
    assert ranked[0][0] == "Claude"

    divergences = top_divergences(profiles.CLAUDE, baseline="Human", n=3)
    assert len(divergences) == 3

    try:
        normalise({"Dialogue Ratio": 3})
        raise AssertionError("expected ValueError for unrecognised key")
    except ValueError:
        pass

    print("OK --", ranked, "| top divergence:", divergences[0])
