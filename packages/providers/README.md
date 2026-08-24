# Provider abstraction layer

Business services depend on **interfaces** in this package. Vendor SDKs belong
only in future adapter modules (not added yet).

## Product defaults (documentation only)

| Interface | Default target |
|-----------|----------------|
| `SearchProvider` | Tavily |
| `ScraperProvider` | Self-hosted Firecrawl |
| `LLMProvider` | Groq or Gemini |
| `StorageProvider` | Supabase Storage (private buckets, signed URLs) |

Auth uses **Supabase Auth** and is not modeled as a provider here.

Do **not** add Clerk, OpenAI, or AWS S3 adapters in this layer.

## Importing from `apps/api` and tests

With the repository root on `PYTHONPATH` (pytest `conftest.py` already does this):

```python
from packages.providers import (
    SearchProvider,
    MockSearchProvider,
    SearchRequest,
    create_mock_providers,
)

mocks = create_mock_providers()
result = mocks.search.search(SearchRequest(query="backend engineer"))
```

Alternatively, set `PYTHONPATH` to the repo root when starting uvicorn:

```bash
# PowerShell
$env:PYTHONPATH = (Get-Location).Path
uvicorn app.main:app --app-dir apps/api --reload
```

## Contracts every adapter must honor

- Typed request/response models (Pydantic)
- Raise `packages.providers.exceptions` subclasses on failure
- Honor `timeout_seconds` on each request (default: 30s)
- Expose `metadata: ProviderMetadata`
- Return `UsageInfo` on every successful response

## Mocks

Use `create_mock_providers()` or individual `Mock*Provider` classes. Pass
`simulate_timeout=True` or `fail_with=...` to exercise error paths.
