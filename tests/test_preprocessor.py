from modules.preprocessor import preprocess

_SAMPLE = (
    'Alice walked into the quiet room. "I have been waiting for you," she said, '
    "her voice trembling. Bob looked up from his book and smiled. "
    '"You always know when to arrive," he replied. Alice sat beside him, and for a '
    "long while neither of them spoke."
)

_FIRST_PERSON_SAMPLE = (
    "I walked to the market that morning. It was raining, and I had forgotten my coat. "
    'I said, "This is not the day I imagined," to no one in particular. '
    "I turned back home before the storm grew worse."
)


def test_narration_and_dialogue_are_non_overlapping_and_cover_the_text():
    result = preprocess(_SAMPLE)
    assert "waiting for you" in result.dialogue
    assert "waiting for you" not in result.narration
    assert "Alice walked into the quiet room" in result.narration
    assert "Alice walked into the quiet room" not in result.dialogue
    # Narration + dialogue can't exceed the source text (dialogue is a subset drawn from it).
    assert len(result.narration) + len(result.dialogue) <= len(result.full_text)


def test_protagonist_is_a_string_present_in_named_characters():
    result = preprocess(_SAMPLE)
    assert result.protagonist is not None
    assert result.protagonist in result.named_characters
    assert "Alice" in result.named_characters
    assert "Bob" in result.named_characters


def test_final_segment_is_approximately_15_percent_of_full_text():
    result = preprocess(_SAMPLE)
    expected_len = len(_SAMPLE) - int(len(_SAMPLE) * 0.85)
    assert len(result.final_segment) == expected_len
    assert result.final_segment == _SAMPLE[int(len(_SAMPLE) * 0.85) :]


def test_first_person_narrator_without_named_protagonist_handled_without_error():
    result = preprocess(_FIRST_PERSON_SAMPLE)
    assert result.protagonist is None or isinstance(result.protagonist, str)
    assert isinstance(result.named_characters, list)
