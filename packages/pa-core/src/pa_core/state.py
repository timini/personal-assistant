"""Generic small key/value state store, backed by activity/.state.json.

For cross-run cursors and 'last run' timestamps (e.g. when email triage last
ran). Mirrors the lightweight persistence used for the Telegram offset, but as
a shared JSON dict so any plugin can stash a scalar/dict under a key.
"""

import json

import pa_core.config as _config


def _state_file():
    """Path to the state file (read at call time so PA_ROOT can be patched in tests)."""
    return _config.PA_ROOT / "activity" / ".state.json"


def _read_all() -> dict:
    f = _state_file()
    if not f.exists():
        return {}
    try:
        text = f.read_text().strip()
        return json.loads(text) if text else {}
    except (json.JSONDecodeError, OSError):
        # Corrupt or unreadable — treat as empty, set_state will repair it.
        return {}


def get_state(key: str, default=None):
    """Return the stored value for key, or default if not set."""
    return _read_all().get(key, default)


def set_state(key: str, value) -> None:
    """Persist value under key, preserving all other keys."""
    data = _read_all()
    data[key] = value
    f = _state_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2))
