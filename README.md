# HireOS AI-Service

This is the only FastAPI service that should be started for HireOS AI features.

`Agentic-Document-Extraction-PDF` is treated as an internal dependency for resume
PDF extraction. Do not start its old standalone backend or frontend for the
HireOS flow.

## Install

```bash
pip install -r requirements.txt
```

## Run

From this `AI-Service` folder:

```bash
python run.py
```

Equivalent:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Resume Extractor Provider

Default:

```env
DOCUMENT_EXTRACTOR_PROVIDER=openai
```

This reads resume PDF text in root `AI-Service`, sends it to OpenAI, and returns
the normalized HireOS resume schema.

Legacy wrapped extractor:

```env
DOCUMENT_EXTRACTOR_PROVIDER=agentic
```

This imports `AI-Service/Agentic-Document-Extraction-PDF/src/pipeline/runner.py`
inside the root AI-Service process. It still does not require starting the old
extractor app separately.
