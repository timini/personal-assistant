"""Tests for pa_core.memory — the shared, file-based assistant memory."""

from unittest.mock import patch

import pytest

import pa_core.memory as memory


@pytest.fixture
def mem(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "memory_dir", lambda: tmp_path / "memory")
    return tmp_path / "memory"


class TestAdd:
    def test_add_writes_markdown_with_frontmatter(self, mem):
        entry = memory.add("preference", "Short emails", "Keep emails brief and relaxed",
                           body="Formal only for legal.", tags=["email"], today="2026-01-05")
        path = mem / "entries" / "short-emails.md"
        assert path.exists()
        text = path.read_text()
        assert text.startswith("---\n")
        assert "type: preference" in text
        assert "Formal only for legal." in text
        assert entry["name"] == "short-emails"
        assert entry["created"] == "2026-01-05"

    def test_add_rejects_unknown_type(self, mem):
        with pytest.raises(ValueError):
            memory.add("gossip", "x", "y")

    def test_add_requires_summary(self, mem):
        with pytest.raises(ValueError):
            memory.add("fact", "x", "  ")

    def test_add_upserts_and_keeps_created(self, mem):
        memory.add("fact", "Family todo", "Shared list is a Google Sheet", today="2026-01-01")
        entry = memory.add("fact", "family-todo", "Shared list is the T&L sheet", today="2026-01-09")
        assert entry["created"] == "2026-01-01"
        assert entry["updated"] == "2026-01-09"
        assert memory.get("family-todo")["summary"] == "Shared list is the T&L sheet"
        assert len(memory.list_entries()) == 1

    def test_upsert_keeps_body_when_not_given(self, mem):
        memory.add("fact", "a", "first", body="details")
        memory.add("fact", "a", "second")
        assert memory.get("a")["body"] == "details"

    def test_loop_requires_due_date(self, mem):
        with pytest.raises(ValueError):
            memory.add("loop", "chase council", "Chase the council reply")


class TestGetAndList:
    def test_get_missing_returns_none(self, mem):
        assert memory.get("nope") is None

    def test_list_filters_by_type(self, mem):
        memory.add("fact", "a", "A")
        memory.add("lesson", "b", "B")
        assert [e["name"] for e in memory.list_entries("lesson")] == ["b"]

    def test_list_on_empty_store(self, mem):
        assert memory.list_entries() == []


class TestArchiveAndLoops:
    def test_archive_moves_entry_out_of_active_set(self, mem):
        memory.add("preference", "sign as assistant", "Sign family messages as the assistant")
        memory.archive("sign-as-assistant", "User asked to stop", today="2026-01-02")
        assert memory.get("sign-as-assistant") is None
        archived = (mem / "archive" / "sign-as-assistant.md").read_text()
        assert "status: archived" in archived
        assert "User asked to stop" in archived

    def test_archive_missing_raises(self, mem):
        with pytest.raises(KeyError):
            memory.archive("nope", "x")

    def test_due_and_upcoming_loops(self, mem):
        memory.add("loop", "past", "Chase A", due="2026-01-01")
        memory.add("loop", "today", "Chase B", due="2026-01-05")
        memory.add("loop", "soon", "Chase C", due="2026-01-08")
        memory.add("loop", "later", "Chase D", due="2026-03-01")
        assert [e["name"] for e in memory.due_loops("2026-01-05")] == ["past", "today"]
        assert [e["name"] for e in memory.upcoming_loops("2026-01-05", days=7)] == ["soon"]

    def test_close_loop_records_outcome(self, mem):
        memory.add("loop", "chase", "Chase the quote", due="2026-01-01")
        memory.close_loop("chase", "Quote received", today="2026-01-03")
        assert memory.due_loops("2026-01-05") == []
        assert "Quote received" in (mem / "archive" / "chase.md").read_text()
        assert "Closed loop chase: Quote received" in memory.recent_journal("2026-01-03", days=1)[0]

    def test_close_non_loop_raises(self, mem):
        memory.add("fact", "a", "A")
        with pytest.raises(ValueError):
            memory.close_loop("a", "x")


class TestJournal:
    def test_journal_appends_dated_lines_per_month(self, mem):
        memory.journal("Triaged inbox, 3 archived", now="2026-01-05 09:10")
        memory.journal("Booked the vet", now="2026-01-06 10:00")
        text = (mem / "journal" / "2026-01.md").read_text()
        assert "- 2026-01-05 09:10 Triaged inbox, 3 archived" in text
        assert "- 2026-01-06 10:00 Booked the vet" in text

    def test_recent_journal_window(self, mem):
        memory.journal("old", now="2025-12-20 09:00")
        memory.journal("new", now="2026-01-04 09:00")
        lines = memory.recent_journal("2026-01-05", days=3)
        assert len(lines) == 1 and "new" in lines[0]

    def test_recent_journal_spans_month_boundary(self, mem):
        memory.journal("december", now="2025-12-31 09:00")
        memory.journal("january", now="2026-01-01 09:00")
        lines = memory.recent_journal("2026-01-01", days=2)
        assert [l.split()[-1] for l in lines] == ["december", "january"]


class TestSearch:
    def test_search_ranks_name_and_summary_above_body(self, mem):
        memory.add("fact", "family todo", "Joint to-do list lives in Google Sheets")
        memory.add("lesson", "gws scopes", "Re-auth gws with all scopes", body="Never only calendar; sheets too")
        results = memory.search("sheets todo")
        assert results[0]["name"] == "family-todo"

    def test_search_includes_journal_hits(self, mem):
        memory.journal("Sent the quote request to the builder", now="2026-01-05 09:00")
        results = memory.search("builder quote")
        assert results and results[0]["type"] == "journal"

    def test_search_no_match(self, mem):
        memory.add("fact", "a", "apples")
        assert memory.search("zebra") == []


class TestBrief:
    def test_brief_empty_store_is_empty(self, mem):
        assert memory.render_brief(today="2026-01-05", checked_in=None) == ""

    def test_brief_orders_loops_first_and_lists_rules(self, mem):
        memory.add("preference", "drafts first", "Show drafts before sending to people")
        memory.add("lesson", "no direct debit tasks", "Direct debit notices never become tasks")
        memory.add("person", "sam", "Sam: partner; invite to family events")
        memory.add("loop", "chase builder", "Chase builder for quote", due="2026-01-04")
        memory.journal("Archived 12 newsletters", now="2026-01-04 18:00")
        brief = memory.render_brief(today="2026-01-05", checked_in=None)
        assert brief.index("Due now") < brief.index("Rules")
        assert "chase-builder: Chase builder for quote (due 2026-01-04)" in brief
        assert "Show drafts before sending" in brief
        assert "Direct debit notices" in brief
        assert "sam: Sam: partner" in brief
        assert "Archived 12 newsletters" in brief

    def test_brief_reports_check_in_status(self, mem):
        memory.add("fact", "a", "A")
        assert "Check-in: done today at 09:10" in memory.render_brief(today="2026-01-05", checked_in="09:10")
        assert "Check-in: not yet today" in memory.render_brief(today="2026-01-05", checked_in=None)


class TestLint:
    def test_lint_flags_stale_loops_and_near_duplicates(self, mem):
        memory.add("loop", "old chase", "Chase the plumber", due="2025-11-01")
        memory.add("preference", "short emails", "Keep emails short and relaxed")
        memory.add("preference", "brief emails", "Keep emails short and relaxed.")
        issues = memory.lint(today="2026-01-05")
        assert any("old-chase" in i and "overdue" in i for i in issues)
        assert any("short-emails" in i and "brief-emails" in i for i in issues)

    def test_lint_clean_store(self, mem):
        memory.add("fact", "a", "Apples are red")
        assert memory.lint(today="2026-01-05") == []


class TestImportClaude:
    def test_import_maps_types_and_skips_index(self, mem, tmp_path):
        src = tmp_path / "claude"
        src.mkdir()
        (src / "MEMORY.md").write_text("- [x](x.md)\n")
        (src / "feedback_drafts.md").write_text(
            "---\nname: Confirm before sending\ndescription: Draft and show before sending\n"
            "metadata:\n  type: feedback\n---\n\nShow drafts.\n")
        (src / "reference_sheet.md").write_text(
            "---\nname: family-sheet\ndescription: Shared sheet location\ntype: reference\n---\nIt is a sheet.\n")
        count = memory.import_claude_memory(src, today="2026-01-05")
        assert count == 2
        pref = memory.get("confirm-before-sending")
        assert pref["type"] == "preference" and pref["source"] == "claude-memory"
        assert memory.get("family-sheet")["type"] == "fact"


class TestMemoryDir:
    def test_env_var_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PA_MEMORY_DIR", str(tmp_path / "m"))
        assert memory.memory_dir() == tmp_path / "m"

    def test_relative_config_path_resolves_under_repo(self, monkeypatch):
        from pa_core.config import PA_ROOT
        monkeypatch.delenv("PA_MEMORY_DIR", raising=False)
        with patch("pa_core.config.get_user_config", return_value={"memory_dir": "notes/mem"}):
            assert memory.memory_dir() == PA_ROOT / "notes" / "mem"

    def test_default_is_private_memory(self, monkeypatch):
        from pa_core.config import PA_ROOT
        monkeypatch.delenv("PA_MEMORY_DIR", raising=False)
        with patch("pa_core.config.get_user_config", side_effect=FileNotFoundError):
            assert memory.memory_dir() == PA_ROOT / "private" / "memory"

    def test_slugify_rejects_empty(self):
        with pytest.raises(ValueError):
            memory.slugify("!!!")
