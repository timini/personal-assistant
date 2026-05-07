"""Telegram Bot API client — send messages, read incoming messages, and briefings."""

import json
import re
from datetime import datetime
from pathlib import Path

import httpx

from pa_core.config import PA_ROOT, get_secret, get_user_config

TELEGRAM_API = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096
_OFFSET_FILE = PA_ROOT / "activity" / ".telegram_offset"
_MEDIA_DIR = PA_ROOT / "activity" / "telegram_media"


def _get_bot_token() -> str:
    return get_secret("TELEGRAM_BOT_TOKEN")


def _get_chat_id() -> str:
    config = get_user_config()
    chat_id = config.get("telegram", {}).get("chat_id")
    if not chat_id:
        raise KeyError(
            "telegram.chat_id not found in user.yaml. "
            "Add it under 'telegram: { chat_id: \"YOUR_ID\" }'"
        )
    return str(chat_id)


def _format_for_telegram(markdown: str) -> str:
    """Convert standard markdown to Telegram-compatible markdown.

    Telegram's Markdown mode supports *bold*, _italic_, `code`, and [links].
    It does NOT support headings (# / ## / ###), so we convert those to bold.
    """
    lines = []
    for line in markdown.split("\n"):
        # Convert ### heading → bold
        if line.startswith("###"):
            line = f"*{line.lstrip('#').strip()}*"
        # Convert ## heading → bold with extra spacing
        elif line.startswith("##"):
            line = f"\n*{line.lstrip('#').strip()}*"
        # Convert # heading → bold uppercase
        elif line.startswith("#"):
            line = f"*{line.lstrip('#').strip()}*"
        lines.append(line)
    return "\n".join(lines)


def _split_message(text: str) -> list[str]:
    """Split text into chunks that fit Telegram's 4096-char limit.

    Splits on paragraph boundaries (double newline) to keep messages readable.
    """
    if len(text) <= MAX_MESSAGE_LENGTH:
        return [text]

    chunks = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= MAX_MESSAGE_LENGTH:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # If a single paragraph exceeds the limit, split on single newlines
            if len(paragraph) > MAX_MESSAGE_LENGTH:
                for line in paragraph.split("\n"):
                    line_candidate = f"{current}\n{line}" if current else line
                    if len(line_candidate) <= MAX_MESSAGE_LENGTH:
                        current = line_candidate
                    else:
                        if current:
                            chunks.append(current)
                        current = line
            else:
                current = paragraph
    if current:
        chunks.append(current)
    return chunks


def send_message(text: str, parse_mode: str = "Markdown") -> list[dict]:
    """Send a message to the configured Telegram chat.

    Returns a list of Telegram API responses (one per chunk if message was split).
    """
    token = _get_bot_token()
    chat_id = _get_chat_id()
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"

    chunks = _split_message(text)
    responses = []
    for chunk in chunks:
        resp = httpx.post(
            url,
            json={"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode},
            timeout=30,
        )
        data = resp.json()
        if not data.get("ok"):
            description = data.get("description", "Unknown error")
            raise RuntimeError(f"Telegram API error: {description}")
        responses.append(data)
    return responses


def _download_photo(file_id: str, target_path: Path) -> Path | None:
    """Download a Telegram photo to ``target_path``.

    Returns the path on success, or ``None`` on failure (non-fatal — the
    caller still surfaces the message, just without an ``image_path``).
    """
    token = _get_bot_token()
    meta_resp = httpx.get(
        f"{TELEGRAM_API}/bot{token}/getFile",
        params={"file_id": file_id},
        timeout=30,
    )
    meta = meta_resp.json()
    if not meta.get("ok"):
        return None
    file_path = meta["result"].get("file_path")
    if not file_path:
        return None
    target_path.parent.mkdir(parents=True, exist_ok=True)
    download = httpx.get(
        f"{TELEGRAM_API}/file/bot{token}/{file_path}",
        timeout=60,
    )
    if download.status_code != 200:
        return None
    target_path.write_bytes(download.content)
    return target_path


def _read_offset() -> int | None:
    """Read the last acknowledged update_id from the offset file."""
    if _OFFSET_FILE.exists():
        text = _OFFSET_FILE.read_text().strip()
        if text:
            return int(text)
    return None


def _write_offset(offset: int) -> None:
    """Write the offset (last acknowledged update_id + 1) to the offset file."""
    _OFFSET_FILE.write_text(str(offset))


def get_messages(limit: int = 100) -> list[dict]:
    """Fetch new messages sent to the bot by the configured chat_id.

    Uses getUpdates with offset tracking. Returns list of
    {update_id, date, time, text, from_name} dicts.

    Two-phase design: call acknowledge_messages() after surfacing to mark as read.
    """
    token = _get_bot_token()
    chat_id = str(_get_chat_id())
    url = f"{TELEGRAM_API}/bot{token}/getUpdates"

    params: dict = {"limit": limit, "allowed_updates": json.dumps(["message"])}
    offset = _read_offset()
    if offset is not None:
        params["offset"] = offset

    resp = httpx.get(url, params=params, timeout=30)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data.get('description', 'Unknown error')}")

    messages = []
    for update in data.get("result", []):
        msg = update.get("message")
        if not msg:
            continue
        # Filter to configured chat_id only
        if str(msg.get("chat", {}).get("id")) != chat_id:
            continue
        text = msg.get("text") or msg.get("caption") or ""
        image_path: str | None = None

        photo = msg.get("photo")
        if photo:
            largest = photo[-1]
            file_id = largest.get("file_id")
            if file_id:
                ts = msg.get("date", 0)
                dt_for_name = datetime.fromtimestamp(ts)
                target = _MEDIA_DIR / (
                    f"{dt_for_name.strftime('%Y-%m-%d')}_{update['update_id']}.jpg"
                )
                downloaded = _download_photo(file_id, target)
                if downloaded is not None:
                    image_path = str(downloaded)

        if not text and not image_path:
            continue

        ts = msg.get("date", 0)
        dt = datetime.fromtimestamp(ts)
        from_user = msg.get("from", {})
        from_name = from_user.get("first_name", "Unknown")
        if from_user.get("last_name"):
            from_name += f" {from_user['last_name']}"

        entry: dict = {
            "update_id": update["update_id"],
            "date": dt.strftime("%Y-%m-%d"),
            "time": dt.strftime("%H:%M"),
            "text": text,
            "from_name": from_name,
        }
        if image_path:
            entry["image_path"] = image_path
        messages.append(entry)

    return messages


def acknowledge_messages(messages: list[dict]) -> None:
    """Mark messages as read by writing max update_id + 1 to offset file.

    Next getUpdates call will skip these messages.
    """
    if not messages:
        return
    max_id = max(m["update_id"] for m in messages)
    _write_offset(max_id + 1)


def send_briefing(date: str | None = None) -> list[dict]:
    """Generate the daily briefing and send it via Telegram."""
    from pa_core.briefing import generate_briefing

    briefing = generate_briefing(date=date)
    formatted = _format_for_telegram(briefing)
    return send_message(formatted)


def send_evening_briefing(date: str | None = None) -> list[dict]:
    """Generate the evening briefing and send it via Telegram."""
    from pa_core.briefing import generate_evening_briefing

    briefing = generate_evening_briefing(date=date)
    formatted = _format_for_telegram(briefing)
    return send_message(formatted)
