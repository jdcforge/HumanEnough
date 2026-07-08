import json
import logging

from modules import deterministic, llm_scorer, logging_config
from modules.preprocessor import preprocess


def test_get_logger_returns_namespaced_child_logger():
    logger = logging_config.get_logger("some_module")
    assert logger.name == "human_enough.some_module"


def test_log_level_respects_env_var(monkeypatch):
    monkeypatch.setenv(logging_config.ENV_VAR, "DEBUG")
    monkeypatch.setattr(logging_config, "_configured", False)
    logging.getLogger(logging_config.NAMESPACE).handlers.clear()

    logging_config.configure()

    assert logging.getLogger(logging_config.NAMESPACE).level == logging.DEBUG


def test_all_documented_level_names_are_accepted(monkeypatch):
    for name in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "debug", "Warning"):
        monkeypatch.setenv(logging_config.ENV_VAR, name)
        monkeypatch.setattr(logging_config, "_configured", False)
        logging.getLogger(logging_config.NAMESPACE).handlers.clear()

        logging_config.configure()

        assert logging.getLogger(logging_config.NAMESPACE).level == getattr(logging, name.upper())


def test_invalid_level_name_falls_back_to_info_with_a_warning(monkeypatch):
    monkeypatch.setenv(logging_config.ENV_VAR, "VERBOSE")
    monkeypatch.setattr(logging_config, "_configured", False)
    root = logging.getLogger(logging_config.NAMESPACE)
    root.handlers.clear()

    records: list[str] = []
    collector = logging.Handler()
    collector.emit = lambda record: records.append(record.getMessage())
    # Attach before configure() so the fallback warning it emits is actually captured --
    # configure() adds its own StreamHandler too, this one is just for the assertion.
    logging.getLogger(logging_config.NAMESPACE).addHandler(collector)

    logging_config.configure()

    assert root.level == logging.INFO
    assert any("VERBOSE" in message and "INFO" in message for message in records)


def test_getattr_against_logging_module_would_have_wrongly_accepted_warn(monkeypatch):
    """Regression guard for the bug caught during review: `getattr(logging, name)` resolves
    `logging.WARN` (a real deprecated alias for WARNING) even though `WARN` was never a
    documented value, and also implicitly resolves non-level attributes. The explicit
    LEVEL_NAMES_TO_VALUES table must never grow to include it or anything not in the
    documented DEBUG/INFO/WARNING/ERROR/CRITICAL set."""
    assert "WARN" not in logging_config.LEVEL_NAMES_TO_VALUES
    assert set(logging_config.LEVEL_NAMES_TO_VALUES) == {
        "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL",
    }


def test_pipeline_never_logs_api_key_or_story_text():
    """The central security contract from docs/architecture.md > Security: diagnostic
    logging must never leak story text or API keys, however deep in the pipeline."""
    secret_key = "sk-ant-super-secret-test-marker-9f3e"
    distinctive_story_phrase = "purple elephant marmalade 4821"
    story = (
        f'Alice said, "{distinctive_story_phrase}," and Bob nodded before he left the room.'
    )

    records: list[str] = []
    collector = logging.Handler()
    collector.emit = lambda record: records.append(record.getMessage())
    root = logging.getLogger(logging_config.NAMESPACE)
    root.addHandler(collector)
    root.setLevel(logging.DEBUG)
    try:
        preprocessed = preprocess(story)
        det_scores = deterministic.score(preprocessed)
        fake_response = json.dumps({f["name"]: 1 for f in llm_scorer.LLM_FEATURES})
        llm_scorer.score(
            preprocessed, det_scores, "anthropic", secret_key, "fake-model",
            _call_fn=lambda prompt: fake_response,
        )
    finally:
        root.removeHandler(collector)

    all_messages = " ".join(records)
    assert secret_key not in all_messages
    assert distinctive_story_phrase not in all_messages
    assert len(records) > 0  # sanity check the handler actually captured something
