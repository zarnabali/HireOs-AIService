# HireOS Document Extraction Dependency

This folder is retained only as the legacy agentic document extraction engine used by `AI-Service`.

It is no longer treated as a standalone product or platform inside HireOS. The removed legacy shell included the old frontend, demo data, standalone launcher, nested repository metadata, broad product docs, and tests tied to those removed assets.

## Retained Files

- `src/`: Python extraction engine imported by `AI-Service` when `DOCUMENT_EXTRACTOR_PROVIDER=agentic`.
- `config.json`: Runtime extraction flags used by `src/config/extraction_config.py`.
- `pyproject.toml` and `requirements.txt`: Dependency metadata for the retained extraction engine.
- `docs/HIREOS_AI_HIRING_AGENT_GUIDE.md`: HireOS-specific integration guide.
- `LICENSE`: Original license file.

## HireOS Runtime Path

The canonical HireOS request path is:

```text
frontend -> backend -> AI-Service -> document extraction adapter -> this retained src package
```

The root AI-Service adapter is:

```text
AI-Service/app/integrations/document_extraction/adapter.py
```

Do not start this folder separately for HireOS. Start `AI-Service` from the root `AI-Service/` folder.
