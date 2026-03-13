# pa-google — Package Instructions

## Goal
**Inbox Zero.** The inbox should be empty at all times.

## Email Triage Rules

1. Fetch ALL inbox emails (read + unread) — not just unread
2. For each email, decide immediately:
   - **Noise** (delivery updates, parking receipts, generic notifications) → archive
   - **Quick action** (pay a bill, RSVP, short reply) → do it, then archive
   - **Needs follow-up** → create Notion task with context + email link, then archive
   - **Time-sensitive** → flag to user
3. If an email has a matching Notion task, archive it immediately
4. Include Gmail links in Notion task notes: `https://mail.google.com/mail/u/0/#inbox/<message_id>`

## Gmail Gotchas

### Archive by THREAD, not message
ALWAYS use `gws gmail users threads modify` — NOT `messages modify`. Gmail UI shows threads. Use `archive_email()` from `pa_google.gmail`.

### gws CLI syntax
- Resources are space-separated: `users messages` not `users.messages`
- Parameters: `--params '<json>'`, request body: `--json '<json>'`
- gws prints preamble before JSON — `parse_json_output()` handles this

## Email Attachments → Google Drive
1. Save attachments using `gws gmail users messages attachments get`
2. Upload to Drive with `gws drive files create --upload <path>`
3. Organise into project folders: `PA/<Project>/<Sender or Context>/`
4. Link Drive files in relevant Notion project page

## Calendar
- Use `get_todays_events()` / `get_upcoming_events()` for context
- When creating events, check `user-instructions.md` at repo root for which calendar to use and who to invite
