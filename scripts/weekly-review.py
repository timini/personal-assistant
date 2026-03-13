#!/usr/bin/env python3
"""Weekly review script — summarise tasks and upcoming events."""

import json
from pa_notion.tasks import list_tasks
from pa_google.calendar import get_upcoming_events


if __name__ == "__main__":
    print("=== Open Tasks ===\n")
    try:
        tasks = list_tasks()
        for t in tasks:
            status = f"[{t['status']}]" if t["status"] else ""
            print(f"  {status} {t['title']}")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n=== Next 7 Days ===\n")
    try:
        events = get_upcoming_events(days=7)
        for e in events:
            time_str = e["start"].split("T")[1][:5] if "T" in e["start"] else e["start"]
            print(f"  {time_str}  {e['summary']}")
    except Exception as e:
        print(f"  Error: {e}")
