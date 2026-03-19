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
uv run pa-telegram messages                    # Show new messages sent to the bot
uv run pa-telegram messages --json             # JSON output
uv run pa-telegram messages --ack              # Acknowledge after reading
uv run pa-telegram briefing                     # Send today's briefing
uv run pa-telegram briefing --date 2026-03-12   # Send specific date's briefing
```

## Reading Messages (getUpdates)

The bot reads incoming messages via Telegram's `getUpdates` long-polling endpoint.

- **Offset tracking**: The last acknowledged `update_id + 1` is stored in `activity/.telegram_offset`. Each `getUpdates` call passes this offset so only new messages are returned.
- **Two-phase design**: `get_messages()` fetches without acknowledging. `acknowledge_messages()` writes the offset. This means messages aren't lost if the process crashes between fetch and display.
- **Chat filtering**: Only messages from the configured `telegram.chat_id` are returned.
- **Auto-acknowledge**: `pa-core checkin` and `pa-core context` automatically acknowledge messages after displaying them. Use `pa-telegram messages` (without `--ack`) for read-only inspection.

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

## Evening Briefing Flow (Interactive via Telegram)

The evening briefing should be interactive — ask Tim about habits, gratitude, etc. via Telegram before generating the briefing.

### Interim approach (until Telegram polling is built — see issue #9)

1. **Send each habit question with inline keyboard buttons** — one question at a time:
   ```bash
   source $PA_ROOT/.env && curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
     -H "Content-Type: application/json" \
     -d '{
       "chat_id": "<chat_id>",
       "text": "💪 Exercise today?",
       "reply_markup": {
         "inline_keyboard": [
           [{"text": "Yes — smashed it", "callback_data": "exercise_yes"}],
           [{"text": "Light / walk", "callback_data": "exercise_light"}],
           [{"text": "Nope", "callback_data": "exercise_no"}]
         ]
       }
     }'
   ```
   Use inline keyboards for ALL check-in questions — never send plain text multiple choice. Tim should be able to tap buttons, not type.

2. **Wait for Tim to tap a button** — use `sleep` or ask Tim to confirm in terminal. Read the callback:
   ```bash
   curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates?offset=-1" | python3 -c "
   import json,sys
   results = json.load(sys.stdin).get('result',[])
   for r in results:
       cb = r.get('callback_query',{})
       if cb: print(cb.get('data',''))
       msg = r.get('message',{})
       if msg: print(msg.get('text',''))
   "
   ```

3. **Send next question** (reading, meditation, energy, gratitude) — each with its own inline keyboard

4. **For gratitude** — send a text question (no buttons, free text reply):
   ```bash
   uv run pa-telegram send "What's one thing you're grateful for today?"
   ```

5. **Log all responses** using `pa_core.daily_log.log_event()`

6. **Generate and send the evening briefing** (now including habit + gratitude data):
   ```bash
   uv run pa-core briefing --evening --save --telegram
   ```

### Button format for each habit

Send questions one at a time. Standard button layouts:

- **Exercise:** "Yes — smashed it" / "Light / walk" / "Nope"
- **Reading:** "Yes" / "No"
- **Meditation:** "Yes" / "No"
- **Energy:** "Good" / "Ok" / "Wiped"
- **Gratitude:** free text reply (no buttons)

### Key rules
- Always do the check-in BEFORE generating the briefing, so habit/gratitude data is included
- Don't skip the check-in — it's the whole point of the evening flow
- If Tim doesn't reply within 5 mins, send a gentle nudge, then generate without if still no reply
- Log everything — habits completed, skipped, or not logged

## Gotchas
- You MUST send `/start` to the bot before it can message you — Telegram requires this
- Telegram Markdown is a subset: no headings, no nested formatting. `_format_for_telegram()` handles conversion.
- If the bot token or chat ID is wrong, the error message from Telegram's API is usually descriptive
