"""Tests for Telegram message integration in pa_core.context."""

from unittest.mock import patch


FAKE_NOW = {
    "date": "2026-03-19",
    "day": "Thursday",
    "time": "10:00",
    "timezone": "Europe/London",
    "period": "morning",
    "display": "Thursday 19 March 2026, 10:00 GMT",
}

FAKE_WEATHER = {
    "location": "London",
    "temperature": 12,
    "feels_like": 10,
    "description": "Partly cloudy",
    "high": 14,
    "low": 8,
    "rain_probability": 20,
    "wind_speed": 15,
}


def _patch_all_fetchers():
    """Patch all external fetchers so get_today_context runs without network."""
    return [
        patch("pa_core.context.get_now", return_value=FAKE_NOW),
        patch("pa_core.context.get_user_config", return_value={}),
        patch("pa_core.context.get_events", return_value=[]),
        patch("pa_core.context._fetch_calendar", return_value=[]),
        patch("pa_core.context._fetch_emails", return_value=[]),
        patch("pa_core.context._fetch_tasks", return_value=([], [])),
        patch("pa_core.context._fetch_weather", return_value=FAKE_WEATHER),
    ]


class TestGetTodayContextTelegram:
    def test_telegram_messages_included_in_context(self):
        fake_msgs = [
            {"update_id": 1, "date": "2026-03-19", "time": "09:00", "text": "reminder", "from_name": "Alice"},
        ]
        patches = _patch_all_fetchers()
        patches.append(patch("pa_telegram.client.get_messages", return_value=fake_msgs))
        for p in patches:
            p.start()
        try:
            from pa_core.context import get_today_context
            ctx = get_today_context()
            assert ctx["telegram_messages"] == fake_msgs
            assert "Telegram" not in str(ctx["errors"])
        finally:
            for p in patches:
                p.stop()

    def test_telegram_error_gracefully_handled(self):
        patches = _patch_all_fetchers()
        patches.append(patch("pa_telegram.client.get_messages", side_effect=RuntimeError("bot down")))
        for p in patches:
            p.start()
        try:
            from pa_core.context import get_today_context
            ctx = get_today_context()
            assert ctx["telegram_messages"] == []
            assert any("Telegram" in e for e in ctx["errors"])
        finally:
            for p in patches:
                p.stop()

    def test_telegram_empty_when_no_messages(self):
        patches = _patch_all_fetchers()
        patches.append(patch("pa_telegram.client.get_messages", return_value=[]))
        for p in patches:
            p.start()
        try:
            from pa_core.context import get_today_context
            ctx = get_today_context()
            assert ctx["telegram_messages"] == []
        finally:
            for p in patches:
                p.stop()


class TestRenderContextTelegram:
    def test_render_with_messages(self):
        from pa_core.context import render_context
        ctx = {
            "now": FAKE_NOW,
            "calendar": [],
            "emails": [],
            "telegram_messages": [
                {"time": "09:15", "from_name": "Alice", "text": "Call dentist"},
            ],
            "tasks_due_soon": [],
            "tasks_urgent": [],
            "completed_today": [],
            "completed_yesterday": [],
            "stats": {
                "completed_today_count": 0, "completed_yesterday_count": 0,
                "completed_7d_count": 0, "completed_30d_count": 0,
                "avg_daily_7d": 0, "avg_daily_30d": 0, "task_streak": 0,
            },
            "habits": [],
            "weather": FAKE_WEATHER,
            "errors": [],
        }
        output = render_context(ctx)
        assert "## Telegram Messages" in output
        assert "[09:15] Alice: Call dentist" in output

    def test_render_without_messages(self):
        from pa_core.context import render_context
        ctx = {
            "now": FAKE_NOW,
            "calendar": [],
            "emails": [],
            "telegram_messages": [],
            "tasks_due_soon": [],
            "tasks_urgent": [],
            "completed_today": [],
            "completed_yesterday": [],
            "stats": {
                "completed_today_count": 0, "completed_yesterday_count": 0,
                "completed_7d_count": 0, "completed_30d_count": 0,
                "avg_daily_7d": 0, "avg_daily_30d": 0, "task_streak": 0,
            },
            "habits": [],
            "weather": FAKE_WEATHER,
            "errors": [],
        }
        output = render_context(ctx)
        assert "## Telegram Messages" in output
        assert "No new messages." in output

    def test_telegram_section_between_emails_and_urgent(self):
        from pa_core.context import render_context
        ctx = {
            "now": FAKE_NOW,
            "calendar": [],
            "emails": [],
            "telegram_messages": [
                {"time": "09:15", "from_name": "Alice", "text": "test"},
            ],
            "tasks_due_soon": [],
            "tasks_urgent": [],
            "completed_today": [],
            "completed_yesterday": [],
            "stats": {
                "completed_today_count": 0, "completed_yesterday_count": 0,
                "completed_7d_count": 0, "completed_30d_count": 0,
                "avg_daily_7d": 0, "avg_daily_30d": 0, "task_streak": 0,
            },
            "habits": [],
            "weather": FAKE_WEATHER,
            "errors": [],
        }
        output = render_context(ctx)
        email_pos = output.index("## Unread Emails")
        telegram_pos = output.index("## Telegram Messages")
        urgent_pos = output.index("## Urgent Tasks")
        assert email_pos < telegram_pos < urgent_pos
