"""Load .env and user.yaml from the PA repo root."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


def _find_pa_root() -> Path:
    """Walk up from this file to find the repo root (contains pyproject.toml with name='pa')."""
    candidate = Path(__file__).resolve()
    while candidate != candidate.parent:
        candidate = candidate.parent
        if (candidate / "pyproject.toml").exists() and (candidate / ".env").exists():
            return candidate
    # Fallback: use cwd
    return Path.cwd()


PA_ROOT = _find_pa_root()

# Load .env once on import
load_dotenv(PA_ROOT / ".env")


def get_secret(key: str) -> str:
    """Get a secret from environment variables (loaded from .env)."""
    value = os.environ.get(key)
    if value is None:
        raise KeyError(f"Secret '{key}' not found. Check your .env file at {PA_ROOT / '.env'}")
    return value


def get_user_config() -> dict:
    """Load user.yaml and return as dict."""
    user_yaml = PA_ROOT / "user.yaml"
    if not user_yaml.exists():
        raise FileNotFoundError(
            f"user.yaml not found at {user_yaml}. Run 'uv run pa-core setup' first."
        )
    with open(user_yaml) as f:
        return yaml.safe_load(f)


def get_user_name() -> str:
    """Convenience: get the user's name from user.yaml."""
    return get_user_config().get("name", "User")


def get_enabled_plugins() -> list[str]:
    """Return list of enabled plugin names."""
    return get_user_config().get("enabled_plugins", [])
