---
name: daily-checkin
description: Run the user's daily check-in and day planning. Use for "good morning", "check-in", "plan my day", "what's on today", "evening review", or the first session of the day when the memory brief says no check-in has happened yet.
---

# Daily check-in

Check in once a day. If the memory brief says it has not happened, ask at a natural point: after any urgent request is handled, never instead of it, and never twice in a day. Read any wellness preferences referenced from memory or `user-instructions.md` first.

## Morning

1. `uv run pa-core checkin`. It prints the date, memory brief, calendar, inbox, tasks, health and a morning prompt. Note what today's log already holds (mood, meals, medication, habits) and do not ask for it again.
2. Triage the inbox now with the `email-triage` skill, unless the brief says it is done today. This is not optional: it is the PA's most basic daily job. Anything urgent it finds (a delivery today, a payment or card problem, a deadline) goes at the top of the day plan.
3. Ask what is urgent.
4. Show today's schedule. Flag appointments that need action or travel: time, place, what to bring.
5. Ask how they are and log it: `uv run pa-core log wellness check_in "<summary>" --details '<json>'`. Read sleep from `uv run pa-health day`; do not ask about it.
6. Run `uv run pa-health alerts` and ask about each unexplained HR alert. Log each answer as the command shows.
7. Exercise, with the `personal-trainer` skill: close yesterday's open plans (the brief's Exercise line lists them), then propose one concrete session and an alternative from today's calendar, get a commitment and record it with `uv run pa-health workout plan`.
8. Offer a shortlist of at most three tasks. On a strong day, include harder items. On a tired, stressed or overwhelmed day, do not suggest an easy day: overwhelm usually comes from the backlog, and putting work off makes it worse. Pick one useful priority, name a small first action and a clear finish line, and help start it. If the user says there is too much to do, choose the first task yourself and start it with them.
9. Let the user choose, then set the chosen tasks due today: `uv run pa-notion tasks update <id> --due <today>`. The plan is finished when the user has chosen, not when you have proposed.
10. Work any **Due now** loops from the brief: resolve, chase with a draft, or move the date with a reason.

The morning check-in is finished only when all of these are true: the brief says email triage is done today, the wellness check-in is logged, an exercise slot is agreed, and the user has chosen today's tasks.

## Evening

1. `uv run pa-core checkin --evening` for habits, gratitude, how the day went and tomorrow's preview.
2. Triage mail that arrived since the last pass with the `email-triage` skill.
3. Ask whether today's planned session happened and record it with the `personal-trainer` skill.
4. Log habits only from what the user says: `uv run pa-core log habit completed "<habit>"` or `... habit skipped ...`.
5. Collect the habit, gratitude and day-review answers before running `uv run pa-core briefing --evening`, otherwise it reports everything as not logged.
6. On Sunday evenings, offer the `task-hygiene` review and the weekly training review from `personal-trainer`.
7. Turn anything unfinished into a memory `loop` with a realistic due date, and journal the day in one line.
