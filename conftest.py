"""Root conftest — provide mock config for CI where user.yaml/.env don't exist."""

import os
from unittest.mock import patch

import pytest

MOCK_USER_CONFIG = {
    "name": "Test User",
    "email": "test@example.com",
    "timezone": "Europe/London",
    "assistant_name": "PA",
    "enabled_plugins": [],
}


@pytest.fixture(autouse=True)
def _mock_user_config():
    """Auto-mock get_user_config so tests don't need user.yaml."""
    with patch("pa_core.config.get_user_config", return_value=MOCK_USER_CONFIG):
        yield


@pytest.fixture(autouse=True)
def _isolate_memory(tmp_path, monkeypatch):
    """Never let a test read or write the real assistant memory."""
    monkeypatch.setenv("PA_MEMORY_DIR", str(tmp_path / "memory"))


@pytest.fixture(autouse=True)
def _isolate_triage_state(monkeypatch):
    """The memory brief reads the real triage cursor; tests start with none."""
    import pa_core.memory
    monkeypatch.setattr(pa_core.memory, "_last_triage", lambda: None, raising=False)
