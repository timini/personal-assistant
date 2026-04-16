"""CLI entry point for pa-whatsapp."""

import argparse
import json
import sys


def cmd_messages(args):
    from pa_whatsapp.client import get_messages, acknowledge_messages

    messages = get_messages(limit=args.limit)
    if args.json:
        print(json.dumps(messages, indent=2))
    else:
        if not messages:
            print("No new WhatsApp messages.")
        else:
            for msg in messages:
                chat = f" ({msg['chat_name']})" if msg.get("chat_name") else ""
                print(f"[{msg['date']} {msg['time']}] {msg['from_name']}{chat}: {msg['text']}")
    if args.ack and messages:
        acknowledge_messages(messages)
        print(f"Acknowledged {len(messages)} message(s).")


def cmd_chats(args):
    from pa_whatsapp.client import list_chats

    chats = list_chats(limit=args.limit)
    if args.json:
        print(json.dumps(chats, indent=2))
    else:
        if not chats:
            print("No chats found.")
        else:
            for chat in chats:
                name = chat.get("name") or chat.get("Name") or chat.get("jid") or "Unknown"
                print(name)


def main():
    parser = argparse.ArgumentParser(prog="pa-whatsapp", description="PA WhatsApp integration (via wacli)")
    sub = parser.add_subparsers(dest="command")

    # messages
    mp = sub.add_parser("messages", help="Show recent WhatsApp messages")
    mp.add_argument("--json", action="store_true", help="Output as JSON")
    mp.add_argument("--ack", action="store_true", help="Acknowledge messages after reading")
    mp.add_argument("--limit", type=int, default=50, help="Max messages to fetch")

    # chats
    cp = sub.add_parser("chats", help="List WhatsApp chats")
    cp.add_argument("--json", action="store_true", help="Output as JSON")
    cp.add_argument("--limit", type=int, default=50, help="Max chats to show")

    args = parser.parse_args()

    if args.command == "messages":
        cmd_messages(args)
    elif args.command == "chats":
        cmd_chats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
