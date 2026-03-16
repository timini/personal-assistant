"""CLI entry point for pa-telegram."""

import argparse
import sys


def cmd_send(args):
    """Send an arbitrary message."""
    from pa_telegram.client import send_message

    try:
        send_message(args.message)
        print("Message sent to Telegram.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_briefing(args):
    """Send the daily briefing."""
    try:
        if args.evening:
            from pa_telegram.client import send_evening_briefing
            send_evening_briefing(date=args.date)
            print("Evening briefing sent to Telegram.")
        else:
            from pa_telegram.client import send_briefing
            send_briefing(date=args.date)
            print("Briefing sent to Telegram.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    from pa_core.config import get_assistant_name

    name = get_assistant_name()
    parser = argparse.ArgumentParser(prog="pa-telegram", description=f"{name} Telegram notifications")
    sub = parser.add_subparsers(dest="command")

    # send
    send_p = sub.add_parser("send", help="Send a message to Telegram")
    send_p.add_argument("message", help="Message text to send")

    # briefing
    bp = sub.add_parser("briefing", help="Send daily briefing to Telegram")
    bp.add_argument("--evening", action="store_true", help="Send evening briefing instead of morning")
    bp.add_argument("--date", default=None, help="Date (YYYY-MM-DD), defaults to today")

    args = parser.parse_args()

    if args.command == "send":
        cmd_send(args)
    elif args.command == "briefing":
        cmd_briefing(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
