---
name: research-doc
description: Do research for the user and save it as a Google Doc linked from the relevant Notion task. Use for supplier or product comparisons, costings, options analysis, "find me the best ...", or any research the user may come back to later.
---

# Research saved to a Google Doc

Research that is not saved gets redone. Save it where the user and the next session can find it.

When the research starts from an email, read it in full first and archive it once the Doc is linked from the task, as the `email-triage` skill describes.

If the user asks for a report, a visual plan or a comparison to look at, use the `visual-report` skill instead.

## Steps

1. Find the related task (`uv run pa-notion tasks list --open --search "<topic>"`) and read its notes with `uv run pa-notion tasks show <id>` so you build on what is already known.
2. Do the research. Read full sources; give prices, dates and links, and say where coverage is incomplete.
3. Create a Google Doc with `gws docs documents create` and write the findings: headings, a comparison table, pros and cons, prices, a recommendation and next steps.
4. File it in Drive under `PA/<Project>/Research/` (for example `PA/House/Research/Door suppliers.gdoc`).
5. Link the Doc in the task: `uv run pa-notion tasks update <id> --append-notes "<date>: research doc <link>"`.
6. Reply with the recommendation in a few lines and the link.
