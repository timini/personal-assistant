# pa-telegram — Telegram Notifications

## Goal
Deliver briefings and notifications to Tim's phone via Telegram Bot API.

## How it works
- Uses the Telegram Bot API directly via `httpx` (no heavy library needed)
- Bot token stored in `.env` as `TELEGRAM_BOT_TOKEN`
- Chat ID stored in `user.yaml` under `telegram.chat_id`
- Messages are formatted from standard markdown to Telegram-compatible markdown (headings → bold)
- Messages over 4096 chars are automatically split on paragraph boundaries

## CLI Commands
```bash
uv run pa-telegram send "Hello world"          # Send arbitrary message
uv run pa-telegram briefing                     # Send today's briefing
uv run pa-telegram briefing --date 2026-03-12   # Send specific date's briefing
```

Also available via pa-core:
```bash
uv run pa-core briefing --telegram              # Send briefing to Telegram
uv run pa-core briefing --save --backup --telegram  # Save + backup + send
```

## Setup
1. Open Telegram, search `@BotFather`, send `/newbot`
2. Choose a name (e.g. "PA Bot") and username (e.g. `pa_briefing_bot`)
3. Copy the token → add to `.env` as `TELEGRAM_BOT_TOKEN=<token>`
4. Send `/start` to your new bot in Telegram (required before bot can message you)
5. Get your chat ID: `curl https://api.telegram.org/bot<TOKEN>/getUpdates` → extract `message.chat.id`
6. Add to `user.yaml`:
   ```yaml
   telegram:
     chat_id: "123456789"
   ```
7. Test: `uv run pa-telegram send "Hello from PA!"`

## Gotchas
- You MUST send `/start` to the bot before it can message you — Telegram requires this
- Telegram Markdown is a subset: no headings, no nested formatting. `_format_for_telegram()` handles conversion.
- If the bot token or chat ID is wrong, the error message from Telegram's API is usually descriptive
