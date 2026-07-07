import base64
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.integrations.document_extraction.adapter import DocumentExtractionAdapter
from app.integrations.document_extraction.normalizer import normalize_resume_extraction
from app.schemas.common import ErrorDetail
from app.schemas.resumes import (
    ExtractionProvenance,
    ResumeExtractionData,
    ResumeExtractionRequest,
    ResumeExtractionResponse,
)


class ResumeExtractorService:
    def __init__(self, adapter: DocumentExtractionAdapter | None = None) -> None:
        self.adapter = adapter or DocumentExtractionAdapter()

    def extract(self, payload: ResumeExtractionRequest) -> ResumeExtractionResponse:
        if payload.source_mime_type not in {
            "application/pdf",
            "application/x-pdf",
            "application/octet-stream",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }:
            raise ValueError("Resume extractor currently accepts PDF or DOCX uploads only")

        with self._resolved_input_file(payload) as file_path:
            state = self.adapter.extract_resume(file_path)
        confidence = float(state.get("overall_confidence") or 0.0)
        warnings = [str(warning) for warning in state.get("warnings", [])]
        errors = [str(error) for error in state.get("errors", [])]

        if errors:
            return ResumeExtractionResponse(
                success=False,
                confidence=confidence,
                warnings=warnings,
                reviewRequired=True,
                error=ErrorDetail(
                    code="DOCUMENT_EXTRACTION_FAILED",
                    message="The document extractor returned errors",
                    details={"errors": errors},
                ),
            )

        structured_resume = normalize_resume_extraction(state)
        data = ResumeExtractionData(
            documentId=payload.document_id,
            candidateId=payload.candidate_id,
            structuredResume=structured_resume,
            provenance=ExtractionProvenance(
                document_id=payload.document_id,
                candidate_id=payload.candidate_id,
                file_path=payload.file_path or payload.file_name or payload.document_id,
                processing_id=state.get("processing_id"),
                document_type=state.get("document_type"),
                schema_name=state.get("selected_schema_name"),
                total_vlm_calls=int(state.get("total_vlm_calls") or 0),
                raw_confidence=confidence,
            ),
        )

        return ResumeExtractionResponse(
            success=True,
            data=data,
            confidence=confidence,
            warnings=warnings,
            reviewRequired=bool(state.get("requires_human_review")) or confidence < 0.7,
        )

    @contextmanager
    def _resolved_input_file(self, payload: ResumeExtractionRequest) -> Iterator[str]:
        if payload.file_content_base64:
            suffix = Path(payload.file_name or payload.file_path or "resume.pdf").suffix
            if suffix.lower() not in {".pdf", ".docx"}:
                suffix = ".docx" if payload.source_mime_type.endswith("document") else ".pdf"
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / f"resume{suffix}"
                temp_path.write_bytes(base64.b64decode(payload.file_content_base64))
                yield str(temp_path)
            return

        if not payload.file_path:
            raise ValueError("Either filePath or fileContentBase64 is required")
        yield payload.file_path
