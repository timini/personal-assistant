"""Telegram Bot API client — send messages and briefings."""

import re

import httpx

from pa_core.config import get_secret, get_user_config

TELEGRAM_API = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096


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
