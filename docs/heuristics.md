# Deterministic Feature Heuristics

This document explains, in plain English, what each of the 15 raw outputs of
`modules/deterministic.py` actually measures, how it's implemented today, where it's known
to break, and what improving it would look like. It consolidates material that's otherwise
scattered across `architecture.md`'s feature tables and its "Known Heuristic Limitations"
section, with the actual implementation details layered in.

All of this is heuristic by design (see `architecture.md` -- the deterministic layer trades
precision for speed and zero API cost). Treat every score here as a structural proxy, not a
ground truth measurement. 14 of these 15 outputs feed the 30-feature profile vector;
**`Dialogue Ratio` is context-only** and is passed to `llm_scorer.py` as context rather than
scored directly (see `architecture.md` > Feature Assignment).

For reference, "narration" is everything outside quotation marks, "the final segment" is the
last 15% of the manuscript by character count, and lexicon matching throughout is
case-insensitive and whole-word (see `modules/preprocessor.py` and `docs/contributing.md`).

---

## Direct Reader Address

**What it measures:** How often the narration speaks to "you" -- the reader -- rather than
staying inside the story. Counted as the density of second-person pronouns (`you`, `your`,
`yours`, `yourself`) in narration only (dialogue is exempt, since a character saying "you"
to another character isn't addressing the reader).

**Failure modes:** Can't distinguish a narrator addressing the reader from a narrator
addressing a character in free indirect discourse, or dialogue that leaked into "narration"
because the preprocessor's quote-detection missed it (see the dialogue detection caveat in
`architecture.md` > Constraints and Assumptions). Second-person narrators (whole stories
written in "you") will produce enormous, meaningless density scores.

**What improving it would look like:** Restricting the count to sentences where the
addressee is genuinely the implied reader (via dependency parsing for a null/implied
subject) rather than any second-person pronoun at all.

## Fourth-Wall Permeability

**What it measures:** A broader signal than Direct Reader Address -- combines the same
second-person pronoun density with explicit reader-address phrases (`"dear reader"`,
`"the reader"`, `"gentle reader"`, `"my reader"`), weighting each phrase hit 3x a bare
pronoun hit, then bins the combined density into an ordinal 1-4 via fixed thresholds
(`0.0005`, `0.002`, `0.006`). If any explicit phrase is found at all, the bin is floored at 3
regardless of density.

**Failure modes:** The threshold constants and the "3x weight, floor at bin 3" rule are
hand-picked, not derived from the paper (which gives no exact binning formula) -- they were
chosen to feel reasonable on short test fixtures, not validated against a labeled corpus.
Same false-positive risk as Direct Reader Address for the pronoun-density component.

**What improving it would look like:** Calibrating the thresholds against a labeled sample
of stories with known fourth-wall behavior, and ideally reporting a confidence interval
rather than a single ordinal bin.

## Dialogue Ratio (context-only)

**What it measures:** What fraction of the story, by word count, is direct dialogue.
Binned into 1-5 via thresholds (`0.05`, `0.15`, `0.30`, `0.50`).

**Failure modes:** Directly inherits the preprocessor's quotation-mark heuristic -- see
`architecture.md` > Constraints and Assumptions. Manuscripts using em dashes for dialogue
(Cormac McCarthy style), single quotes, or no quotation marks at all will score near zero
regardless of actual dialogue content.

**What improving it would look like:** Not applicable to this feature in isolation --
this is entirely downstream of dialogue/narration splitting quality in
`modules/preprocessor.py`. Improving the splitter improves this for free.

## Chronological Discontinuity

**What it measures:** How often the story's timeline jumps around, approximated as
`temporal.json` lexicon density plus pluperfect ("had walked", "had known") verb density
across the *full* text, binned 1-5 via thresholds (`0.005`, `0.015`, `0.035`, `0.07`).
Pluperfect detection looks for a `have`-lemma token tagged `VBD` immediately followed by a
`VBN` (past participle) token.

**Failure modes:** The immediately-adjacent-token pluperfect check misses "had never truly
known" (an adverb breaks the adjacency) and any pluperfect construction split across a
clause boundary. Lexicon density conflates genuine anachrony ("years earlier, she had...")
with unrelated uses of the same phrases (a character literally saying "the night before" in
dialogue, which does get picked up since this runs on full text, not narration only).

**What improving it would look like:** A dependency-parse-based pluperfect detector that
tolerates intervening adverbs, and scoping the lexicon match to narration (or weighting
narration higher than dialogue) so a character's own words don't count as authorial
anachrony.

## Anachrony Intensity

**What it measures:** Similar inputs to Chronological Discontinuity but weighted toward the
backward-looking signal specifically: pluperfect density counted twice, temporal lexicon
density once, binned 1-5 via thresholds (`0.006`, `0.02`, `0.05`, `0.1`).

**Failure modes:** Same as Chronological Discontinuity -- these two features are
intentionally correlated (both draw from the same two underlying signals with different
weights), which is a reasonable approximation of the paper's intent but means they will
rarely disagree sharply on any given manuscript. A story that's nonlinear in a way that
doesn't route through pluperfect grammar or the temporal lexicon (e.g., an achronological
structure using scene breaks and date headers instead of prose signals) will under-score
on both.

**What improving it would look like:** A genuinely independent signal for this feature --
e.g., detecting explicit date/time headers or scene-break patterns -- so it's not just a
re-weighting of the same two numbers as its sibling feature.

## Nonlinear Disclosure Framing

**What it measures:** Whether anachrony markers cluster early in the story (suggesting the
story front-loads its nonlinearity, e.g. an opening flash-forward) vs. late. Each
`temporal.json` match is weighted by `1 - (position / text length)`, so a match at the very
start of the text gets weight ~1 and a match at the very end gets weight ~0. Weights are
summed, normalized by word count, scaled by 100, and binned 1-5 via thresholds (`0.5`,
`1.5`, `3.5`, `7.0`).

**Failure modes:** Position-in-characters is a crude proxy for "narrative position" --
a story with a long, slow opening scene will structurally compress its early matches into a
smaller fraction of total length than a story that jumps into action immediately, even if
the *narrative* significance of the timing is identical. This feature has the least direct
grounding of the three temporal features (the paper doesn't specify an exact position-weighting
formula either).

**What improving it would look like:** Weighting by scene or paragraph position instead of
raw character offset, and validating the weighting curve (linear here) against real
examples of front-loaded vs. back-loaded nonlinearity.

## Location Variety

**What it measures:** Count of distinct spaCy `GPE` (geopolitical entity) and `LOC`
(non-GPE location) named entities, lowercased and deduplicated, binned 1-4 via thresholds
(`2`, `4`, `7`) on the raw count.

**Failure modes:** This is the feature most exposed to spaCy NER's known weaknesses (see
`architecture.md` > Constraints and Assumptions). It only counts entities spaCy recognizes as
proper nouns -- generic references like "the mountains," "the river," "the village" (used
without a proper name) are invisible to it, even though they clearly establish distinct
locations in the prose. Fantasy and historical fiction with invented place names fare worse,
since spaCy's NER was trained on real-world entities.

**What improving it would look like:** Supplementing NER with a noun-phrase-based location
detector (definite noun phrases headed by a location-type noun, e.g. "the harbor," "the old
mill") so unnamed but distinct settings still count.

## Named Intertextuality

**What it measures:** Whether the story makes specific, named references outside itself --
`WORK_OF_ART` entities (book/song/film titles), plus `PERSON` entities that aren't part of
the story's own named cast (i.e., real or external figures referenced by name). Binary: 1 if
the combined count is at least 1.

**Failure modes:** Depends entirely on `preprocessed.named_characters` being accurate --
any story character spaCy fails to tag as `PERSON` in the initial pass (e.g., only referred
to by nickname or title) can get miscounted as an "external" reference, inflating this
feature. Conversely, a real-world figure who shares a name with a story character wouldn't
be caught. `WORK_OF_ART` is one of spaCy's less reliable entity types in practice.

**What improving it would look like:** Cross-referencing against a broader alias list per
character (built during preprocessing) rather than exact-string matching against
`named_characters`, and considering an LLM-confirmed pass for this feature given how
semantically loaded "is this reference external to the story" really is (this is in fact
already flagged in `architecture.md` as informing two "hybrid" LLM features --
Vague Intertextual Allusion and Balanced Intertextual Mix -- which use this score as context).

## Olfactory Imagery

**What it measures:** Density of smell-related words from `sensory.json`'s `olfactory`
list across the full text. Binary threshold at density >= 0.0005 (roughly 1 match per
2,000 words).

**Failure modes:** No disambiguation between literal smell description ("the stench of the
docks") and figurative or unrelated use ("something smelled wrong about the deal" as
metaphor, or "whiff" used to mean "a hint of"). The fixed threshold was chosen by feel, not
calibrated against a labeled corpus.

**What improving it would look like:** Same fix as Sensory Density below -- sense
disambiguation via context, and empirical threshold calibration.

## Sensory Density

**What it measures:** Combined lexicon match density across all five senses (olfactory,
auditory, tactile, gustatory, visual) in `sensory.json`, binned 1-5 via thresholds (`0.01`,
`0.02`, `0.035`, `0.055`).

**Failure modes:** Visual and auditory vocabulary are inherently more common in ordinary
prose than the other three senses (verbs like "saw" and "heard" are structurally
unavoidable in narrative), so this feature likely over-weights toward whichever story uses
more basic scene-setting verbs, independent of genuinely rich sensory writing. No
distinction between sensory description that's doing real work and incidental sensory verbs.

**What improving it would look like:** Per-sense normalization (so one sense dominating
doesn't drown out the others) and possibly excluding a small set of "structural" sensory
verbs (saw, heard, looked) that appear in almost all prose regardless of sensory richness.

## Embodied Emotion Expression

**What it measures:** Density of `body_sensation.json` matches (chest, throat, pulse,
trembling, etc.) in narration only. Binary threshold at density >= 0.006.

**Failure modes:** This is one of the four areas `architecture.md` explicitly flags as a
known weak point. Lexicon matching cannot tell the difference between a character
*experiencing* a tightening chest (the AI-elevated pattern this feature is meant to
capture), a character *observing* someone else's body language, and purely figurative
language reusing the same words. A story with a lot of physical description that isn't
emotionally motivated (a boxing match, a medical drama) will false-positive heavily.

**What improving it would look like:** Requiring the body-sensation noun to appear in a
dependency relation to the point-of-view character specifically (e.g., possessive
determiner referring to the protagonist, or the sensation as subject of an experiential
verb) rather than anywhere in the narration.

## Causal Chain Continuity

**What it measures:** Density of explicit causal connectives (`because`, `therefore`,
`as a result`, etc.) from `causal.json` across the full text, binned 1-5 via thresholds
(`0.003`, `0.008`, `0.016`, `0.03`) -- higher density maps to higher continuity (the paper's
"inverted" note in `architecture.md` just clarifies this is the intuitive direction, not an
inversion in the formula).

**Failure modes:** This is the other explicitly flagged weak point in `architecture.md`.
Connective density measures explicit causation *language*, not actual narrative causality --
a story can be tightly plotted without ever writing "because," and a story can use dozens of
causal connectives inside dialogue or characters' internal arguments without having a tight
causal chain at the plot level. This is, per the architecture doc, "the most likely to
require replacement with a dependency-parse or discourse-relation approach."

**What improving it would look like:** A discourse-parsing approach (e.g., PDTB-style
discourse relation classification) that identifies causal relations between *events*, not
just the presence of connective words -- ideally scoped to narration, not dialogue.

## Protagonist-Driven Resolution

**What it measures:** Whether the protagonist takes agentive action (is the grammatical
subject of a verb) within the final segment (last 15% of the text). Looks for either an
exact-name match to a `PERSON` entity in that span, or -- as a broad fallback -- *any*
pronoun subject at all. Binary: 1 if either condition is met once; 0 if `protagonist` is
`None` or neither condition ever fires.

**Failure modes:** The "any pronoun subject counts" fallback is deliberately loose (real
coreference resolution -- figuring out which pronoun refers to the protagonist specifically
-- is out of scope for this heuristic), which means almost any final segment with dialogue
or narration containing pronouns will score 1 regardless of whether the *protagonist*
specifically drove the resolution. This is the weakest of the binary features as
implemented; it's closer to "did anyone act with agency near the end" than the feature name
suggests.

**What improving it would look like:** Real coreference resolution (spaCy's `en_core_web_lg`
doesn't include a coreference model; a `coreferee` or transformer-based coreference pass
would be needed) so pronoun subjects can actually be resolved to the protagonist before
counting.

## Moral Ambivalence

**What it measures:** Whether a hedging word or phrase (`perhaps`, `seemed`, `might`,
`as if`, etc.) co-occurs in the same sentence as a protagonist mention, anywhere in
narration. Binary: 1 if any sentence matches; 0 if `protagonist` is `None` or no sentence
qualifies.

**Failure modes:** Same loose "any pronoun counts as the protagonist" logic as
Protagonist-Driven Resolution, plus no requirement that the hedge actually modifies a moral
or ethical judgment specifically -- a hedge about the weather in the same sentence as a
pronoun would satisfy this heuristic. The hedge-word list is small and hand-picked, not
derived from the paper (which describes the concept qualitatively, without a wordlist).

**What improving it would look like:** Restricting the hedge match to sentences with
evaluative/moral vocabulary nearby (not just any hedge), and again, real coreference
resolution instead of "any pronoun."

## No Subplots

**What it measures:** Whether any named character (other than the protagonist) appears by
exact-string match in the first half of the text but not in the final 20% -- evidence of a
secondary character thread that was introduced and dropped. Binary: 1 (no subplots) if no
such character exists; 0 if at least one does.

**Failure modes:** The other explicitly flagged weak point in `architecture.md`. Exact-name
thread-tracking only catches *character-driven* subplots specifically. It misses thematic
subplots that never introduce a new named character, and setting- or object-driven secondary
threads entirely. A story can have rich subplot structure and still score "no subplots" (1)
under this heuristic if every secondary character happens to be mentioned once near the end,
even in passing.

**What improving it would look like:** This is the feature `architecture.md` most strongly
suggests needs a different approach altogether -- likely a semantic/LLM-assisted pass that
identifies narrative threads (not just character name occurrences) and tracks whether each
is resolved, rather than a purely lexical presence/absence check.
