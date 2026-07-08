"""Similarity Map (Plotly) + text report.

The map is a territory map, not a statistical projection -- it must never be described as a
classifier, embedding, latent space, UMAP, PCA, or evidence of authorship (docs/architecture.md).

`similarity_map()` and `text_report()` both need the manuscript's placement on the map, but
only `similarity_map()`'s spec signature accepts it as a parameter. `place_manuscript()` is
the shared, publicly-exposed engine behind both: app.py can call it once and pass the result
into `similarity_map()`, while `text_report()` calls it internally.
"""

import math

import numpy as np
import plotly.graph_objects as go

from modules import normaliser, profiles
from modules.logging_config import get_logger

logger = get_logger("visualiser")

REQUIRED_CAPTION = (
    "Entering the Human zone does not imply human authorship; it indicates the manuscript "
    "is comparatively dissimilar to known AI narrative profiles and lies within the region "
    "associated with human narrative variability."
)

_MAP_RANGE = (0, 100)
_ZONE_LABEL_COLOR = "#898781"  # dataviz skill's muted ink -- identical in light and dark.


# --- Placement engine ------------------------------------------------------------------


def _weighted_centroid(llm_similarities: dict[str, float]) -> tuple[float, float]:
    total_weight = sum(llm_similarities.values())
    if total_weight <= 0:
        weights = {name: 1.0 for name in llm_similarities}
        total_weight = len(weights)
    else:
        weights = llm_similarities
    cx = sum(weights[name] * profiles.LLM_MAP_COORDS[name][0] for name in weights) / total_weight
    cy = sum(weights[name] * profiles.LLM_MAP_COORDS[name][1] for name in weights) / total_weight
    return cx, cy


def _placement_from_similarities(llm_similarities: dict[str, float]) -> tuple[float, float]:
    """Pure geometry step, independent of how the similarities were computed -- lets tests
    exercise placement edge cases with hand-crafted similarity dicts."""
    centroid = _weighted_centroid(llm_similarities)

    mean_similarity = sum(llm_similarities.values()) / len(llm_similarities)
    repulsion_magnitude = (1 - mean_similarity) * 35

    ai_x, ai_y = profiles.AI_ZONE_CENTRE
    dx, dy = centroid[0] - ai_x, centroid[1] - ai_y
    norm = math.hypot(dx, dy)
    if norm < 1e-9:
        # Fallback: centroid exactly equals the AI zone centre -> direction toward Human zone.
        hx, hy = profiles.HUMAN_ZONE_CENTRE
        dx, dy = hx - ai_x, hy - ai_y
        norm = math.hypot(dx, dy)
    unit_x, unit_y = dx / norm, dy / norm

    px = centroid[0] + unit_x * repulsion_magnitude
    py = centroid[1] + unit_y * repulsion_magnitude
    px = max(_MAP_RANGE[0], min(_MAP_RANGE[1], px))
    py = max(_MAP_RANGE[0], min(_MAP_RANGE[1], py))
    return px, py


def place_manuscript(your_scores: dict) -> tuple[tuple[float, float], dict[str, float]]:
    """Returns (manuscript_xy, llm_similarities) for a normalised 30-feature score dict."""
    llm_similarities = dict(normaliser.rank_profiles(your_scores))
    position = _placement_from_similarities(llm_similarities)
    logger.info(
        "Manuscript placed at (%.1f, %.1f), zone=%s, similarities=%s",
        position[0], position[1], zone_of(position),
        {name: round(sim, 3) for name, sim in llm_similarities.items()},
    )
    return position, llm_similarities


def zone_of(position: tuple[float, float]) -> str:
    def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    if _dist(position, profiles.AI_ZONE_CENTRE) <= profiles.AI_ZONE_RADIUS:
        return "AI zone"
    if _dist(position, profiles.HUMAN_ZONE_CENTRE) <= profiles.HUMAN_ZONE_RADIUS:
        return "Human zone"
    return "Undetermined"


# --- Similarity Map (Plotly) ------------------------------------------------------------


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _add_gaussian_blob(
    fig: go.Figure, centre: tuple[float, float], radius: float, hex_color: str,
    n_rings: int = 10, max_opacity: float = 0.30,
) -> None:
    """Simulate a soft radial-gradient blob by stacking concentric semi-transparent rings,
    largest (faintest) first so opacity builds toward the centre."""
    r, g, b = _hex_to_rgb(hex_color)
    cx, cy = centre
    theta = np.linspace(0, 2 * np.pi, 72)
    for i in range(n_rings, 0, -1):
        frac = i / n_rings
        ring_radius = radius * frac
        opacity = max_opacity * math.exp(-3 * (frac**2))
        xs = cx + ring_radius * np.cos(theta)
        ys = cy + ring_radius * np.sin(theta)
        fig.add_trace(
            go.Scatter(
                x=xs, y=ys, mode="lines", fill="toself", line=dict(width=0),
                fillcolor=f"rgba({r},{g},{b},{opacity:.4f})",
                hoverinfo="skip", showlegend=False,
            )
        )


def similarity_map(
    your_scores: dict,
    story_title: str,
    llm_similarities: dict[str, float],
    manuscript_xy: tuple[float, float],
) -> go.Figure | None:
    """Returns None if the underlying score set is insufficient (fewer than 24/30 valid
    features) -- app.py should already have checked normaliser.is_sufficient() before
    calling this, but this is a defensive second check rather than trusting the caller."""
    if not normaliser.is_sufficient(your_scores):
        return None

    fig = go.Figure()

    # Zones -- fixed, never change between manuscripts. Tinted with the AI_AVG/Human
    # identity colours since the zones represent those groups in aggregate.
    _add_gaussian_blob(fig, profiles.AI_ZONE_CENTRE, profiles.AI_ZONE_RADIUS, profiles.PROFILE_COLORS["AI_AVG"])
    _add_gaussian_blob(fig, profiles.HUMAN_ZONE_CENTRE, profiles.HUMAN_ZONE_RADIUS, profiles.PROFILE_COLORS["Human"])
    fig.add_annotation(
        x=profiles.AI_ZONE_CENTRE[0], y=profiles.AI_ZONE_CENTRE[1], text="AI zone",
        showarrow=False, font=dict(size=12, color=_ZONE_LABEL_COLOR),
    )
    fig.add_annotation(
        x=profiles.HUMAN_ZONE_CENTRE[0], y=profiles.HUMAN_ZONE_CENTRE[1], text="Human zone",
        showarrow=False, font=dict(size=12, color=_ZONE_LABEL_COLOR),
    )

    # Nearest-neighbour connector line, drawn under the markers.
    nearest_name = max(llm_similarities, key=llm_similarities.get)
    nearest_xy = profiles.LLM_MAP_COORDS[nearest_name]
    fig.add_trace(
        go.Scatter(
            x=[manuscript_xy[0], nearest_xy[0]], y=[manuscript_xy[1], nearest_xy[1]],
            mode="lines", line=dict(width=1, color=_ZONE_LABEL_COLOR, dash="dot"),
            hoverinfo="skip", showlegend=False,
        )
    )

    # Fixed LLM reference points.
    for name, (x, y) in profiles.LLM_MAP_COORDS.items():
        sim = llm_similarities.get(name)
        hover = f"{name}<br>Cosine similarity: {sim:.3f}" if sim is not None else name
        fig.add_trace(
            go.Scatter(
                x=[x], y=[y], mode="markers+text", text=[name], textposition="top center",
                textfont=dict(size=11, color=_ZONE_LABEL_COLOR),
                marker=dict(size=12, color=profiles.PROFILE_COLORS[name], symbol="circle",
                            line=dict(width=1, color="rgba(255,255,255,0.6)")),
                hovertext=[hover], hoverinfo="text", name=name,
            )
        )

    # Manuscript marker -- distinct shape and colour from the LLM points.
    zone = zone_of(manuscript_xy)
    fig.add_trace(
        go.Scatter(
            x=[manuscript_xy[0]], y=[manuscript_xy[1]], mode="markers+text",
            text=[story_title], textposition="bottom center",
            textfont=dict(size=12, color=_ZONE_LABEL_COLOR),
            marker=dict(size=18, color=profiles.PROFILE_COLORS["Manuscript"], symbol="star",
                        line=dict(width=1, color="rgba(255,255,255,0.8)")),
            hovertext=[f"{story_title}<br>Zone: {zone}"], hoverinfo="text", name=story_title,
        )
    )

    fig.update_xaxes(visible=False, range=list(_MAP_RANGE), fixedrange=True)
    fig.update_yaxes(visible=False, range=list(_MAP_RANGE), fixedrange=True)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(font=dict(color=_ZONE_LABEL_COLOR)),
        margin=dict(l=10, r=10, t=10, b=10),
        height=520,
    )
    return fig


# --- Text report -------------------------------------------------------------------------


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
    ranked = normaliser.rank_profiles(your_scores)
    position, _ = place_manuscript(your_scores)

    report = {
        "nearest": ranked[0],
        "second_nearest": ranked[1],
        "zone": zone_of(position),
        "human_distance": 1 - normaliser.similarity(your_scores, profiles.HUMAN),
        "divergences": normaliser.top_divergences(your_scores, baseline="Human", n=6),
    }
    logger.info(
        "Text report generated: zone=%s, nearest=%s (%.3f), human_distance=%.3f",
        report["zone"], report["nearest"][0], report["nearest"][1], report["human_distance"],
    )
    return report


if __name__ == "__main__":
    # Edge case 1: identical to Claude's profile -> lands nearest Claude, within the AI zone.
    xy, sims = place_manuscript(profiles.CLAUDE)
    assert zone_of(xy) == "AI zone", zone_of(xy)
    assert max(sims, key=sims.get) == "Claude"

    # Edge case 2: equidistant from all five -> lands near the AI cluster centre.
    equal_sims = {name: 0.8 for name in profiles.LLM_PROFILES}
    xy2 = _placement_from_similarities(equal_sims)
    dist_to_ai_centre = math.hypot(xy2[0] - profiles.AI_ZONE_CENTRE[0], xy2[1] - profiles.AI_ZONE_CENTRE[1])
    assert dist_to_ai_centre < 10, dist_to_ai_centre

    # Edge case 3: uniformly low similarity -> pushed well clear of the AI cluster.
    low_sims = {name: 0.1 for name in profiles.LLM_PROFILES}
    xy3 = _placement_from_similarities(low_sims)
    assert zone_of(xy3) != "AI zone", zone_of(xy3)

    # Fallback direction: centroid exactly at the AI zone centre.
    fig = similarity_map(profiles.CLAUDE, "Test Story", sims, xy)
    assert fig is not None

    insufficient = {name: None for name in profiles.FEATURE_NAMES}
    assert similarity_map(insufficient, "Test", sims, xy) is None

    report = text_report(profiles.CLAUDE, "Test Story")
    assert report["nearest"][0] == "Claude"
    assert report["zone"] == "AI zone"
    assert len(report["divergences"]) == 6

    print("OK --", report["zone"], report["nearest"], "| human_distance:", round(report["human_distance"], 3))
