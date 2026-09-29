"""Tests for pa_google.cli emails --since-last / --mark-triaged."""

from unittest.mock import patch

from pa_google import cli


def _run(argv):
    with patch.object(cli.sys, "argv", ["pa-google", *argv]):
        cli.main()


def test_since_last_with_state_passes_after():
    with patch("pa_google.cli.get_state", return_value={"epoch": 1718000000, "display": "Mon 12 Jun"}), \
         patch("pa_google.cli.get_inbox_emails", return_value=[]) as m:
        _run(["emails", "--since-last"])
    assert m.call_args.kwargs.get("after") == 1718000000


def test_since_last_no_state_full_inbox():
    with patch("pa_google.cli.get_state", return_value=None), \
         patch("pa_google.cli.get_inbox_emails", return_value=[]) as m:
        _run(["emails", "--since-last"])
    assert m.call_args.kwargs.get("after") is None


def test_plain_emails_no_after():
    with patch("pa_google.cli.get_inbox_emails", return_value=[]) as m:
        _run(["emails"])
    assert m.call_args.kwargs.get("after") is None


def test_mark_triaged_writes_state():
    with patch("pa_google.cli.set_state") as ms, \
         patch("pa_google.cli.get_now", return_value={"epoch": 1718999999, "display": "Mon 15 Jun 14:00"}), \
         patch("pa_google.cli.get_inbox_emails") as fetch:
        _run(["emails", "--mark-triaged"])
    ms.assert_called_once()
    args = ms.call_args.args
    assert args[0] == "last_email_triage"
    assert args[1]["epoch"] == 1718999999
    # marking triaged should not fetch emails
    fetch.assert_not_called()
