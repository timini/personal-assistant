"""Achievement heatmap — GitHub-style activity grid rendered on a Notion page."""

import os
from datetime import datetime, timedelta

from pa_core.config import get_secret
from pa_core.daily_log import get_events

from pa_notion.client import NotionClient

EMOJI_SCALE = [
    (0, "\u2b1c"),   # ⬜ white
    (1, "\U0001f7e9"),   # 🟩 green
    (3, "\U0001f7e8"),   # 🟨 yellow
    (6, "\U0001f7e7"),   # 🟧 orange
    (10, "\U0001f7e5"),  # 🟥 red
]

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _count_to_emoji(count: int) -> str:
    emoji = EMOJI_SCALE[0][1]
    for threshold, e in EMOJI_SCALE:
        if count >= threshold:
            emoji = e
    return emoji


def _get_daily_counts(weeks: int = 12) -> dict[str, int]:
    """Count task completions per day for the last N weeks."""
    today = datetime.now().date()
    counts = {}
    for i in range(weeks * 7):
        day = today - timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        events = get_events(date_str)
        count = sum(
            1 for e in events
            if e.get("category") == "task" and e.get("action") in ("completed", "created")
        )
        counts[date_str] = count
    return counts


def _build_grid(counts: dict[str, int], weeks: int = 12) -> str:
    """Build the emoji grid string. Rows = days (Mon-Sun), columns = weeks."""
    today = datetime.now().date()

    # Find the Monday of the current week
    current_monday = today - timedelta(days=today.weekday())

    # Start Monday is `weeks - 1` weeks before current Monday
    start_monday = current_monday - timedelta(weeks=weeks - 1)

    # Build month labels header
    month_labels = "     "  # padding for day name column
    prev_month = None
    for w in range(weeks):
        week_monday = start_monday + timedelta(weeks=w)
        month = week_monday.strftime("%b")
        if month != prev_month:
            month_labels += month[:3]
            prev_month = month
        else:
            month_labels += "  "
        # Each column is 2 chars wide (emoji + space), but emojis are wider
        # We'll pad to align with the grid
        month_labels += " "

    lines = [month_labels.rstrip()]

    for day_idx in range(7):
        row = f"{DAY_NAMES[day_idx]}  "
        for w in range(weeks):
            date = start_monday + timedelta(weeks=w, days=day_idx)
            if date > today:
                row += "  "  # future dates are blank
            else:
                date_str = date.strftime("%Y-%m-%d")
                count = counts.get(date_str, 0)
                row += _count_to_emoji(count) + " "
        lines.append(row.rstrip())

    return "\n".join(lines)


def _compute_stats(counts: dict[str, int]) -> dict:
    """Compute summary stats from daily counts."""
    today = datetime.now().date()
    total = sum(counts.values())
    days_with_data = sum(1 for v in counts.values() if v > 0)
    active_days = len(counts)
    avg = total / active_days if active_days > 0 else 0

    # Current streak: consecutive days with tasks ending at today
    streak = 0
    day = today
    while True:
        date_str = day.strftime("%Y-%m-%d")
        if counts.get(date_str, 0) > 0:
            streak += 1
            day -= timedelta(days=1)
        else:
            break

    return {
        "total": total,
        "active_days": days_with_data,
        "daily_avg": round(avg, 1),
        "streak": streak,
    }


def generate_heatmap_blocks(weeks: int = 12) -> list[dict]:
    """Generate Notion blocks for the heatmap."""
    counts = _get_daily_counts(weeks)
    grid = _build_grid(counts, weeks)
    stats = _compute_stats(counts)

    today = datetime.now().date()
    start = today - timedelta(weeks=weeks)
    date_range = f"{start.strftime('%d %b %Y')} \u2013 {today.strftime('%d %b %Y')}"

    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": f"Activity Heatmap \u2014 {date_range}"}}],
            },
        },
        {
            "object": "block",
            "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": grid}}],
                "language": "plain text",
            },
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": "\u2b1c 0  \U0001f7e9 1-2  \U0001f7e8 3-5  \U0001f7e7 6-9  \U0001f7e5 10+"}}],
            },
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": (
                                f"Total: {stats['total']} tasks  \u00b7  "
                                f"Active days: {stats['active_days']}  \u00b7  "
                                f"Daily avg: {stats['daily_avg']}  \u00b7  "
                                f"Current streak: {stats['streak']} day{'s' if stats['streak'] != 1 else ''}"
                            )
                        },
                    }
                ],
            },
        },
    ]
    return blocks


def update_heatmap_page(page_id: str | None = None, weeks: int = 12) -> str:
    """Update (or create) the heatmap Notion page. Returns the page URL.

    SAFETY: Only operates on a dedicated heatmap page (from NOTION_HEATMAP_PAGE_ID
    or created as a new child page). Never pass the PA root page ID directly —
    this function clears all blocks before rewriting.
    """
    client = NotionClient()

    if not page_id:
        page_id = os.environ.get("NOTION_HEATMAP_PAGE_ID")

    pa_root = get_secret("NOTION_PA_PAGE_ID")

    # Safety check — refuse to operate on the PA root page
    if page_id and page_id.replace("-", "") == pa_root.replace("-", ""):
        raise RuntimeError(
            "Refusing to write heatmap directly to PA root page — "
            "this would delete all existing content. "
            "Use NOTION_HEATMAP_PAGE_ID for a dedicated child page."
        )

    if not page_id:
        # Create a new child page under PA root
        result = client.create_page_in_page(pa_root, "Achievement Heatmap")
        page_id = result["id"]
        print(f"Created heatmap page: {page_id}")
        print(f"Add NOTION_HEATMAP_PAGE_ID={page_id} to .env to reuse this page.")

    # Clear existing content on the dedicated heatmap page
    existing = client.get_block_children(page_id)
    for block in existing:
        client.delete_block(block["id"])

    # Write fresh heatmap
    blocks = generate_heatmap_blocks(weeks)
    client.append_blocks(page_id, blocks)

    # Return page URL
    clean_id = page_id.replace("-", "")
    return f"https://www.notion.so/{clean_id}"
