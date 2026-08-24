from __future__ import annotations

import pytest
from sqlalchemy import text

from app.config import get_settings
from app.database import get_engine, init_db


@pytest.mark.integration
def test_database_connection() -> None:
    settings = get_settings()
    init_db(settings)
    engine = get_engine()

    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar_one()

    assert result == 1
