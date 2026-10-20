"""Tests for the `pa-core memory` subcommands."""

from unittest.mock import patch

import pytest

import pa_core.memory as memory


@pytest.fixture(autouse=True)
def mem(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "memory_dir", lambda: tmp_path / "memory")
    return tmp_path / "memory"


def run(*argv):
    with patch("sys.argv", ["pa-core", "memory", *argv]):
        from pa_core.cli import main
        main()


def test_add_then_show(capsys):
    run("add", "fact", "family todo", "Shared list is a Google Sheet", "--tags", "family,lists")
    run("show", "family-todo")
    out = capsys.readouterr().out
    assert "Saved fact family-todo" in out
    assert "Shared list is a Google Sheet" in out
    assert memory.get("family-todo")["tags"] == ["family", "lists"]


def test_add_loop_with_due(capsys):
    run("add", "loop", "chase builder", "Chase builder quote", "--due", "2026-01-08")
    assert memory.get("chase-builder")["due"] == "2026-01-08"


def test_add_invalid_type_exits(capsys):
    with pytest.raises(SystemExit):
        run("add", "gossip", "x", "y")


def test_add_loop_without_due_reports_error(capsys):
    with pytest.raises(SystemExit):
        run("add", "loop", "x", "y")
    assert "due date" in capsys.readouterr().err


def test_show_missing(capsys):
    with pytest.raises(SystemExit):
        run("show", "nope")
    assert "No memory entry" in capsys.readouterr().err


def test_search(capsys):
    memory.add("lesson", "gws scopes", "Re-auth gws with every scope")
    run("search", "gws")
    assert "gws-scopes" in capsys.readouterr().out


def test_list_by_type(capsys):
    memory.add("lesson", "a", "Lesson A")
    memory.add("fact", "b", "Fact B")
    run("list", "--type", "lesson")
    out = capsys.readouterr().out
    assert "Lesson A" in out and "Fact B" not in out


def test_done_closes_loop(capsys):
    memory.add("loop", "chase", "Chase it", due="2026-01-01")
    run("done", "chase", "Replied")
    assert memory.get("chase") is None
    assert "Closed" in capsys.readouterr().out


def test_archive(capsys):
    memory.add("preference", "old", "Old rule")
    run("archive", "old", "Superseded by new rule")
    assert memory.get("old") is None


def test_journal(capsys):
    run("journal", "Archived", "12", "newsletters")
    assert "Archived 12 newsletters" in memory.recent_journal()[0]


def test_brief(capsys):
    memory.add("preference", "drafts", "Show drafts first")
    run("brief")
    assert "Show drafts first" in capsys.readouterr().out


def test_lint_clean(capsys):
    run("lint")
    assert "No issues" in capsys.readouterr().out


def test_import_claude(tmp_path, capsys):
    src = tmp_path / "claude"
    src.mkdir()
    (src / "f.md").write_text("---\nname: x\ndescription: X rule\ntype: feedback\n---\nBody\n")
    run("import-claude", str(src))
    assert "Imported 1" in capsys.readouterr().out
