# pa-notion — Package Instructions

## Goal
**Single source of truth for all tasks and commitments.** Every actionable item should end up as a Notion task.

## Task Rules

1. Every task needs: **status, priority, project, and clear title**
2. **Clear task names** — include enough context to act on (e.g. "Pay £800 for Landplan" not "800 Landplan")
3. **Group related tasks** under a parent using `Parent Task` relation
4. **Set due dates** on time-sensitive items — work backwards from actual deadlines
5. **Present tasks grouped by project** when showing to user
6. When creating tasks from emails, include Gmail link in Notes field

## Notion DB Schema (Tasks database)

- `Task` (title) — NOT "Name"
- `Status` (select: To Do / In Progress / Waiting / Done) — NOT "status" type, it's "select"
- `Priority` (select: Urgent / High / Medium / Low)
- `Project` (select: Day Job, AI Transformation, Line Management, House Renovation, House Declutter, Garden, Fitness, Music, Landplan, Admin / Finance)
- `Due Date` (date)
- `Notes` (rich_text)
- `Parent Task` (self-relation for sub-tasks)

## Sub-task Pattern
```python
parent_id = client.create_page(db_id, parent_props)["id"]
client.update_page(child_id, {"Parent Task": {"relation": [{"id": parent_id}]}})
```

## Project Pages
Each project has a dedicated page in Notion with task checklists, context, and reference material. When working on a project, check and update its page.
