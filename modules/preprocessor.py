"""Segment story text into narration vs. dialogue; identify protagonist and named characters.

Uses spaCy (`en_core_web_lg`) for named-entity recognition and dependency parsing.
"""

import re
import time
from collections import Counter
from dataclasses import dataclass

from modules.logging_config import get_logger

SPACY_MODEL_NAME = "en_core_web_lg"
FINAL_SEGMENT_FRACTION = 0.15

# Matches text inside straight double quotes ("...") or curly double quotes (“...”).
_QUOTE_PATTERN = re.compile(r'"([^"]*)"|“([^”]*)”')

_nlp = None
logger = get_logger("preprocessor")


class PreprocessError(Exception):
    """Raised for any preprocessing failure. The message is safe to show directly to the user."""


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy

        try:
            _nlp = spacy.load(SPACY_MODEL_NAME)
            logger.info("spaCy model '%s' loaded", SPACY_MODEL_NAME)
        except OSError as exc:
            logger.error("spaCy model '%s' not found", SPACY_MODEL_NAME)
            raise PreprocessError(
                f"Language model not found. Run: python -m spacy download {SPACY_MODEL_NAME}"
            ) from exc
    return _nlp


@dataclass
class PreprocessResult:
    full_text: str
    narration: str
    dialogue: str
    protagonist: str | None
    named_characters: list[str]
    final_segment: str


def _split_narration_dialogue(text: str) -> tuple[str, str]:
    """Split on quoted spans. Narration is everything outside quotes; dialogue is the
    concatenated inner content of quoted spans. Non-overlapping by construction."""
    narration_parts = []
    dialogue_parts = []
    last_end = 0
    for match in _QUOTE_PATTERN.finditer(text):
        narration_parts.append(text[last_end : match.start()])
        inner = match.group(1) if match.group(1) is not None else match.group(2)
        if inner.strip():
            dialogue_parts.append(inner)
        last_end = match.end()
    narration_parts.append(text[last_end:])
    return "".join(narration_parts), "\n".join(dialogue_parts)


def _named_characters(doc) -> list[str]:
    seen: dict[str, None] = {}
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            seen.setdefault(ent.text, None)
    return list(seen.keys())


def _detect_protagonist(narration_doc, full_text_doc) -> str | None:
    # Primary signal: named character most often the subject of an action verb in narration.
    person_token_index: dict[int, str] = {
        i: ent.text
        for ent in narration_doc.ents
        if ent.label_ == "PERSON"
        for i in range(ent.start, ent.end)
    }
    subject_counts: Counter[str] = Counter()
    for token in narration_doc:
        if token.dep_ in ("nsubj", "nsubjpass") and token.head.pos_ == "VERB":
            name = person_token_index.get(token.i)
            if name:
                subject_counts[name] += 1
    if subject_counts:
        return subject_counts.most_common(1)[0][0]

    # Fallback: most frequently occurring PERSON entity across the whole text.
    person_counts = Counter(
        ent.text for ent in full_text_doc.ents if ent.label_ == "PERSON"
    )
    if person_counts:
        return person_counts.most_common(1)[0][0]

    # No PERSON entities found at all -- protagonist-dependent features are skipped.
    return None


def preprocess(text: str) -> PreprocessResult:
    """Segment text into narration and dialogue; identify protagonist and named characters."""
    started = time.perf_counter()
    nlp = _get_nlp()

    narration, dialogue = _split_narration_dialogue(text)

    narration_doc = nlp(narration)
    full_text_doc = nlp(text)

    protagonist = _detect_protagonist(narration_doc, full_text_doc)
    named_characters = _named_characters(full_text_doc)

    cutoff = int(len(text) * (1 - FINAL_SEGMENT_FRACTION))
    final_segment = text[cutoff:]

    # Never log names or text content -- only counts and booleans (see logging_config.py).
    elapsed = time.perf_counter() - started
    logger.info(
        "Preprocessing complete: %d narration words, %d dialogue words, "
        "protagonist_found=%s, %d named character(s), %.3fs",
        len(narration.split()), len(dialogue.split()) if dialogue else 0,
        protagonist is not None, len(named_characters), elapsed,
    )

    return PreprocessResult(
        full_text=text,
        narration=narration,
        dialogue=dialogue,
        protagonist=protagonist,
        named_characters=named_characters,
        final_segment=final_segment,
    )


if __name__ == "__main__":
    sample = (
        'Alice walked into the quiet room. "I have been waiting for you," she said, '
        "her voice trembling. Bob looked up from his book and smiled. "
        '"You always know when to arrive," he replied. Alice sat beside him, and for a '
        "long while neither of them spoke. Alice thought about the years that had passed "
        "since they first met, and how much had changed. In the end, Alice decided to stay."
    )
    result = preprocess(sample)
    assert result.protagonist in result.named_characters, result.protagonist
    assert "Alice" in result.named_characters
    assert "Bob" in result.named_characters
    assert "waiting for you" in result.dialogue
    assert "waiting for you" not in result.narration
    assert len(result.final_segment) == len(sample) - int(len(sample) * 0.85)
    print("OK -- protagonist:", result.protagonist, "| named characters:", result.named_characters)
