"""Tests for the throughput / net-flow monitor (pure functions in pa_notion.flow)."""

from pa_notion import flow


def _task(id, status="To Do", lane="🅿️ Parked", due="", created="2026-01-01", last_edited="2026-06-21"):
    return {"id": id, "title": id, "status": status, "lane": lane,
            "due": due, "created": created, "last_edited": last_edited}


class TestComputeSnapshot:
    def test_counts_and_aging(self):
        today = "2026-06-21"
        tasks = [
            _task("d1", status="Done", last_edited="2026-06-21"),
            _task("d2", status="Done", last_edited="2026-06-20"),
            _task("overdue_live", status="To Do", lane="🔥 Live", due="2026-06-10"),
            _task("stale_live", status="In Progress", lane="🔥 Live", last_edited="2026-06-01"),
            _task("fresh_parked", status="To Do", lane="🅿️ Parked", created="2026-06-21"),
        ]
        s = flow.compute_snapshot(tasks, today)
        assert s["open"] == 3            # 3 non-Done
        assert s["done_total"] == 2
        assert s["added_today"] == 1     # fresh_parked created today
        assert s["overdue"] == 1         # overdue_live
        assert s["live_open"] == 2       # the two Live
        assert set(s["aging_live"]) == {"overdue_live", "stale_live"}

    def test_fresh_live_not_aging(self):
        today = "2026-06-21"
        tasks = [_task("ok_live", status="To Do", lane="🔥 Live", last_edited="2026-06-20", due="2026-07-30")]
        s = flow.compute_snapshot(tasks, today)
        assert s["aging_live"] == []


class TestNetFlow:
    def test_delta_when_history(self):
        today = "2026-06-21"
        snaps = [{"date": "2026-06-14", "open": 200, "done_total": 400}]
        tasks = (
            [_task(f"done{i}", status="Done") for i in range(410)]
            + [_task(f"open{i}", status="To Do", created=("2026-06-18" if i < 4 else "2026-01-01")) for i in range(190)]
        )
        nf = flow.net_flow(snaps, tasks, today, days=7)
        assert nf["added"] == 4
        assert nf["completed"] == 10          # 410 - 400
        assert nf["source"] == "delta"
        assert nf["net"] == 6
        assert nf["open_then"] == 200
        assert nf["open_trend"] == -10        # 190 - 200
        assert nf["verdict"] == "clearing"

    def test_fallback_without_history(self):
        today = "2026-06-21"
        tasks = [
            _task("a", status="Done", last_edited="2026-06-19"),
            _task("b", status="Done", last_edited="2026-06-01"),   # outside window
            _task("c", status="To Do", created="2026-06-20"),
        ]
        nf = flow.net_flow([], tasks, today, days=7)
        assert nf["completed"] == 1            # only 'a' edited in window
        assert nf["source"] == "last_edited"
        assert nf["added"] == 1

    def test_building_verdict_on_rising_open(self):
        today = "2026-06-21"
        snaps = [{"date": "2026-06-14", "open": 100, "done_total": 50}]
        tasks = [_task(f"o{i}", status="To Do", created="2026-01-01") for i in range(110)] + \
                [_task(f"d{i}", status="Done") for i in range(55)]
        nf = flow.net_flow(snaps, tasks, today, days=7)
        assert nf["open_trend"] == 10          # 110 - 100
        assert nf["verdict"] == "building"


class TestFlowLine:
    def test_renders_verdict_and_extras(self):
        snap = {"overdue": 2, "aging_live": ["x"]}
        nf = {"added": 3, "completed": 7, "net": 4, "open_now": 184, "open_then": 190,
              "open_trend": -6, "verdict": "clearing", "days": 7}
        line = flow.flow_line(snap, nf)
        assert "net +4" in line and "clearing" in line
        assert "190→184" in line
        assert "2 overdue" in line and "1 aging" in line

    def test_no_extras_when_clean(self):
        snap = {"overdue": 0, "aging_live": []}
        nf = {"added": 1, "completed": 1, "net": 0, "open_now": 50, "open_then": 50,
              "open_trend": 0, "verdict": "holding", "days": 7}
        line = flow.flow_line(snap, nf)
        assert "⚠️" not in line


class TestBuildUpAlerts:
    def test_two_building_in_a_row(self):
        snaps = [
            {"date": "2026-06-19", "verdict": "building", "overdue": 1, "aging_live": []},
            {"date": "2026-06-20", "verdict": "building", "overdue": 1, "aging_live": []},
            {"date": "2026-06-21", "verdict": "building", "overdue": 1, "aging_live": []},
        ]
        alerts = flow.build_up_alerts(snaps, "2026-06-21")
        assert any("BUILDING" in a for a in alerts)

    def test_rising_overdue_and_aging(self):
        snaps = [
            {"date": "2026-06-20", "verdict": "holding", "overdue": 1, "aging_live": []},
            {"date": "2026-06-21", "verdict": "holding", "overdue": 3, "aging_live": ["a", "b"]},
        ]
        alerts = flow.build_up_alerts(snaps, "2026-06-21")
        assert any("Overdue rising" in a for a in alerts)
        assert any("aging" in a for a in alerts)

    def test_silent_when_on_track(self):
        snaps = [
            {"date": "2026-06-20", "verdict": "clearing", "overdue": 2, "aging_live": []},
            {"date": "2026-06-21", "verdict": "clearing", "overdue": 1, "aging_live": []},
        ]
        assert flow.build_up_alerts(snaps, "2026-06-21") == []
