import json
import os

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

from providers import EbayProvider, AwinFeedProvider

load_dotenv()

app = Flask(__name__)


def _load_awin_providers():
    """
    AWIN_FEEDS in .env is a JSON list, e.g.:
    [
      {"name": "Euro Car Parts", "url": "https://productdata.awin.com/...csv"},
      {"name": "GSF Car Parts", "url": "https://productdata.awin.com/...csv",
       "columns": {"title": "name", "price": "price_gbp"}}
    ]
    Empty or missing -> no Awin-backed sources are searched, no error.
    """
    raw = os.environ.get("AWIN_FEEDS", "").strip()
    if not raw:
        return []

    try:
        configs = json.loads(raw)
    except json.JSONDecodeError:
        print("WARNING: AWIN_FEEDS in .env is not valid JSON — ignoring it.")
        return []

    providers = []
    for cfg in configs:
        if not cfg.get("name") or not cfg.get("url"):
            continue
        providers.append(
            AwinFeedProvider(
                name=cfg["name"],
                url=cfg["url"],
                columns=cfg.get("columns"),
                refresh_hours=cfg.get("refresh_hours", 24),
            )
        )
    return providers


PROVIDERS = [EbayProvider()] + _load_awin_providers()


@app.route("/")
def home():
    return render_template("index.html", sources=[p.name for p in PROVIDERS])


@app.route("/search")
def search():
    make = request.args.get("make", "").strip()
    model = request.args.get("model", "").strip()
    year = request.args.get("year", "").strip()
    part = request.args.get("part", "").strip()

    query = " ".join(x for x in [make, model, year, part] if x)

    if not query:
        return jsonify({"error": "Enter at least one search field."}), 400

    all_results = []
    warnings = []

    for provider in PROVIDERS:
        results, error = provider.safe_search(query, limit=20)
        all_results.extend(results)
        if error:
            warnings.append(error)

    # Cheapest first; unknown prices sink to the bottom rather than
    # sorting first (which Python would otherwise do with None).
    all_results.sort(
        key=lambda r: (r.get("price_value") is None, r.get("price_value") or 0)
    )

    return jsonify(
        {
            "query": query,
            "results": all_results,
            "warnings": warnings,  # non-fatal: e.g. one source down, others still returned
        }
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok", "providers": [p.name for p in PROVIDERS]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
