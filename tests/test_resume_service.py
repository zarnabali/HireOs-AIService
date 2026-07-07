from app.schemas.resumes import ResumeExtractionRequest
from app.services.resume_extractor_service import ResumeExtractorService


class FakeAdapter:
    def extract_resume(self, file_path: str) -> dict:
        return {
            "processing_id": "proc_123",
            "overall_confidence": 0.91,
            "merged_extraction": {
                "full_name": {"value": "John Smith"},
                "skills": {"value": ["Python", "Docker"]},
            },
            "warnings": [],
            "errors": [],
        }


def test_resume_service_returns_hireos_response_shape() -> None:
    payload = ResumeExtractionRequest(
        documentId="11111111-1111-1111-1111-111111111111",
        candidateId="22222222-2222-2222-2222-222222222222",
        filePath="/tmp/resume.pdf",
        sourceMimeType="application/pdf",
        options={},
    )

    response = ResumeExtractorService(adapter=FakeAdapter()).extract(payload)

    assert response.success is True
    assert response.confidence == 0.91
    assert response.data is not None
    assert response.data.structured_resume.contact.full_name == "John Smith"
    assert response.data.structured_resume.skills == ["Python", "Docker"]
