"""WhatsApp client — wraps wacli CLI to read messages."""

import json
from datetime import datetime, timedelta

from pa_core.cli_runner import run_cli, parse_json_output
from pa_core.config import PA_ROOT

_OFFSET_FILE = PA_ROOT / "activity" / ".whatsapp_offset"


def _run_wacli(args: list[str], *, timeout: int = 60) -> list | dict:
    """Run a wacli command with --json and parse the output."""
    cmd = ["wacli", "--json", *args]
    result = run_cli(cmd, timeout=timeout, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else ""
        raise RuntimeError(f"wacli error: {stderr or 'unknown error'}")
    stdout = result.stdout.strip()
    if not stdout:
        return []
    return json.loads(stdout)


def _read_offset() -> str | None:
    """Read the last acknowledged timestamp from the offset file."""
    if _OFFSET_FILE.exists():
        text = _OFFSET_FILE.read_text().strip()
        if text:
            return text
    return None


def _write_offset(timestamp: str) -> None:
    """Write the latest message timestamp to the offset file."""
    _OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OFFSET_FILE.write_text(timestamp)


def get_messages(limit: int = 50) -> list[dict]:
    """Fetch recent WhatsApp messages since last acknowledgment.

    Returns list of {date, time, text, from_name, chat_name, message_id} dicts.
    Two-phase design: call acknowledge_messages() after surfacing to mark as read.
    """
    offset = _read_offset()

    args = ["messages", "list", "--limit", str(limit)]
    if offset:
        args.extend(["--after", offset])
    else:
        # First run: only get messages from today
        today = datetime.now().strftime("%Y-%m-%d")
        args.extend(["--after", today])

    data = _run_wacli(args)
    if not isinstance(data, list):
        data = [data] if data else []

    messages = []
    for msg in data:
        text = msg.get("body") or msg.get("text") or msg.get("Body") or msg.get("Text", "")
        if not text:
            continue

        # Parse timestamp
        ts = msg.get("timestamp") or msg.get("Timestamp") or msg.get("time") or ""
        try:
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts)
            elif ts:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                dt = datetime.now()
        except (ValueError, OSError):
            dt = datetime.now()

        # Extract sender and chat info
        from_name = (
            msg.get("pushName")
            or msg.get("PushName")
            or msg.get("sender_name")
            or msg.get("SenderName")
            or msg.get("from")
            or "Unknown"
        )
        chat_name = (
            msg.get("chat_name")
            or msg.get("ChatName")
            or msg.get("chatName")
            or ""
        )
        message_id = msg.get("id") or msg.get("ID") or msg.get("message_id") or ""

        messages.append({
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M"),
            "text": text,
            "from_name": from_name,
            "chat_name": chat_name,
            "message_id": str(message_id),
            "timestamp": ts,
        })

    return messages


def acknowledge_messages(messages: list[dict]) -> None:
    """Mark messages as read by writing latest timestamp to offset file.

    Next get_messages() call will skip these messages.
    """
    if not messages:
        return
    # Find the latest timestamp
    timestamps = [m.get("timestamp", "") for m in messages if m.get("timestamp")]
    if timestamps:
        _write_offset(str(max(timestamps)))
    else:
        # Fallback: use current time
        _write_offset(datetime.now().isoformat())


def list_chats(limit: int = 50) -> list[dict]:
    """List WhatsApp chats."""
    return _run_wacli(["chats", "list", "--limit", str(limit)])
