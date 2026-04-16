#!/usr/bin/env python3
"""
Fetch latest market data for Strategy Preferreds tracker and update the site files.
- Updates CUR prices in index.html with live Yahoo Finance prices
- Updates buildChartData() with real historical weekly closes
- Commits and pushes to GitHub

Run via cron: 0 * * * * /usr/bin/python3 /Users/tradbot/.openclaw/workspace/strategy-preferreds-deploy/update_market_data.py >> /Users/tradbot/.openclaw/workspace/strategy-preferreds-deploy/update.log 2>&1
"""

import yfinance as yf
import json
import os
import re
import subprocess
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(SCRIPT_DIR, 'index.html')

# Tickers to track
TICKERS = ['SPY', 'QQQ', 'BTC-USD', 'MSTR', 'STRC', 'STRK', 'STRD', 'STRF']

def get_price(ticker, period='5d'):
    """Get latest closing price for a ticker."""
    try:
        data = yf.Ticker(ticker).history(period=period)
        if not data.empty:
            return round(float(data['Close'].iloc[-1]), 2)
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching {ticker}: {e}")
    return None

def get_weekly_data(ticker, weeks=60):
    """Get weekly close data for chart series."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=f'{weeks}wk', interval='1wk')
        if hist.empty:
            hist = t.history(period=f'{weeks}d', interval='1d')
        result = []
        for date, row in hist['Close'].items():
            result.append({
                'x': date.isoformat(),
                'y': round(float(row), 2)
            })
        return result
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching weekly {ticker}: {e}")
        return []

def update_index_html(prices, chart_data):
    """Update the CUR object and buildChartData in index.html."""
    with open(INDEX_FILE, 'r') as f:
        content = f.read()

    # Update CUR object with live prices
    stre_price = prices.get('STRE', 85.50)
    old_cur = r"var CUR = \{[^;]+\};"
    new_cur = f"""var CUR = {{
  STRC: {{ price: {prices.get('STRC', '?')}, effRate: 0.1152, name: 'Stretch Monthly', statedRate: 0.115 }},
  STRK: {{ price: {prices.get('STRK', '?')}, effRate: 0.1150, name: 'Strike 10% Quarterly', statedRate: 0.10 }},
  STRD: {{ price: {prices.get('STRD', '?')}, effRate: 0.1450, name: 'Strike Discount', statedRate: 0.10 }},
  STRF: {{ price: {prices.get('STRF', '?')}, effRate: 0.0980, name: 'Flex Variable', statedRate: 0.08 }},
  STRE: {{ price: {stre_price}, effRate: 0.1200, name: 'Stream EU', statedRate: 0.10 }}
}};"""
    content = re.sub(old_cur, new_cur, content, flags=re.DOTALL)

    # Update TODAY date
    content = re.sub(r"var TODAY = new Date\('[0-9-]+'\);", f"var TODAY = new Date('{datetime.now().strftime('%Y-%m-%d')}');", content)

    # Update buildChartData with real data
    def make_series_data(weekly_data):
        if not weekly_data:
            # Fallback to par
            return "[{x: new Date(), y: 100}]"
        # Convert to JavaScript array format
        items = []
        for pt in weekly_data[-60:]:  # Last 60 data points
            items.append(f"{{x: new Date('{pt['x'][:10]}'), y: {pt['y']}}}")
        return "[" + ", ".join(items) + "]"

    strc_data = make_series_data(chart_data.get('STRC', []))
    strk_data = make_series_data(chart_data.get('STRK', []))
    strd_data = make_series_data(chart_data.get('STRD', []))
    strf_data = make_series_data(chart_data.get('STRF', []))

    old_build = r"function buildChartData\(\) \{[^}]+\{[^}]+\}[^}]+\}"
    new_build = f"""function buildChartData() {{
  return {{
    STRC: {strc_data},
    STRK: {strk_data},
    STRD: {strd_data},
    STRF: {strf_data},
    STRE: [],
    '$100 Par': []
  }};
}}"""
    content = re.sub(old_build, new_build, content, flags=re.DOTALL)

    with open(INDEX_FILE, 'w') as f:
        f.write(content)

    print(f"[{datetime.now()}] Updated {INDEX_FILE}")

def commit_and_push():
    """Commit and push updated site to GitHub."""
    try:
        subprocess.run(['git', 'config', 'user.email', 'tradbot@traditionsales.com'], cwd=SCRIPT_DIR, check=True)
        subprocess.run(['git', 'config', 'user.name', 'TradBot'], cwd=SCRIPT_DIR, check=True)
        subprocess.run(['git', 'add', 'index.html', 'update_market_data.py'], cwd=SCRIPT_DIR, check=True)
        result = subprocess.run(['git', 'commit', '-m', f'Auto-update live prices {datetime.now().strftime("%Y-%m-%d %H:%M")}'], cwd=SCRIPT_DIR, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[{datetime.now()}] Committed: {result.stdout.strip()}")
        elif 'nothing to commit' in result.stdout:
            print(f"[{datetime.now()}] No changes to commit")
        else:
            print(f"[{datetime.now()}] Commit: {result.stderr[:200]}")
        result = subprocess.run(['git', 'push', 'origin', 'main'], cwd=SCRIPT_DIR, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[{datetime.now()}] Pushed to GitHub")
        else:
            print(f"[{datetime.now()}] Push: {result.stderr[:200]}")
    except Exception as e:
        print(f"[{datetime.now()}] Git error: {e}")

def main():
    print(f"[{datetime.now()}] === Starting market data update ===")

    # Get current prices
    prices = {}
    for t in TICKERS:
        p = get_price(t)
        if p:
            prices[t] = p
            print(f"[{datetime.now()}] {t}: ${p}")

    # Get weekly chart data for preferreds
    chart_data = {}
    for t in ['STRC', 'STRK', 'STRD', 'STRF']:
        data = get_weekly_data(t, weeks=60)
        if data:
            chart_data[t] = data
            print(f"[{datetime.now()}] {t} chart data: {len(data)} points, latest: ${data[-1]['y'] if data else '?'}")

    if prices:
        update_index_html(prices, chart_data)
        commit_and_push()
    else:
        print(f"[{datetime.now()}] WARNING: No data fetched, skipping update")

    print(f"[{datetime.now()}] === Update complete ===")

if __name__ == '__main__':
    main()
