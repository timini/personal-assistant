"""Lane must survive the flattening in _extract_task.

Without it, anything ranking or filtering on lane silently no-ops: Live tasks
never get prioritised, and — worse — Parked tasks are never excluded. Parked is
68 of 73 open tasks, so a shortlist that cannot filter it is useless.
"""
from pa_notion.tasks import _extract_task


def _page(lane=None):
    props = {
        "Task": {"title": [{"plain_text": "Finish shed roof"}]},
        "Status": {"select": {"name": "To Do"}},
    }
    if lane is not None:
        props["Lane"] = {"select": {"name": lane}} if lane else {"select": None}
    return {"id": "abc", "properties": props}


def test_lane_is_returned():
    assert _extract_task(_page("🔥 Live"))["lane"] == "🔥 Live"


def test_parked_lane_is_returned():
    assert _extract_task(_page("🅿️ Parked"))["lane"] == "🅿️ Parked"


def test_missing_lane_property_is_empty_not_absent():
    """Consumers use task['lane'] directly; a missing key would KeyError."""
    task = _extract_task(_page(None))
    assert "lane" in task
    assert task["lane"] == ""


def test_null_lane_select_is_empty():
    assert _extract_task(_page(""))["lane"] == ""
