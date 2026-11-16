"""Tests for pa_notebooklm.cli — arg parsing dispatches to client with expected kwargs."""

from unittest.mock import patch

import pytest

from pa_notebooklm import cli


def _run(argv):
    with patch.object(cli.sys, "argv", ["pa-notebooklm", *argv]):
        cli.main()


def test_explain_passes_sources_and_flags():
    with patch("pa_notebooklm.client.explain") as mock_explain:
        mock_explain.return_value = {
            "notebook_id": "nb1",
            "title": "X",
            "artifacts_started": ["audio", "video"],
            "waited": False,
        }
        _run(["explain", "a.pdf", "https://x.y", "--title", "X", "--only", "audio,video"])

    mock_explain.assert_called_once()
    args, kwargs = mock_explain.call_args
    assert args[0] == ["a.pdf", "https://x.y"]
    assert kwargs["title"] == "X"
    assert kwargs["artifacts"] == {"audio", "video"}
    assert kwargs["wait"] is False
    assert kwargs["language"] == "en"


def test_explain_default_artifacts_none():
    with patch("pa_notebooklm.client.explain") as mock_explain:
        mock_explain.return_value = {
            "notebook_id": "nb1",
            "title": "Explainer — a",
            "artifacts_started": ["audio"],
            "waited": True,
        }
        _run(["explain", "a.pdf", "--wait"])

    kwargs = mock_explain.call_args.kwargs
    assert kwargs["artifacts"] is None  # no --only → client uses its default set
    assert kwargs["wait"] is True


def test_explain_error_exits_1():
    with patch("pa_notebooklm.client.explain", side_effect=RuntimeError("boom")):
        with pytest.raises(SystemExit) as exc:
            _run(["explain", "a.pdf"])
    assert exc.value.code == 1


def test_list_calls_client(capsys):
    with patch("pa_notebooklm.client.list_notebooks", return_value=[{"id": "nb1", "title": "T", "sources": 2}]):
        _run(["list"])
    out = capsys.readouterr().out
    assert "T" in out and "nb1" in out


def test_list_json(capsys):
    with patch("pa_notebooklm.client.list_notebooks", return_value=[{"id": "nb1", "title": "T", "sources": 2}]):
        _run(["list", "--json"])
    out = capsys.readouterr().out
    assert '"id": "nb1"' in out
