#!/usr/bin/env python3
"""
Strategy Preferreds - Market Data Update Script
===============================================
This script fetches live prices from Finnhub and writes them to prices.json.
The HTML loads prices.json via fetch() on page load.

IMPORTANT: This script does NOT modify index.html in any way.
It only writes to prices.json which is loaded dynamically by the page.

Run manually: python3 update_market_data.py
Or set up a cron job: 0 * * * * cd /path/to/repo && python3 update_market_data.py >> update.log 2>&1
"""

import json, urllib.request, datetime, sys, os

API_KEY = "d6f31jhr01qvn4o1lap0d6f31jhr01qvn4o1lapg"
PRICE_FILE = os.path.join(os.path.dirname(__file__), "prices.json")
INDEX_FILE = os.path.join(os.path.dirname(__file__), "index.html")

# Tickers to track
TICKERS = {
    "STRC": {"name": "STRC", "statedRate": 0.115, "freq": "monthly"},
    "STRK": {"name": "STRK", "statedRate": 0.10, "freq": "quarterly"},
    "STRD": {"name": "STRD", "statedRate": 0.10, "freq": "quarterly"},
    "STRF": {"name": "STRF", "statedRate": 0.08, "freq": "quarterly"},
    "STRE": {"name": "STRE", "statedRate": 0.10, "freq": "quarterly"},
}

PAR = 100.0

def get_finnhub_quote(ticker):
    """Fetch quote from Finnhub. Returns dict with 'c' (close price) or None on failure."""
    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={API_KEY}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("c") and data["c"] > 0:
                return {"price": data["c"], "o": data.get("o", 0), "h": data.get("h", 0), "l": data.get("l", 0), "pc": data.get("pc", 0)}
    except Exception as e:
        print(f"  Finnhub error for {ticker}: {e}", file=sys.stderr)
    return None

def get_cached_or_fetch(ticker, cache):
    """Try cache first (last known price), then Finnhub live."""
    if ticker in cache and cache[ticker].get("price"):
        return cache[ticker]
    quote = get_finnhub_quote(ticker)
    if quote:
        return quote
    # Fall back to cache even if stale
    if ticker in cache:
        return cache[ticker]
    return None

def compute_yield(price, stated_rate):
    """Compute effective yield based on price vs par."""
    if price and price > 0:
        annual_div = PAR * stated_rate
        return annual_div / price
    return None

def main():
    print(f"[{datetime.datetime.now().isoformat()}] Updating market data...")

    # Load existing cache
    cache = {}
    if os.path.exists(PRICE_FILE):
        try:
            with open(PRICE_FILE) as f:
                cache = json.load(f)
        except:
            pass

    results = {}
    for ticker, info in TICKERS.items():
        quote = get_cached_or_fetch(ticker, cache)
        if quote:
            eff_yield = compute_yield(quote["price"], info["statedRate"])
            results[ticker] = {
                "price": round(quote["price"], 2),
                "effRate": round(eff_yield, 4) if eff_yield else None,
                "statedRate": info["statedRate"],
                "name": info["name"],
                "freq": info["freq"],
                "par": PAR,
                "updated": datetime.datetime.now().isoformat(),
                "prev_close": quote.get("pc", quote.get("o", 0)),
            }
            print(f"  {ticker}: ${quote['price']:.2f} (eff yield: {(eff_yield*100):.2f}% if eff_yield else 'N/A')")
        else:
            print(f"  {ticker}: FAILED - using stale cache")
            if ticker in cache:
                results[ticker] = cache[ticker]
                results[ticker]["stale"] = True

    # Write prices.json
    with open(PRICE_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Wrote {PRICE_FILE}")

    print("[Done] Market data updated successfully.")

if __name__ == "__main__":
    main()
