import math

from modules import profiles, visualiser


def test_placement_identical_to_claude_lands_nearest_claude_within_ai_zone():
    position, sims = visualiser.place_manuscript(profiles.CLAUDE)
    assert max(sims, key=sims.get) == "Claude"
    assert visualiser.zone_of(position) == "AI zone"


def test_placement_equidistant_from_all_five_lands_near_ai_cluster_centre():
    equal_sims = {name: 0.8 for name in profiles.LLM_PROFILES}
    position = visualiser._placement_from_similarities(equal_sims)
    dist = math.hypot(
        position[0] - profiles.AI_ZONE_CENTRE[0], position[1] - profiles.AI_ZONE_CENTRE[1]
    )
    assert dist < 10


def test_placement_uniformly_low_similarity_lands_outside_ai_zone():
    low_sims = {name: 0.1 for name in profiles.LLM_PROFILES}
    position = visualiser._placement_from_similarities(low_sims)
    assert visualiser.zone_of(position) != "AI zone"


def test_fallback_direction_used_when_centroid_equals_ai_zone_centre(monkeypatch):
    # Two synthetic points that average out to exactly profiles.AI_ZONE_CENTRE (38, 26).
    monkeypatch.setitem(profiles.LLM_MAP_COORDS, "A", (30.0, 26.0))
    monkeypatch.setitem(profiles.LLM_MAP_COORDS, "B", (46.0, 26.0))
    sims = {"A": 0.5, "B": 0.5}

    position = visualiser._placement_from_similarities(sims)

    ai_x, ai_y = profiles.AI_ZONE_CENTRE
    hx, hy = profiles.HUMAN_ZONE_CENTRE
    to_position = (position[0] - ai_x, position[1] - ai_y)
    to_human = (hx - ai_x, hy - ai_y)
    # Cross product ~0 means the placement lies on the AI-centre -> Human-centre ray.
    cross = to_position[0] * to_human[1] - to_position[1] * to_human[0]
    assert abs(cross) < 1e-6
    assert to_position[0] * to_human[0] + to_position[1] * to_human[1] > 0  # same direction


def test_final_coordinates_clamped_to_0_100(monkeypatch):
    monkeypatch.setitem(profiles.LLM_MAP_COORDS, "Far", (95.0, 95.0))
    position = visualiser._placement_from_similarities({"Far": 0.0})
    assert 0.0 <= position[0] <= 100.0
    assert 0.0 <= position[1] <= 100.0
    assert position[0] == 100.0 or position[1] == 100.0  # pushed hard toward the corner


def test_is_sufficient_false_blocks_map_generation():
    insufficient = {name: None for name in profiles.FEATURE_NAMES}
    xy, sims = visualiser.place_manuscript(profiles.CLAUDE)
    result = visualiser.similarity_map(insufficient, "Test Story", sims, xy)
    assert result is None
