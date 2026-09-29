"""Tests for pa_google.gmail.get_inbox_emails date filtering."""

from unittest.mock import patch

from pa_google.gmail import get_inbox_emails


@patch("pa_google.gmail.run_gws")
def test_after_adds_query_filter(mock_gws):
    mock_gws.return_value = {"messages": []}
    get_inbox_emails(after=1718000000)
    # first call is the messages.list call; params is the 4th positional arg
    params = mock_gws.call_args_list[0].args[3]
    assert "after:1718000000" in params["q"]


@patch("pa_google.gmail.run_gws")
def test_no_after_keeps_plain_query(mock_gws):
    mock_gws.return_value = {"messages": []}
    get_inbox_emails()
    params = mock_gws.call_args_list[0].args[3]
    assert "after:" not in params["q"]
    assert params["q"] == "in:inbox"


@patch("pa_google.gmail.run_gws")
def test_after_combines_with_unread(mock_gws):
    mock_gws.return_value = {"messages": []}
    get_inbox_emails(unread_only=True, after=1718000000)
    params = mock_gws.call_args_list[0].args[3]
    assert "is:unread" in params["q"]
    assert "after:1718000000" in params["q"]
