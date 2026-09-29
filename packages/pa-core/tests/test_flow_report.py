"""Weekly task-flow aggregation.

Opened is exact (creation timestamp). Closed is inferred from the last-edited
timestamp of tasks now Done/Discarded, because Notion does not record when a
status changed — the report must say so, and the aggregation must not pretend
otherwise.
"""
from pa_core.flow_report import week_start, aggregate_weeks


def test_week_start_snaps_to_monday():
    assert week_start("2026-08-23") == "2026-08-17"  # a Sunday
    assert week_start("2026-08-17") == "2026-08-17"  # the Monday itself
    assert week_start("2026-08-19") == "2026-08-17"  # midweek


def test_open_task_counts_as_opened_but_never_closed():
    rows = [{"created": "2026-08-18", "edited": "2026-08-20", "status": "To Do"}]
    weeks = aggregate_weeks(rows)
    assert weeks[0]["opened"] == 1
    assert weeks[0]["closed"] == 0


def test_done_and_discarded_split_out():
    rows = [
        {"created": "2026-08-18", "edited": "2026-08-19", "status": "Done"},
        {"created": "2026-08-18", "edited": "2026-08-19", "status": "Discarded"},
    ]
    weeks = aggregate_weeks(rows)
    assert weeks[0]["opened"] == 2
    assert weeks[0]["closed"] == 2
    assert weeks[0]["done"] == 1
    assert weeks[0]["discarded"] == 1


def test_running_open_accumulates_across_weeks():
    rows = [
        {"created": "2026-08-10", "edited": "2026-08-10", "status": "To Do"},
        {"created": "2026-08-10", "edited": "2026-08-10", "status": "To Do"},
        {"created": "2026-08-17", "edited": "2026-08-17", "status": "To Do"},
        # opened in week 1, closed in week 2 — must land in different buckets
        {"created": "2026-08-10", "edited": "2026-08-18", "status": "Done"},
    ]
    weeks = aggregate_weeks(rows)
    assert [w["week"] for w in weeks] == ["2026-08-10", "2026-08-17"]
    assert weeks[0]["opened"] == 3 and weeks[0]["closed"] == 0
    assert weeks[1]["opened"] == 1 and weeks[1]["closed"] == 1
    assert weeks[0]["running"] == 3
    assert weeks[1]["running"] == 3  # +1 opened, -1 closed


def test_weeks_with_no_activity_are_omitted_not_zero_filled():
    rows = [
        {"created": "2026-08-03", "edited": "2026-08-03", "status": "To Do"},
        {"created": "2026-08-17", "edited": "2026-08-17", "status": "To Do"},
    ]
    weeks = aggregate_weeks(rows)
    assert [w["week"] for w in weeks] == ["2026-08-03", "2026-08-17"]


def test_missing_timestamps_are_skipped_not_crashed():
    rows = [
        {"created": "", "edited": "2026-08-19", "status": "Done"},
        {"created": "2026-08-18", "edited": "", "status": "Done"},
        {"created": "2026-08-18", "edited": "2026-08-19", "status": "Done"},
    ]
    weeks = aggregate_weeks(rows)
    assert weeks[0]["opened"] == 2  # the two with a created date
    assert weeks[0]["closed"] == 2  # the two Done rows that have an edited date
