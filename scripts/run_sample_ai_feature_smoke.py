import json
import os
import re
import socket
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.agents import AIServiceAgent
from app.core.config import get_settings
from app.integrations.document_extraction.normalizer import normalize_resume_extraction
from app.integrations.document_extraction.pdf_text import extract_document_text
from app.schemas.resumes import ResumeExtractionRequest
from app.services.resume_extractor_service import ResumeExtractorService


TEST_DATA_DIR = SERVICE_ROOT / "test-data"
RESULTS_DIR = SERVICE_ROOT / "test-results"
PDF_PATH = TEST_DATA_DIR / "Zarnab_Ali_Resume.pdf"
DOCX_PATH = TEST_DATA_DIR / "Zarnab_Ali_Resume.docx"


def json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str in {"data_uri", "base64_encoded"} and isinstance(item, str):
                cleaned[key_str] = f"<redacted base64 length={len(item)}>"
            else:
                cleaned[key_str] = json_safe(item)
        return cleaned
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def run_case(output_dir: Path, file_name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    start = time.perf_counter()
    started_at = datetime.now(UTC).isoformat()
    try:
        result = fn()
        payload = {
            "status": "completed",
            "startedAt": started_at,
            "durationSeconds": round(time.perf_counter() - start, 3),
            "result": json_safe(result),
        }
    except Exception as exc:
        payload = {
            "status": "failed",
            "startedAt": started_at,
            "durationSeconds": round(time.perf_counter() - start, 3),
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }
    write_json(output_dir / file_name, payload)
    return payload


def extract_pdf() -> dict[str, Any]:
    request = ResumeExtractionRequest(
        documentId="doc_zarnab_pdf",
        candidateId="candidate_zarnab",
        filePath=str(PDF_PATH),
        sourceMimeType="application/pdf",
    )
    response = ResumeExtractorService().extract(request)
    return response.model_dump(mode="json", by_alias=True)


def local_extract_pdf() -> dict[str, Any]:
    return local_extract_document(PDF_PATH, "doc_zarnab_pdf")


def local_extract_docx() -> dict[str, Any]:
    return local_extract_document(DOCX_PATH, "doc_zarnab_docx")


def local_extract_document(path: Path, document_id: str) -> dict[str, Any]:
    resume_text = extract_document_text(path)
    state = {
        "processing_id": None,
        "document_type": "resume",
        "selected_schema_name": "hireos_resume",
        "overall_confidence": 0.62,
        "merged_extraction": {},
        "field_metadata": {},
        "page_images": [{"page_number": 1, "text_content": resume_text}],
        "total_vlm_calls": 0,
        "requires_human_review": True,
        "warnings": [],
        "errors": [],
    }
    structured_resume = normalize_resume_extraction(state).model_dump(mode="json")
    return {
        "success": True,
        "data": {
            "documentId": document_id,
            "candidateId": "candidate_zarnab",
            "structuredResume": structured_resume,
            "provenance": {
                "source": "local-document-text-parser-smoke-test",
                "document_id": document_id,
                "candidate_id": "candidate_zarnab",
                "file_path": str(path),
                "processing_id": None,
                "document_type": "resume",
                "schema_name": "hireos_resume",
                "total_vlm_calls": 0,
                "raw_confidence": 0.62,
            },
        },
        "confidence": 0.62,
        "warnings": [
            "Local-only smoke mode used deterministic text parsing instead of OpenAI extraction.",
            "Use external OpenAI smoke only after explicitly approving resume content transfer to OpenAI.",
        ],
        "reviewRequired": True,
        "error": None,
        "rawTextPreview": resume_text[:1200],
    }


def heuristic_resume_from_text(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email = next(iter(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)), None)
    phone = next(iter(re.findall(r"(?:\+?\d[\d\s().-]{8,}\d)", text)), None)
    urls = re.findall(r"https?://[^\s)]+|(?:linkedin\.com|github\.com)/[^\s)]+", text, flags=re.IGNORECASE)
    known_skills = [
        "Python",
        "FastAPI",
        "Django",
        "Flask",
        "JavaScript",
        "TypeScript",
        "React",
        "Next.js",
        "Node.js",
        "PostgreSQL",
        "Supabase",
        "Redis",
        "Celery",
        "Docker",
        "AWS",
        "OpenAI",
        "LangGraph",
        "LangChain",
        "SQL",
        "Tailwind",
        "Git",
    ]
    lower_text = text.lower()
    skills = [skill for skill in known_skills if skill.lower() in lower_text]
    name = lines[0] if lines else None
    summary = " ".join(lines[:5])[:700] if lines else None
    achievements = [
        line for line in lines if re.search(r"\b\d+%|\b\d+x|\b\d+\+|\b\d{2,}\b", line)
    ][:8]
    projects = [
        {"name": line[:80], "description": line, "technologies": skills[:6], "url": None}
        for line in lines
        if "project" in line.lower()
    ][:5]
    return {
        "contact": {
            "full_name": name,
            "email": email,
            "phone": phone,
            "location": None,
            "linkedin": next((url for url in urls if "linkedin" in url.lower()), None),
            "github": next((url for url in urls if "github" in url.lower()), None),
            "portfolio": next((url for url in urls if "linkedin" not in url.lower() and "github" not in url.lower()), None),
        },
        "summary": summary,
        "skills": skills,
        "experience": [{"company": None, "title": None, "achievements": achievements}],
        "education": [],
        "projects": projects,
        "certifications": [],
        "languages": [],
        "achievements": achievements,
        "links": [{"label": "link", "url": url} for url in urls],
        "raw_sections": {"text": text[:10000]},
    }


def extract_docx_unsupported() -> dict[str, Any]:
    request = ResumeExtractionRequest(
        documentId="doc_zarnab_docx",
        candidateId="candidate_zarnab",
        filePath=str(DOCX_PATH),
        sourceMimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response = ResumeExtractorService().extract(request)
    return response.model_dump(mode="json", by_alias=True)


def run_legacy_agentic_probe() -> dict[str, Any]:
    extractor_root = SERVICE_ROOT / "Agentic-Document-Extraction-PDF"
    os.environ["DEBUG"] = "false"
    os.environ.setdefault("LM_STUDIO_TIMEOUT", "5")
    os.environ.setdefault("LM_STUDIO_MAX_RETRIES", "0")
    os.environ.setdefault("PDF_ENABLE_ENHANCEMENT", "false")
    sys.path.insert(0, str(extractor_root))

    from src.pipeline.runner import PipelineRunner

    runner = PipelineRunner(
        enable_checkpointing=False,
        max_retries=0,
        dpi=120,
        max_image_dimension=1024,
        enable_image_enhancement=False,
    )
    state = runner.extract_from_pdf(
        pdf_path=str(PDF_PATH),
        custom_schema={
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
        },
        profile_override="generic-document",
    )
    return dict(state)


def run_legacy_agentic_health_probe() -> dict[str, Any]:
    extractor_root = SERVICE_ROOT / "Agentic-Document-Extraction-PDF"
    sys.path.insert(0, str(extractor_root))

    from src.pipeline.runner import PipelineRunner

    import_ok = PipelineRunner is not None
    reachable = False
    connection_error = None
    try:
        with socket.create_connection(("127.0.0.1", 1234), timeout=1):
            reachable = True
    except OSError as exc:
        connection_error = str(exc)

    return {
        "success": True,
        "mode": "health_probe",
        "extractorRoot": str(extractor_root),
        "samplePdf": str(PDF_PATH),
        "pipelineRunnerImportOk": import_ok,
        "localVlm": {
            "baseUrl": "http://localhost:1234/v1",
            "reachable": reachable,
            "connectionError": connection_error,
        },
        "note": (
            "Full legacy agentic extraction is skipped by default because it requires "
            "a local OpenAI-compatible vision model. Pass --run-full-legacy-agentic "
            "to execute the full legacy pipeline."
        ),
    }


def structured_resume_from(extraction_payload: dict[str, Any]) -> dict[str, Any]:
    result = extraction_payload.get("result") or {}
    data = result.get("data") or {}
    return data.get("structuredResume") or {}


def sample_jobs() -> list[dict[str, Any]]:
    return [
        {
            "id": "job_backend_python_ai",
            "title": "Backend AI Engineer",
            "description": (
                "Build FastAPI, Python, PostgreSQL, Redis, Docker, LangGraph, "
                "OpenAI, and AWS services for an AI hiring platform."
            ),
            "requirements": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "LangGraph", "OpenAI", "AWS"],
            "location": "Remote",
            "salaryRange": {"min": 90000, "max": 140000},
        },
        {
            "id": "job_fullstack_next",
            "title": "Full Stack Engineer",
            "description": "Next.js, TypeScript, Node.js, Supabase, Tailwind, shadcn/ui, API design.",
            "requirements": ["Next.js", "TypeScript", "Node.js", "Supabase", "Tailwind"],
            "location": "Hybrid",
        },
        {
            "id": "job_data_analyst",
            "title": "Data Analyst",
            "description": "SQL dashboards, BI reporting, Excel, stakeholder analysis, analytics pipelines.",
            "requirements": ["SQL", "Excel", "BI", "Analytics"],
            "location": "Onsite",
        },
    ]


def weaker_candidate_resume() -> dict[str, Any]:
    return {
        "contact": {"full_name": "Comparison Candidate"},
        "summary": "Entry-level analyst with SQL and Excel experience.",
        "skills": ["SQL", "Excel", "Tableau"],
        "experience": [{"company": "Example Co", "title": "Data Intern", "achievements": ["Created weekly dashboards"]}],
        "education": [{"institution": "Example University", "degree": "BS"}],
        "projects": [],
    }


def main() -> int:
    local_only = "--local-only" in sys.argv or os.environ.get("HIREOS_SMOKE_LOCAL_ONLY", "").lower() in {
        "1",
        "true",
        "yes",
    }
    run_full_legacy = "--run-full-legacy-agentic" in sys.argv
    if local_only:
        os.environ["OPENAI_API_KEY"] = ""

    settings = get_settings()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = RESULTS_DIR / timestamp

    manifest: dict[str, Any] = {
        "runId": timestamp,
        "serviceRoot": str(SERVICE_ROOT),
        "testData": {
            "pdf": str(PDF_PATH),
            "pdfExists": PDF_PATH.exists(),
            "docx": str(DOCX_PATH),
            "docxExists": DOCX_PATH.exists(),
        },
        "environment": {
            "environment": settings.environment,
            "openaiModel": settings.openai_model,
            "openaiApiKeyPresent": bool(settings.openai_api_key),
            "localOnly": local_only,
            "runFullLegacyAgentic": run_full_legacy,
            "documentExtractorProvider": settings.document_extractor_provider,
            "documentExtractorRoot": str(settings.resolved_document_extractor_root),
        },
        "outputs": {},
    }

    if not PDF_PATH.exists():
        write_json(output_dir / "manifest.json", {**manifest, "fatal": "PDF sample file not found."})
        return 1

    extraction = run_case(output_dir, "01_resume_extractor_pdf.json", local_extract_pdf if local_only else extract_pdf)
    manifest["outputs"]["resumeExtractorPdf"] = "01_resume_extractor_pdf.json"

    docx_result = run_case(
        output_dir,
        "01b_resume_extractor_docx.json",
        local_extract_docx if local_only else extract_docx_unsupported,
    )
    manifest["outputs"]["resumeExtractorDocx"] = "01b_resume_extractor_docx.json"

    legacy_probe = run_case(
        output_dir,
        "01c_legacy_agentic_pipeline_probe.json",
        run_legacy_agentic_probe if run_full_legacy else run_legacy_agentic_health_probe,
    )
    manifest["outputs"]["legacyAgenticPipelineProbe"] = "01c_legacy_agentic_pipeline_probe.json"

    structured_resume = structured_resume_from(extraction)
    agent = AIServiceAgent()
    jobs = sample_jobs()

    run_case(
        output_dir,
        "02_resume_analyzer.json",
        lambda: agent.run(
            "resume_analyzer",
            {
                "candidateId": "candidate_zarnab",
                "resumeId": "resume_zarnab",
                "structuredResume": structured_resume,
                "targetRole": "Backend AI Engineer",
                "targetJobDescription": jobs[0]["description"],
            },
        ),
    )
    manifest["outputs"]["resumeAnalyzer"] = "02_resume_analyzer.json"

    run_case(
        output_dir,
        "03_job_matcher.json",
        lambda: agent.run(
            "job_matcher",
            {
                "candidateId": "candidate_zarnab",
                "resumeId": "resume_zarnab",
                "structuredResume": structured_resume,
                "jobs": jobs,
                "filters": {"remote": True, "targetRole": "Backend AI Engineer"},
                "limit": 3,
            },
        ),
    )
    manifest["outputs"]["jobMatcher"] = "03_job_matcher.json"

    run_case(
        output_dir,
        "04_candidate_scorer.json",
        lambda: agent.run(
            "candidate_scorer",
            {
                "job": jobs[0],
                "applications": [
                    {"candidate_id": "candidate_zarnab", "resume_id": "resume_zarnab"},
                    {"candidate_id": "candidate_comparison", "resume_id": "resume_comparison"},
                ],
                "resumes": [
                    {"id": "resume_zarnab", "structured_data": structured_resume},
                    {"id": "resume_comparison", "structured_data": weaker_candidate_resume()},
                ],
            },
        ),
    )
    manifest["outputs"]["candidateScorer"] = "04_candidate_scorer.json"

    interview_generation = run_case(
        output_dir,
        "05_interview_generator.json",
        lambda: agent.run(
            "interview_generator",
            {
                "candidateId": "candidate_zarnab",
                "resumeId": "resume_zarnab",
                "jobId": jobs[0]["id"],
                "structuredResume": structured_resume,
                "job": jobs[0],
                "focusAreas": ["FastAPI", "Docker", "OpenAI", "LangGraph"],
            },
        ),
    )
    manifest["outputs"]["interviewGenerator"] = "05_interview_generator.json"

    question = "Explain how you would design a reliable resume extraction service."
    generated_result = interview_generation.get("result") or {}
    questions = generated_result.get("questions") or []
    if questions and isinstance(questions[0], dict) and questions[0].get("question"):
        question = str(questions[0]["question"])

    run_case(
        output_dir,
        "05b_mock_interview_evaluator.json",
        lambda: agent.run(
            "mock_interview_evaluator",
            {
                "interviewSessionId": "interview_zarnab_smoke",
                "question": question,
                "answer": (
                    "I would separate upload, extraction, validation, and persistence. "
                    "The backend stores the file and calls AI-Service. AI-Service extracts "
                    "structured fields, validates confidence, returns warnings, and the "
                    "backend persists the normalized resume. I would add retries, queueing, "
                    "tests, and human review for low confidence fields."
                ),
            },
        ),
    )
    manifest["outputs"]["mockInterviewEvaluator"] = "05b_mock_interview_evaluator.json"

    run_case(
        output_dir,
        "06_hiring_assistant.json",
        lambda: agent.run(
            "hiring_assistant",
            {
                "recruiterId": "recruiter_smoke",
                "companyId": "company_smoke",
                "message": "Show me candidates with Python, FastAPI, OpenAI, and Docker experience.",
                "context": {"jobId": jobs[0]["id"], "candidateCount": 2},
            },
        ),
    )
    manifest["outputs"]["hiringAssistant"] = "06_hiring_assistant.json"

    run_case(
        output_dir,
        "07_career_assistant.json",
        lambda: agent.run(
            "career_assistant",
            {
                "candidateId": "candidate_zarnab",
                "message": "How can I improve my resume for backend AI engineer jobs?",
                "context": {
                    "resumeId": "resume_zarnab",
                    "targetRole": "Backend AI Engineer",
                    "structuredResume": structured_resume,
                },
            },
        ),
    )
    manifest["outputs"]["careerAssistant"] = "07_career_assistant.json"

    statuses = {}
    for key, file_name in manifest["outputs"].items():
        payload = json.loads((output_dir / file_name).read_text(encoding="utf-8"))
        statuses[key] = payload.get("status")
    manifest["statuses"] = statuses
    manifest["completedAt"] = datetime.now(UTC).isoformat()
    write_json(output_dir / "manifest.json", manifest)
    print(json.dumps({"outputDir": str(output_dir), "statuses": statuses}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
