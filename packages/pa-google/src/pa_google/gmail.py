"""Gmail helpers — uses cli_runner to call gws CLI."""

import base64
import mimetypes
from email.message import EmailMessage
from email.mime.text import MIMEText
from pathlib import Path

from pa_core.cli_runner import run_gws


def get_inbox_emails(
    limit: int = 50, unread_only: bool = False, after: int | None = None, query: str | None = None
) -> list[dict]:
    """Fetch emails in inbox. By default gets ALL inbox emails (read + unread) for full triage.

    If `after` (Unix epoch seconds) is given, only return mail received after that
    time (Gmail `after:` accepts epoch seconds) — used for incremental triage.
    A `query` replaces the inbox scope with any Gmail search, e.g. "from:x in:all".
    """
    q = query or "in:inbox"
    if unread_only:
        q += " is:unread"
    if after:
        q += f" after:{after}"
    result = run_gws("gmail", "users.messages", "list", {
        "userId": "me",
        "q": q,
        "maxResults": limit,
    })
    messages = result.get("messages", [])
    if not messages:
        return []

    detailed = []
    for msg in messages:
        detail = run_gws("gmail", "users.messages", "get", {
            "userId": "me",
            "id": msg["id"],
            "format": "full",
        })
        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        detailed.append({
            "id": msg["id"],
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "snippet": detail.get("snippet", ""),
        })
    return detailed


def archive_email(message_id: str) -> None:
    """Archive an email by removing INBOX label at the thread level.

    IMPORTANT: Must use threads.modify, not messages.modify — Gmail UI
    shows threads, and archiving individual messages doesn't remove the
    thread from inbox if other messages in the thread still have INBOX.
    """
    # Get the thread ID from the message
    msg = run_gws("gmail", "users.messages", "get", {
        "userId": "me",
        "id": message_id,
        "format": "minimal",
    })
    thread_id = msg["threadId"]
    run_gws("gmail", "users.threads", "modify", {
        "userId": "me",
        "id": thread_id,
    }, body={"removeLabelIds": ["INBOX", "UNREAD"]})


def create_draft(
    to: str,
    subject: str,
    body: str,
    *,
    thread_id: str | None = None,
    from_addr: str = "me",
    attachments: list[Path] | None = None,
) -> dict:
    """Create a Gmail draft and return {"draft_id": ..., "message_id": ..., "link": ...}.

    Uses email.mime to build a proper RFC 2822 message. If thread_id is provided,
    the draft is threaded into that conversation.

    Raises RuntimeError if the draft ends up trashed (Gmail silently trashes
    drafts with malformed headers).
    """
    if attachments:
        msg = EmailMessage()
        msg.set_content(body)
        for attachment in attachments:
            content_type, _ = mimetypes.guess_type(attachment.name)
            maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
            msg.add_attachment(
                attachment.read_bytes(),
                maintype=maintype,
                subtype=subtype,
                filename=attachment.name,
            )
    else:
        msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to
    msg["Subject"] = subject
    if from_addr and from_addr != "me":
        msg["From"] = from_addr

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    draft_body: dict = {"message": {"raw": raw}}
    if thread_id:
        draft_body["message"]["threadId"] = thread_id

    result = run_gws("gmail", "users.drafts", "create", {"userId": "me"}, body=draft_body)

    draft_id = result.get("id", "")
    message_id = result.get("message", {}).get("id", "")

    # Gmail sometimes silently trashes drafts (especially on existing threads).
    # This can happen asynchronously after creation, so we wait briefly and
    # check twice to catch delayed trashing.
    import time
    for _ in range(2):
        time.sleep(1)
        check = run_gws("gmail", "users.messages", "get", {
            "userId": "me", "id": message_id, "format": "minimal",
        })
        if "TRASH" in check.get("labelIds", []):
            run_gws("gmail", "users.messages", "untrash", {"userId": "me", "id": message_id})

    link = f"https://mail.google.com/mail/u/0/#drafts/{message_id}"
    return {"draft_id": draft_id, "message_id": message_id, "link": link}


def _walk(part: dict):
    yield part
    for child in part.get("parts", []):
        yield from _walk(child)


def _decode(part: dict) -> str:
    data = part.get("body", {}).get("data", "")
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace") if data else ""


def read_email(message_id: str) -> dict:
    """Fetch one message with headers, readable body text and attachment list.

    Searches nested MIME parts. Falls back to the HTML part converted to text when
    there is no plain-text part.
    """
    from bs4 import BeautifulSoup

    msg = run_gws("gmail", "users.messages", "get", {"userId": "me", "id": message_id, "format": "full"})
    payload = msg.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    parts = list(_walk(payload))

    body = next((_decode(p) for p in parts if p.get("mimeType") == "text/plain" and _decode(p)), "")
    if not body:
        html = next((_decode(p) for p in parts if p.get("mimeType") == "text/html" and _decode(p)), "")
        body = BeautifulSoup(html, "html.parser").get_text(" ", strip=True) if html else ""

    attachments = [
        {"filename": p["filename"], "attachment_id": p.get("body", {}).get("attachmentId", ""),
         "mime_type": p.get("mimeType", "")}
        for p in parts if p.get("filename")
    ]
    return {
        "id": message_id,
        "thread_id": msg.get("threadId", ""),
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "subject": headers.get("Subject", ""),
        "date": headers.get("Date", ""),
        "labels": msg.get("labelIds", []),
        "body": body,
        "attachments": attachments,
        "link": f"https://mail.google.com/mail/u/0/#all/{message_id}",
    }


def get_email_body(message_id: str) -> str:
    """Get the readable body of an email."""
    return read_email(message_id)["body"]
