---
name: visual-report
description: Build a visual report (HTML and PDF, saved to Drive and emailed) from structured facts. Use when the user asks for a report, a visual plan, options with a calendar, "make it visual", a progress or TODO report, or a comparison they want to look at rather than edit.
---

# Visual report

`pa-core report` renders the report. Do not read `report.py`, write a Playwright or HTML script, or rename output files: write a JSON file and run one command.

## Steps

1. Gather the facts first: read the sources in full and get real prices, dates and links. When a source is an email, archive it after the report is delivered, as the `email-triage` skill describes.
2. Write the input JSON to `activity/reports/<slug>/input.json` (ignored by git). Every activity, option and place needs a `url`.
3. Preview locally: `uv run pa-core report --kind research --input activity/reports/<slug>/input.json --name <slug> --no-insights --dry-run`. Open the HTML path it prints and check it.
4. Deliver: run the same command with `--deliver` instead of `--dry-run`. It renders a PDF, uploads it to Drive and emails it to the user, then prints the Drive link.
5. Reply with the recommendation in a few lines and the Drive link. If the report belongs to a task, add the link to its notes with `uv run pa-notion tasks update <id> --append-notes "<date>: report <link>"`.

## Input shape

`title` and an ordered list of `sections` are required. Each section may combine any of these blocks:

```json
{
  "title": "Half-term options",
  "sections": [
    {
      "heading": "Recommendation",
      "paragraphs": ["Keep the grandparent days for childcare and go away at the weekend."],
      "bullets": ["No extra leave used"],
      "cards": [
        {"title": "Forest pod", "subtitle": "Fri to Sun", "cost": "£235",
         "url": "https://example.com/pod", "points": ["Arrive before 7pm"]}
      ]
    },
    {
      "heading": "Calendar",
      "calendar": [
        {"date": "2026-10-26", "label": "Mon", "items": [
          {"text": "Grandparent covers", "kind": "covered"},
          {"text": "Art club 9 to 3", "kind": "trip", "url": "https://example.com/art"}
        ]}
      ]
    },
    {
      "heading": "Clubs",
      "table": {"columns": ["Club", "Dates", "Price"],
                "rows": [[{"text": "Art club", "url": "https://example.com/art"}, "3 Nov", "£30"]]},
      "sources": [{"label": "Club listings", "url": "https://example.com/clubs"}]
    }
  ],
  "warnings": ["Prices checked today; availability can change."]
}
```

Calendar `kind` sets the colour: `covered` (green), `gap` (red), `leave` (amber), `trip` (blue). Anything else is grey.

## Rules

- Lead with the recommendation, then the options, then the detail.
- Keep facts and judgement apart: put caveats in `warnings`.
- Use a Google Doc (the `research-doc` skill) instead when the user wants written research they will edit or come back to.
