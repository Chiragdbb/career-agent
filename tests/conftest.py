from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"

# REPO_ROOT enables `import packages.providers` and `import database`.
# API_ROOT enables `import app`.
for path in (str(REPO_ROOT), str(API_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def static_jwt_verifier():
    from app.auth.jwt import AuthClaims, StaticJwtVerifier

    verifier = StaticJwtVerifier(
        {
            "token-user-a": AuthClaims(subject="supabase-user-a"),
            "token-user-b": AuthClaims(subject="supabase-user-b"),
        }
    )
    return verifier


@pytest.fixture
def auth_client(static_jwt_verifier):
    """API test client with mocked JWT verifier (no real Supabase calls)."""
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    settings = get_settings()
    app = create_app(settings)
    app.state.jwt_verifier = static_jwt_verifier

    with TestClient(app) as client:
        yield client
