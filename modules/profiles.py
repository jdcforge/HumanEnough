"""Reference profiles and feature metadata for the 30 core StoryScope narrative features.

All values are transcribed from the "Reference Profile Values" table in docs/architecture.md,
which in turn derives from Table 15 (HUMAN/AI_AVG means) and Section 5 + Table 16
(per-model fingerprint deltas) of the StoryScope paper (Russell et al., 2026).

Feature order matches the paper's table: 20 AI-elevated features first, then 10
human-elevated features. "Moral/Philosophical Weight" (index 1) was added to close a gap
in the original architecture doc's Feature Assignment tables — see docs/architecture.md.
"""

# Columns per feature: (HUMAN, AI_AVG, CLAUDE, GPT, GEMINI, DEEPSEEK, KIMI)
_PROFILE_TABLE: dict[str, tuple[float, float, float, float, float, float, float]] = {
    # --- AI-elevated (20) ---
    "Thematic Explicitness":            (0.656, 0.788, 0.750, 0.790, 0.800, 0.785, 0.788),
    "Moral/Philosophical Weight":       (0.652, 0.736, 0.710, 0.740, 0.745, 0.735, 0.736),
    "Thematic Unity":                   (0.882, 0.948, 0.940, 0.945, 0.965, 0.948, 0.948),
    "Narrator Thematic Commentary":     (0.520, 0.770, 0.780, 0.765, 0.775, 0.770, 0.770),
    "Dialogue as Philosophy":           (0.340, 0.590, 0.600, 0.620, 0.575, 0.590, 0.590),
    "Vague Intertextual Allusion":      (0.500, 0.720, 0.730, 0.705, 0.725, 0.720, 0.720),
    "Embodied Emotion Expression":      (0.380, 0.810, 0.820, 0.815, 0.805, 0.810, 0.810),
    "Setting as Psychological Mirror":  (0.716, 0.814, 0.810, 0.810, 0.830, 0.812, 0.814),
    "Environmental Emphasis":           (0.566, 0.642, 0.630, 0.638, 0.660, 0.642, 0.642),
    "Olfactory Imagery":                (0.570, 0.820, 0.800, 0.825, 0.830, 0.818, 0.820),
    "Sensory Density":                  (0.732, 0.786, 0.780, 0.790, 0.795, 0.785, 0.786),
    "Interior Access Depth":            (0.734, 0.786, 0.790, 0.785, 0.788, 0.786, 0.786),
    "Causal Chain Continuity":          (0.784, 0.840, 0.800, 0.835, 0.850, 0.840, 0.840),
    "Spatial Granularity":              (0.568, 0.633, 0.625, 0.630, 0.640, 0.635, 0.633),
    "Protagonist-Driven Resolution":    (0.460, 0.690, 0.670, 0.695, 0.700, 0.690, 0.690),
    "External Character Introduction":  (0.300, 0.520, 0.510, 0.525, 0.530, 0.520, 0.520),
    "No Subplots":                      (0.570, 0.790, 0.800, 0.775, 0.810, 0.790, 0.790),
    "Internal Resolution Mode":         (0.270, 0.470, 0.480, 0.440, 0.475, 0.470, 0.470),
    "Clear Opening Setting":            (0.530, 0.583, 0.575, 0.578, 0.610, 0.620, 0.583),
    "Pre-Threat Character Investment":  (0.552, 0.598, 0.590, 0.598, 0.600, 0.625, 0.598),
    # --- Human-elevated (10) ---
    "Named Intertextuality":            (0.470, 0.240, 0.220, 0.260, 0.235, 0.240, 0.240),
    "Balanced Intertextual Mix":        (0.370, 0.160, 0.150, 0.175, 0.155, 0.160, 0.160),
    "Fourth-Wall Permeability":         (0.168, 0.098, 0.090, 0.108, 0.095, 0.098, 0.098),
    "Direct Reader Address":            (0.093, 0.023, 0.020, 0.028, 0.022, 0.023, 0.023),
    "Revelation Recontextualisation":   (0.656, 0.590, 0.620, 0.580, 0.585, 0.590, 0.590),
    "Chronological Discontinuity":      (0.480, 0.424, 0.390, 0.460, 0.415, 0.424, 0.424),
    "Nonlinear Disclosure Framing":     (0.392, 0.336, 0.310, 0.360, 0.330, 0.336, 0.336),
    "Anachrony Intensity":              (0.516, 0.462, 0.420, 0.490, 0.455, 0.462, 0.462),
    "Location Variety":                 (0.335, 0.270, 0.260, 0.295, 0.265, 0.270, 0.270),
    "Moral Ambivalence":                (0.590, 0.380, 0.360, 0.420, 0.370, 0.378, 0.380),
}

FEATURE_NAMES: list[str] = list(_PROFILE_TABLE.keys())

AI_ELEVATED: list[str] = FEATURE_NAMES[:20]
HUMAN_ELEVATED: list[str] = FEATURE_NAMES[20:]

HUMAN: dict[str, float] = {name: vals[0] for name, vals in _PROFILE_TABLE.items()}
AI_AVG: dict[str, float] = {name: vals[1] for name, vals in _PROFILE_TABLE.items()}
CLAUDE: dict[str, float] = {name: vals[2] for name, vals in _PROFILE_TABLE.items()}
GPT: dict[str, float] = {name: vals[3] for name, vals in _PROFILE_TABLE.items()}
GEMINI: dict[str, float] = {name: vals[4] for name, vals in _PROFILE_TABLE.items()}
DEEPSEEK: dict[str, float] = {name: vals[5] for name, vals in _PROFILE_TABLE.items()}
KIMI: dict[str, float] = {name: vals[6] for name, vals in _PROFILE_TABLE.items()}

# The five profiles that drive manuscript placement (HUMAN and AI_AVG are excluded --
# they are used for scoring comparison and the text report only, per architecture spec).
LLM_PROFILES: dict[str, dict[str, float]] = {
    "Claude": CLAUDE,
    "GPT": GPT,
    "Gemini": GEMINI,
    "DeepSeek": DEEPSEEK,
    "Kimi": KIMI,
}

# --- Scale types, used by normaliser.py to pick the correct divisor ---
# "scale_1_5" / "ordinal_1_4" / "ordinal_1_3" / "binary" / "prevalence"
FEATURE_SCALE_TYPES: dict[str, str] = {
    "Thematic Explicitness": "scale_1_5",
    "Moral/Philosophical Weight": "scale_1_5",
    "Thematic Unity": "scale_1_5",
    "Narrator Thematic Commentary": "binary",
    "Dialogue as Philosophy": "binary",
    "Vague Intertextual Allusion": "binary",
    "Embodied Emotion Expression": "binary",
    "Setting as Psychological Mirror": "scale_1_5",
    "Environmental Emphasis": "scale_1_5",
    "Olfactory Imagery": "binary",
    "Sensory Density": "scale_1_5",
    "Interior Access Depth": "scale_1_5",
    "Causal Chain Continuity": "scale_1_5",
    "Spatial Granularity": "ordinal_1_4",
    "Protagonist-Driven Resolution": "binary",
    "External Character Introduction": "binary",
    "No Subplots": "binary",
    "Internal Resolution Mode": "binary",
    "Clear Opening Setting": "ordinal_1_4",
    "Pre-Threat Character Investment": "scale_1_5",
    "Named Intertextuality": "binary",
    "Balanced Intertextual Mix": "binary",
    "Fourth-Wall Permeability": "ordinal_1_4",
    "Direct Reader Address": "prevalence",
    "Revelation Recontextualisation": "scale_1_5",
    "Chronological Discontinuity": "scale_1_5",
    "Nonlinear Disclosure Framing": "scale_1_5",
    "Anachrony Intensity": "scale_1_5",
    "Location Variety": "ordinal_1_4",
    "Moral Ambivalence": "binary",
}

SCALE_MAXIMA: dict[str, float] = {
    "scale_1_5": 5.0,
    "ordinal_1_4": 4.0,
    "ordinal_1_3": 3.0,
    "binary": 1.0,
    "prevalence": 1.0,
}

FEATURE_DESCRIPTIONS: dict[str, str] = {
    "Thematic Explicitness": "How explicitly the story articulates its themes or morals.",
    "Moral/Philosophical Weight": "How heavily the story foregrounds moral or philosophical questions.",
    "Thematic Unity": "How much subplots and flourishes serve a central thematic concern.",
    "Narrator Thematic Commentary": "Whether the narrator explicitly comments on themes beyond characters' perspectives.",
    "Dialogue as Philosophy": "Whether dialogue primarily serves philosophical debate rather than plot or character.",
    "Vague Intertextual Allusion": "Whether references to other works are vague/implicit rather than specific and named.",
    "Embodied Emotion Expression": "How often emotion is conveyed through physical sensation rather than named directly.",
    "Setting as Psychological Mirror": "How much the physical environment mirrors characters' inner states.",
    "Environmental Emphasis": "How prominent the natural environment or ecology is in the narrative.",
    "Olfactory Imagery": "How much smell-based imagery the story uses.",
    "Sensory Density": "How dense sensory description is across the narrative.",
    "Interior Access Depth": "How deep into characters' inner life the narration goes.",
    "Causal Chain Continuity": "How continuous the causal chain from inciting incident to ending is.",
    "Spatial Granularity": "How fine-grained the story's depiction of physical space is.",
    "Protagonist-Driven Resolution": "Whether the resolution is driven by the protagonist's choices rather than external events.",
    "External Character Introduction": "Whether central characters are primarily introduced via external physical description.",
    "No Subplots": "Whether the story has no secondary character threads.",
    "Internal Resolution Mode": "Whether the story resolves through internal understanding/acceptance rather than external action.",
    "Clear Opening Setting": "How clearly the opening grounds the reader in a specific physical setting.",
    "Pre-Threat Character Investment": "How much the story builds reader investment before major jeopardy.",
    "Named Intertextuality": "Whether the story makes specific, named references to other works.",
    "Balanced Intertextual Mix": "Whether the story balances explicit and implicit cultural references evenly.",
    "Fourth-Wall Permeability": "How much the story breaks the boundary between story-world and reader.",
    "Direct Reader Address": "How often the narration directly addresses the reader.",
    "Revelation Recontextualisation": "How extensively a late revelation forces reinterpretation of earlier scenes.",
    "Chronological Discontinuity": "How often the narrative jumps across time.",
    "Nonlinear Disclosure Framing": "How much the story uses time jumps to stage revelations.",
    "Anachrony Intensity": "How heavily the narrative relies on flashbacks or flash-forwards.",
    "Location Variety": "How many distinct physical locations the story inhabits.",
    "Moral Ambivalence": "How morally ambiguous the protagonist's choices are framed as being.",
}

# --- Colours, from the dataviz skill's validated reference categorical palette ---
# Fixed slot order (never cycled): blue, aqua, yellow, green, violet, red, magenta, orange.
PROFILE_COLORS: dict[str, str] = {
    "Claude": "#2a78d6",       # slot 1 blue
    "GPT": "#1baf7a",          # slot 2 aqua
    "Gemini": "#eda100",       # slot 3 yellow
    "DeepSeek": "#008300",     # slot 4 green
    "Kimi": "#4a3aa7",         # slot 5 violet
    "Manuscript": "#e34948",   # slot 6 red -- highlight/"you are here" marker
    "Human": "#e87ba4",        # slot 7 magenta -- reference only, no map coordinate
    "AI_AVG": "#eb6834",       # slot 8 orange -- reference only, no map coordinate
}
PROFILE_COLORS_DARK: dict[str, str] = {
    "Claude": "#3987e5",
    "GPT": "#199e70",
    "Gemini": "#c98500",
    "DeepSeek": "#008300",
    "Kimi": "#9085e9",
    "Manuscript": "#e66767",
    "Human": "#d55181",
    "AI_AVG": "#d95926",
}

# --- Similarity Map geometry (Section: visualiser.py in docs/architecture.md) ---
LLM_MAP_COORDS: dict[str, tuple[float, float]] = {
    "Claude": (28, 38),
    "GPT": (38, 22),
    "Gemini": (44, 24),
    "DeepSeek": (46, 26),
    "Kimi": (40, 20),
}
AI_ZONE_CENTRE: tuple[float, float] = (38, 26)
AI_ZONE_RADIUS: float = 20.0
HUMAN_ZONE_CENTRE: tuple[float, float] = (68, 72)
HUMAN_ZONE_RADIUS: float = 30.0


if __name__ == "__main__":
    assert len(FEATURE_NAMES) == 30
    assert len(AI_ELEVATED) == 20
    assert len(HUMAN_ELEVATED) == 10
    assert set(FEATURE_SCALE_TYPES) == set(FEATURE_NAMES)
    assert set(FEATURE_DESCRIPTIONS) == set(FEATURE_NAMES)
    for profile in (HUMAN, AI_AVG, CLAUDE, GPT, GEMINI, DEEPSEEK, KIMI):
        assert set(profile) == set(FEATURE_NAMES)
        assert all(0.0 <= v <= 1.0 for v in profile.values())
    print(f"OK -- {len(FEATURE_NAMES)} features, {len(LLM_PROFILES)} LLM profiles.")
