# pa-ebay — eBay Browse API Integration

## Goal

Search and price research. Programmatic eBay search for comparing listings, checking prices, and finding specific items during sessions.

## Setup

1. Create an eBay developer account at https://developer.ebay.com
2. Create an application and get a **production** keyset
3. Add credentials to `.env`:
   ```
   EBAY_CLIENT_ID=your_client_id
   EBAY_CLIENT_SECRET=your_client_secret
   ```
4. Run `uv sync` to register the package

No user auth needed — the Browse API search endpoint uses application-level (client credentials) OAuth only.

## CLI Commands

```bash
# Basic search
uv run pa-ebay search "vintage bell tent"

# With filters
uv run pa-ebay search "vintage bell tent" --condition used --sort price --limit 20
uv run pa-ebay search "vintage bell tent" --min-price 50 --max-price 500
uv run pa-ebay search "vintage bell tent" --uk-only

# JSON output (for Claude to process)
uv run pa-ebay search "vintage bell tent" --uk-only --json
```

## Browse API Filter Reference

- **Condition**: `--condition new` or `--condition used`
- **Sort**: `price` (low-high), `-price` (high-low), `newlyListed`, `endingSoonest`
- **Price range**: `--min-price 50 --max-price 500` (GBP)
- **Location**: `--uk-only` restricts to UK sellers

## Gotchas

- **Rate limits**: ~5000 calls/day on production keys. Plenty for manual research, but don't loop unnecessarily.
- **Marketplace**: Defaults to `EBAY_GB` (UK). Hardcoded since Tim is UK-based.
- **OAuth tokens**: Cached in-process, last ~2 hours. One token fetch per CLI invocation.
- **Results**: Browse API returns max 200 items per request. Default limit is 10.
- **Condition values**: Must be uppercase in API calls (`NEW`, `USED`). The CLI accepts either case.
