# ApexRML — Car Parts Finder

Searches multiple part suppliers at once by make, model, year, and part
name, and shows the cheapest results first with the source shop labelled
on each one.

Currently wired up for:
- **eBay UK** — live search via eBay's official Browse API (not scraping,
  so it won't break every time eBay changes their site or get your IP
  blocked)
- **Euro Car Parts** (and any other Awin-network retailer, e.g. GSF Car
  Parts) — via their affiliate product data feed, once you're approved

Adding another supplier later is just adding one more entry to
`AWIN_FEEDS` in your `.env` file — no code changes needed, as long as
they're on the Awin network too (most UK parts retailers are).

## What you need first

**For eBay:**
1. An approved eBay Developer account (usually ~1 business day):
   https://developer.ebay.com/join
2. Once approved, go to **My Account → Application Keys** and copy your
   **App ID (Client ID)** and **Cert ID (Client Secret)** from the
   **Production** keyset (not Sandbox).

**For Euro Car Parts (optional, can add later):**
1. Sign up as an affiliate: https://ui.awin.com (Awin runs their
   programme). Approval isn't instant — they check your site is genuinely
   car-related, which yours will be.
2. Once approved, search for "Euro Car Parts" in Awin's merchant
   directory, join their programme, then go to **Datafeeds** and copy the
   CSV download URL for their product feed.
3. Paste that URL into `AWIN_FEEDS` in your `.env` (see the example in
   `.env.example`).
4. The exact CSV column names can vary slightly by merchant — if searches
   come back empty once it's plugged in, open the feed in Excel, check
   the header row against `providers/awin_feed.py`, and adjust the
   `columns` mapping in `.env` if needed. I've documented this inline in
   that file.

You don't need Euro Car Parts sorted before going live — the site works
fine on eBay alone and Euro Car Parts results just slot in whenever
you add the feed URL.

## Running it on your own PC (to test)

1. Install Python 3.11+ if you don't have it: https://www.python.org/downloads/
2. Open a terminal/command prompt in this folder and run:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to a new file called `.env` and paste in your real
   eBay keys:
   ```
   EBAY_CLIENT_ID=your_real_app_id
   EBAY_CLIENT_SECRET=your_real_cert_id
   EBAY_MARKETPLACE=EBAY_GB
   ```
4. Run it:
   ```
   python app.py
   ```
5. Open http://127.0.0.1:5000 in your browser.

**Never share your `.env` file or paste your keys into chat, a public
repo, or anywhere else.** The `.gitignore` file already stops it from
being uploaded if you use GitHub.

## Putting it online 24/7 (no PC needed)

You asked for it to run by itself — that means hosting it somewhere,
since your own PC would need to stay switched on forever otherwise.
Two free-to-start options that both work well with this project:

### Option A: Render (recommended, simplest)
1. Create a free account at https://render.com
2. Push this folder to a GitHub repo (Render deploys from GitHub)
3. In Render: **New → Web Service** → connect your repo
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`
6. Under **Environment**, add `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`,
   `EBAY_MARKETPLACE` with your real values
7. Deploy — Render gives you a live `.onrender.com` URL immediately.
   You can point your own domain name at it later.

### Option B: Railway
Same idea as Render — https://railway.app — connect GitHub repo, set the
same three environment variables, deploy.

Free tiers on both will "sleep" the site after inactivity and wake up
in a few seconds when someone visits — fine to start with. A few pounds
a month upgrades it to always-on with no wake-up delay, worth it once
you're getting real customers using it.

## Files in this project

| File | What it does |
|---|---|
| `app.py` | The backend — runs every configured provider and merges results |
| `providers/base.py` | The shared contract every source follows |
| `providers/ebay.py` | Live eBay search |
| `providers/awin_feed.py` | Downloads, caches, and searches any Awin retailer's product feed |
| `templates/index.html` | The website your customers see |
| `requirements.txt` | List of Python packages needed |
| `.env.example` | Template showing what secret keys/feeds are needed |
| `Procfile` | Tells Render/Railway how to start the app |
| `data/` | Local cache of downloaded product feeds (not committed to git) |

## Notes

- `EBAY_MARKETPLACE=EBAY_GB` searches eBay UK. Leave as-is unless you
  want to search a different country's eBay site.
- If eBay searches suddenly stop working, check your eBay Developer
  dashboard — Production API access sometimes needs a short compliance
  form after the first couple of weeks of live use.
- Awin feeds refresh once every 24 hours by default (configurable per
  feed via `refresh_hours` in `AWIN_FEEDS`). The first search after a
  refresh takes a bit longer since it's downloading and re-caching the
  whole feed; every search after that is instant.
- If one source fails (feed URL down, eBay token expired, etc.) the
  others still return results — you'll see a small note in the status
  line rather than the whole search failing.
- Adding a further Awin retailer (GSF Car Parts, MicksGarage, etc.) is
  just one more object in `AWIN_FEEDS` — no code changes.
