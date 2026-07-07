from app.services.candidate_scorer_service import CandidateScorerService
from app.services.chat_services import CareerAssistantService, HiringAssistantService
from app.services.interview_service import InterviewService
from app.services.job_matcher_service import JobMatcherService
from app.services.resume_analyzer_service import ResumeAnalyzerService


def sample_resume() -> dict:
    return {
        "contact": {"full_name": "Jane Doe", "email": "jane@example.com"},
        "summary": "Backend engineer building Python APIs.",
        "skills": ["Python", "FastAPI", "AWS", "Docker", "Postgres", "Redis"],
        "experience": [
            {
                "company": "Acme",
                "title": "Backend Engineer",
                "achievements": ["Improved API latency by 35%", "Supported 1M requests/day"],
            }
        ],
        "education": [{"institution": "State University", "degree": "BS Computer Science"}],
        "projects": [{"name": "Hiring agent", "technologies": ["LangGraph", "OpenAI"]}],
    }


def sample_job() -> dict:
    return {
        "id": "job_1",
        "title": "Backend Engineer",
        "description": "Python FastAPI AWS Docker Postgres Redis Kubernetes APIs",
        "requirements": ["Python", "FastAPI", "AWS", "Docker", "Kubernetes"],
    }


def test_resume_analyzer_returns_score_breakdown_and_suggestions() -> None:
    result = ResumeAnalyzerService().analyze(
        {
            "resumeId": "resume_1",
            "structuredResume": sample_resume(),
            "targetRole": "Backend Engineer",
            "targetJobDescription": sample_job()["description"],
        }
    )

    assert result["success"] is True
    assert result["score"] >= 70
    assert "skillsCoverage" in result["breakdown"]
    assert isinstance(result["suggestions"], list)


def test_job_matcher_ranks_relevant_jobs() -> None:
    result = JobMatcherService().match(
        {
            "structuredResume": sample_resume(),
            "jobs": [
                sample_job(),
                {"id": "job_2", "title": "Designer", "description": "Figma brand systems"},
            ],
            "limit": 2,
        }
    )

    assert result["matches"][0]["jobId"] == "job_1"
    assert result["matches"][0]["matchScore"] > result["matches"][1]["matchScore"]
    assert "Python" in [skill.title() for skill in result["matches"][0]["matchedSkills"]]
    assert result["matches"][0]["reasons"]
    assert "evidence" in result["matches"][0]


def test_job_matcher_does_not_require_llm_for_explanations() -> None:
    result = JobMatcherService().match(
        {
            "structuredResume": sample_resume(),
            "jobs": [sample_job()],
            "filters": {"remoteType": "remote"},
            "limit": 1,
        }
    )

    assert result["success"] is True
    assert result["matches"][0]["matchScore"] >= 70
    assert result["matches"][0]["reasons"][0].startswith("Backend Engineer match is based on")


def test_job_matcher_uses_candidate_resume_profile_not_generic_scores() -> None:
    backend_resume_result = JobMatcherService().match(
        {
            "structuredResume": sample_resume(),
            "jobs": [
                sample_job(),
                {"id": "job_2", "title": "Product Designer", "description": "Figma brand systems wireframes user research"},
            ],
            "limit": 2,
        }
    )
    designer_resume_result = JobMatcherService().match(
        {
            "structuredResume": {
                "summary": "Product designer focused on Figma, design systems, wireframes, and user research.",
                "skills": ["Figma", "User Research", "Wireframes", "Design Systems"],
                "experience": [{"title": "Product Designer", "achievements": ["Led usability research for 20 customer interviews"]}],
                "projects": [{"name": "Brand system", "technologies": ["Figma"]}],
            },
            "jobs": [
                sample_job(),
                {"id": "job_2", "title": "Product Designer", "description": "Figma brand systems wireframes user research"},
            ],
            "limit": 2,
        }
    )

    assert backend_resume_result["matches"][0]["jobId"] == "job_1"
    assert designer_resume_result["matches"][0]["jobId"] == "job_2"


def test_candidate_scorer_returns_rankings_with_evidence() -> None:
    result = CandidateScorerService().score_batch(
        {
            "job": sample_job(),
            "applications": [{"candidate_id": "cand_1", "resume_id": "resume_1"}],
            "resumes": [{"id": "resume_1", "structured_data": sample_resume()}],
        }
    )

    ranking = result["rankings"][0]
    assert ranking["candidateId"] == "cand_1"
    assert ranking["score"] >= 70
    assert ranking["evidence"]["skills"]
    assert "Kubernetes" in ranking["interviewFocus"]


def test_interview_service_generates_and_evaluates() -> None:
    generated = InterviewService().generate(
        {
            "structuredResume": sample_resume(),
            "job": sample_job(),
            "focusAreas": ["FastAPI"],
            "difficulty": "hard",
            "questionCount": 8,
        }
    )
    assert generated["questions"]
    assert generated["questions"][0]["rubric"]
    question_texts = [item["question"] for item in generated["questions"]]
    assert len(question_texts) == len(set(question_texts))
    assert len({item["type"] for item in generated["questions"]}) >= 4
    assert any(item["difficulty"] == "hard" for item in generated["questions"])

    evaluated = InterviewService().evaluate_mock_answer(
        {
            "interviewSessionId": "int_1",
            "question": "Explain FastAPI dependency injection.",
            "answer": "FastAPI dependency injection lets us declare reusable providers for auth, database sessions, and services. For example, I used it to share a session factory and improved testability.",
        }
    )
    assert evaluated["score"] >= 60
    assert evaluated["data"]["feedback"]


def test_hiring_assistant_returns_structured_actions() -> None:
    result = HiringAssistantService().chat(
        {
            "recruiterId": "rec_1",
            "message": "Show me candidates with React and AWS experience.",
            "context": {"jobId": "job_1"},
        }
    )

    assert result["intent"] == "search_candidates"
    assert result["actions"][0]["requiresBackendExecution"] is True


def test_career_assistant_returns_candidate_safe_actions() -> None:
    result = CareerAssistantService().chat(
        {
            "candidateId": "cand_1",
            "message": "How can I improve my resume for backend jobs?",
            "context": {"resumeId": "resume_1"},
        }
    )

    assert result["intent"] == "resume_advice"
    assert result["actions"][0]["type"] == "analyze_resume"
