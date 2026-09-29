# pa-whatsapp — Package Instructions

## Goal
**Surface and act on important messages.** WhatsApp is high-noise — flag messages needing response, ignore the rest.

## Status
Phase 1 — Read-only. Messages are surfaced in daily context/checkin alongside email and Telegram.

## Dependency
Requires `wacli` CLI tool installed and authenticated:
```bash
brew install steipete/tap/wacli
wacli auth  # One-time QR code scan with WhatsApp phone app
```

Auth state stored in `~/.wacli`. No API keys needed in `.env`.

## How it works
- `client.py` wraps `wacli` via subprocess (like pa-google wraps gws)
- Messages are fetched with `wacli --json messages list --after <offset>`
- Offset tracking in `activity/.whatsapp_offset` prevents duplicate reads
- Two-phase design: fetch messages, then acknowledge after surfacing

## CLI Commands
```bash
uv run pa-whatsapp messages              # Show recent messages
uv run pa-whatsapp messages --json       # JSON output
uv run pa-whatsapp messages --ack        # Acknowledge after reading
uv run pa-whatsapp chats                 # List chats
```

## Integration
- Messages appear automatically in `uv run pa-core context` and `uv run pa-core checkin`
- Auto-acknowledged after display (same as Telegram)

## Gotchas
- wacli must be authenticated first (`wacli auth`)
- wacli syncs from WhatsApp Web protocol — needs initial sync run (`wacli sync --follow`)
- Message format from wacli JSON may vary — client.py handles multiple field name conventions
