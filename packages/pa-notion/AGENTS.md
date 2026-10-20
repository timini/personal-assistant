# pa-notion — Package Instructions

## Goal
**Single source of truth for the user's tasks.** Only real work belongs here: something the user must do that the assistant cannot do or draft. See the root `AGENTS.md` for what never becomes a task.

## Task Rules

1. Every task needs: **status, priority, project, and clear title**
2. **Clear task names** — include enough context to act on (e.g. "Pay supplier invoice" not "Invoice")
3. **Group related tasks** under a parent using `Parent item` relation
4. **Set due dates** on time-sensitive items — work backwards from actual deadlines
5. **Present tasks grouped by project** when showing to user
6. When creating tasks from emails, include Gmail link in Notes field
7. **ALWAYS keep task Notes up to date.** Notion is the knowledge base. When working on a task, update its Notes with the current state of play — decisions made, emails sent/received, options discussed, draft content, and next steps. Notes should be detailed enough that anyone picking up the task can understand what's happened and what to do next. This applies especially to tasks involving email threads, people conversations, and multi-step processes.
8. **Search before adding.** `add_task()` and `pa-notion tasks add` refuse a title that nearly matches an open task and show the match. Update that task instead. Use `--force` only when the work is genuinely separate.
9. **Due dates carry lead time.** Set the due date a few days before the real deadline (renewals, lapses, payment dates), never on the deadline itself.

## Commands

```bash
uv run pa-notion tasks list --open --search "boiler" --json      # also --project, --lane, --due-before
uv run pa-notion tasks show <id>                                 # properties, notes and page body
uv run pa-notion tasks update <id> --append-notes "19 Oct: quote received, <gmail link>"
uv run pa-notion tasks update <id> --lane "🅿️ Parked" --due none # clear a due date
uv run pa-notion tasks add "Title" --project P --priority High --due 2026-01-08 --notes "..."
```

Use `--append-notes` to add to a task's notes; `--notes` replaces them. Task dicts from `list --json` include `notes`.

## Notion DB Schema (Tasks database)

- `Task` (title) — NOT "Name"
- `Status` (select: To Do / In Progress / Waiting / Done) — NOT "status" type, it's "select"
- `Priority` (select: Urgent / High / Medium / Low)
- `Project` (select: read available options from the configured database)
- `Due Date` (date)
- `Notes` (rich_text)
- `Parent item` (built-in sub-items relation)

## Task Hygiene

Use the `task-hygiene` skill for the weekly review. **Never mark a task Done without the user's explicit confirmation.**

## Sub-task Pattern
```python
parent_id = client.create_page(db_id, parent_props)["id"]
client.update_page(child_id, {"Parent item": {"relation": [{"id": parent_id}]}})
```

## Embedding Images from Google Drive

Notion image blocks require a publicly accessible URL. Private Google Drive files won't render via `drive.google.com/uc?id=...`. Instead:

1. Get the file's `thumbnailLink` via `gws drive files get --params '{"fileId": "...", "fields": "thumbnailLink"}'`
2. Replace the `=s220` size suffix with `=s1600` (or any desired resolution)
3. Use that `lh3.googleusercontent.com` URL as the external image URL in Notion

```python
# Example: add image block to a Notion page
{
    "type": "image",
    "image": {
        "type": "external",
        "external": {"url": "https://lh3.googleusercontent.com/drive-storage/...=s1600"},
        "caption": [{"type": "text", "text": {"content": "description"}}]
    }
}
```

The `gws drive files download` command does NOT reliably work for binary files. Always use the thumbnail URL approach for embedding in Notion.

## Project Pages
Each project has a dedicated page in Notion with task checklists, context, and reference material. When working on a project, check and update its page.
