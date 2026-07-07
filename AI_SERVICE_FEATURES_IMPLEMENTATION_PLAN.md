# AI-Service Features Implementation Plan

## Purpose

This document defines how the `AI-Service` module will own all AI features for HireOS and how the existing `AI-Service/Agentic-Document-Extraction-PDF` project will be converted from a standalone document extraction product into one internal AI feature: **AI Resume Extractor**.

The current extraction project is valuable, but it should not remain a separate product surface with its own frontend, dashboard, auth model, and product routes. It should become a reusable service module called by the main `AI-Service` FastAPI application.

## Final Service Boundary

```text
frontend/  ->  backend/  ->  AI-Service/
Next.js        Node.js       FastAPI + LangGraph + OpenAI + Celery + Redis
```

Rules:

- `frontend` calls `backend` only.
- `backend` owns Supabase CRUD and storage.
- `backend` calls `AI-Service` through internal HTTP APIs.
- `AI-Service` owns AI execution only.
- `AI-Service` returns structured results; `backend` validates and persists them.
- `AI-Service/Agentic-Document-Extraction-PDF` is an internal implementation dependency for resume/document extraction.

## Target `AI-Service` Folder Structure

```text
AI-Service/
  app/
    main.py
    api/
      routes/
        health.py
        resumes.py
        jobs.py
        candidates.py
        interviews.py
        chats.py
        tasks.py
    core/
      config.py
      logging.py
      errors.py
      security.py
    schemas/
      common.py
      resumes.py
      jobs.py
      candidates.py
      interviews.py
      chats.py
      tasks.py
    services/
      resume_extractor_service.py
      resume_analyzer_service.py
      job_matcher_service.py
      candidate_scorer_service.py
      interview_service.py
      hiring_assistant_service.py
      career_assistant_service.py
    agents/
      graph.py
      state.py
      router.py
      candidate_graph.py
      recruiter_graph.py
      tools/
    clients/
      openai_client.py
    queues/
      celery_app.py
      redis.py
    workers/
      resume_tasks.py
      scoring_tasks.py
      interview_tasks.py
      chat_tasks.py
    integrations/
      document_extraction/
        adapter.py
        normalizer.py
        schemas.py
        errors.py
  Agentic-Document-Extraction-PDF/
  tests/
    unit/
    integration/
```

## Converting `Agentic-Document-Extraction-PDF`

### Current Problem

`Agentic-Document-Extraction-PDF` is currently shaped like a full product:

- It has its own FastAPI API.
- It has a Next.js frontend.
- It has product docs, dashboards, auth, queue routes, health routes, and exports.
- It supports many document profiles, including healthcare and finance.

For HireOS, this is too broad. The needed feature is:

```text
Resume PDF/DOCX/image extraction -> structured resume profile
```

### Target Role

Use it as an internal extraction engine behind:

```text
AI-Service/app/integrations/document_extraction/adapter.py
```

The adapter should expose a narrow API:

```python
extract_resume(file_path: str, options: ResumeExtractionOptions) -> ResumeExtractionResult
extract_resume_batch(items: list[ResumeExtractionJob]) -> list[ResumeExtractionResult]
```

Do not expose the old Veridoc frontend or product API to `backend`.

### Conversion Steps

1. Keep the existing folder in place:

```text
AI-Service/Agentic-Document-Extraction-PDF/
```

2. Create an adapter layer:

```text
AI-Service/app/integrations/document_extraction/adapter.py
```

3. Import the extraction pipeline from the existing code, preferably `PipelineRunner` or a stable CLI/service boundary.

4. Force extraction into a HireOS resume schema:

```text
contact
skills
experience
education
projects
certifications
languages
achievements
links
raw_sections
confidence
warnings
provenance
```

5. Disable or ignore standalone product surfaces:

- Do not use its Next.js frontend.
- Do not expose its dashboard routes as the HireOS user-facing API.
- Do not let it write directly to Supabase.
- Do not let its healthcare/FHIR exports become part of the resume flow.

6. Wrap failures in AI-Service error envelopes:

```json
{
  "success": false,
  "error": {
    "code": "resume_extraction_failed",
    "message": "Extraction failed",
    "details": {}
  }
}
```

7. Add tests at the AI-Service adapter level:

- Extract from a sample resume PDF.
- Normalize empty/missing sections.
- Return confidence and warnings.
- Fail cleanly on unsupported/invalid files.

### AI Resume Extractor API

Internal AI-Service endpoint:

```text
POST /ai/resumes/extract
```

Request from backend:

```json
{
  "document_id": "doc_123",
  "candidate_id": "cand_123",
  "file_path": "/tmp/hireos/doc_123.pdf",
  "source_mime_type": "application/pdf",
  "options": {
    "include_provenance": true,
    "include_raw_text": false,
    "language": "en"
  }
}
```

Response to backend:

```json
{
  "success": true,
  "document_id": "doc_123",
  "candidate_id": "cand_123",
  "structured_resume": {
    "contact": {},
    "skills": [],
    "experience": [],
    "education": [],
    "projects": [],
    "certifications": [],
    "languages": [],
    "achievements": [],
    "links": []
  },
  "confidence": {
    "overall": 0.87,
    "fields": {}
  },
  "warnings": [],
  "review_required": false
}
```

### Backend Responsibility

Backend endpoint:

```text
POST /api/resumes/upload
```

Backend flow:

1. Authenticate candidate/recruiter.
2. Validate file.
3. Upload raw file to Supabase Storage.
4. Create `documents` row.
5. Download or stage file for AI-Service.
6. Call `POST /ai/resumes/extract`.
7. Validate AI response with Zod.
8. Insert/update:
   - `document_extractions`
   - `resumes`
   - `resume_versions`
9. Return structured profile to frontend.

For recruiter bulk uploads, backend should queue extraction with AI-Service and track task status.

## Shared AI-Service Standards

All 7 features must follow these standards.

### Endpoint Style

Use `/ai/*` internal endpoints:

```text
POST /ai/resumes/extract
POST /ai/resumes/analyze
POST /ai/jobs/match
POST /ai/candidates/score
POST /ai/interviews/generate
POST /ai/interviews/mock/evaluate
POST /ai/recruiter/chat
POST /ai/candidate/chat
GET  /ai/tasks/{task_id}
```

### Response Envelope

Every response should use:

```json
{
  "success": true,
  "data": {},
  "confidence": 0.0,
  "warnings": [],
  "review_required": false,
  "error": null
}
```

### Async Rule

Use Celery/Redis for:

- Bulk resume extraction.
- Bulk candidate scoring.
- Long interview reports.
- Large recruiter search/chat operations.
- Multi-step agent workflows.

Use sync FastAPI for:

- Single resume analysis.
- Single job match.
- Single candidate score.
- Generating small interview question sets.
- Chat turns when response time is acceptable.

### Backend Persistence Rule

AI-Service does not own product persistence. Backend persists:

- Resume extraction results.
- Scores.
- Job matches.
- Interview questions.
- Mock interview evaluations.
- Chat transcripts.
- Audit logs.

AI-Service may store temporary task status in Redis/Celery, but product truth belongs in Supabase through backend.

## Feature 1: AI Resume Extractor

### Goal

Extract structured resume data from PDF/DOCX/images.

### Inputs

```json
{
  "document_id": "doc_123",
  "candidate_id": "cand_123",
  "file_path": "/tmp/resume.pdf",
  "source_mime_type": "application/pdf"
}
```

### AI-Service Components

```text
schemas/resumes.py
services/resume_extractor_service.py
integrations/document_extraction/adapter.py
integrations/document_extraction/normalizer.py
workers/resume_tasks.py
api/routes/resumes.py
```

### Implementation Plan

1. Define `ResumeExtractionRequest`, `StructuredResume`, and `ResumeExtractionResponse` Pydantic schemas.
2. Build `DocumentExtractionAdapter`.
3. Call existing `Agentic-Document-Extraction-PDF` pipeline through adapter.
4. Normalize extracted output into `StructuredResume`.
5. Add confidence and warnings.
6. Expose `POST /ai/resumes/extract`.
7. Add Celery task `extract_resume_task`.
8. Add tests for PDF success, bad file failure, missing fields, and normalization.

### Backend Contract

Backend calls:

```text
POST AI_SERVICE_URL/ai/resumes/extract
```

Backend persists:

- `documents`
- `document_extractions`
- `resumes`
- `resume_versions`

Backend returns parsed resume to frontend.

## Feature 2: AI Resume Analyzer and ATS Score

### Goal

Analyze a structured resume for quality, ATS compatibility, keyword coverage, grammar, formatting issues, and improvement suggestions.

### Inputs

```json
{
  "candidate_id": "cand_123",
  "resume_id": "resume_123",
  "structured_resume": {},
  "target_role": "Backend Engineer",
  "target_job_description": null
}
```

### AI-Service Components

```text
schemas/resumes.py
services/resume_analyzer_service.py
agents/tools/resume_analysis_tools.py
api/routes/resumes.py
```

### Scoring Dimensions

- ATS compatibility.
- Skills coverage.
- Experience clarity.
- Measurable achievements.
- Grammar and wording.
- Role alignment.
- Formatting risk.
- Missing sections.

### Implementation Plan

1. Define deterministic scoring rubric.
2. Use LLM only for critique and rewrite suggestions.
3. Add `ResumeAnalysisRequest` and `ResumeAnalysisResponse`.
4. Build service that combines:
   - deterministic checks
   - keyword analysis
   - LLM improvement suggestions
5. Return score breakdown, not only one score.
6. Expose `POST /ai/resumes/analyze`.
7. Add tests for score stability and response schema.

### Backend Contract

Backend sends structured resume from Supabase to AI-Service.

Backend persists:

- `resume_scores`
- `resume_improvement_suggestions`

Frontend displays:

- resume score
- breakdown
- suggestions
- rewrite examples

## Feature 3: AI Job Matcher

### Goal

Match candidates to relevant jobs and explain why each job fits.

### Inputs

```json
{
  "candidate_id": "cand_123",
  "resume_id": "resume_123",
  "structured_resume": {},
  "jobs": [
    {
      "job_id": "job_123",
      "title": "Backend Engineer",
      "description": "...",
      "requirements": []
    }
  ],
  "filters": {
    "remote": true,
    "min_salary": 100000
  }
}
```

### AI-Service Components

```text
schemas/jobs.py
services/job_matcher_service.py
agents/tools/job_match_tools.py
api/routes/jobs.py
```

### Implementation Plan

1. Backend performs SQL and pgvector candidate/job retrieval.
2. Backend sends a bounded candidate resume and candidate job list to AI-Service.
3. AI-Service computes deterministic requirement overlap.
4. AI-Service uses LLM to explain matches and missing skills.
5. Return ranked jobs with evidence.
6. Expose `POST /ai/jobs/match`.
7. Add tests for deterministic score math and explanation shape.

### Backend Contract

Backend owns job retrieval from Supabase.

Backend persists:

- `candidate_job_matches`
- optional `saved_jobs` if user saves a match

Frontend displays:

- match score
- matched skills
- missing skills
- explanation

## Feature 4: AI Candidate Scorer

### Goal

Score candidate resumes against a recruiter job posting and rank applicants.

### Inputs

```json
{
  "job_id": "job_123",
  "job": {},
  "candidates": [
    {
      "candidate_id": "cand_1",
      "resume_id": "resume_1",
      "structured_resume": {}
    }
  ]
}
```

### AI-Service Components

```text
schemas/candidates.py
services/candidate_scorer_service.py
workers/scoring_tasks.py
api/routes/candidates.py
```

### Implementation Plan

1. Define score rubric:
   - must-have skills
   - nice-to-have skills
   - experience years
   - seniority alignment
   - project relevance
   - domain relevance
   - certifications
2. Build single candidate scoring endpoint:

```text
POST /ai/candidates/score
```

3. Build batch candidate scoring endpoint:

```text
POST /ai/candidates/score-batch
```

4. Use Celery for batch scoring.
5. Return ranked list and explanation for each candidate.
6. Add tests for score determinism and no protected-attribute fields.

### Backend Contract

Backend gathers job and candidate resume records from Supabase.

Backend calls AI-Service for scores.

Backend persists:

- `candidate_job_scores`
- `candidate_rankings`
- `shortlists`

Frontend displays:

- ranked candidates
- why score
- concerns
- interview focus

## Feature 5: AI Interview Generator and Mock Interview

### Goal

Generate role/candidate-specific interview questions and conduct mock interviews with feedback.

### Inputs

Question generation:

```json
{
  "candidate_id": "cand_123",
  "resume_id": "resume_123",
  "job_id": "job_123",
  "structured_resume": {},
  "job": {},
  "focus_areas": ["FastAPI", "Docker", "AWS"]
}
```

Mock response evaluation:

```json
{
  "interview_session_id": "int_123",
  "question_id": "q_123",
  "question": "Explain dependency injection in FastAPI.",
  "answer": "..."
}
```

### AI-Service Components

```text
schemas/interviews.py
services/interview_service.py
workers/interview_tasks.py
api/routes/interviews.py
```

### Implementation Plan

1. Define interview question schema:
   - question
   - type
   - difficulty
   - skill tested
   - rubric
   - expected signals
2. Generate interview kits from resume + job.
3. Add mock interview turn evaluator.
4. Score technical accuracy, clarity, communication, confidence, and completeness.
5. Return feedback and suggested next question.
6. Expose:

```text
POST /ai/interviews/generate
POST /ai/interviews/mock/evaluate
POST /ai/interviews/mock/final-report
```

7. Use Celery for final report generation.
8. Add tests for schema, scoring bands, and safe feedback.

### Backend Contract

Backend persists:

- `interview_questions`
- `mock_interviews`
- `mock_interview_messages`
- `mock_interview_evaluations`

Frontend displays:

- question set
- live mock interview
- final report

## Feature 6: AI Hiring Assistant

### Goal

Provide recruiter chat for searching candidates, comparing applicants, summarizing resumes, creating shortlists, and answering hiring questions.

### Example

Recruiter asks:

```text
Show me candidates with React and AWS experience.
```

### Inputs

```json
{
  "recruiter_id": "rec_123",
  "company_id": "comp_123",
  "message": "Show me candidates with React and AWS experience.",
  "context": {
    "job_id": "job_123"
  }
}
```

### AI-Service Components

```text
schemas/chats.py
services/hiring_assistant_service.py
agents/recruiter_graph.py
agents/tools/recruiter_tools.py
api/routes/chats.py
workers/chat_tasks.py
```

### Implementation Plan

1. Build recruiter assistant LangGraph.
2. Define allowed intents:
   - search candidates
   - summarize candidate
   - compare candidates
   - create shortlist
   - generate interview focus
3. Backend supplies scoped data or search results.
4. AI-Service produces answer and structured action suggestions.
5. Never let AI-Service bypass backend permissions.
6. Expose:

```text
POST /ai/recruiter/chat
```

7. Add tests for intent routing, response shape, and permission-safe data boundaries.

### Backend Contract

Backend:

1. Authenticates recruiter.
2. Checks company/job access.
3. Retrieves scoped candidate/job context.
4. Calls AI-Service.
5. Persists conversation.
6. Executes any approved follow-up action itself.

Backend persists:

- `conversations`
- `conversation_messages`
- `assistant_actions`
- optional `shortlists`

## Feature 7: AI Career Assistant

### Goal

Provide candidate chat for resume improvement, job discovery, interview prep, and career planning.

### Example

Candidate asks:

```text
How can I improve my chances of getting a backend developer job?
```

### Inputs

```json
{
  "candidate_id": "cand_123",
  "message": "How can I improve my chances of getting a backend developer job?",
  "context": {
    "resume_id": "resume_123",
    "target_role": "Backend Developer"
  }
}
```

### AI-Service Components

```text
schemas/chats.py
services/career_assistant_service.py
agents/candidate_graph.py
agents/tools/candidate_tools.py
api/routes/chats.py
workers/chat_tasks.py
```

### Implementation Plan

1. Build candidate assistant LangGraph.
2. Define allowed intents:
   - resume advice
   - job search help
   - skill roadmap
   - interview prep
   - career direction
3. Backend supplies candidate-owned context only.
4. AI-Service returns answer plus structured recommended actions.
5. Expose:

```text
POST /ai/candidate/chat
```

6. Add tests for safe advice, schema output, and no unauthorized context access.

### Backend Contract

Backend:

1. Authenticates candidate.
2. Loads candidate resume, job matches, applications, and mock interview history.
3. Calls AI-Service.
4. Persists chat.
5. Optionally creates recommended tasks or saved jobs.

Backend persists:

- `conversations`
- `conversation_messages`
- `career_recommendations`
- `candidate_action_items`

## AI-Service Pipeline Architecture

### Synchronous Path

Use for small tasks.

```text
backend
  -> POST /ai/resumes/analyze
  -> AI-Service service
  -> OpenAI client / deterministic scoring
  -> response
  -> backend persists
```

### Asynchronous Path

Use for long tasks.

```text
backend
  -> POST /ai/candidates/score-batch
  -> AI-Service creates Celery task
  -> returns task_id
backend
  -> polls GET /ai/tasks/{task_id}
worker
  -> processes task
  -> returns result
backend
  -> persists result
```

### LangGraph Path

Use for multi-step chat/workflows.

```text
backend sends scoped context
  -> AI-Service graph router
  -> intent node
  -> tool node
  -> validation node
  -> response node
  -> backend persists conversation/action
```

## Backend API Mapping

| Frontend action | Backend endpoint | AI-Service endpoint | Backend persistence |
|---|---|---|---|
| Upload resume | `POST /api/resumes/upload` | `POST /ai/resumes/extract` | `documents`, `document_extractions`, `resumes` |
| Analyze resume | `POST /api/resumes/:id/analyze` | `POST /ai/resumes/analyze` | `resume_scores` |
| Match jobs | `POST /api/jobs/matches` | `POST /ai/jobs/match` | `candidate_job_matches` |
| Score applicants | `POST /api/jobs/:id/score-candidates` | `POST /ai/candidates/score-batch` | `candidate_job_scores`, `candidate_rankings` |
| Generate interview | `POST /api/interviews/generate` | `POST /ai/interviews/generate` | `interview_questions` |
| Evaluate mock answer | `POST /api/interviews/:id/evaluate` | `POST /ai/interviews/mock/evaluate` | `mock_interview_evaluations` |
| Recruiter chat | `POST /api/recruiter/chat` | `POST /ai/recruiter/chat` | `conversations`, `assistant_actions` |
| Candidate chat | `POST /api/candidate/chat` | `POST /ai/candidate/chat` | `conversations`, `career_recommendations` |

## Implementation Phases

### Phase 1: AI-Service Foundation

- Create `AI-Service/app`.
- Add FastAPI `main.py`.
- Add config, logging, errors, health route.
- Add OpenAI client wrapper.
- Add Pydantic response envelope.
- Add Celery and Redis setup.
- Add task status route.

### Phase 2: Resume Extractor Conversion

- Create document extraction adapter.
- Integrate `Agentic-Document-Extraction-PDF`.
- Normalize output into `StructuredResume`.
- Add `/ai/resumes/extract`.
- Add `extract_resume_task`.
- Add tests.

### Phase 3: Resume Analyzer

- Add deterministic rubric.
- Add LLM suggestions.
- Add `/ai/resumes/analyze`.
- Add backend persistence contract.

### Phase 4: Matching and Scoring

- Add job matcher.
- Add candidate scorer.
- Add batch scoring worker.
- Add score evidence output.

### Phase 5: Interview AI

- Add interview generator.
- Add mock interview evaluator.
- Add final report worker.

### Phase 6: Chat Assistants

- Add recruiter graph.
- Add candidate graph.
- Add tool registry.
- Add conversation response schema.

### Phase 7: Hardening

- Add integration tests with backend mock client.
- Add queue retry policies.
- Add rate limits.
- Add prompt/version tracking.
- Add model cost/latency logs.
- Add privacy filtering and no-protected-attribute checks.

## What Not To Do

- Do not keep `Agentic-Document-Extraction-PDF` as a separate user-facing product.
- Do not use its frontend in HireOS.
- Do not call it from frontend.
- Do not let AI-Service write product records directly to Supabase.
- Do not let LLM output directly become final candidate decisions.
- Do not build one giant chat endpoint that handles all AI features without typed tools.

## First Build Target

Build this vertical slice first:

```text
backend uploads/stages resume
  -> AI-Service /ai/resumes/extract
  -> document extraction adapter
  -> structured resume response
  -> backend validates and persists
  -> frontend displays parsed resume
```

Only after that is stable, build:

```text
resume analyzer -> job matcher -> candidate scorer -> interview generator -> recruiter chat -> career chat
```
