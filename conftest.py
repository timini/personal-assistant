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
    "telegram": {"chat_id": "123456"},
}


@pytest.fixture(autouse=True)
def _mock_user_config():
    """Auto-mock get_user_config so tests don't need user.yaml."""
    with patch("pa_core.config.get_user_config", return_value=MOCK_USER_CONFIG):
        yield
