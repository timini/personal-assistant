"""eBay Browse API client — OAuth token management and search."""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass, asdict

import httpx

from pa_core.config import get_secret

# Module-level token cache
_token: str | None = None
_token_expiry: float = 0.0

EBAY_AUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_SCOPE = "https://api.ebay.com/oauth/api_scope"
DEFAULT_MARKETPLACE = "EBAY_GB"


@dataclass
class SearchResult:
    title: str
    price: str
    currency: str
    condition: str
    url: str
    image_url: str | None
    seller: str
    location: str | None
    shipping: str | None
    item_id: str

    def to_dict(self) -> dict:
        return asdict(self)


def _get_credentials() -> tuple[str, str]:
    """Read eBay API credentials from .env."""
    return get_secret("EBAY_CLIENT_ID"), get_secret("EBAY_CLIENT_SECRET")


def _get_app_token() -> str:
    """Fetch or return cached OAuth application token."""
    global _token, _token_expiry

    if _token and time.time() < _token_expiry:
        return _token

    client_id, client_secret = _get_credentials()
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    with httpx.Client() as client:
        resp = client.post(
            EBAY_AUTH_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {credentials}",
            },
            data={
                "grant_type": "client_credentials",
                "scope": EBAY_SCOPE,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    _token = data["access_token"]
    _token_expiry = time.time() + data.get("expires_in", 7200) - 60  # 60s buffer
    return _token


def _extract_item(item: dict) -> SearchResult:
    """Map a Browse API itemSummary to SearchResult."""
    price_info = item.get("price", {})
    condition = item.get("condition", "")
    image = item.get("image", {})
    seller = item.get("seller", {})
    shipping_info = item.get("shippingOptions", [{}])
    shipping_cost = None
    if shipping_info:
        cost = shipping_info[0].get("shippingCost", {})
        if cost:
            val = cost.get("value", "0.00")
            shipping_cost = "Free" if val == "0.00" else f"{cost.get('currency', 'GBP')} {val}"

    return SearchResult(
        title=item.get("title", ""),
        price=price_info.get("value", "0.00"),
        currency=price_info.get("currency", "GBP"),
        condition=condition,
        url=item.get("itemWebUrl", ""),
        image_url=image.get("imageUrl"),
        seller=seller.get("username", ""),
        location=item.get("itemLocation", {}).get("country"),
        shipping=shipping_cost,
        item_id=item.get("itemId", ""),
    )


def search(
    query: str,
    *,
    condition: str | None = None,
    sort: str | None = None,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    uk_only: bool = False,
) -> list[SearchResult]:
    """Search eBay via the Browse API.

    Args:
        query: Search keywords.
        condition: "NEW" or "USED".
        sort: "price", "-price", "newlyListed", "endingSoonest".
        limit: Max results (1-200).
        min_price: Minimum price in GBP.
        max_price: Maximum price in GBP.
        uk_only: Restrict to UK sellers.

    Returns:
        List of SearchResult dataclasses.
    """
    token = _get_app_token()

    # Build filter string
    filters = []
    if condition:
        filters.append(f"conditions:{{{condition.upper()}}}")
    if min_price is not None or max_price is not None:
        lo = f"{min_price:.2f}" if min_price is not None else ""
        hi = f"{max_price:.2f}" if max_price is not None else ""
        filters.append(f"price:[{lo}..{hi}],priceCurrency:GBP")
    if uk_only:
        filters.append("itemLocationCountry:GB")

    params: dict[str, str | int] = {
        "q": query,
        "limit": min(limit, 200),
    }
    if filters:
        params["filter"] = ",".join(filters)
    if sort:
        params["sort"] = sort

    with httpx.Client() as client:
        resp = client.get(
            EBAY_SEARCH_URL,
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": DEFAULT_MARKETPLACE,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    items = data.get("itemSummaries", [])
    return [_extract_item(item) for item in items]
