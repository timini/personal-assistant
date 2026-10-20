import json
from pathlib import Path
from unittest.mock import patch


def sample_facts():
    return {
        "kind": "daily",
        "date": "2026-08-24",
        "title": "Assistant Daily Report",
        "health": {"sleep_hours": 8.1, "steps": 4321, "avg_stress": 27},
        "activities": [{"name": "Run", "distance_km": 2.94, "duration": "15:29", "pace": "5:16/km"}],
        "habits": [{"name": "Exercise", "emoji": "💪", "status": "completed", "streak": 3}],
        "tasks": {
            "live": 69,
            "start": 76,
            "created_today": 1,
            "completed_today": 7,
            "discarded_today": 1,
            "by_status": {"To Do": 53, "Waiting": 3},
            "by_project": {"House Renovation": 26},
            "trend": [{"date": "2026-08-24", "completed": 7}],
        },
        "wins": ["Paid supplier invoice"],
        "calendar": [],
        "warnings": [],
    }


def test_render_html_is_deterministic_and_escapes():
    from pa_core.report import render_html

    facts = sample_facts()
    facts["wins"].append("Safe <script>alert(1)</script>")
    facts["calendar"] = [{"time": "16:15", "summary": "Child's Climbing", "calendar": "Family"}]
    first = render_html(facts, insights=None)
    second = render_html(facts, insights=None)

    assert first == second
    assert "<!doctype html>" in first.lower()
    assert "Task burndown" in first
    assert "2.94 km" in first
    assert "16:15" in first and "Child&#39;s Climbing" in first
    assert "Safe &lt;script&gt;" in first
    assert "<script>alert" not in first


def test_generate_report_saves_stable_html_and_manifest(tmp_path):
    from pa_core.report import generate_report

    with patch("pa_core.report.collect_daily_facts", return_value=sample_facts()):
        bundle = generate_report(date="2026-08-24", output_root=tmp_path, insights=False)

    assert bundle.report_id == "daily-2026-08-24"
    assert bundle.html_path.read_text().startswith("<!doctype html>")
    manifest = json.loads(bundle.manifest_path.read_text())
    assert manifest["report_id"] == bundle.report_id
    assert manifest["facts_sha256"]
    assert manifest["deliveries"] == {}


def test_insights_are_cached_by_fact_hash(tmp_path):
    from pa_core.report import generate_insights

    facts = sample_facts()
    response = {
        "summary": "Solid progress.",
        "insights": [{"text": "Backlog fell.", "evidence_keys": ["tasks.live"]}],
        "watchouts": [],
        "next_actions": [],
    }
    with patch("pa_core.report._run_claude", return_value=response) as run:
        assert generate_insights(facts, tmp_path) == response
        assert generate_insights(facts, tmp_path) == response
    run.assert_called_once()


def test_invalid_insight_evidence_falls_back_without_crashing(tmp_path):
    from pa_core.report import generate_insights

    invalid = {
        "summary": "Made up.",
        "insights": [{"text": "Unknown", "evidence_keys": ["bank.balance"]}],
        "watchouts": [],
        "next_actions": [],
    }
    with patch("pa_core.report._run_claude", return_value=invalid):
        assert generate_insights(sample_facts(), tmp_path) is None


def test_insight_evidence_can_reference_list_items(tmp_path):
    from pa_core.report import generate_insights

    valid = {
        "summary": "Run captured.",
        "insights": [{"text": "Distance recorded.", "evidence_keys": ["activities.0.distance_km"]}],
        "watchouts": [], "next_actions": [],
    }
    with patch("pa_core.report._run_claude", return_value=valid):
        assert generate_insights(sample_facts(), tmp_path) == valid


def test_deliver_attempts_all_channels_after_one_failure(tmp_path):
    from pa_core.report import ReportBundle, deliver_report

    html = tmp_path / "report.html"
    html.write_text("<html>ok</html>")
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    bundle = ReportBundle("daily-2026-08-24", "daily", "2026-08-24", sample_facts(), None, html, manifest)

    with (
        patch("pa_google.reports.publish_report", side_effect=RuntimeError("drive down")),
        patch("pa_google.reports.email_report", return_value={"id": "mail"}) as email,
    ):
        result = deliver_report(bundle)

    assert result["drive"]["ok"] is False
    assert result["email"]["ok"] is True
    assert set(result) == {"drive", "email"}
    email.assert_called_once()


def test_report_cli_generates_and_delivers(monkeypatch, tmp_path, capsys):
    from pa_core import cli

    bundle = type("Bundle", (), {
        "html_path": tmp_path / "report.html",
        "manifest_path": tmp_path / "manifest.json",
    })()
    with (
        patch("pa_core.report.generate_report", return_value=bundle) as generate,
        patch("pa_core.report.deliver_report", return_value={
            "drive": {"ok": True, "url": "https://drive/report"},
            "email": {"ok": True},
        }) as deliver,
    ):
        monkeypatch.setattr("sys.argv", ["pa-core", "report", "--kind", "daily", "--date", "2026-08-24", "--deliver", "--no-insights"])
        cli.main()

    generate.assert_called_once()
    assert generate.call_args.kwargs["insights"] is False
    deliver.assert_called_once_with(bundle)
    assert "https://drive/report" in capsys.readouterr().out


def test_research_sections_are_structured_and_escaped(tmp_path):
    from pa_core.report import generate_report

    source = tmp_path / "research.json"
    source.write_text(json.dumps({
        "title": "Kettle report",
        "sections": [{
            "heading": "Recommendation",
            "paragraphs": ["Choose <script>alert(1)</script> steel."],
            "bullets": ["£19.99"],
            "sources": [{"label": "Amazon", "url": "https://example.com/item"}],
        }],
    }))
    bundle = generate_report(kind="research", date="2026-08-24", input_path=source,
                             output_root=tmp_path / "out", insights=False)
    html = bundle.html_path.read_text()
    assert "Choose &lt;script&gt;" in html
    assert "<script>alert" not in html
    assert 'href="https://example.com/item"' in html


def test_insights_respect_configured_model():
    from pa_core.report import _run_claude

    wrapper = {"structured_output": {"summary": "ok", "insights": [], "watchouts": [], "next_actions": []}}
    completed = type("Completed", (), {"stdout": json.dumps(wrapper)})()
    with (
        patch("pa_core.report.get_user_config", return_value={"reports": {"llm_model": "sonnet"}}),
        patch("pa_core.report.subprocess.run", return_value=completed) as run,
    ):
        _run_claude({"tasks": {"live": 1}})
    args = run.call_args.args[0]
    assert args[args.index("--model") + 1] == "sonnet"


def test_config_can_disable_insights(tmp_path):
    from pa_core.report import generate_report

    with (
        patch("pa_core.report.collect_daily_facts", return_value=sample_facts()),
        patch("pa_core.report.get_user_config", return_value={"reports": {"insights_enabled": False}}),
        patch("pa_core.report._run_claude") as claude,
    ):
        generate_report(date="2026-08-24", output_root=tmp_path, insights=True)
    claude.assert_not_called()
