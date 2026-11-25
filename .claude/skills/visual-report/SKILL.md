---
name: visual-report
description: Build a visual report (HTML and PDF, saved to Drive and emailed) from structured facts. Use when the user asks for a report, a visual plan, options with a calendar, "make it visual", a progress or TODO report, an interview briefing or preparation pack, or a comparison they want to look at rather than edit.
---

# Visual report

Use accessible visual HTML with a matching printable PDF. Read the private `visual-planning-reports` memory preference for the current approved example and any personal accessibility requirements. Keep personal information and example report contents out of tracked skill files.

## Default visual style

- Use large, left-aligned Arial or another familiar sans-serif: 24px body text on screen, with a 28px larger-text control. Use generous line spacing (about 1.5) and headings around twice body size.
- Use a light warm background, dark high-contrast text, generous white space and coloured cards with explicit labels. Never rely on colour alone.
- Give each section one purpose. Prefer short prompts and two or three compact cards over dense prose or tables. Do not force a fixed page count.
- Explain sequences with numbered steps and arrows; use timelines, comparisons or calendars when they clarify the content. Visuals must communicate relationships, not merely decorate text.
- Start with the key takeaway and immediate actions. Put detailed evidence behind links or optional sections. For preparation packs, include a quick-reference page and a short rehearsal sequence.
- Include simple anchor navigation, a larger-text control, a reset control and print/PDF support. Keep the layout responsive and usable at enlarged text sizes.
- For PDF, choose page orientation to suit the content and retain comfortably large text (about 17–18pt for landscape cards). Add pages rather than shrinking content to fit. Check for clipped text and footer overlap.

## Rendering route

Use `pa-core report` with structured JSON when its output meets these requirements. If it cannot reproduce the requested visual structure or accessibility, adapt the approved private HTML example and render it to PDF with an available local document renderer. Local HTML/PDF generation scripts are allowed; do not change the shared renderer merely to produce a one-off report. Save generated content and scripts under ignored `activity/reports/<slug>/`.

## Steps

1. Gather the facts first: read the sources in full and get real prices, dates and links. When a source is an email, archive it after the report is delivered, as the `email-triage` skill describes.
2. For the standard renderer, write the input JSON to `activity/reports/<slug>/input.json` (ignored by git). Every activity, option and place needs a `url`.
3. Preview locally: `uv run pa-core report --kind research --input activity/reports/<slug>/input.json --name <slug> --no-insights --dry-run`. Open the HTML path it prints and check it.
4. Deliver: run the same command with `--deliver` instead of `--dry-run`. It renders a PDF, uploads it to Drive and emails it to the user, then prints the Drive link.
For custom HTML, preview the actual HTML and rendered PDF, check representative pages and text enlargement, then upload both files to Drive. Email the user the report links only when authorised by the request or standing delivery instructions. Do not treat this skill as permission to message other people. Link the delivered files from the existing task.

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
- Use a Google Doc (the `research-doc` skill) when the user requests an editable prose document. Returning to a report later is not a reason to replace the requested visual HTML format.
