"""
Every provider (eBay, Euro Car Parts via Awin, future ones) implements the
same simple interface: search(query, limit) -> list of result dicts.

Result dict shape (all providers must return this):
{
    "title": str,
    "price": str,        # display string, e.g. "12.99 GBP"
    "price_value": float or None,   # numeric price for sorting, None if unknown
    "condition": str,
    "link": str,
    "image": str,
    "seller": str,
    "source": str,        # "eBay UK", "Euro Car Parts", etc.
}

Keeping this contract consistent means app.py never needs to know the
details of any individual retailer — adding a new one is just writing a
new provider file and registering it.
"""


class Provider:
    name = "base"

    def search(self, query, limit=20):
        raise NotImplementedError

    def safe_search(self, query, limit=20):
        """Wraps search() so one provider failing doesn't take down the others."""
        try:
            return self.search(query, limit=limit), None
        except Exception as e:
            return [], f"{self.name}: {e}"
