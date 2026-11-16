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


def cmd_messages(args):
    """Show new messages sent to the bot."""
    import json as json_mod

    from pa_telegram.client import acknowledge_messages, get_messages, read_archive

    try:
        if getattr(args, "history", None) is not None:
            # Re-list from the durable archive — survives acknowledgement.
            archived = read_archive(limit=args.history if args.history > 0 else None)
            if args.json:
                print(json_mod.dumps(archived, indent=2))
            elif archived:
                for m in archived:
                    line = f"[{m['date']} {m['time']}] {m['from_name']}: {m['text']}"
                    if m.get("image_path"):
                        line += f"\n  📷 {m['image_path']}"
                    print(line)
            else:
                print("No archived messages.")
            return

        messages = get_messages()
        if args.json:
            print(json_mod.dumps(messages, indent=2))
        elif messages:
            for m in messages:
                line = f"[{m['date']} {m['time']}] {m['from_name']}: {m['text']}"
                if m.get("image_path"):
                    line += f"\n  📷 {m['image_path']}"
                print(line)
        else:
            print("No new messages.")

        if args.ack and messages:
            acknowledge_messages(messages)
            print(f"Acknowledged {len(messages)} message(s).")
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

    # messages
    mp = sub.add_parser("messages", help="Show new messages sent to the bot")
    mp.add_argument("--json", action="store_true", help="JSON output")
    mp.add_argument("--ack", action="store_true", help="Acknowledge messages after reading")
    mp.add_argument(
        "--history",
        nargs="?",
        type=int,
        const=0,
        default=None,
        help="List from the durable inbox archive instead of fetching new "
        "(optionally the last N). Survives acknowledgement.",
    )

    # briefing
    bp = sub.add_parser("briefing", help="Send daily briefing to Telegram")
    bp.add_argument("--evening", action="store_true", help="Send evening briefing instead of morning")
    bp.add_argument("--date", default=None, help="Date (YYYY-MM-DD), defaults to today")

    args = parser.parse_args()

    if args.command == "send":
        cmd_send(args)
    elif args.command == "messages":
        cmd_messages(args)
    elif args.command == "briefing":
        cmd_briefing(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
