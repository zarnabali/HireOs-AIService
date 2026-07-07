from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def auth_headers() -> dict[str, str]:
    settings = get_settings()
    settings.ai_service_api_key = "test-key"
    return {"x-api-key": "test-key"}


def test_backend_ai_routes_are_registered() -> None:
    client = TestClient(app)
    routes = set(app.openapi()["paths"].keys())

    assert "/ai/resumes/analyze" in routes
    assert "/ai/jobs/match" in routes
    assert "/ai/candidates/score-batch" in routes
    assert "/ai/interviews/generate" in routes
    assert "/ai/interviews/mock/evaluate" in routes
    assert "/ai/recruiter/chat" in routes
    assert "/ai/candidate/chat" in routes
    assert "/ai/tasks/{task_id}" in routes

    response = client.post(
        "/ai/recruiter/chat",
        headers=auth_headers(),
        json={"message": "Find candidates with Python", "context": {}},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_resume_analyze_route_returns_backend_compatible_fields() -> None:
    client = TestClient(app)
    response = client.post(
        "/ai/resumes/analyze",
        headers=auth_headers(),
        json={
            "resumeId": "resume_1",
            "structuredResume": {
                "contact": {"email": "a@example.com"},
                "skills": ["Python", "AWS"],
                "experience": [],
                "education": [],
            },
            "targetRole": "Backend Engineer",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert isinstance(payload["score"], int)
    assert isinstance(payload["suggestions"], list)
    assert isinstance(payload["warnings"], list)


def test_all_backend_facing_ai_routes_return_success_envelopes() -> None:
    client = TestClient(app)
    headers = auth_headers()
    resume = {
        "contact": {"email": "jane@example.com"},
        "skills": ["Python", "FastAPI", "AWS", "Docker"],
        "experience": [{"achievements": ["Improved latency by 35%"]}],
        "education": [{"degree": "BS Computer Science"}],
    }

    cases = [
        (
            "/ai/jobs/match",
            {
                "candidateId": "cand_1",
                "resumeId": "resume_1",
                "structuredResume": resume,
                "jobs": [{"id": "job_1", "title": "Backend", "description": "Python FastAPI AWS"}],
                "filters": {},
                "limit": 5,
            },
        ),
        (
            "/ai/candidates/score-batch",
            {
                "job": {"id": "job_1", "description": "Python FastAPI AWS"},
                "applications": [{"candidate_id": "cand_1", "resume_id": "resume_1"}],
                "resumes": [{"id": "resume_1", "structured_data": resume}],
            },
        ),
        (
            "/ai/interviews/generate",
            {"candidateId": "cand_1", "resumeId": "resume_1", "structuredResume": resume, "focusAreas": ["FastAPI"]},
        ),
        (
            "/ai/interviews/mock/evaluate",
            {
                "interviewSessionId": "int_1",
                "question": "Explain FastAPI.",
                "answer": "FastAPI is a Python framework for APIs. I used it with dependency injection and tests.",
            },
        ),
        (
            "/ai/candidate/chat",
            {"candidateId": "cand_1", "message": "Help me prepare for interviews", "context": {"resumeId": "resume_1"}},
        ),
    ]

    for path, payload in cases:
        response = client.post(path, headers=headers, json=payload)
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True
