from pathlib import Path

from app.integrations.document_extraction.adapter import DocumentExtractionAdapter


class FakeSettings:
    document_extractor_enabled = True
    document_extractor_provider = "openai"


def test_openai_provider_returns_pipeline_state_shape(monkeypatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(
        "app.integrations.document_extraction.adapter.get_settings",
        lambda: FakeSettings(),
    )
    monkeypatch.setattr(
        "app.integrations.document_extraction.adapter.extract_pdf_text",
        lambda path: "Jane Doe\njane@example.com\nPython, AWS",
    )

    class FakeClient:
        def extract_resume_fields(self, resume_text: str) -> dict:
            return {"full_name": "Jane Doe", "skills": ["Python", "AWS"]}

    monkeypatch.setattr(
        "app.integrations.document_extraction.adapter.OpenAIResumeClient",
        lambda: FakeClient(),
    )

    state = DocumentExtractionAdapter().extract_resume(pdf_path)

    assert state["document_type"] == "resume"
    assert state["selected_schema_name"] == "hireos_resume"
    assert state["merged_extraction"]["full_name"]["value"] == "Jane Doe"
