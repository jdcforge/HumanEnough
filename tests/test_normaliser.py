import pytest

from modules import normaliser, profiles


def test_all_30_features_normalise_to_0_1_given_valid_raw_inputs():
    raw = {
        name: profiles.SCALE_MAXIMA[profiles.FEATURE_SCALE_TYPES[name]]
        for name in profiles.FEATURE_NAMES
    }
    normalised = normaliser.normalise(raw)
    assert set(normalised) == set(profiles.FEATURE_NAMES)
    assert all(v == 1.0 for v in normalised.values())


def test_scale_1_5_normalises_correctly():
    normalised = normaliser.normalise({"Thematic Explicitness": 1})
    assert normalised["Thematic Explicitness"] == pytest.approx(0.2)
    normalised = normaliser.normalise({"Thematic Explicitness": 5})
    assert normalised["Thematic Explicitness"] == pytest.approx(1.0)


def test_binary_features_pass_through_unchanged():
    normalised = normaliser.normalise({"Moral Ambivalence": 0, "No Subplots": 1})
    assert normalised["Moral Ambivalence"] == 0.0
    assert normalised["No Subplots"] == 1.0


def test_none_values_pass_through_unchanged():
    normalised = normaliser.normalise({"Thematic Explicitness": None})
    assert normalised["Thematic Explicitness"] is None


def test_count_valid_returns_correct_count_for_mixed_none_and_float():
    scores = {name: 0.5 for name in profiles.FEATURE_NAMES}
    for name in profiles.FEATURE_NAMES[:5]:
        scores[name] = None
    assert normaliser.count_valid(scores) == 25


def test_is_sufficient_boundary_at_24_of_30():
    scores = {name: 0.5 for name in profiles.FEATURE_NAMES}
    for name in profiles.FEATURE_NAMES[:6]:
        scores[name] = None
    assert normaliser.count_valid(scores) == 24
    assert normaliser.is_sufficient(scores) is True

    scores[profiles.FEATURE_NAMES[6]] = None
    assert normaliser.count_valid(scores) == 23
    assert normaliser.is_sufficient(scores) is False


def test_cosine_similarity_computed_over_subset_when_some_features_are_none():
    partial = {name: profiles.CLAUDE[name] for name in profiles.FEATURE_NAMES[:10]}
    for name in profiles.FEATURE_NAMES[10:]:
        partial[name] = None
    sim = normaliser.similarity(partial, profiles.CLAUDE)
    assert sim > 0.999  # Identical on the 10 shared, non-None dimensions.


def test_cosine_similarity_of_identical_vectors_is_1():
    assert normaliser.similarity(profiles.CLAUDE, profiles.CLAUDE) == pytest.approx(1.0)


def test_normalise_raises_on_unrecognised_key():
    with pytest.raises(ValueError):
        normaliser.normalise({"Dialogue Ratio": 3})
