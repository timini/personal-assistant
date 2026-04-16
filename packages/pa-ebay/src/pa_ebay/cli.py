"""CLI entry point for pa-ebay."""

import argparse
import json
import sys

from pa_ebay.client import search


def cmd_search(args):
    """Search eBay listings."""
    try:
        results = search(
            args.query,
            condition=args.condition,
            sort=args.sort,
            limit=args.limit,
            min_price=args.min_price,
            max_price=args.max_price,
            uk_only=args.uk_only,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("No results found.")
        return

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        for i, r in enumerate(results, 1):
            shipping = f" + {r.shipping}" if r.shipping and r.shipping != "Free" else ""
            shipping_label = " (Free shipping)" if r.shipping == "Free" else shipping
            print(f"{i}. {r.title}")
            print(f"   {r.currency} {r.price}{shipping_label}  |  {r.condition}  |  Seller: {r.seller}")
            if r.location:
                print(f"   Location: {r.location}")
            print(f"   {r.url}")
            print()


def main():
    parser = argparse.ArgumentParser(prog="pa-ebay", description="PA eBay integration — search and price research")
    sub = parser.add_subparsers(dest="command", required=True)

    search_p = sub.add_parser("search", help="Search eBay listings")
    search_p.add_argument("query", help="Search keywords")
    search_p.add_argument("--condition", choices=["new", "used", "NEW", "USED"], help="Item condition filter")
    search_p.add_argument("--sort", choices=["price", "-price", "newlyListed", "endingSoonest"], help="Sort order")
    search_p.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    search_p.add_argument("--min-price", type=float, help="Minimum price in GBP")
    search_p.add_argument("--max-price", type=float, help="Maximum price in GBP")
    search_p.add_argument("--uk-only", action="store_true", help="Restrict to UK sellers")
    search_p.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)


if __name__ == "__main__":
    main()
