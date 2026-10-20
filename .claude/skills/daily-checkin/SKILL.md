---
name: daily-checkin
description: Run the user's daily check-in and day planning. Use for "good morning", "check-in", "plan my day", "what's on today", "evening review", or the first session of the day when the memory brief says no check-in has happened yet.
---

# Daily check-in

Check in once a day. If the memory brief says it has not happened, ask at a natural point: after any urgent request is handled, never instead of it, and never twice in a day. Read any wellness preferences referenced from memory or `user-instructions.md` first.

## Morning

1. `uv run pa-core checkin`. It prints the date, memory brief, calendar, inbox, tasks, health and a morning prompt.
2. Ask what is urgent.
3. Show today's schedule. Flag appointments that need action or travel: time, place, what to bring.
4. Ask how they are and log it: `uv run pa-core log wellness check_in "<summary>" --details '<json>'`.
5. Offer a shortlist of at most three tasks matched to energy. Strong day: harder items. Low day: one or two easy wins and protect the rest. Combine signals: the check-in, calendar density and sleep (`uv run pa-health day`).
6. Let the user choose, then set the chosen tasks due today: `uv run pa-notion tasks update <id> --due <today>`. The plan is finished when the user has chosen, not when you have proposed.
7. Work any **Due now** loops from the brief: resolve, chase with a draft, or move the date with a reason.

## Evening

1. `uv run pa-core checkin --evening` for habits, gratitude, how the day went and tomorrow's preview.
2. Log habits only from what the user says: `uv run pa-core log habit completed "<habit>"` or `... habit skipped ...`.
3. Collect the habit, gratitude and day-review answers before running `uv run pa-core briefing --evening`, otherwise it reports everything as not logged.
4. On Sunday evenings, offer the `task-hygiene` review.
5. Turn anything unfinished into a memory `loop` with a realistic due date, and journal the day in one line.
