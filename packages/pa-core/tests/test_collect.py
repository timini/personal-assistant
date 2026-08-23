"""Context collection and caching.

get_today_context() already fetches every source with graceful per-source
error handling. What was missing is persistence: nothing wrote the result down,
so every session refetched the calendar, inbox, tasks and weather from scratch.
These tests cover the caching layer, not the fetching.
"""
import json
from unittest.mock import patch

from pa_core.collect import collect, read_state, state_path, write_state


def test_state_path_is_dated(tmp_path):
    with patch("pa_core.collect.STATE_DIR", tmp_path):
        assert state_path("2026-08-23") == tmp_path / "2026-08-23.json"


def test_write_then_read_round_trips(tmp_path):
    with patch("pa_core.collect.STATE_DIR", tmp_path):
        write_state({"date": "2026-08-23", "calendar": [{"summary": "Therapy"}]})
        got = read_state("2026-08-23")
        assert got["calendar"][0]["summary"] == "Therapy"


def test_read_state_returns_none_when_absent(tmp_path):
    with patch("pa_core.collect.STATE_DIR", tmp_path):
        assert read_state("2026-01-01") is None


def test_read_state_returns_none_when_stale(tmp_path):
    with patch("pa_core.collect.STATE_DIR", tmp_path):
        write_state({"date": "2026-08-23", "collected_at": "2026-08-23T08:00:00"})
        # 09:30 against an 08:00 collection is 90 minutes old
        assert read_state("2026-08-23", max_age_minutes=60, now="2026-08-23T09:30:00") is None
        assert read_state("2026-08-23", max_age_minutes=120, now="2026-08-23T09:30:00") is not None


def test_read_state_ignores_age_when_no_limit_given(tmp_path):
    with patch("pa_core.collect.STATE_DIR", tmp_path):
        write_state({"date": "2026-08-23", "collected_at": "2020-01-01T00:00:00"})
        assert read_state("2026-08-23") is not None


def test_collect_lifts_the_nested_date_to_top_level(tmp_path):
    """get_today_context() nests date under "now"; the state file needs it flat."""
    fake = {"now": {"date": "2026-08-23"}, "calendar": [], "errors": []}
    with patch("pa_core.collect.STATE_DIR", tmp_path), \
         patch("pa_core.collect.get_today_context", return_value=fake):
        assert collect()["date"] == "2026-08-23"


def test_collect_stamps_when_it_ran(tmp_path):
    fake = {"now": {"date": "2026-08-23"}, "calendar": [], "errors": []}
    with patch("pa_core.collect.STATE_DIR", tmp_path), \
         patch("pa_core.collect.get_today_context", return_value=fake):
        ctx = collect()
        assert "collected_at" in ctx
        assert ctx["date"] == "2026-08-23"


def test_collect_writes_the_state_file(tmp_path):
    fake = {"now": {"date": "2026-08-23"}, "calendar": [], "errors": []}
    with patch("pa_core.collect.STATE_DIR", tmp_path), \
         patch("pa_core.collect.get_today_context", return_value=fake):
        collect()
        written = json.loads((tmp_path / "2026-08-23.json").read_text())
        assert written["date"] == "2026-08-23"


def test_collect_surfaces_source_errors_rather_than_hiding_them(tmp_path):
    fake = {"now": {"date": "2026-08-23"}, "calendar": [], "errors": ["Calendar: boom"]}
    with patch("pa_core.collect.STATE_DIR", tmp_path), \
         patch("pa_core.collect.get_today_context", return_value=fake):
        ctx = collect()
        assert ctx["errors"] == ["Calendar: boom"]
        assert ctx["ok"] is False


def test_collect_marks_ok_when_every_source_succeeded(tmp_path):
    fake = {"now": {"date": "2026-08-23"}, "calendar": [], "errors": []}
    with patch("pa_core.collect.STATE_DIR", tmp_path), \
         patch("pa_core.collect.get_today_context", return_value=fake):
        assert collect()["ok"] is True


def test_message_queues_are_never_written_to_the_cache(tmp_path):
    """Telegram/WhatsApp queues are live state. Caching them and then
    acknowledging would ack messages already acked and miss new arrivals."""
    fake = {
        "now": {"date": "2026-08-23"}, "calendar": [], "errors": [],
        "telegram_messages": [{"text": "hello"}],
        "whatsapp_messages": [{"text": "hi"}],
    }
    with patch("pa_core.collect.STATE_DIR", tmp_path), \
         patch("pa_core.collect.get_today_context", return_value=fake):
        ctx = collect()
        # the caller still gets them...
        assert ctx["telegram_messages"] == [{"text": "hello"}]
        # ...but they are not persisted
        written = json.loads((tmp_path / "2026-08-23.json").read_text())
        assert written["telegram_messages"] == []
        assert written["whatsapp_messages"] == []
