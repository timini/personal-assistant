"""Tests for the email and calendar commands that replace hand-written gws scripts."""

import base64
import json
from unittest.mock import patch

import pytest

from pa_google import cli
from pa_google.gmail import get_inbox_emails, read_email


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def _run(argv, capsys):
    with patch.object(cli.sys, "argv", ["pa-google", *argv]):
        cli.main()
    return capsys.readouterr().out


MESSAGE = {
    "id": "m1", "threadId": "t1", "labelIds": ["INBOX"],
    "payload": {
        "headers": [{"name": "From", "value": "School <office@example.org>"},
                    {"name": "Subject", "value": "Newsletter"},
                    {"name": "Date", "value": "Mon, 19 Oct 2026 09:00:00 +0100"}],
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "multipart/alternative", "parts": [
                {"mimeType": "text/html", "body": {"data": _b64("<p>Trip on <b>4 Nov</b></p>")}},
            ]},
            {"mimeType": "application/pdf", "filename": "letter.pdf", "body": {"attachmentId": "a1", "size": 10}},
        ],
    },
}


@patch("pa_google.gmail.run_gws", return_value=MESSAGE)
def test_read_email_finds_nested_html_and_lists_attachments(_gws):
    email = read_email("m1")
    assert email["subject"] == "Newsletter"
    assert email["thread_id"] == "t1"
    assert "Trip on 4 Nov" in email["body"]
    assert email["attachments"] == [{"filename": "letter.pdf", "attachment_id": "a1", "mime_type": "application/pdf"}]
    assert email["link"] == "https://mail.google.com/mail/u/0/#all/m1"


@patch("pa_google.gmail.run_gws")
def test_read_email_prefers_plain_text(mock_gws):
    msg = json.loads(json.dumps(MESSAGE))
    msg["payload"]["parts"][0]["parts"].insert(0, {"mimeType": "text/plain", "body": {"data": _b64("Plain body")}})
    mock_gws.return_value = msg
    assert read_email("m1")["body"] == "Plain body"


@patch("pa_google.gmail.run_gws")
def test_query_replaces_inbox_scope(mock_gws):
    mock_gws.return_value = {"messages": []}
    get_inbox_emails(query="from:school in:all")
    assert mock_gws.call_args_list[0].args[3]["q"] == "from:school in:all"


def test_cli_read_prints_headers_and_body(capsys):
    email = {"id": "m1", "thread_id": "t1", "from": "a@example.org", "to": "", "subject": "Hi",
             "date": "today", "body": "Hello there", "attachments": [], "link": "L", "labels": []}
    with patch("pa_google.cli.read_email", return_value=email):
        out = _run(["read", "m1"], capsys)
    assert "Subject: Hi" in out and "Hello there" in out


def test_cli_archive_handles_several_ids(capsys):
    with patch("pa_google.cli.archive_email") as m:
        out = _run(["archive", "m1", "m2"], capsys)
    assert [c.args[0] for c in m.call_args_list] == ["m1", "m2"]
    assert "Archived 2" in out


def test_cli_draft_reads_body_from_file(capsys, tmp_path):
    body = tmp_path / "body.txt"
    body.write_text("Line one\nLine two")
    with patch("pa_google.cli.create_draft", return_value={"link": "https://draft"}) as m:
        out = _run(["draft", "--to", "a@example.org", "--subject", "Re: x",
                    "--body-file", str(body), "--thread", "t1"], capsys)
    assert m.call_args.kwargs["body"] == "Line one\nLine two"
    assert m.call_args.kwargs["thread_id"] == "t1"
    assert "https://draft" in out


def test_cli_emails_query(capsys):
    with patch("pa_google.cli.get_inbox_emails", return_value=[]) as m:
        _run(["emails", "--query", "invoice in:all"], capsys)
    assert m.call_args.kwargs["query"] == "invoice in:all"


def test_cli_event_add(capsys):
    event = {"id": "e1", "summary": "Dentist", "start": "2026-11-02T09:00:00Z", "end": "x",
             "link": "https://cal", "calendar_id": "primary"}
    with patch("pa_google.cli.add_event", return_value=event) as m:
        out = _run(["event", "add", "Dentist", "--start", "2026-11-02T09:00", "--calendar", "Family",
                    "--attendee", "a@example.org", "--attendee", "b@example.org"], capsys)
    assert m.call_args.args == ("Dentist", "2026-11-02T09:00", None)
    assert m.call_args.kwargs["calendar"] == "Family"
    assert m.call_args.kwargs["attendees"] == ["a@example.org", "b@example.org"]
    assert "e1" in out and "https://cal" in out


def test_cli_event_update_and_delete(capsys):
    with patch("pa_google.cli.update_event", return_value={"id": "e1", "summary": "S", "start": "s",
                                                           "end": "e", "link": "", "calendar_id": "p"}) as up:
        _run(["event", "update", "e1", "--title", "S"], capsys)
    assert up.call_args.kwargs["title"] == "S"
    assert up.call_args.kwargs["start"] is None
    with patch("pa_google.cli.delete_event") as de:
        out = _run(["event", "delete", "e1", "--calendar", "Family"], capsys)
    de.assert_called_once_with("e1", calendar="Family")
    assert "Deleted" in out


def test_cli_calendar_text_shows_event_ids(capsys):
    events = [{"id": "e1", "summary": "Dentist", "start": "2026-11-02T09:00:00Z", "calendar": None}]
    with patch("pa_google.cli.get_all_todays_events", return_value=events):
        out = _run(["calendar"], capsys)
    assert "e1" in out


def test_cli_event_add_bad_times_exits_cleanly(capsys):
    with patch("pa_google.cli.add_event", side_effect=ValueError("End before start")):
        with pytest.raises(SystemExit):
            _run(["event", "add", "X", "--start", "2026-11-02T09:00", "--end", "2026-11-02T08:00"], capsys)


def test_send_draft_finds_draft_by_message_id_and_verifies_sent():
    from pa_google.gmail import send_draft

    def fake(service, resource, method, params=None, body=None, **kw):
        if (resource, method) == ("users.drafts", "list"):
            return {"drafts": [{"id": "r-1", "message": {"id": "other"}},
                               {"id": "r-2", "message": {"id": "m9"}}]}
        if (resource, method) == ("users.drafts", "send"):
            assert body == {"id": "r-2"}
            return {"id": "s1", "threadId": "t1"}
        if (resource, method) == ("users.messages", "get"):
            return {"id": "s1", "labelIds": ["SENT"], "payload": {"headers": [
                {"name": "To", "value": "a@example.com"}, {"name": "Subject", "value": "Hi"}]}}
        raise AssertionError((resource, method))

    with patch("pa_google.gmail.run_gws", side_effect=fake):
        sent = send_draft("m9")
    assert sent == {"id": "s1", "to": "a@example.com", "subject": "Hi",
                    "link": "https://mail.google.com/mail/u/0/#sent/s1"}


def test_send_draft_unknown_id_raises():
    from pa_google.gmail import send_draft

    with patch("pa_google.gmail.run_gws", return_value={"drafts": []}):
        with pytest.raises(ValueError):
            send_draft("missing")


def test_cli_send_prints_links(capsys):
    sent = {"id": "s1", "to": "a@example.com", "subject": "Hi", "link": "https://sent/s1"}
    with patch("pa_google.cli.send_draft", return_value=sent) as m:
        out = _run(["send", "m1", "m2"], capsys)
    assert m.call_count == 2
    assert "Sent to a@example.com: Hi  https://sent/s1" in out
