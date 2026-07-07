# HireOS AI Hiring Agent Guide for Agentic Document Extraction

## Purpose

This repository is a full-stack document intelligence system named **Veridoc**. It converts PDFs, scans, images, spreadsheets, DOCX files, and some healthcare/finance formats into structured extraction results using a local vision language model, schema selection, validation, confidence scoring, provenance metadata, and optional exports.

For HireOS, the useful role is a document intake and evidence extraction layer for an AI hiring agent. The hiring agent should not ask a model to read raw resumes, offer letters, certificates, or background-check PDFs directly every time. Instead, it should send the file to Veridoc, receive structured JSON plus confidence and provenance, then reason over that normalized data.

This guide explains what the project is, how it works, how to set it up, and how to use it safely in hiring workflows.

## What This Project Is

Veridoc is not just a PDF parser. It is an agentic extraction pipeline with these major parts:

| Area | What it does | Key files |
|---|---|---|
| CLI and dev launcher | Runs extraction, batch extraction, backend, and frontend | `main.py` |
| Backend API | FastAPI app with document, task, schema, health, auth, dashboard, queue, and webhook routes | `src/api/app.py`, `src/api/routes/` |
| Pipeline runner | Converts documents into page images and runs the extraction workflow | `src/pipeline/runner.py` |
| Agents | Analyze, split, extract, validate, reconcile, detect tables/components, and route human review | `src/agents/` |
| VLM client | Talks to an OpenAI-compatible local vision model, mainly LM Studio by default | `src/client/lm_client.py` |
| Profiles | Determines document domain such as generic, finance, or medical-RCM | `src/profiles/` |
| Schemas | Built-in schemas for invoices, W-2, 1099, bank statements, medical forms, and generic fallback | `src/schemas/` |
| Preprocessing | Renders PDFs, DOCX, images, spreadsheets, DICOM, and EDI-like files into page images | `src/preprocessing/` |
| Exports | Writes JSON, Excel, Markdown, FHIR, bbox overlays, and signed receipts | `src/export/` |
| Frontend | Next.js app for upload, dashboard, document review, task queue, settings, and source view | `frontend/` |

The current built-in profiles are:

- `generic-document`: default fallback for unknown documents.
- `finance`: W-2, 1099, invoices, bank statements, and similar financial docs.
- `medical-rcm`: CMS-1500, UB-04, EOB, superbills, and healthcare revenue-cycle docs.

For HireOS, most resume and hiring documents should use `generic-document` unless you add a dedicated hiring profile.

## Why It Matters for HireOS

An AI hiring agent needs repeatable, inspectable document understanding. Raw LLM reading is risky because it can hallucinate fields, ignore page evidence, and produce inconsistent outputs. Veridoc helps by:

- Converting documents into images and text snippets before extraction.
- Producing structured fields and per-field confidence.
- Supporting validation and human-review routing.
- Preserving output artifacts for audit and review.
- Providing batch and async processing for high-volume intake.
- Supporting local inference, which is important for private candidate data.

In HireOS, Veridoc can become the **document extraction microservice**. The hiring agent remains responsible for decisions, ranking, policy, scoring, and conversation. Veridoc should be responsible for turning uploaded candidate documents into structured evidence.

## How The Pipeline Works

The core flow is:

1. A file enters through CLI, API, upload endpoint, or batch command.
2. `PipelineRunner` validates the file and converts each page to a base64 PNG image.
3. The analyzer classifies document type and decides profile/schema.
4. Extraction agents call the configured vision model through `LMStudioClient`.
5. Validation checks confidence, field formats, patterns, and cross-field consistency.
6. The orchestrator decides whether the extraction is complete, retryable, failed, or needs human review.
7. Results are returned through API or written to output files.

Supported upload extensions in the API include:

```text
.pdf, .png, .jpg, .jpeg, .tiff, .tif, .bmp,
.docx, .doc, .xlsx, .csv,
.dcm, .dicom, .edi, .x12, .835, .837
```

The async Celery task path currently accepts a narrower image/PDF set in `src/queue/tasks.py`: PDF plus common image formats. For broad file support, prefer the sync path or confirm the async path supports the format you need before relying on it.

## Setup

### Prerequisites

- Python 3.11 or newer.
- Node.js 18 or newer for the frontend.
- A local OpenAI-compatible vision model endpoint, usually LM Studio at `http://localhost:1234/v1`.
- A vision-capable model loaded in LM Studio. The repo examples mention Qwen/Gemma-style VLMs; the active `config.json` uses `google/gemma-4-26b-a4b`.
- Redis if you want Celery async workers and queues. Sync CLI/API can run without Redis.

### Backend Install

From the repository root:

```bash
cd "D:\Pyhton AI\HireOS\Agentic-Document-Extraction-PDF"
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Optional extras:

```bash
pip install -e ".[dev,phi]"            # PHI/PII redaction support
pip install -e ".[dev,observability]"  # Phoenix/PostHog tracing
pip install -e ".[dev,fhir]"           # validated FHIR export
```

For HireOS, start with `.[dev]`. Add `phi` only if you want the heavier ML privacy redaction path.

### Frontend Install

```bash
cd frontend
npm install
```

The frontend expects the backend at localhost. The launcher sets `NEXT_PUBLIC_API_URL=http://localhost:8000`; the frontend README also mentions `http://localhost:8000/api`, so verify the client code if you customize this.

### Model Setup

Start LM Studio and expose an OpenAI-compatible API:

```text
Base URL: http://localhost:1234/v1
Model: a vision-capable local model
```

Useful environment variables:

```bash
set LM_STUDIO_BASE_URL=http://localhost:1234/v1
set LM_STUDIO_MODEL=google/gemma-4-26b-a4b
set LM_MIN_MAX_TOKENS=4096
```

The model name must match what LM Studio exposes in `/v1/models`.

### Preflight Check

```bash
python main.py --check
```

This checks Python, Node, npm, backend packages, frontend dependencies, and basic environment configuration.

## Running The System

### CLI Extraction

Best for local testing, one-off files, and batch data preparation:

```bash
python main.py extract "data\demo\invoice_clean.pdf" -o output\invoice_test --mode general
```

Useful options:

```bash
python main.py extract resume.pdf --mode general -o output\resume_001
python main.py extract candidate_packet.pdf --profile generic-document --mask-phi -o output\candidate_packet
python main.py batch input_documents --mode general -o output\batch_001
```

Expected output for CLI runs can include:

- `<stem>_results.json`
- `<stem>_consolidated.xlsx`
- `<stem>_report.md`
- `<stem>.fhir.json` for healthcare profile when applicable
- `validations.json`
- `receipt.json`

For HireOS, the JSON result is the primary artifact. Excel and Markdown are useful for review and operations.

### Backend Only

```bash
python main.py --backend
```

Backend URL:

```text
http://localhost:8000
```

OpenAPI docs:

```text
http://localhost:8000/docs
```

### Full Stack

```bash
python main.py
```

Default URLs:

```text
API: http://127.0.0.1:8000
UI:  http://127.0.0.1:3000
```

### Frontend Only

```bash
cd frontend
npm run dev
```

## API Usage

### Sync Processing From A Server-Side File Path

Endpoint:

```text
POST /api/v1/documents/process
```

Example body:

```json
{
  "pdf_path": "./uploads/candidate_resume.pdf",
  "export_format": "json",
  "output_dir": "./output/hireos/candidate_123",
  "mask_phi": false,
  "extraction_mode": "multi",
  "profile_override": "generic-document",
  "modality_override": [],
  "async_processing": false
}
```

Use this when the HireOS backend already has the file on disk in an allowed path. The API validates paths against allowed directories such as `./uploads`, `./data`, `./input`, and the temp directory.

### Async Upload

Endpoint:

```text
POST /api/v1/documents/upload
```

Form fields:

| Field | Use |
|---|---|
| `file` | Uploaded document |
| `export_format` | `json`, `excel`, `markdown`, `both`, or `all` |
| `mask_phi` | Redact sensitive values in exports |
| `extraction_mode` | `multi`, `single`, or `auto` |
| `profile_override` | Use `generic-document` for hiring docs |
| `modality_override` | JSON list such as `["printed"]` or `["fax", "handwritten"]` |
| `phi_mode` | Optional redaction override |

Example:

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" ^
  -F "file=@candidate_resume.pdf" ^
  -F "export_format=json" ^
  -F "extraction_mode=multi" ^
  -F "profile_override=generic-document"
```

Response:

```json
{
  "task_id": "celery-task-id",
  "status": "pending",
  "message": "Document uploaded and queued for processing",
  "status_url": "/api/v1/tasks/celery-task-id"
}
```

Poll task status:

```text
GET /api/v1/tasks/{task_id}
```

Async upload requires Redis/Celery to be configured and workers running.

### Schema APIs

Useful endpoints:

```text
GET  /api/v1/schemas
GET  /api/v1/schemas/{schema_name}
GET  /api/v1/schemas/{schema_name}/fields
POST /api/v1/schemas/suggest
POST /api/v1/schemas/proposals/{proposal_id}/refine
POST /api/v1/schemas/proposals/{proposal_id}/save
```

For HireOS, the schema suggestion endpoints are important if you want to create a dedicated schema for resumes, certificates, offer letters, or background checks.

## HireOS Integration Architecture

Recommended architecture:

```text
Candidate uploads document
        |
        v
HireOS document service stores raw file
        |
        v
Veridoc extraction service
        |
        v
Structured JSON + confidence + provenance + artifacts
        |
        v
HireOS evidence store
        |
        v
AI hiring agent uses structured evidence for screening, matching, questions, and review
```

Do not let the hiring agent make final employment decisions directly from unverified raw extraction. Store the extracted fields with confidence and source metadata. Route low-confidence or sensitive cases to a human reviewer.

## Hiring Scenarios

### 1. Resume Parsing

Use case:

- Extract candidate name, email, phone, location, education, skills, experience, certifications, employers, dates, projects, and links.

Recommended mode:

```text
profile_override: generic-document
extraction_mode: multi or auto
```

How HireOS should use the result:

- Normalize skills into your skill taxonomy.
- Build a candidate profile draft.
- Ask follow-up questions for missing or low-confidence fields.
- Attach extracted evidence to candidate records.

Guardrails:

- Do not infer protected class attributes.
- Do not score gaps, age, school prestige, or identity-linked attributes unless your policy explicitly allows it.
- Treat low-confidence dates and employer names as review-needed.

### 2. Candidate Packet Extraction

Use case:

- A single PDF contains resume, cover letter, references, portfolio snippets, and certificates.

Recommended mode:

```text
extraction_mode: multi
profile_override: generic-document
```

Why:

- The multi-record pipeline is designed for documents with multiple entities or sections per page.
- Splitter/table agents can help segment content.

How HireOS should use it:

- Group extracted fields by document section.
- Store each section as an evidence source.
- Let the hiring agent summarize each section separately before producing a candidate overview.

### 3. Offer Letter or Employment Contract Intake

Use case:

- Extract role title, compensation, start date, location, employment type, reporting manager, notice period, and signature status.

Recommended mode:

```text
profile_override: generic-document
```

Future improvement:

- Add a `legal-contract` or `employment-document` profile and schema. The CLI help mentions `legal-contract`, but built-in eager registration currently covers generic, finance, and medical-RCM. Confirm registration before relying on that profile.

Guardrails:

- Route contract terms to human review.
- Do not let the hiring agent rewrite legal clauses based only on extraction.

### 4. Payroll and Tax Onboarding Documents

Use case:

- W-2, 1099, bank statements, invoices, or payment setup documents.

Recommended mode:

```text
profile_override: finance
mask_phi: true
```

Why:

- Finance profile has signals for W-2, 1099, bank statements, invoices, EIN, routing/account labels, and tax year.
- Built-in schemas include W-2, 1099, invoice, and bank statement.

Guardrails:

- Enable masking for exports that could be viewed by non-payroll users.
- Store raw documents with stricter access controls than normal resumes.
- Route account/routing extraction to human review before payment setup.

### 5. Credential and Certificate Verification

Use case:

- Extract certificate name, issuer, credential ID, issue date, expiry date, candidate name, and verification URL.

Recommended mode:

```text
profile_override: generic-document
modality_override: ["printed"]
```

How HireOS should use it:

- Match issuer and credential ID against external verification services.
- Ask candidate to provide missing verification URLs.
- Mark expired credentials for recruiter review.

Future improvement:

- Add a `credential-certificate` schema and route certificates to it.

### 6. Background Check Reports

Use case:

- Extract report status, report provider, candidate identity fields, check type, timestamps, and adjudication fields.

Recommended mode:

```text
profile_override: generic-document
mask_phi: true
```

Guardrails:

- Background checks are sensitive and regulated. Keep extraction as evidence capture only.
- Route all adverse or ambiguous results to human/compliance review.
- Avoid using the hiring agent to make automatic rejection decisions.

### 7. Job Description Parsing

Use case:

- Extract required skills, preferred skills, experience years, responsibilities, location, salary range, employment type, and screening questions from a job description PDF/DOCX.

Recommended mode:

```text
profile_override: generic-document
```

How HireOS should use it:

- Build a structured job profile.
- Match candidate evidence against explicit requirements.
- Generate interview questions tied to job requirements.

### 8. Bulk Candidate Intake

Use case:

- Recruiter uploads a folder of resumes or candidate packets.

Recommended flow:

```bash
python main.py batch input_candidates --mode general -o output\hireos_batch
```

Or use async upload with Celery workers if integrated into the HireOS backend.

Guardrails:

- Add retry limits.
- Keep original files and extracted artifacts linked by candidate ID.
- Track extraction failures separately from candidate suitability.

## Recommended HireOS Data Model

Store extraction as evidence, not as final truth:

```json
{
  "candidate_id": "cand_123",
  "document_id": "doc_456",
  "document_type": "resume",
  "source_file_path": "uploads/cand_123/resume.pdf",
  "extraction_engine": "veridoc",
  "processing_id": "extract_...",
  "profile": "generic-document",
  "status": "completed",
  "fields": {
    "candidate_name": {
      "value": "Jane Doe",
      "confidence": 0.91,
      "source": {
        "page": 1,
        "bbox": [0.1, 0.2, 0.4, 0.25]
      }
    }
  },
  "warnings": [],
  "requires_human_review": false,
  "artifacts": {
    "json": "output/...",
    "markdown": "output/...",
    "excel": "output/..."
  }
}
```

Then the hiring agent can consume this evidence through a stable internal API:

```text
get_candidate_evidence(candidate_id)
get_document_extraction(document_id)
get_low_confidence_fields(candidate_id)
request_candidate_clarification(candidate_id, missing_fields)
```

## What To Build Next For HireOS

The repo is generic and finance/healthcare-oriented today. For hiring use, add a first-class HireOS profile and schemas.

### Suggested Profile: `hireos-candidate`

Add a new profile under `src/profiles/hireos_candidate.py` with signals such as:

- `resume`
- `curriculum vitae`
- `work experience`
- `education`
- `certifications`
- `skills`
- `linkedin`
- `github`
- `portfolio`

Register it in `src/profiles/__init__.py`.

### Suggested Schemas

Create schemas for:

- `resume`
- `cover_letter`
- `candidate_packet`
- `certificate`
- `offer_letter`
- `job_description`
- `background_check_summary`
- `reference_letter`

Each schema should define the fields the hiring agent needs and avoid protected attributes by default.

### Suggested Output Contract

Normalize Veridoc output into a HireOS-specific contract:

```json
{
  "identity": {
    "name": null,
    "email": null,
    "phone": null,
    "location": null
  },
  "experience": [],
  "education": [],
  "skills": [],
  "certifications": [],
  "links": [],
  "documents": [],
  "confidence": {
    "overall": 0.0,
    "low_confidence_fields": []
  },
  "review": {
    "required": false,
    "reasons": []
  }
}
```

This lets the rest of HireOS stay independent from Veridoc internals.

## Security and Compliance Guidance

Hiring documents contain sensitive personal data. Use these rules:

- Keep raw uploads in a restricted storage location.
- Enable API authentication before production with `API_AUTH_ENABLED=true`.
- Set strong `SECRET_KEY`, `ENCRYPTION_KEY`, and `JWT_SECRET_KEY`.
- Use `mask_phi` or privacy redaction for payroll, tax, background check, medical, or identity documents.
- Keep audit logs for document access and extraction.
- Do not expose bbox page-image endpoints publicly without authorization.
- Do not send candidate documents to external models unless policy and consent allow it.
- Use local LM Studio or another private VLM backend for sensitive documents.
- Treat extraction confidence as a risk signal, not as a decision score.

Production settings refuse to boot in some unsafe configurations unless bypass acknowledgements are set. Do not use bypass acknowledgements as a normal deployment path.

## Validation and Human Review

Recommended routing for HireOS:

| Condition | Action |
|---|---|
| Overall confidence >= 0.85 | Auto-ingest as draft evidence |
| Confidence 0.50 to 0.85 | Ingest but mark important fields for review |
| Confidence < 0.50 | Human review required |
| Missing key fields | Ask candidate or recruiter for clarification |
| Sensitive document | Human/compliance review required |
| Contradiction across documents | Human review before using in ranking |

Key point: the hiring agent should never silently convert low-confidence extraction into a candidate rejection or acceptance.

## Example HireOS Service Wrapper

Python-style integration:

```python
import requests


def extract_candidate_document(file_path: str, output_dir: str) -> dict:
    payload = {
        "pdf_path": file_path,
        "export_format": "json",
        "output_dir": output_dir,
        "mask_phi": False,
        "extraction_mode": "multi",
        "profile_override": "generic-document",
        "async_processing": False,
    }
    response = requests.post(
        "http://localhost:8000/api/v1/documents/process",
        json=payload,
        timeout=600,
    )
    response.raise_for_status()
    return response.json()
```

Async upload flow:

```python
import time
import requests


def upload_and_wait(path: str) -> dict:
    with open(path, "rb") as f:
        queued = requests.post(
            "http://localhost:8000/api/v1/documents/upload",
            files={"file": f},
            data={
                "export_format": "json",
                "extraction_mode": "multi",
                "profile_override": "generic-document",
            },
            timeout=60,
        )
    queued.raise_for_status()
    status_url = queued.json()["status_url"]

    while True:
        status = requests.get(f"http://localhost:8000{status_url}", timeout=30)
        status.raise_for_status()
        data = status.json()
        if data["ready"]:
            return data
        time.sleep(2)
```

## Local Validation Commands

Use these before integrating into HireOS:

```bash
python main.py --check
python main.py extract "data\demo\invoice_clean.pdf" --mode general -o output\smoke_invoice
pytest tests\unit\test_pipeline_runner.py
pytest tests\unit\test_api.py
cd frontend && npm run type-check
cd frontend && npm test
```

Full test suite:

```bash
pytest tests\ -m "not slow"
```

Frontend checks:

```bash
cd frontend
npm run type-check
npm test
```

## Current Caveats

- The existing docs are written for Veridoc and healthcare/finance document extraction, not HireOS specifically.
- `pyproject.toml` says proprietary license while `README.md` says Apache 2.0 and the repo has a `LICENSE`; resolve licensing before commercial use.
- Async upload relies on Celery/Redis. Without workers, queued tasks will not complete.
- Built-in profiles do not yet include a dedicated hiring/resume profile.
- Some API result retrieval paths are placeholders unless results are stored through the queue/storage path.
- Multi-tenancy is present in settings and middleware but should be validated before SaaS production use.
- The default development API auth is off. Turn it on for production.
- Model quality depends heavily on the loaded VLM. Test with your actual resume and hiring-document corpus.

## Recommended First Implementation Plan

1. Run the CLI against 20 to 50 real or representative hiring documents.
2. Compare JSON output against expected candidate fields.
3. Define a HireOS normalized evidence contract.
4. Add a `hireos-candidate` profile and resume/certificate/job-description schemas.
5. Build a HireOS backend wrapper around `/api/v1/documents/process`.
6. Store raw files, extracted JSON, output artifacts, confidence, and review flags.
7. Add human review UI for low-confidence and sensitive fields.
8. Only then connect the AI hiring agent to the normalized evidence store.

## Bottom Line

Use Veridoc as HireOS's document extraction and evidence grounding service. It should extract and validate candidate documents; HireOS should normalize, store, review, and reason over the results. The strongest near-term path is to use `generic-document` for resumes and general hiring PDFs, `finance` for payroll/tax onboarding documents, then add HireOS-specific profiles and schemas once you have sample documents and expected fields.
