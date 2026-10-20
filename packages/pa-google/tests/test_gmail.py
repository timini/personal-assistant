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
import base64
from email import message_from_bytes
from email import policy

from pa_google.gmail import create_draft


def test_create_draft_attaches_file(monkeypatch, tmp_path):
    photo = tmp_path / "bike.jpg"
    photo.write_bytes(b"jpeg-data")
    calls = []

    def fake_run_gws(service, resource, method, params=None, *, body=None, **kwargs):
        calls.append((resource, method, body))
        if resource == "users.drafts" and method == "create":
            return {"id": "draft-1", "message": {"id": "message-1"}}
        return {"labelIds": ["DRAFT"]}

    monkeypatch.setattr("pa_google.gmail.run_gws", fake_run_gws)
    monkeypatch.setattr("time.sleep", lambda _: None)

    create_draft(
        "claims@example.com",
        "Claim evidence",
        "Please see attached.",
        attachments=[photo],
    )

    raw = calls[0][2]["message"]["raw"]
    message = message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default)
    attached = list(message.iter_attachments())
    assert len(attached) == 1
    assert attached[0].get_filename() == "bike.jpg"
    assert attached[0].get_payload(decode=True) == b"jpeg-data"
