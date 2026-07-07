from pathlib import Path
from zipfile import ZipFile
import re
import xml.etree.ElementTree as ET


def extract_pdf_text(pdf_path: str | Path) -> str:
    path = Path(pdf_path)
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to read resume PDFs") from exc

    chunks: list[str] = []
    with fitz.open(path) as document:
        for page in document:
            text = page.get_text("text").strip()
            if text:
                chunks.append(text)
    return "\n\n".join(chunks)


def extract_docx_text(docx_path: str | Path) -> str:
    path = Path(docx_path)
    try:
        with ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except KeyError as exc:
        raise ValueError("DOCX file does not contain word/document.xml") from exc

    root = ET.fromstring(xml_bytes)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lines: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        parts = [
            node.text or ""
            for node in paragraph.findall(".//w:t", namespace)
            if node.text
        ]
        text = re.sub(r"\s+", " ", "".join(parts)).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def extract_document_text(path: str | Path) -> str:
    document_path = Path(path)
    suffix = document_path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(document_path)
    if suffix == ".docx":
        return extract_docx_text(document_path)
    raise ValueError("Resume extractor currently accepts PDF or DOCX files only")
