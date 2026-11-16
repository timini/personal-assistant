"""CLI entry point for pa-notebooklm."""

import argparse
import json
import sys


def cmd_login(args):
    """First-run auth: open a browser via the notebooklm-py login, then verify."""
    from pa_core.cli_runner import run_cli
    from pa_notebooklm import client

    try:
        run_cli(["notebooklm", "login"], capture=False, timeout=300)
    except Exception as e:
        print(f"Login command failed: {e}", file=sys.stderr)
        sys.exit(1)

    if client.check_auth():
        print("✓ Authenticated with NotebookLM.")
    else:
        print("Login ran but the auth check failed — try again.", file=sys.stderr)
        sys.exit(1)


def cmd_explain(args):
    """Create a notebook from documents/URLs and fire the explainer generations."""
    from pa_notebooklm import client

    artifacts = None
    if args.only:
        artifacts = {a.strip() for a in args.only.split(",") if a.strip()}

    try:
        res = client.explain(
            args.sources,
            title=args.title,
            artifacts=artifacts,
            wait=args.wait,
            language=args.language,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"✓ Notebook '{res['title']}' created (id {res['notebook_id']}).")
    print(f"  Generating: {', '.join(res['artifacts_started'])}")
    if res["waited"]:
        print("  All generations complete.")
    else:
        print("  Open the NotebookLM app on your phone — they'll appear there shortly.")


def cmd_list(args):
    """List notebooks."""
    from pa_notebooklm import client

    try:
        nbs = client.list_notebooks()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(nbs, indent=2))
        return
    if not nbs:
        print("No notebooks.")
        return
    for n in nbs:
        print(f"  {n['title']}  ({n['sources']} sources)  [{n['id']}]")


def main():
    parser = argparse.ArgumentParser(
        prog="pa-notebooklm",
        description="Turn documents into NotebookLM audio/video/explainers",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Authenticate with NotebookLM (opens a browser)")

    ep = sub.add_parser(
        "explain", help="Create a notebook from documents/URLs and generate explainers"
    )
    ep.add_argument("sources", nargs="+", help="Local file paths and/or http(s) URLs")
    ep.add_argument("--title", help="Notebook title (auto-derived if omitted)")
    ep.add_argument(
        "--only",
        help="Comma-separated subset of: audio,video,slides,report,mindmap",
    )
    ep.add_argument(
        "--wait", action="store_true", help="Wait for generations to finish (slow)"
    )
    ep.add_argument("--language", default="en", help="Language (default: en)")

    lp = sub.add_parser("list", help="List your NotebookLM notebooks")
    lp.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    {"login": cmd_login, "explain": cmd_explain, "list": cmd_list}[args.command](args)


if __name__ == "__main__":
    main()
