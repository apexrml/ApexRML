import os
import time
import base64
import requests

from .base import Provider

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"


def _parse_price_value(price_str):
    try:
        return float(price_str)
    except (TypeError, ValueError):
        return None


class EbayProvider(Provider):
    name = "eBay UK"

    def __init__(self):
        self.client_id = os.environ.get("EBAY_CLIENT_ID", "")
        self.client_secret = os.environ.get("EBAY_CLIENT_SECRET", "")
        self.marketplace = os.environ.get("EBAY_MARKETPLACE", "EBAY_GB")
        self._token_cache = {"access_token": None, "expires_at": 0}

    def is_configured(self):
        return bool(self.client_id and self.client_secret)

    def _get_token(self):
        now = time.time()
        if self._token_cache["access_token"] and now < self._token_cache["expires_at"] - 60:
            return self._token_cache["access_token"]

        if not self.is_configured():
            raise RuntimeError("Missing EBAY_CLIENT_ID / EBAY_CLIENT_SECRET in .env")

        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        }

        res = requests.post(TOKEN_URL, headers=headers, data=data, timeout=15)
        res.raise_for_status()
        payload = res.json()

        self._token_cache["access_token"] = payload["access_token"]
        self._token_cache["expires_at"] = now + payload.get("expires_in", 7200)
        return self._token_cache["access_token"]

    def search(self, query, limit=20, retry=True):
        if not self.is_configured():
            # Silently skip rather than error, so eBay being unset doesn't
            # break the whole search if other providers are enabled.
            return []

        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
            "Content-Type": "application/json",
        }
        params = {"q": query, "limit": limit}

        res = requests.get(SEARCH_URL, headers=headers, params=params, timeout=15)

        if res.status_code == 401 and retry:
            self._token_cache["access_token"] = None
            return self.search(query, limit=limit, retry=False)

        res.raise_for_status()
        body = res.json()

        items = []
        for item in body.get("itemSummaries", []):
            price = item.get("price", {})
            image = item.get("image", {})
            price_value = price.get("value")
            items.append(
                {
                    "title": item.get("title", ""),
                    "price": f"{price.get('value', '')} {price.get('currency', '')}".strip(),
                    "price_value": _parse_price_value(price_value),
                    "condition": item.get("condition", ""),
                    "link": item.get("itemWebUrl", "#"),
                    "image": image.get("imageUrl", ""),
                    "seller": item.get("seller", {}).get("username", ""),
                    "source": self.name,
                }
            )
        return items
