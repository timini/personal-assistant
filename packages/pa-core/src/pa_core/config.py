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


def get_assistant_name() -> str:
    """Get the assistant's display name from user.yaml, defaulting to 'PA'."""
    return get_user_config().get("assistant_name", "PA")


def get_enabled_plugins() -> list[str]:
    """Return list of enabled plugin names."""
    return get_user_config().get("enabled_plugins", [])


def get_user_profile() -> dict:
    """Return the profile section from user.yaml, or empty dict if not set."""
    return get_user_config().get("profile", {})


def get_profile_field(field: str) -> str | None:
    """Return a specific profile field, or None if not set."""
    return get_user_profile().get(field)


def set_profile_field(field: str, value: str) -> None:
    """Set a profile field in user.yaml, preserving all existing config."""
    user_yaml = PA_ROOT / "user.yaml"
    with open(user_yaml) as f:
        config = yaml.safe_load(f) or {}
    profile = config.get("profile", {})
    profile[field] = value
    config["profile"] = profile
    with open(user_yaml, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def get_now() -> dict:
    """Return current date/time info formatted for session context.

    Returns dict with keys: date, day, time, timezone, period (morning/afternoon/evening).
    Always call this at the start of every session to determine the correct context.
    """
    from datetime import datetime
    import zoneinfo

    tz_name = get_user_config().get("timezone", "Europe/London")
    tz = zoneinfo.ZoneInfo(tz_name)
    now = datetime.now(tz)

    hour = now.hour
    if hour < 12:
        period = "morning"
    elif hour < 17:
        period = "afternoon"
    else:
        period = "evening"

    return {
        "date": now.strftime("%Y-%m-%d"),
        "day": now.strftime("%A"),
        "time": now.strftime("%H:%M"),
        "timezone": tz_name,
        "period": period,
        "display": now.strftime("%A %d %B %Y, %H:%M %Z"),
    }
