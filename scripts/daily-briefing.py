#!/usr/bin/env python3
"""Daily briefing script. Run manually or from a harness-scheduled job."""

from pa_core.briefing import generate_briefing, save_briefing
import sys

if __name__ == "__main__":
    save = "--save" in sys.argv
    if save:
        path = save_briefing()
        print(f"Saved to {path}")
    else:
        print(generate_briefing())
