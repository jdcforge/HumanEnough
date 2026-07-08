from modules.extractor import ExtractionError, extract


class _FakeUpload:
    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def _build_minimal_pdf(text: str) -> bytes:
    """Build a tiny, valid single-page PDF containing `text`, computing its own xref table
    so pdfplumber/pypdf can parse it without needing a real PDF-authoring dependency."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 300 300] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream_content = f"BT /F1 18 Tf 10 250 Td ({text}) Tj ET".encode("latin-1")
    objects.append(
        b"<< /Length " + str(len(stream_content)).encode() + b" >>\nstream\n"
        + stream_content + b"\nendstream"
    )

    buf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(buf)
    buf += f"xref\n0 {len(objects) + 1}\n".encode()
    buf += b"0000000000 65535 f \n"
    for off in offsets:
        buf += f"{off:010d} 00000 n \n".encode()
    buf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    buf += f"startxref\n{xref_offset}\n%%EOF".encode()
    return bytes(buf)


def test_pdf_extraction_returns_text_and_correct_word_count():
    pdf_bytes = _build_minimal_pdf("Hello PDF World")
    result = extract(_FakeUpload("story.pdf", pdf_bytes))
    assert result.text.strip() != ""
    assert "Hello PDF World" in result.text
    assert result.word_count == len(result.text.split())


def test_markdown_extraction_strips_yaml_front_matter():
    md = "---\ntitle: Test Story\nauthor: Someone\n---\n# Heading\n\nBody paragraph text."
    result = extract(_FakeUpload("story.md", md.encode("utf-8")))
    assert "title: Test Story" not in result.text
    assert "---" not in result.text
    assert "Body paragraph text." in result.text


def test_txt_extraction_returns_text_unchanged():
    text = "This is plain text.\nWith two lines."
    result = extract(_FakeUpload("story.txt", text.encode("utf-8")))
    assert result.text == text
    assert result.char_count == len(text)


def test_unsupported_file_type_raises_clear_error():
    try:
        extract(_FakeUpload("story.docx", b"irrelevant content"))
        assert False, "expected ExtractionError"
    except ExtractionError as exc:
        assert "pdf" in str(exc) and "md" in str(exc) and "txt" in str(exc)


def test_empty_file_raises_clear_error():
    try:
        extract(_FakeUpload("empty.txt", b""))
        assert False, "expected ExtractionError"
    except ExtractionError as exc:
        assert "empty" in str(exc).lower()
