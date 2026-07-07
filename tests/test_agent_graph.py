from app.agents import AIServiceAgent


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


def assert_agent_metadata(result: dict, feature: str, tool_name: str) -> None:
    assert result["success"] is True
    assert result["agent"]["feature"] == feature
    assert result["agent"]["toolName"] == tool_name
    assert result["agent"]["status"] == "success"
    assert result["agent"]["graph"] == "hireos_ai_service_agent"


def test_resume_analyzer_runs_through_agent_tool() -> None:
    result = AIServiceAgent().run(
        "resume_analyzer",
        {
            "resumeId": "resume_1",
            "structuredResume": sample_resume(),
            "targetRole": "Backend Engineer",
            "targetJobDescription": sample_job()["description"],
        },
    )

    assert_agent_metadata(result, "resume_analyzer", "analyze_resume")
    assert result["score"] >= 70
    assert result["breakdown"]["skillsCoverage"] >= 0


def test_job_matcher_runs_through_agent_tool() -> None:
    result = AIServiceAgent().run(
        "job_matcher",
        {
            "structuredResume": sample_resume(),
            "jobs": [
                sample_job(),
                {"id": "job_2", "title": "Designer", "description": "Figma brand systems"},
            ],
            "limit": 2,
        },
    )

    assert_agent_metadata(result, "job_matcher", "match_jobs_to_candidate")
    assert result["matches"][0]["jobId"] == "job_1"


def test_candidate_scorer_runs_through_agent_tool() -> None:
    result = AIServiceAgent().run(
        "candidate_scorer",
        {
            "job": sample_job(),
            "applications": [{"candidate_id": "cand_1", "resume_id": "resume_1"}],
            "resumes": [{"id": "resume_1", "structured_data": sample_resume()}],
        },
    )

    assert_agent_metadata(result, "candidate_scorer", "score_candidate_batch")
    assert result["rankings"][0]["candidateId"] == "cand_1"


def test_interview_features_run_through_agent_tools() -> None:
    generated = AIServiceAgent().run(
        "interview_generator",
        {
            "structuredResume": sample_resume(),
            "job": sample_job(),
            "focusAreas": ["FastAPI"],
        },
    )
    assert_agent_metadata(generated, "interview_generator", "generate_interview_kit")
    assert generated["questions"]

    evaluated = AIServiceAgent().run(
        "mock_interview_evaluator",
        {
            "interviewSessionId": "int_1",
            "question": "Explain FastAPI dependency injection.",
            "answer": (
                "FastAPI dependency injection lets us declare reusable providers for "
                "auth, database sessions, and services. For example, I used it to "
                "share a session factory and improved testability."
            ),
        },
    )
    assert_agent_metadata(evaluated, "mock_interview_evaluator", "evaluate_interview_response")
    assert evaluated["score"] >= 60


def test_chat_features_run_through_agent_tools() -> None:
    recruiter = AIServiceAgent().run(
        "hiring_assistant",
        {
            "recruiterId": "rec_1",
            "message": "Show me candidates with React and AWS experience.",
            "context": {"jobId": "job_1"},
        },
    )
    assert_agent_metadata(recruiter, "hiring_assistant", "recruiter_assistant_chat")
    assert recruiter["intent"] == "search_candidates"

    candidate = AIServiceAgent().run(
        "career_assistant",
        {
            "candidateId": "cand_1",
            "message": "How can I improve my resume for backend jobs?",
            "context": {"resumeId": "resume_1"},
        },
    )
    assert_agent_metadata(candidate, "career_assistant", "candidate_career_chat")
    assert candidate["intent"] == "resume_advice"


def test_unknown_agent_feature_returns_typed_error() -> None:
    result = AIServiceAgent().run("unknown_feature", {})

    assert result["success"] is False
    assert result["agent"]["status"] == "failed"
    assert result["error"]["code"] == "UNKNOWN_AGENT_FEATURE"
