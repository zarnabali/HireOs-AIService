import sys
from pathlib import Path
from typing import Any

from app.clients.openai_client import OpenAIResumeClient
from app.core.config import get_settings
from app.integrations.document_extraction.pdf_text import extract_document_text, extract_pdf_text


class DocumentExtractionAdapter:
    """Internal adapter for the legacy Agentic-Document-Extraction-PDF pipeline."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def extract_resume(self, pdf_path: str | Path) -> dict[str, Any]:
        if not self.settings.document_extractor_enabled:
            raise RuntimeError("Document extractor integration is disabled")

        path = Path(pdf_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Resume file not found: {path}")

        if path.suffix.lower() not in {".pdf", ".docx"}:
            raise ValueError("Resume extractor currently accepts PDF or DOCX files only")

        provider = self.settings.document_extractor_provider.strip().lower()
        if provider == "openai":
            return self._extract_with_openai(path)
        if provider == "agentic":
            return self._extract_with_agentic_pipeline(path)
        raise ValueError("DOCUMENT_EXTRACTOR_PROVIDER must be either 'openai' or 'agentic'")

    def _extract_with_openai(self, path: Path) -> dict[str, Any]:
        resume_text = extract_pdf_text(path) if path.suffix.lower() == ".pdf" else extract_document_text(path)
        if not resume_text.strip():
            raise ValueError("No text could be extracted from the resume file")

        extracted = OpenAIResumeClient().extract_resume_fields(resume_text)
        return {
            "processing_id": None,
            "document_type": "resume",
            "selected_schema_name": "hireos_resume",
            "overall_confidence": 0.8,
            "merged_extraction": {
                key: {"value": value, "confidence": 0.8}
                for key, value in extracted.items()
            },
            "field_metadata": {},
            "page_images": [{"page_number": 1, "text_content": resume_text}],
            "total_vlm_calls": 1,
            "requires_human_review": False,
            "warnings": [],
            "errors": [],
        }

    def _extract_with_agentic_pipeline(self, path: Path) -> dict[str, Any]:
        if path.suffix.lower() != ".pdf":
            raise ValueError("Agentic document extraction provider currently accepts PDF files only")

        extractor_root = self.settings.resolved_document_extractor_root
        if not extractor_root.exists():
            raise RuntimeError(f"Document extractor root not found: {extractor_root}")

        root_str = str(extractor_root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        from src.pipeline.runner import PipelineRunner

        runner = PipelineRunner(
            enable_checkpointing=False,
            dpi=self.settings.document_extractor_dpi,
            max_image_dimension=self.settings.document_extractor_max_image_dimension,
            enable_image_enhancement=False,
        )

        state = runner.extract_from_pdf(
            pdf_path=str(path),
            custom_schema=_resume_custom_schema(),
            profile_override="generic-document",
        )
        return dict(state)


def _resume_custom_schema() -> dict[str, Any]:
    return {
        "schema_name": "hireos_resume",
        "description": "Extract structured candidate resume information for HireOS.",
        "fields": [
            "full_name",
            "email",
            "phone",
            "location",
            "linkedin",
            "github",
            "portfolio",
            "professional_summary",
            "skills",
            "work_experience",
            "education",
            "projects",
            "certifications",
            "languages",
            "achievements",
        ],
    }
