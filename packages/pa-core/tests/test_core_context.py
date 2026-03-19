"""Tests for pa_core.context — all fetchers, stats, streaks, and render."""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest


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


# ---------------------------------------------------------------------------
# streak_count
# ---------------------------------------------------------------------------

class TestStreakCount:
    @patch("pa_core.context.get_events")
    def test_zero_streak(self, mock_events):
        mock_events.return_value = []
        from pa_core.context import streak_count
        assert streak_count("Exercise", "2026-03-19") == 0

    @patch("pa_core.context.get_events")
    def test_streak_of_three(self, mock_events):
        def events_for_date(date_str):
            # Return completed habit for 3 consecutive days before 2026-03-19
            if date_str in ("2026-03-18", "2026-03-17", "2026-03-16"):
                return [{"category": "habit", "action": "completed", "summary": "Exercise"}]
            return []
        mock_events.side_effect = events_for_date
        from pa_core.context import streak_count
        assert streak_count("Exercise", "2026-03-19") == 3

    @patch("pa_core.context.get_events")
    def test_streak_breaks_on_gap(self, mock_events):
        def events_for_date(date_str):
            if date_str == "2026-03-18":
                return [{"category": "habit", "action": "completed", "summary": "Exercise"}]
            if date_str == "2026-03-17":
                return []  # gap
            if date_str == "2026-03-16":
                return [{"category": "habit", "action": "completed", "summary": "Exercise"}]
            return []
        mock_events.side_effect = events_for_date
        from pa_core.context import streak_count
        assert streak_count("Exercise", "2026-03-19") == 1


# ---------------------------------------------------------------------------
# _task_streak
# ---------------------------------------------------------------------------

class TestTaskStreak:
    @patch("pa_core.context.get_events")
    def test_task_streak_zero(self, mock_events):
        mock_events.return_value = []
        from pa_core.context import _task_streak
        assert _task_streak("2026-03-19") == 0

    @patch("pa_core.context.get_events")
    def test_task_streak_counts_consecutive(self, mock_events):
        def events_for_date(date_str):
            if date_str in ("2026-03-18", "2026-03-17"):
                return [{"category": "task", "action": "completed", "summary": "Did stuff"}]
            return []
        mock_events.side_effect = events_for_date
        from pa_core.context import _task_streak
        assert _task_streak("2026-03-19") == 2

    @patch("pa_core.context.get_events")
    def test_task_streak_counts_created(self, mock_events):
        """'created' actions also count toward streak."""
        def events_for_date(date_str):
            if date_str == "2026-03-18":
                return [{"category": "task", "action": "created", "summary": "New task"}]
            return []
        mock_events.side_effect = events_for_date
        from pa_core.context import _task_streak
        assert _task_streak("2026-03-19") == 1


# ---------------------------------------------------------------------------
# _count_completed
# ---------------------------------------------------------------------------

class TestCountCompleted:
    @patch("pa_core.context.get_events")
    def test_counts_across_days(self, mock_events):
        def events_for_date(date_str):
            return [{"category": "task", "action": "completed", "summary": "X"}]
        mock_events.side_effect = events_for_date
        from pa_core.context import _count_completed
        assert _count_completed("2026-03-19", 3) == 3

    @patch("pa_core.context.get_events")
    def test_ignores_non_task_events(self, mock_events):
        mock_events.return_value = [
            {"category": "email", "action": "archived", "summary": "Y"},
            {"category": "task", "action": "completed", "summary": "X"},
        ]
        from pa_core.context import _count_completed
        assert _count_completed("2026-03-19", 1) == 1


# ---------------------------------------------------------------------------
# _fetch_weather
# ---------------------------------------------------------------------------

class TestFetchWeather:
    @patch("httpx.get")
    def test_fetch_weather_success(self, mock_get):
        geo_resp = MagicMock()
        geo_resp.json.return_value = {"latitude": 51.5, "longitude": -0.1, "city": "London"}
        weather_resp = MagicMock()
        weather_resp.json.return_value = {
            "current": {
                "temperature_2m": 12, "apparent_temperature": 10,
                "weather_code": 2, "wind_speed_10m": 15,
            },
            "daily": {
                "temperature_2m_max": [14], "temperature_2m_min": [8],
                "precipitation_probability_max": [20],
            },
        }
        mock_get.side_effect = [geo_resp, weather_resp]

        from pa_core.context import _fetch_weather
        result = _fetch_weather()
        assert result["location"] == "London"
        assert result["temperature"] == 12
        assert result["description"] == "Partly cloudy"
        assert result["rain_probability"] == 20

    @patch("httpx.get")
    def test_fetch_weather_unknown_code(self, mock_get):
        geo_resp = MagicMock()
        geo_resp.json.return_value = {"latitude": 51.5, "longitude": -0.1, "city": "London"}
        weather_resp = MagicMock()
        weather_resp.json.return_value = {
            "current": {"weather_code": 999},
            "daily": {},
        }
        mock_get.side_effect = [geo_resp, weather_resp]

        from pa_core.context import _fetch_weather
        result = _fetch_weather()
        assert result["description"] == "Unknown"


# ---------------------------------------------------------------------------
# _fetch_calendar
# ---------------------------------------------------------------------------

class TestFetchCalendar:
    @patch("pa_google.calendar.get_all_todays_events")
    def test_fetch_calendar(self, mock_cal):
        mock_cal.return_value = [
            {"start": "2026-03-19T09:00:00Z", "summary": "Standup", "calendar": "Work"},
            {"start": "2026-03-19", "summary": "All day", "calendar": None},
        ]
        from pa_core.context import _fetch_calendar
        result = _fetch_calendar()
        assert len(result) == 2
        assert result[0]["time"] == "09:00"
        assert result[0]["summary"] == "Standup"
        assert result[0]["calendar"] == "Work"
        assert result[1]["time"] == "2026-03-19"  # all-day, no T

    @patch("pa_google.calendar.get_all_todays_events")
    def test_fetch_calendar_empty(self, mock_cal):
        mock_cal.return_value = []
        from pa_core.context import _fetch_calendar
        assert _fetch_calendar() == []

    @patch("pa_google.calendar.get_all_todays_events")
    def test_fetch_calendar_no_title(self, mock_cal):
        mock_cal.return_value = [{"start": "2026-03-19T10:00:00Z"}]
        from pa_core.context import _fetch_calendar
        result = _fetch_calendar()
        assert result[0]["summary"] == "No title"


# ---------------------------------------------------------------------------
# _fetch_emails
# ---------------------------------------------------------------------------

class TestFetchEmails:
    @patch("pa_google.gmail.get_inbox_emails")
    def test_fetch_emails(self, mock_emails):
        mock_emails.return_value = [
            {"from": "alice@test.com", "subject": "Hello", "snippet": "Hi...", "id": "abc"},
        ]
        from pa_core.context import _fetch_emails
        result = _fetch_emails()
        assert len(result) == 1
        assert result[0]["from"] == "alice@test.com"

    @patch("pa_google.gmail.get_inbox_emails")
    def test_fetch_emails_empty(self, mock_emails):
        mock_emails.return_value = []
        from pa_core.context import _fetch_emails
        assert _fetch_emails() == []


# ---------------------------------------------------------------------------
# _fetch_tasks
# ---------------------------------------------------------------------------

class TestFetchTasks:
    @patch("pa_notion.tasks.list_tasks")
    def test_fetch_tasks_due_soon_and_urgent(self, mock_tasks):
        from datetime import date
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        mock_tasks.return_value = [
            {"title": "Urgent thing", "status": "To Do", "priority": "Urgent", "due_date": None},
            {"title": "Due tomorrow", "status": "To Do", "priority": "High", "due_date": tomorrow},
            {"title": "Done task", "status": "Done", "priority": "Low", "due_date": today},
            {"title": "Far away", "status": "To Do", "priority": "Low", "due_date": "2099-01-01"},
        ]
        from pa_core.context import _fetch_tasks
        due_soon, urgent = _fetch_tasks()
        assert len(urgent) == 1
        assert urgent[0]["title"] == "Urgent thing"
        assert len(due_soon) == 1
        assert due_soon[0]["title"] == "Due tomorrow"

    @patch("pa_notion.tasks.list_tasks")
    def test_fetch_tasks_empty(self, mock_tasks):
        mock_tasks.return_value = []
        from pa_core.context import _fetch_tasks
        due_soon, urgent = _fetch_tasks()
        assert due_soon == []
        assert urgent == []


# ---------------------------------------------------------------------------
# _fetch_habits
# ---------------------------------------------------------------------------

class TestFetchHabits:
    @patch("pa_core.context.streak_count", return_value=5)
    @patch("pa_core.context.get_events")
    @patch("pa_core.context.get_user_config")
    def test_habits_completed(self, mock_config, mock_events, mock_streak):
        mock_config.return_value = {"habits": [{"name": "Exercise", "emoji": "💪"}]}
        mock_events.return_value = [
            {"category": "habit", "action": "completed", "summary": "Exercise"},
        ]
        from pa_core.context import _fetch_habits
        result = _fetch_habits("2026-03-19")
        assert len(result) == 1
        assert result[0]["status"] == "completed"
        assert result[0]["streak"] == 6  # 5 + 1 for today

    @patch("pa_core.context.get_events")
    @patch("pa_core.context.get_user_config")
    def test_habits_skipped(self, mock_config, mock_events):
        mock_config.return_value = {"habits": [{"name": "Exercise", "emoji": "💪"}]}
        mock_events.return_value = [
            {"category": "habit", "action": "skipped", "summary": "Exercise"},
        ]
        from pa_core.context import _fetch_habits
        result = _fetch_habits("2026-03-19")
        assert result[0]["status"] == "skipped"
        assert result[0]["streak"] == 0

    @patch("pa_core.context.get_events")
    @patch("pa_core.context.get_user_config")
    def test_habits_not_logged(self, mock_config, mock_events):
        mock_config.return_value = {"habits": [{"name": "Exercise", "emoji": "💪"}]}
        mock_events.return_value = []
        from pa_core.context import _fetch_habits
        result = _fetch_habits("2026-03-19")
        assert result[0]["status"] == "not_logged"

    @patch("pa_core.context.get_user_config")
    def test_no_habits_configured(self, mock_config):
        mock_config.return_value = {}
        from pa_core.context import _fetch_habits
        assert _fetch_habits("2026-03-19") == []


# ---------------------------------------------------------------------------
# _fetch_completed
# ---------------------------------------------------------------------------

class TestFetchCompleted:
    @patch("pa_core.context.get_events")
    def test_fetch_completed(self, mock_events):
        mock_events.return_value = [
            {"category": "task", "action": "completed", "summary": "Did X"},
            {"category": "email", "action": "archived", "summary": "Not a task"},
            {"category": "task", "action": "created", "summary": "Created Y"},
        ]
        from pa_core.context import _fetch_completed
        result = _fetch_completed("2026-03-19")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _fetch_stats
# ---------------------------------------------------------------------------

class TestFetchStats:
    @patch("pa_core.context._task_streak", return_value=3)
    @patch("pa_core.context._count_completed")
    def test_fetch_stats(self, mock_count, mock_streak):
        mock_count.side_effect = lambda date_str, days: {
            ("2026-03-19", 1): 2,
            ("2026-03-18", 1): 1,
            ("2026-03-19", 7): 10,
            ("2026-03-19", 30): 40,
        }.get((date_str, days), 0)
        from pa_core.context import _fetch_stats
        result = _fetch_stats("2026-03-19")
        assert result["completed_today_count"] == 2
        assert result["completed_yesterday_count"] == 1
        assert result["completed_7d_count"] == 10
        assert result["completed_30d_count"] == 40
        assert result["avg_daily_7d"] == round(10 / 7, 1)
        assert result["avg_daily_30d"] == round(40 / 30, 1)
        assert result["task_streak"] == 3


# ---------------------------------------------------------------------------
# get_today_context — error handling
# ---------------------------------------------------------------------------

class TestGetTodayContextErrors:
    def _patch_all_ok(self):
        return [
            patch("pa_core.context.get_now", return_value=FAKE_NOW),
            patch("pa_core.context.get_user_config", return_value={}),
            patch("pa_core.context.get_events", return_value=[]),
            patch("pa_core.context._fetch_calendar", return_value=[]),
            patch("pa_core.context._fetch_emails", return_value=[]),
            patch("pa_core.context._fetch_tasks", return_value=([], [])),
            patch("pa_core.context._fetch_weather", return_value=FAKE_WEATHER),
            patch("pa_telegram.client.get_messages", return_value=[]),
        ]

    def test_calendar_error(self):
        patches = self._patch_all_ok()
        # Override calendar to fail
        patches[3] = patch("pa_core.context._fetch_calendar", side_effect=RuntimeError("cal fail"))
        for p in patches:
            p.start()
        try:
            from pa_core.context import get_today_context
            ctx = get_today_context()
            assert ctx["calendar"] == []
            assert any("Calendar" in e for e in ctx["errors"])
        finally:
            for p in patches:
                p.stop()

    def test_email_error(self):
        patches = self._patch_all_ok()
        patches[4] = patch("pa_core.context._fetch_emails", side_effect=RuntimeError("email fail"))
        for p in patches:
            p.start()
        try:
            from pa_core.context import get_today_context
            ctx = get_today_context()
            assert ctx["emails"] == []
            assert any("Email" in e for e in ctx["errors"])
        finally:
            for p in patches:
                p.stop()

    def test_tasks_error(self):
        patches = self._patch_all_ok()
        patches[5] = patch("pa_core.context._fetch_tasks", side_effect=RuntimeError("task fail"))
        for p in patches:
            p.start()
        try:
            from pa_core.context import get_today_context
            ctx = get_today_context()
            assert ctx["tasks_due_soon"] == []
            assert ctx["tasks_urgent"] == []
            assert any("Tasks" in e for e in ctx["errors"])
        finally:
            for p in patches:
                p.stop()

    def test_stats_error(self):
        patches = self._patch_all_ok()
        for p in patches:
            p.start()
        try:
            with patch("pa_core.context._fetch_stats", side_effect=RuntimeError("stats fail")):
                from pa_core.context import get_today_context
                ctx = get_today_context()
                assert ctx["stats"]["completed_today_count"] == 0
                assert any("Stats" in e for e in ctx["errors"])
        finally:
            for p in patches:
                p.stop()

    def test_habits_error(self):
        patches = self._patch_all_ok()
        for p in patches:
            p.start()
        try:
            with patch("pa_core.context._fetch_habits", side_effect=RuntimeError("habits fail")):
                from pa_core.context import get_today_context
                ctx = get_today_context()
                assert ctx["habits"] == []
                assert any("Habits" in e for e in ctx["errors"])
        finally:
            for p in patches:
                p.stop()

    def test_weather_error(self):
        patches = self._patch_all_ok()
        patches[6] = patch("pa_core.context._fetch_weather", side_effect=RuntimeError("weather fail"))
        for p in patches:
            p.start()
        try:
            from pa_core.context import get_today_context
            ctx = get_today_context()
            assert ctx["weather"]["description"] == "Unavailable"
            assert any("Weather" in e for e in ctx["errors"])
        finally:
            for p in patches:
                p.stop()

    def test_daily_log_error(self):
        patches = self._patch_all_ok()
        for p in patches:
            p.start()
        try:
            with patch("pa_core.context._fetch_completed", side_effect=RuntimeError("log fail")):
                from pa_core.context import get_today_context
                ctx = get_today_context()
                assert ctx["completed_today"] == []
                assert ctx["completed_yesterday"] == []
                assert any("Daily log" in e for e in ctx["errors"])
        finally:
            for p in patches:
                p.stop()

    def test_all_ok_no_errors(self):
        patches = self._patch_all_ok()
        for p in patches:
            p.start()
        try:
            from pa_core.context import get_today_context
            ctx = get_today_context()
            assert ctx["errors"] == []
        finally:
            for p in patches:
                p.stop()


# ---------------------------------------------------------------------------
# render_context — template sections
# ---------------------------------------------------------------------------

class TestRenderContext:
    def _base_ctx(self, **overrides):
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
        ctx.update(overrides)
        return ctx

    def test_render_calendar_events(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(calendar=[
            {"time": "09:00", "summary": "Standup", "calendar": "Work"},
        ])
        output = render_context(ctx)
        assert "09:00 [Work] Standup" in output

    def test_render_calendar_no_label(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(calendar=[
            {"time": "10:00", "summary": "Lunch", "calendar": None},
        ])
        output = render_context(ctx)
        assert "10:00 Lunch" in output
        assert "[None]" not in output

    def test_render_emails(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(emails=[
            {"from": "alice@test.com", "subject": "Hello", "snippet": "Hi", "id": "x"},
        ])
        output = render_context(ctx)
        assert "Unread Emails (1)" in output
        assert "**alice@test.com**: Hello" in output

    def test_render_inbox_zero(self):
        from pa_core.context import render_context
        ctx = self._base_ctx()
        output = render_context(ctx)
        assert "Inbox zero!" in output

    def test_render_urgent_tasks(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(tasks_urgent=[
            {"title": "Fix bug", "due_date": "2026-03-19", "project": "Day Job"},
        ])
        output = render_context(ctx)
        assert "Fix bug" in output
        assert "due 2026-03-19" in output
        assert "[Day Job]" in output

    def test_render_due_soon_tasks(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(tasks_due_soon=[
            {"title": "Pay bill", "due_date": "2026-03-20", "project": "Admin / Finance", "priority": "High"},
        ])
        output = render_context(ctx)
        assert "[High] Pay bill — due 2026-03-20 [Admin / Finance]" in output

    def test_render_completed_today(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(completed_today=[
            {"summary": "Finished report"},
        ])
        output = render_context(ctx)
        assert "Finished report" in output

    def test_render_stats(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(stats={
            "completed_today_count": 3, "completed_yesterday_count": 2,
            "completed_7d_count": 15, "completed_30d_count": 50,
            "avg_daily_7d": 2.1, "avg_daily_30d": 1.7, "task_streak": 5,
        })
        output = render_context(ctx)
        assert "Today: 3" in output
        assert "Yesterday: 2" in output
        assert "Task streak: 5 days" in output

    def test_render_task_streak_singular(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(stats={
            "completed_today_count": 1, "completed_yesterday_count": 0,
            "completed_7d_count": 1, "completed_30d_count": 1,
            "avg_daily_7d": 0.1, "avg_daily_30d": 0.0, "task_streak": 1,
        })
        output = render_context(ctx)
        assert "1 day " in output  # singular

    def test_render_weather_unavailable(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(weather={
            "location": "Unknown", "temperature": None, "feels_like": None,
            "description": "Unavailable", "rain_probability": 0,
            "high": None, "low": None, "wind_speed": None,
        })
        output = render_context(ctx)
        assert "Weather unavailable." in output

    def test_render_habits_completed(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(habits=[
            {"name": "Exercise", "emoji": "💪", "status": "completed", "streak": 3, "logged_today": True},
        ])
        output = render_context(ctx)
        assert "💪 Exercise — streak: 3 days" in output

    def test_render_habits_skipped(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(habits=[
            {"name": "Exercise", "emoji": "💪", "status": "skipped", "streak": 0, "logged_today": True},
        ])
        output = render_context(ctx)
        assert "Exercise — skipped (streak reset)" in output

    def test_render_habits_not_logged(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(habits=[
            {"name": "Exercise", "emoji": "💪", "status": "not_logged", "streak": 0, "logged_today": False},
        ])
        output = render_context(ctx)
        assert "Exercise — not logged today" in output

    def test_render_no_habits(self):
        from pa_core.context import render_context
        ctx = self._base_ctx()
        output = render_context(ctx)
        assert "No habits configured." in output

    def test_render_errors(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(errors=["Calendar: connection timeout"])
        output = render_context(ctx)
        assert "## Errors" in output
        assert "Calendar: connection timeout" in output

    def test_render_no_errors_section_hidden(self):
        from pa_core.context import render_context
        ctx = self._base_ctx()
        output = render_context(ctx)
        assert "## Errors" not in output

    def test_render_completed_yesterday(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(completed_yesterday=[{"summary": "Fixed bug"}])
        output = render_context(ctx)
        assert "Fixed bug" in output

    def test_render_no_completed_yesterday(self):
        from pa_core.context import render_context
        ctx = self._base_ctx()
        output = render_context(ctx)
        assert "Nothing logged." in output

    def test_render_urgent_no_due_date(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(tasks_urgent=[
            {"title": "Urgent no date", "due_date": None, "project": None},
        ])
        output = render_context(ctx)
        assert "Urgent no date" in output
        assert "due" not in output.split("Urgent no date")[1].split("\n")[0]

    def test_render_due_soon_no_priority(self):
        from pa_core.context import render_context
        ctx = self._base_ctx(tasks_due_soon=[
            {"title": "Simple task", "due_date": "2026-03-20", "project": None, "priority": None},
        ])
        output = render_context(ctx)
        assert "Simple task — due 2026-03-20" in output
        assert "[None]" not in output
