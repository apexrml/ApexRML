"""
Euro Car Parts (and most other UK parts retailers — GSF Car Parts,
MicksGarage, etc.) don't offer a live search API. What they DO offer,
once you're an approved Awin affiliate, is a product data feed: a big
CSV file listing every product, price, and a trackable link, refreshed
by them periodically.

This provider downloads that feed, caches it in a local SQLite database
(so you're not re-downloading tens of thousands of rows on every search),
and searches the cached copy. Re-downloads automatically once the cache
goes stale (default: once a day).

Awin's standard export columns are usually:
    product_name, aw_deep_link, aw_image_url, search_price, category_name,
    in_stock, merchant_name, description
Some merchants rename a few columns. If search results come back empty
once you plug in a real feed, open the CSV in Excel/Sheets, check the
actual header row, and adjust COLUMN MAPPING below (or override via the
"columns" key in AWIN_FEEDS — see .env.example).
"""

import csv
import io
import os
import sqlite3
import time
import requests

from .base import Provider

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "awin_cache.db")

DEFAULT_COLUMNS = {
    "title": "product_name",
    "price": "search_price",
    "link": "aw_deep_link",
    "image": "aw_image_url",
    "category": "category_name",
    "in_stock": "in_stock",
}


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            source TEXT,
            title TEXT,
            price_value REAL,
            price_display TEXT,
            link TEXT,
            image TEXT,
            category TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feed_meta (
            source TEXT PRIMARY KEY,
            last_updated REAL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_products_source ON products(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_products_title ON products(title)")
    conn.commit()
    return conn


def _parse_price(raw):
    if raw is None:
        return None, None
    cleaned = str(raw).replace(",", "").strip()
    for symbol in ("£", "GBP", "$", "€"):
        cleaned = cleaned.replace(symbol, "")
    cleaned = cleaned.strip()
    try:
        value = float(cleaned)
        return value, f"{value:.2f} GBP"
    except ValueError:
        return None, str(raw)


class AwinFeedProvider(Provider):
    def __init__(self, name, url, columns=None, refresh_hours=24):
        self.name = name
        self.url = url
        self.columns = {**DEFAULT_COLUMNS, **(columns or {})}
        self.refresh_seconds = refresh_hours * 3600

    def is_configured(self):
        return bool(self.url)

    def _is_stale(self, conn):
        row = conn.execute(
            "SELECT last_updated FROM feed_meta WHERE source = ?", (self.name,)
        ).fetchone()
        if not row:
            return True
        return (time.time() - row[0]) > self.refresh_seconds

    def _refresh_feed(self, conn):
        res = requests.get(self.url, timeout=60, stream=True)
        res.raise_for_status()

        # Decode the stream as text and let csv.Sniffer figure out the
        # delimiter (Awin feeds are sometimes comma, sometimes tab).
        raw_text = res.content.decode("utf-8", errors="replace")
        sample = raw_text[:2000]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except csv.Error:
            dialect = csv.excel  # fall back to comma

        reader = csv.DictReader(io.StringIO(raw_text), dialect=dialect)

        cols = self.columns
        rows_to_insert = []
        for row in reader:
            title = row.get(cols["title"])
            if not title:
                continue

            in_stock_raw = row.get(cols.get("in_stock", ""), None)
            if in_stock_raw is not None and str(in_stock_raw).strip().lower() in (
                "0", "false", "no", "out of stock",
            ):
                continue

            price_value, price_display = _parse_price(row.get(cols["price"]))

            rows_to_insert.append(
                (
                    self.name,
                    title,
                    price_value,
                    price_display,
                    row.get(cols["link"], "#"),
                    row.get(cols["image"], ""),
                    row.get(cols.get("category", ""), ""),
                )
            )

        conn.execute("DELETE FROM products WHERE source = ?", (self.name,))
        conn.executemany(
            """
            INSERT INTO products (source, title, price_value, price_display, link, image, category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
        conn.execute(
            """
            INSERT INTO feed_meta (source, last_updated) VALUES (?, ?)
            ON CONFLICT(source) DO UPDATE SET last_updated = excluded.last_updated
            """,
            (self.name, time.time()),
        )
        conn.commit()

    def search(self, query, limit=20):
        if not self.is_configured():
            return []

        conn = _connect()
        try:
            if self._is_stale(conn):
                self._refresh_feed(conn)

            words = [w for w in query.split() if w]
            if not words:
                return []

            clauses = []
            params = [self.name]
            for w in words:
                clauses.append("(title LIKE ? OR category LIKE ?)")
                params.extend([f"%{w}%", f"%{w}%"])

            sql = f"""
                SELECT title, price_value, price_display, link, image
                FROM products
                WHERE source = ? AND {" AND ".join(clauses)}
                ORDER BY (price_value IS NULL), price_value ASC
                LIMIT ?
            """
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [
                {
                    "title": r[0],
                    "price_value": r[1],
                    "price": r[2] or "Price on site",
                    "condition": "New",
                    "link": r[3],
                    "image": r[4],
                    "seller": self.name,
                    "source": self.name,
                }
                for r in rows
            ]
        finally:
            conn.close()
