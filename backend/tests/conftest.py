"""Pytest configuration and shared fixtures.

Environment variables are set BEFORE importing any app module so the database engine and cached
settings point at an isolated temporary SQLite database in Demo Mode. No real integrations or
production credentials are ever used.
"""

from __future__ import annotations

import os
import tempfile

# --- Must run before importing app modules ---------------------------------------------
_TMP_DB = os.path.join(tempfile.gettempdir(), "lifeagent_test.db")
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)

# Isolate tests from any real `.env` on the host (e.g. a production Backend Mac config).
os.environ["LIFE_AGENT_ENV_FILE"] = os.path.join(tempfile.gettempdir(), "lifeagent_no_env_file")
os.environ["LIFE_AGENT_ENV"] = "testing"
os.environ["LIFE_AGENT_MODE"] = "demo"
os.environ["LIFE_AGENT_EXECUTION_MODE"] = "simulation"
os.environ["LIFE_AGENT_LLM_PROVIDER"] = "mock"
os.environ["LIFE_AGENT_DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["LIFE_AGENT_DEV_API_TOKEN"] = "test-token"
os.environ["LIFE_AGENT_DATA_DIR"] = tempfile.gettempdir()
os.environ["LIFE_AGENT_DOCUMENTS_DIR"] = os.path.join(tempfile.gettempdir(), "docs")
os.environ["LIFE_AGENT_LOG_DIR"] = os.path.join(tempfile.gettempdir(), "logs")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import reset_database  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def _fresh_db():
    reset_database()
    yield


@pytest.fixture
def seeded():
    seed()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
