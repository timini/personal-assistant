# pa-google — Package Instructions

## Goal
**Inbox Zero.** The inbox should be empty at all times.

## Email Triage Rules

> **Principle: No email exists in isolation.** Always check if an email relates to something already tracked in Notion before deciding how to handle it. Extract every date, deadline, link, and action item — don't leave value on the table.

1. Fetch ALL inbox emails (read + unread) — not just unread
2. **Cross-reference each email against Notion tasks/projects** before categorising:
   - Search for related tasks by keyword (sender name, subject terms, project names)
   - If a related task exists, extract and act on ALL information in the email:
     - **Dates/events** → create calendar events (use Family Calendar for personal, primary for work)
     - **Deadlines** → update task due dates or create sub-tasks
     - **Links** (fundraising pages, sign-up forms, resources) → add to task notes
     - **Action items** → create sub-tasks or update existing task notes
     - **Key contacts/details** → add to task notes
   - An email that seems like "just info" on its own may be critical context for an existing task
3. **Then** categorise and act on each email:
   - **Noise** (delivery updates, parking receipts, generic notifications with no task relevance) → archive
   - **Quick action** (pay a bill, RSVP, short reply) → do it, then archive
   - **Needs follow-up** → create Notion task with context + email link, then archive
   - **Time-sensitive** → flag to user
4. If an email has a matching Notion task, archive it immediately
5. Include Gmail links in Notion task notes: `https://mail.google.com/mail/u/0/#inbox/<message_id>`

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

When composing any email on the user's behalf, use the `create_draft()` helper:
```python
from pa_google.gmail import create_draft
result = create_draft(
    to="recipient@example.com",
    subject="Re: Thread subject",
    body="Email body text",
    thread_id="<thread_id>",  # optional, for replies
)
print(result["link"])  # link for user to review
```

**Do NOT build raw RFC 2822 messages manually** — `create_draft()` uses `email.mime` for proper encoding and auto-recovers if Gmail silently trashes the draft (a known Gmail API quirk with malformed headers).

**NEVER use the Gmail MCP tool (`mcp__claude_ai_Gmail__gmail_create_draft`)** — it has a known bug where using `threadId` produces drafts with empty bodies. Always use `pa_google.gmail.create_draft()` which handles encoding, trash detection, and recovery correctly.

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
