from zipfile import ZipFile

from app.integrations.document_extraction.pdf_text import extract_docx_text


def test_extract_docx_text_reads_paragraph_text(tmp_path) -> None:
    docx_path = tmp_path / "resume.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>ZARNAB ALI</w:t></w:r></w:p>
    <w:p><w:r><w:t>Python FastAPI AWS</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    with ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    assert extract_docx_text(docx_path) == "ZARNAB ALI\nPython FastAPI AWS"
