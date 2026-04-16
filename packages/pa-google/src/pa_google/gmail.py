"""Gmail helpers — uses cli_runner to call gws CLI."""

import base64
from email.mime.text import MIMEText

from pa_core.cli_runner import run_gws


def get_inbox_emails(limit: int = 50, unread_only: bool = False) -> list[dict]:
    """Fetch emails in inbox. By default gets ALL inbox emails (read + unread) for full triage."""
    q = "in:inbox"
    if unread_only:
        q += " is:unread"
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
) -> dict:
    """Create a Gmail draft and return {"draft_id": ..., "message_id": ..., "link": ...}.

    Uses email.mime to build a proper RFC 2822 message. If thread_id is provided,
    the draft is threaded into that conversation.

    Raises RuntimeError if the draft ends up trashed (Gmail silently trashes
    drafts with malformed headers).
    """
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


def get_email_body(message_id: str) -> str:
    """Get the full body of an email."""
    result = run_gws("gmail", "users.messages", "get", {
        "userId": "me",
        "id": message_id,
        "format": "full",
    })
    payload = result.get("payload", {})
    parts = payload.get("parts", [payload])
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8")
    return ""
