---
name: task-hygiene
description: Weekly review and clean-up of the user's Notion task list. Use for "weekly review", "tidy my tasks", "task hygiene", "what's stale", or when offering the Sunday evening review. Finds duplicates, stale and overdue items and vague titles, and proposes decisions in a batch.
---

# Task hygiene

Run weekly (offer it on Sunday evenings). Propose decisions; never apply them unasked, and never mark a task Done without the user's confirmation or a verified receipt.

## Steps

1. `uv run pa-notion tasks list --open --json` for every open task with status, priority, lane, project, due date and notes. `uv run pa-notion tasks show <id>` for one task's full notes and page.
2. Audit for:
   - **Duplicates:** the same action in two or more tasks. Propose a merge.
   - **Stale In Progress:** In Progress for 14 or more days with no notes update. Ask if it is still active.
   - **Notes out of date:** every In Progress task needs its current state in the notes.
   - **Urgent without a date:** add the date or drop the priority.
   - **Overdue:** bump the date, mark Waiting, or close (`--due-before <today>` lists them).
   - **Vague titles:** rewrite so the next action is clear.
   - **Container tasks:** a "{Project} tasks" page should hold context, not act as a dumping ground. Link sub-tasks through `Parent item`.
   - **Orphan groups:** related tasks in the same project that should share a parent.
   - **Lanes:** at most three `🔥 Live` projects. Move the rest to `🅿️ Parked` or `💤 Someday`.
3. Present the findings as one batch of short decisions ("reply done, park or drop"), at most a handful at a time.
4. Apply what the user agrees, using `uv run pa-notion tasks update <id>` with `--status`, `--lane`, `--due`, `--title` or `--append-notes`.
5. Journal the outcome: `uv run pa-core memory journal "Task hygiene: ..."`.

Schema and the sub-task pattern: see `packages/pa-notion/AGENTS.md`.
