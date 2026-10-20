---
name: email-triage
description: Triage the user's Gmail inbox to empty. Use when asked to triage, check, clear or go through email, or as part of a morning check-in. Covers incremental triage since the last pass, the six outcomes per email, the bar for new tasks, and reading school newsletters in full.
---

# Email triage

Goal: an empty inbox, and only real work in the task list. Turning mail into tasks is how the backlog grows, so the bar for a new task is high.

## Steps

1. `uv run pa-google emails --since-last --json` lists mail since the last pass. On the first run there is no cursor, so it shows the whole inbox and says so.
2. Read each thread in full with `uv run pa-google read <id>`: body, attachments and linked documents, not the snippet.
3. Give each email exactly one outcome (below).
4. Archive with `uv run pa-google archive <id> [<id> ...]`. It archives whole threads.
5. Finish with `uv run pa-google emails --mark-triaged`. Mail that arrives mid-pass is picked up next time.
6. Summarise in a few lines: what needs the user, what you did, and how many you archived. Then `uv run pa-core memory journal "Triage: ..."` with the counts.

## Outcomes

1. **Archive.** Noise and anything with no action.
2. **Done now.** You handled it: calendar entry added (`pa-google event add`), invite accepted, receipt filed, fact saved to memory. Then archive.
3. **Update an existing task.** Search first (`uv run pa-notion tasks list --open --search "<words>"`). Add the facts and the Gmail link with `uv run pa-notion tasks update <id> --append-notes "..."`, adjust `--due` if needed, then archive.
4. **Digest.** Worth knowing, nothing to do. Mention it in the summary, then archive.
5. **Draft a reply.** `uv run pa-google draft --to ... --subject ... --body-file ... --thread <thread-id>`, show the link, and archive once the user has dealt with it. Never send.
6. **New task.** Only if all of these hold:
   - the user personally has to do something (you cannot do it or draft it);
   - it takes more than a few minutes or has a real deadline;
   - no open task already covers it (`pa-notion tasks add` refuses near-duplicates).

Never create a task for:

- automatic payments, direct debits, payment retries and receipts (check the receipt instead);
- deliveries, dispatch notices and order confirmations;
- security sign-in alerts, unless they show a new device or location the user did not recognise (then one task, not one per alert);
- usage or quota alerts, SEO and analytics reports, and newsletters (read them, extract dates, then archive);
- "read this document" requests, unless they have a deadline;
- verifying something you can check yourself (calendar, receipts, account pages).

Limits: at most three new tasks per pass without asking. If more seem needed, list them in the summary and let the user pick. Group related items into one task with sub-points.

Before archiving anything with a date or event, make sure it is on the right calendar (`uv run pa-google calendar --days 30` to check, `pa-google event add` to add). Include the Gmail link in task notes: `https://mail.google.com/mail/u/0/#all/<message-id>`.

## School newsletters

- Read the actual newsletter, not only the email wrapper. Check HTML and plain text, attachments and linked documents; tracking links can hide a Google Docs URL in the anchor text.
- Download the PDF, or export a linked Google Doc as PDF. Save the source in ignored activity records.
- Extract the text and also look at image-only pages, posters, flyers and date tables. Empty extracted text does not mean an empty page.
- Use the current child, year and class mappings from private user instructions; recheck each school year. Include events for the relevant classes and years, whole-school dates that affect the children, and existing family tasks. Leave out other year groups and adverts.
- Check the family calendar before adding dates. Update changed details rather than duplicating repeated items. Use the configured invitees, source links and preparation details, and the configured time zone. Do not invent times, deadlines or years.
- Optional club availability is not a booking. Add optional items only when they fit existing family plans, marked "not booked". Do not backfill expired adverts.
- Track consent, payment, kit, costume, booking and childcare actions in existing tasks where possible. Check receipts before treating a payment reminder as unpaid. Optional donation requests do not authorise purchases.
- Archive only after the full source is read, calendar writes are verified and actions are tracked. If access fails, leave it in the inbox and say why.

Gmail gotchas (searching Trash and Spam, attachments to Drive): see `packages/pa-google/AGENTS.md`.
