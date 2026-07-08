"""File ingestion: PDF, MD, TXT -> plain text.

Accepts an in-memory file object such as Streamlit's UploadedFile (anything exposing
`.name` and either `.getvalue()` or `.read()`).
"""

from dataclasses import dataclass

from modules.logging_config import get_logger

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB, per the Error States table.
SUPPORTED_EXTENSIONS = (".pdf", ".md", ".txt")

logger = get_logger("extractor")


class ExtractionError(Exception):
    """Raised for any file-ingestion failure. The message is safe to show directly to the user."""


@dataclass
class ExtractionResult:
    text: str  # Plain UTF-8 story text
    word_count: int  # Word count of extracted text
    char_count: int  # Character count of extracted text


def _read_bytes(file) -> bytes:
    if hasattr(file, "getvalue"):
        return file.getvalue()
    return file.read()


def _strip_yaml_front_matter(text: str) -> str:
    """Strip a leading YAML front-matter block delimited by `---` lines, if present."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "".join(lines[i + 1 :])
    return text  # Unterminated front matter -- leave the text untouched.


def _extract_pdf_text(raw: bytes) -> str:
    try:
        import pdfplumber
        from io import BytesIO

        with pdfplumber.open(BytesIO(raw)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        text = "\n".join(pages).strip()
        if text:
            logger.info("PDF extracted via pdfplumber (%d pages)", len(pages))
            return text
    except Exception:
        logger.warning("pdfplumber failed to extract PDF text, falling back to pypdf")

    try:
        from pypdf import PdfReader
        from io import BytesIO

        reader = PdfReader(BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        if text:
            logger.info("PDF extracted via pypdf fallback (%d pages)", len(pages))
            return text
    except Exception:
        logger.warning("pypdf fallback also failed to extract PDF text")

    logger.error("PDF has no extractable text layer")
    raise ExtractionError(
        "This PDF appears to be scanned. Text extraction requires a PDF with a text layer."
    )


def extract(file) -> ExtractionResult:
    """Accept a Streamlit UploadedFile. Return text, word count, and character count."""
    import time

    started = time.perf_counter()
    # Deliberately not logging the filename -- it can itself be revealing about an
    # unpublished manuscript's title or contents. Only the extension is diagnostic.
    name = getattr(file, "name", "")
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    logger.info("Extraction requested (type=%s)", suffix or "unknown")

    if suffix not in SUPPORTED_EXTENSIONS:
        logger.error("Unsupported file type: %s", suffix or "unknown")
        raise ExtractionError("Please upload a .pdf, .md, or .txt file.")

    raw = _read_bytes(file)
    if len(raw) > MAX_FILE_SIZE_BYTES:
        logger.error("File exceeds size limit: %d bytes", len(raw))
        raise ExtractionError("File exceeds the 10MB limit. Try splitting the manuscript.")
    if not raw:
        logger.error("Uploaded file is empty (0 bytes)")
        raise ExtractionError("The uploaded file is empty.")

    if suffix == ".pdf":
        text = _extract_pdf_text(raw)
    elif suffix == ".md":
        text = _strip_yaml_front_matter(raw.decode("utf-8", errors="replace"))
    else:  # .txt
        text = raw.decode("utf-8", errors="replace")

    text = text.strip()
    if not text:
        logger.error("Extracted text is empty after processing")
        raise ExtractionError("The uploaded file is empty.")

    word_count = len(text.split())
    char_count = len(text)
    elapsed = time.perf_counter() - started
    logger.info("Extraction complete: %d words, %d chars, %.3fs", word_count, char_count, elapsed)
    return ExtractionResult(text=text, word_count=word_count, char_count=char_count)


if __name__ == "__main__":
    from io import BytesIO

    class _FakeUpload:
        def __init__(self, name: str, content: bytes):
            self.name = name
            self._content = content

        def getvalue(self) -> bytes:
            return self._content

    sample = "This is a short sample story. It has a few words in it."
    result = extract(_FakeUpload("sample.txt", sample.encode("utf-8")))
    assert result.text == sample
    assert result.word_count == len(sample.split())

    md_sample = "---\ntitle: Test\n---\n# Heading\n\nBody text."
    md_result = extract(_FakeUpload("sample.md", md_sample.encode("utf-8")))
    assert "title: Test" not in md_result.text
    assert "Body text." in md_result.text

    try:
        extract(_FakeUpload("sample.docx", b"irrelevant"))
        raise AssertionError("expected ExtractionError for unsupported type")
    except ExtractionError:
        pass

    try:
        extract(_FakeUpload("empty.txt", b""))
        raise AssertionError("expected ExtractionError for empty file")
    except ExtractionError:
        pass

    print("OK --", result.word_count, "words extracted from sample .txt")
