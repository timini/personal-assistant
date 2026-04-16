# pa-notion — Package Instructions

## Goal
**Single source of truth for all tasks and commitments.** Every actionable item should end up as a Notion task.

## Task Rules

1. Every task needs: **status, priority, project, and clear title**
2. **Clear task names** — include enough context to act on (e.g. "Pay £800 for Landplan" not "800 Landplan")
3. **Group related tasks** under a parent using `Parent item` relation
4. **Set due dates** on time-sensitive items — work backwards from actual deadlines
5. **Present tasks grouped by project** when showing to user
6. When creating tasks from emails, include Gmail link in Notes field
7. **ALWAYS keep task Notes up to date.** Notion is the knowledge base. When working on a task, update its Notes with the current state of play — decisions made, emails sent/received, options discussed, draft content, and next steps. Notes should be detailed enough that anyone picking up the task can understand what's happened and what to do next. This applies especially to tasks involving email threads, people conversations, and multi-step processes.

## Notion DB Schema (Tasks database)

- `Task` (title) — NOT "Name"
- `Status` (select: To Do / In Progress / Waiting / Done) — NOT "status" type, it's "select"
- `Priority` (select: Urgent / High / Medium / Low)
- `Project` (select: Day Job, AI Transformation, Line Management, House Renovation, House Declutter, Garden, Fitness, Music, Landplan, Admin / Finance)
- `Due Date` (date)
- `Notes` (rich_text)
- `Parent item` (built-in sub-items relation)

## Task Hygiene

Tasks accumulate cruft. Every week (see CLAUDE.md Weekly workflow — Sunday evening checkin), run a hygiene pass to prevent the list becoming stale and overwhelming.

**Audit categories:**
- **No duplicates** — same action tracked in 2+ tasks → propose merge
- **Notes up to date** — every In Progress task must have current state in Notes (see rule 7 in Task Rules)
- **Stale In Progress** — In Progress for 14+ days with no Notes update → ask if still active
- **Urgent = due date** — Urgent priority without a due date is invalid; add the date or drop priority
- **Overdue is not a lie** — if due date has passed and the task isn't Done, decide: bump date, mark Waiting, or close
- **Meta/container tasks** — the `{Project} — tasks` pattern should be a home page with context, not a dumping ground; sub-tasks should be linked via `Parent item` relation
- **Orphan groups** — clusters of related tasks (same project, same topic) that should be linked via `Parent item`

**Never mark a task Done without the user's explicit confirmation** — he's been burned by this before. When in doubt, ASK.

## Sub-task Pattern
```python
parent_id = client.create_page(db_id, parent_props)["id"]
client.update_page(child_id, {"Parent item": {"relation": [{"id": parent_id}]}})
```

## Google Tasks Sync

**ALWAYS sync Google Tasks back to Notion at the start of every session** — run `uv run pa-notion tasks sync` before doing anything else. This picks up tasks the user completed on his phone and marks them Done in Notion. Without this, the task list is stale.

Sync also runs automatically during briefing generation (`pa-core briefing`), but that's not sufficient — sync must happen at session start regardless of whether a briefing is generated.

### Google Task Lists
Only the `🌈Today` list is configured (ID read from `GOOGLE_TODAY_TASKLIST_ID` env var). Set this in `.env`.

### Orphaned task import
If a Google Task has no Notion link (e.g. added directly on phone), sync will automatically create a matching Notion task and update the Google Task with the Notion link. Completed orphans are created as Done and removed from Google Tasks. Incomplete orphans stay on the phone with the Notion link added to notes. `[Project]` prefixes in titles are parsed back into the Notion project field.

### gws CLI gotcha
The `showCompleted` and `showHidden` params must be strings (`"true"`) not booleans (`True`) — gws serialises booleans incorrectly.

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
