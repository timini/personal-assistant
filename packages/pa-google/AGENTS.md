# pa-google — Package Instructions

## Goal
**Inbox Zero.** The inbox should be empty at all times.

## Email triage

Use the `email-triage` skill (`.claude/skills/email-triage/SKILL.md`). The triage cursor lives in `activity/.state.json` under `last_email_triage`; `emails --since-last` reads it and `emails --mark-triaged` sets it.

## Gmail Gotchas

### Archive by THREAD, not message
Gmail UI shows threads, so archiving one message can leave the thread in the inbox. `uv run pa-google archive <message-id> ...` archives whole threads (it wraps `archive_email()`).

### Reading a message
`uv run pa-google read <message-id>` prints headers, thread id, attachment ids and the body. It searches nested MIME parts and converts HTML to text when there is no plain-text part. Use `--json` for scripts. Search with `uv run pa-google emails --query "from:x in:all"`.

### gws CLI syntax
- Resources are space-separated: `users messages` not `users.messages`
- Parameters: `--params '<json>'`, request body: `--json '<json>'`
- gws prints preamble before JSON — `parse_json_output()` handles this

### Searching Gmail — include trash and spam by default
By default, `gws gmail users messages list` only returns mail from the **inbox + archive**. Items in **Trash** and **Spam** are excluded unless you explicitly opt in.

When searching for an email and not finding it (e.g. order confirmations, receipts, anything the user expected to receive), **always re-run the search including Trash and Spam** before concluding it's not there. Users routinely auto-delete or accidentally trash receipts that turn out to be load-bearing later.

Two ways to do this:
- Add `in:all` to your query string: `'q': 'Brisks in:all'`
- Or pass `"includeSpamTrash": true` in the params

Example:
```bash
gws gmail users messages list --params '{"userId":"me","q":"Brisks in:all","maxResults":15}'
```

Default search flow when looking for a missing email:
1. Search inbox+archive
2. If nothing relevant → search again with `in:all`
3. Only declare "not found" after both have come up empty

## Email Attachments → Google Drive
1. Save attachments using `gws gmail users messages attachments get`
2. Upload to Drive with `gws drive files create --upload <path>`
3. Organise into project folders: `PA/<Project>/<Sender or Context>/`
4. Link Drive files in relevant Notion project page

## Sending Emails

**Never ask "shall I send it?" — always create a Gmail draft and provide the review link.**

When composing any email on the user's behalf, create a draft and give the link:
```bash
uv run pa-google draft --to recipient@example.com --subject "Re: Thread subject" \
  --body-file /path/to/body.txt --thread <thread_id>   # --thread is optional, for replies
```
This wraps `create_draft()` in `pa_google.gmail`.

When the user approves a draft ("send it", "send both"), send it with `uv run pa-google send <draft-id> [...]`, using the id from the `#drafts/<id>` link. It wraps `send_draft()`, which checks the message is labelled SENT and prints the Sent link. Never send without that approval.

**Do NOT build raw RFC 2822 messages manually** — `create_draft()` uses `email.mime` for proper encoding and auto-recovers if Gmail silently trashes the draft (a known Gmail API quirk with malformed headers).

**NEVER use the Gmail MCP tool (`mcp__claude_ai_Gmail__gmail_create_draft`)** — it has a known bug where using `threadId` produces drafts with empty bodies. Use `pa-google draft`, which handles encoding, trash detection, and recovery correctly.

## Research

Use the `research-doc` skill: research is saved as a Google Doc under `PA/<Project>/Research/` and linked from the task.

## Calendar

- `uv run pa-google calendar [--days N] [--json]` lists events from every configured calendar, with ids.
- `uv run pa-google event add "Title" --start 2026-01-08T14:00 [--end ...] [--calendar <label>] [--location ...] [--description ...] [--attendee a@example.com]`. Use `--start YYYY-MM-DD` for all-day events. Times without an offset are in the user's time zone. The command re-fetches the event and prints its id and link.
- `uv run pa-google event show|update|delete <id> --calendar <label>`. `update` changes only the fields given.
- `--calendar` takes a label from `user.yaml` (any case) or a raw calendar id; the default is the primary calendar.
- Check `user-instructions.md` and memory for which calendar to use and who to invite.

School newsletters are covered in the `email-triage` skill.
