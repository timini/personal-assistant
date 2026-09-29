"""The morning planning prompt and the evening reflection prompt.

The morning one is the highest-value piece in this work. Measured over 104 days,
days that start with a plan complete 3.26 tasks against 1.27 — and the median
goes from 0 to 2. Planning currently happens on 35% of days because nothing
prompts it.

So the prompt must arrive already carrying the day: schedule, a short
shortlist, and the questions. Replying to it *is* planning.
"""
from pa_core.prompts import build_evening_prompt, build_morning_prompt, shortlist


FAKE_TASKS = [
    {"title": "Submit AMP abstract", "lane": "🔥 Live", "due_date": "2026-08-30", "priority": "High"},
    {"title": "Pay TTC invoice", "lane": "", "due_date": "2026-08-18", "priority": "High"},
    {"title": "Fix utility room door", "lane": "", "due_date": "", "priority": "Medium"},
    {"title": "Order the ducting", "lane": "", "due_date": "", "priority": "Medium"},
    {"title": "Example project internet", "lane": "", "due_date": "", "priority": "Low"},
    {"title": "KonMari books", "lane": "🅿️ Parked", "due_date": "", "priority": "Low"},
    {"title": "Deep clean", "lane": "", "due_date": "2026-08-25", "priority": "Medium"},
]


def test_shortlist_is_capped_so_it_never_overwhelms():
    """The never-overwhelm rule: a wall of tasks at 06:30 gets ignored."""
    assert len(shortlist(FAKE_TASKS, today="2026-08-24")) <= 5


def test_live_lane_leads_then_recent_overdue():
    """Deliberate change: Live leads. Work he has chosen beats work he is being
    reminded he failed to do. Recent overdue still ranks above everything else."""
    titles = [t["title"] for t in shortlist(FAKE_TASKS, today="2026-08-24")]
    assert titles[0] == "Submit AMP abstract"          # Live
    assert titles[1] == "Pay TTC invoice"              # overdue 6 days


def test_live_lane_ranks_above_undated_backlog():
    titles = [t["title"] for t in shortlist(FAKE_TASKS, today="2026-08-24")]
    assert titles.index("Submit AMP abstract") < titles.index("Fix utility room door")


def test_parked_tasks_never_appear():
    titles = [t["title"] for t in shortlist(FAKE_TASKS, today="2026-08-24")]
    assert "KonMari books" not in titles


def test_morning_prompt_carries_the_schedule_and_the_shortlist():
    text = build_morning_prompt(
        schedule=[{"time": "16:00", "summary": "Therapy", "calendar": None}],
        tasks=FAKE_TASKS,
        today="2026-08-24",
    )
    assert "Therapy" in text
    assert "16:00" in text
    assert "Pay TTC invoice" in text


def test_morning_prompt_asks_for_mood_energy_and_an_intention():
    text = build_morning_prompt(schedule=[], tasks=[], today="2026-08-24").lower()
    assert "mood" in text
    assert "energy" in text
    # the anti-procrastination question, in his words
    assert "get going" in text


def test_morning_prompt_survives_an_empty_day():
    """No calendar, no tasks — must still send something useful, not blank."""
    text = build_morning_prompt(schedule=[], tasks=[], today="2026-08-24")
    assert len(text) > 50
    assert "nothing" in text.lower() or "clear" in text.lower()


def test_evening_prompt_asks_only_habits_that_are_due():
    habits = [
        {"name": "Exercise", "emoji": "💪", "cadence": "daily"},
        {"name": "Review finances", "emoji": "💷", "cadence": "monthly"},
    ]
    # mid-month: the monthly habit should not be asked about
    text = build_evening_prompt(habits=habits, events=[], today="2026-08-10")
    assert "Exercise" in text
    assert "Review finances" not in text


def test_evening_prompt_asks_the_monthly_habit_near_month_end():
    habits = [{"name": "Review finances", "emoji": "💷", "cadence": "monthly"}]
    text = build_evening_prompt(habits=habits, events=[], today="2026-08-28")
    assert "Review finances" in text


def test_evening_prompt_covers_gratitude_reflection_and_winding_down():
    text = build_evening_prompt(habits=[], events=[], today="2026-08-24").lower()
    assert "grateful" in text or "gratitude" in text
    assert "switch off" in text or "wind down" in text


def test_evening_prompt_does_not_nag_when_every_habit_is_done():
    habits = [{"name": "Exercise", "emoji": "💪", "cadence": "daily"}]
    events = [{"date": "2026-08-24", "category": "habit", "action": "completed", "summary": "Exercise"}]
    text = build_evening_prompt(habits=habits, events=events, today="2026-08-24")
    assert "Exercise" not in text


# --- the shortlist must motivate, not accuse ---------------------------------

STALE = [
    {"title": "Cut edge noggins", "lane": "", "due_date": "2026-06-15", "priority": "Medium"},
    {"title": "Pay Toby 400", "lane": "", "due_date": "2026-06-30", "priority": "Medium"},
    {"title": "AMP speaker tasks", "lane": "🔥 Live", "due_date": "2026-08-30", "priority": "High"},
    {"title": "Chase school re violin", "lane": "", "due_date": "2026-08-25", "priority": "Medium"},
    {"title": "Send the key back", "lane": "", "due_date": "2026-08-18", "priority": "Medium"},
]


def test_live_lane_leads_the_shortlist_not_ancient_overdue():
    """AGENTS.md: 'here's what would make today a win', not 'here's what's overdue'.
    Sorting oldest-first surfaces exactly the items he has most avoided."""
    titles = [t["title"] for t in shortlist(STALE, today="2026-08-24")]
    assert titles[0] == "AMP speaker tasks"


def test_months_stale_items_sink_below_live_and_recent():
    titles = [t["title"] for t in shortlist(STALE, today="2026-08-24")]
    assert titles.index("Chase school re violin") < titles.index("Cut edge noggins")
    assert titles.index("Send the key back") < titles.index("Pay Toby 400")


def test_recent_overdue_still_ranks_above_undated_backlog():
    tasks = STALE + [{"title": "Someday thing", "lane": "", "due_date": "", "priority": "Low"}]
    titles = [t["title"] for t in shortlist(tasks, today="2026-08-24")]
    assert titles.index("Send the key back") < titles.index("Someday thing")


def test_all_day_events_render_as_all_day_not_a_raw_date():
    text = build_morning_prompt(
        schedule=[{"time": "2026-08-24", "summary": "Home", "calendar": None}],
        tasks=[], today="2026-08-24",
    )
    assert "2026-08-24  Home" not in text
    assert "all-day" in text
