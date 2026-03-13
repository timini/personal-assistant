"""Gmail helpers — uses cli_runner to call gws CLI."""

from pa_core.cli_runner import run_gws


def get_unread_emails(limit: int = 10) -> list[dict]:
    """Fetch unread emails via gws CLI."""
    result = run_gws("gmail", "users.messages", "list", {
        "userId": "me",
        "q": "is:unread",
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
            "format": "metadata",
            "metadataHeaders": ["From", "Subject", "Date"],
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
