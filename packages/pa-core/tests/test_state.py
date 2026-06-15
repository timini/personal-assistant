"""Tests for pa_core.state — generic key/value state store (activity/.state.json)."""

from unittest.mock import patch

import pa_core.state as state


def test_set_then_get_roundtrip(tmp_path):
    with patch("pa_core.config.PA_ROOT", tmp_path):
        state.set_state("foo", 123)
        assert state.get_state("foo") == 123


def test_get_missing_returns_default(tmp_path):
    with patch("pa_core.config.PA_ROOT", tmp_path):
        assert state.get_state("nope") is None
        assert state.get_state("nope", "fallback") == "fallback"


def test_set_preserves_other_keys(tmp_path):
    with patch("pa_core.config.PA_ROOT", tmp_path):
        state.set_state("a", 1)
        state.set_state("b", 2)
        assert state.get_state("a") == 1
        assert state.get_state("b") == 2


def test_corrupt_file_tolerated(tmp_path):
    with patch("pa_core.config.PA_ROOT", tmp_path):
        (tmp_path / "activity").mkdir()
        (tmp_path / "activity" / ".state.json").write_text("{not valid json")
        assert state.get_state("x", "def") == "def"
        state.set_state("x", 5)  # should repair/overwrite
        assert state.get_state("x") == 5


def test_stores_dict_value(tmp_path):
    with patch("pa_core.config.PA_ROOT", tmp_path):
        state.set_state("last_email_triage", {"epoch": 100, "display": "Mon"})
        assert state.get_state("last_email_triage")["epoch"] == 100
