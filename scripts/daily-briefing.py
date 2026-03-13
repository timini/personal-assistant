#!/usr/bin/env python3
"""Daily briefing script — can be run via cron or manually."""

from pa_google.cli import cmd_briefing


class Args:
    json = False


if __name__ == "__main__":
    cmd_briefing(Args())
