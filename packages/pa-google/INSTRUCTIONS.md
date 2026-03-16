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

## Sending Emails

**Never ask "shall I send it?" — always create a Gmail draft and provide the review link.**

When composing any email on the user's behalf:
1. Build the MIME message and create a draft: `gws gmail users drafts create`
2. Provide the link: `https://mail.google.com/mail/u/0/#drafts/<message_id>`
3. The user will review and send themselves

## Research Tasks → Google Docs

When doing research (supplier comparisons, costings, options analysis, etc.), **always save the output as a Google Doc** so it persists across conversations.

1. **Create a Google Doc** with the research findings using `gws docs documents create`
2. **Organise in Drive** under the relevant project folder: `PA/<Project>/Research/`
   - e.g. `PA/House Renovation/Research/Door Suppliers Comparison.gdoc`
   - e.g. `PA/Garden/Research/Tree Costings.gdoc`
3. **Link the Doc** in the relevant Notion task notes so it's easy to find later
4. **Structure the doc clearly** — use headings, tables, pros/cons, pricing. Make it actionable.

Research that isn't saved is research wasted. The user should never have to ask Claude to redo work from a previous session.

## Calendar
- Use `get_all_todays_events()` / `get_all_upcoming_events()` for multi-calendar support
- Use `get_todays_events()` / `get_upcoming_events()` for single-calendar queries
- When creating events, check `user-instructions.md` at repo root for which calendar to use and who to invite
