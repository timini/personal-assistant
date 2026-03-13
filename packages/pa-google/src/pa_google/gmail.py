"""Gmail helpers — uses cli_runner to call gws CLI."""

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


def get_email_body(message_id: str) -> str:
    """Get the full body of an email."""
    import base64
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
