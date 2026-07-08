# Human Enough

Human Enough is a narrative analysis tool for fiction writers. It scores your manuscript
across 30 discourse-level narrative features from the StoryScope research paper and shows
you how your story's structural choices compare to human authors and five AI models
(Claude, GPT, Gemini, DeepSeek, Kimi).

**Version 0.1.0**

This tool runs entirely on your own computer. Nothing about your manuscript is ever sent
anywhere except, briefly, to the AI provider you choose (Anthropic or OpenAI) for part of
the analysis -- and your API key is never saved to disk.

## Before you start

You'll need three things installed on your computer: Python 3.14, git, and Poetry. If
you've never used a terminal before, that's fine -- each step below explains what to type
and why. Follow the block for your operating system.

Across all platforms, Poetry's officially recommended install method is
[`pipx install poetry`](https://pipx.pypa.io/) or the standalone installer at
[install.python-poetry.org](https://install.python-poetry.org/). `pip install poetry`
(used below) also works and is simpler if `pipx` is unfamiliar to you, but it's a shortcut,
not the officially recommended path.

### Windows

1. **Python 3.14** -- download it from [python.org/downloads](https://www.python.org/downloads/).
   During installation, tick the box that says "Add Python to PATH" -- this is easy to miss
   and is the most common cause of install problems.
2. **git** -- download it from [git-scm.com](https://git-scm.com/downloads).
3. **Poetry** -- open Command Prompt or PowerShell and run:

   ```
   pip install poetry
   ```

   If the `poetry` command isn't recognized right after installing, close the terminal
   window completely and open a new one -- Windows only picks up the updated PATH in a
   fresh session.

### macOS

1. **Python 3.14 and git** -- the easiest path is [Homebrew](https://brew.sh/):

   ```
   brew install python@3.14 git
   ```

   You can also download Python from [python.org/downloads](https://www.python.org/downloads/)
   instead, but if you do, you must also run `Install Certificates.command` (found inside
   the Python 3.14 folder in your Applications folder) before Python can make secure network
   connections -- see Troubleshooting below.
2. **Poetry** -- open Terminal and run either:

   ```
   pipx install poetry
   ```

   or

   ```
   pip install poetry
   ```

### Linux

1. **Python 3.14 and git** -- install via your distribution's package manager. For example,
   on Debian/Ubuntu:

   ```
   sudo apt install python3.14 git
   ```

   Substitute your distro's equivalent (e.g. `dnf` on Fedora, `pacman` on Arch) if you're
   not on a Debian-based system.
2. **Poetry** -- open your terminal emulator and run either:

   ```
   pipx install poetry
   ```

   or

   ```
   pip install poetry
   ```

## Setup

Open a terminal and run each command in order. A one-line explanation comes before each one.

**1. Download the project's code to your computer:**

```
git clone https://github.com/jdcforge/HumanEnough
cd HumanEnough
```

**2. Install all the project's dependencies into an isolated environment**, so they don't
interfere with anything else on your computer:

```
poetry install
```

**3. Download the language model** the tool uses to read sentence structure. This is a
separate, large (~800MB) download that Poetry can't manage on its own:

```
poetry run python -m spacy download en_core_web_lg
```

**4. Start the application.** This opens the tool in your web browser:

```
poetry run streamlit run app.py
```

Leave the terminal window open while you use the tool -- closing it shuts the application
down. To stop the tool, go back to the terminal and press `Ctrl+C` (on Windows you may need
to press it twice). If you try to start the tool again and see a "port already in use"
error, either wait a moment and retry, or add `--server.port 8502` to the command to use a
different port.

## Getting an API key

Part of the analysis is done by an AI model, which requires an API key from either
Anthropic or OpenAI (your choice, selected in the app's sidebar). You only need one.

- **Anthropic (Claude):** create a key at [console.anthropic.com](https://console.anthropic.com/)
  under "API Keys".
- **OpenAI (GPT):** create a key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

Both providers require you to add billing details. Cost varies by manuscript length and
model. The app shows an estimate before you run it. A short story on the cheapest model
costs a fraction of a cent; a novel-length manuscript on a more capable model may cost
$0.30-$0.50. Your key is entered directly into the app's sidebar each time you use it; it
is held only in that browser session and is never written to disk or logged anywhere.

## Using the app

1. In the sidebar, choose a provider (Anthropic or OpenAI), a model, and paste in your API key.
2. Upload your manuscript (`.pdf`, `.md`, or `.txt`), or click **Try with sample story** to
   see how it works without your own file.
3. Check the estimated cost, then click **Analyse**.
4. Review your results: the Similarity Map, your nearest AI/human profile matches, and a
   full breakdown of all 30 features.

Manuscripts under 2,000 words may produce unreliable scores; manuscripts over 60,000 words
are truncated for the AI-scored half of the analysis (the structural half always runs on
the full text).

## Troubleshooting

- **`poetry` command not found after install** -- close the terminal completely and open a
  new one, then try again. On Windows, make sure Python was added to PATH during
  installation.
- **spaCy download fails or times out** -- the model is ~800MB. Try again on a stable
  connection. If it repeatedly fails, try:

  ```
  poetry run python -m spacy download en_core_web_lg --timeout 300
  ```

- **App opens but API key is rejected** -- check there are no leading or trailing spaces
  when pasting. Anthropic keys start with `sk-ant-`; OpenAI keys start with `sk-`.
- **PDF uploads but no text is extracted** -- the PDF is likely scanned (image-based). The
  tool requires a PDF with a text layer. Try exporting from your word processor as a PDF
  rather than scanning a printed page.
- **macOS: Python install from python.org doesn't work** -- run
  `Install Certificates.command`, found in your Python 3.14 application folder, then try
  again.
- **Need more detail to diagnose a problem** -- set `HUMAN_ENOUGH_LOG_LEVEL` before starting
  the app for diagnostic output in the terminal (never your manuscript text or API key --
  see `docs/architecture.md` > Security). Valid values, from most to least verbose: `DEBUG`,
  `INFO` (the default), `WARNING`, `ERROR`, `CRITICAL`. An unrecognised value falls back to
  `INFO` and prints a one-line warning saying so.

  ```
  HUMAN_ENOUGH_LOG_LEVEL=DEBUG poetry run streamlit run app.py
  ```

## Citation

This tool's feature definitions and reference profiles are derived from:

> Russell, J., Rajendhran, R., Pham, C. M., Iyyer, M., & Wieting, J. (2026). StoryScope:
> Investigating idiosyncrasies in AI fiction. arXiv:2604.03136.

```bibtex
@article{russell2026storyscope,
  title   = {StoryScope: Investigating idiosyncrasies in AI fiction},
  author  = {Russell, Jenna and Rajendhran, Rishanth and Pham, Chau Minh and Iyyer, Mohit and Wieting, John},
  journal = {arXiv preprint arXiv:2604.03136},
  year    = {2026}
}
```

See `NOTICE` for the full attribution statement and `docs/architecture.md` for how each feature
maps back to the paper.

## Limitations

The Similarity Map is a conceptual visualisation, not a statistical projection or a
classifier -- it does not determine authorship. Reference profiles are approximations
derived from the paper's published aggregate statistics, not its trained model weights.
See `docs/architecture.md` > "Known Heuristic Limitations" and `docs/heuristics.md` for where the
structural scoring is weakest (protagonist detection, subplot detection, embodied emotion,
and causal continuity).

## Development

Run the full test suite:

```
poetry run pytest
```

Run a single test file:

```
poetry run pytest tests/test_extractor.py
```

See `docs/development.md` for how to update lexicons, pricing constants, and reference
profiles, and how to add new narrative features.
