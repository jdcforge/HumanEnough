"""Diagnostic logging setup.

Console-only (stderr), never persisted to disk -- this keeps the existing "the tool does
not store any user data" guarantee (see docs/architecture.md > Constraints and Assumptions)
trivially true, with no log file retention/rotation policy to design or maintain.

Level is controlled by the HUMAN_ENOUGH_LOG_LEVEL environment variable (default INFO), set
before launching the app, e.g.:

    HUMAN_ENOUGH_LOG_LEVEL=DEBUG poetry run streamlit run app.py

Valid values are Python's standard `logging` level names (case-insensitive): DEBUG, INFO,
WARNING, ERROR, CRITICAL. An unrecognised value falls back to INFO and logs a one-line
warning naming the invalid value, rather than failing silently.

Security (see docs/architecture.md > Security): loggers configured here must never receive
story text, prompts, raw LLM responses, or API keys -- only stage names, counts, durations,
and the already-sanitised messages carried by this codebase's *Error exception classes
(ExtractionError, PreprocessError, DeterministicScoringError, LLMScoringError). Every call
site in this codebase that logs an exception logs `str(exc)` from one of those classes, not
the underlying raw exception -- see each module's `except ... as exc: logger.error(...)`.
"""

import logging
import os

NAMESPACE = "human_enough"
ENV_VAR = "HUMAN_ENOUGH_LOG_LEVEL"
DEFAULT_LEVEL = "INFO"

# Single source of truth for valid HUMAN_ENOUGH_LOG_LEVEL values -- deliberately an explicit
# lookup table rather than `getattr(logging, name)` against the whole `logging` module, which
# would also resolve unintended attributes (e.g. `logging.WARN`, a deprecated alias for
# WARNING, or non-level attributes like `logging.BASIC_FORMAT`) as if they were valid,
# documented level names.
LEVEL_NAMES_TO_VALUES: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_configured = False


def configure() -> None:
    """Idempotent -- safe to call from every module (and on every Streamlit rerun) without
    duplicating handlers or re-reading the environment variable after the first call."""
    global _configured
    if _configured:
        return

    raw_level_name = os.environ.get(ENV_VAR, DEFAULT_LEVEL).upper()
    level = LEVEL_NAMES_TO_VALUES.get(raw_level_name)
    invalid_level_name = raw_level_name if level is None else None
    if level is None:
        level = LEVEL_NAMES_TO_VALUES[DEFAULT_LEVEL]

    root = logging.getLogger(NAMESPACE)
    root.setLevel(level)
    root.propagate = False
    if not root.handlers:
        handler = logging.StreamHandler()  # stderr; nothing written to disk.
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
        )
        root.addHandler(handler)

    _configured = True

    if invalid_level_name is not None:
        root.warning(
            "%s=%r is not a recognised log level (expected one of %s) -- falling back to %s",
            ENV_VAR, invalid_level_name, tuple(LEVEL_NAMES_TO_VALUES), DEFAULT_LEVEL,
        )


def get_logger(short_name: str) -> logging.Logger:
    """Returns a logger under the shared 'human_enough' namespace, e.g. get_logger('app')."""
    configure()
    return logging.getLogger(f"{NAMESPACE}.{short_name}")


if __name__ == "__main__":
    logger = get_logger("logging_config")
    logger.info("Diagnostic logging configured (level=%s)", logging.getLevelName(logger.getEffectiveLevel()))
    print("OK -- logger namespace:", logger.name)
