#!/usr/bin/env python3
"""
Fetch DAILY market data for Strategy Preferreds tracker.
- Updates CUR prices in index.html with live Yahoo Finance prices
- Updates window._chartData with real DAILY closes for chart
- Commits and pushes to GitHub
"""

import yfinance as yf
import json
import os
import re
import subprocess
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(SCRIPT_DIR, 'index.html')

TICKERS = ['SPY', 'QQQ', 'BTC-USD', 'MSTR', 'STRC', 'STRK', 'STRD', 'STRF']

def get_price(ticker, period='5d'):
    try:
        data = yf.Ticker(ticker).history(period=period)
        if not data.empty:
            return round(float(data['Close'].iloc[-1]), 2)
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching {ticker}: {e}")
    return None

def get_daily_data(ticker, months=9):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=f'{months}mo', interval='1d')
        result = []
        for date, row in hist['Close'].items():
            result.append({
                'x': date.isoformat(),
                'y': round(float(row), 2)
            })
        return result
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching daily {ticker}: {e}")
        return []

def update_index_html(prices, chart_data):
    with open(INDEX_FILE, 'r') as f:
        content = f.read()

    today_str = datetime.now().strftime('%Y-%m-%d')

    # 1. Update CUR object with live prices
    old_cur = r"var CUR = \{[^;]+\};"
    new_cur = f"""var CUR = {{
  STRC: {{ price: {prices.get('STRC', '?')}, effRate: 0.1152, name: 'Stretch Monthly', statedRate: 0.115 }},
  STRK: {{ price: {prices.get('STRK', '?')}, effRate: 0.1150, name: 'Strike 10% Quarterly', statedRate: 0.10 }},
  STRD: {{ price: {prices.get('STRD', '?')}, effRate: 0.1450, name: 'Strike Discount', statedRate: 0.10 }},
  STRF: {{ price: {prices.get('STRF', '?')}, effRate: 0.0980, name: 'Flex Variable', statedRate: 0.08 }},
  STRE: {{ price: {prices.get('STRE', 85.5)}, effRate: 0.1200, name: 'Stream EU', statedRate: 0.10 }}
}};"""
    content = re.sub(old_cur, new_cur, content, flags=re.DOTALL)

    # 2. Update window._chartData with real daily data
    def make_js_array(arr):
        if not arr:
            return "[]"
        items = [f"{{x: new Date('{pt['x'][:10]}'), y: {pt['y']}}}" for pt in arr]
        return "[" + ", ".join(items) + "]"

    chart_js = f"""window._chartData = {{
  STRC: {make_js_array(chart_data.get('STRC', []))},
  STRK: {make_js_array(chart_data.get('STRK', []))},
  STRD: {make_js_array(chart_data.get('STRD', []))},
  STRF: {make_js_array(chart_data.get('STRF', []))},
  SPY:  {make_js_array(chart_data.get('SPY', []))},
  QQQ:  {make_js_array(chart_data.get('QQQ', []))},
  BTC:  {make_js_array(chart_data.get('BTC-USD', []))},
  MSTR: {make_js_array(chart_data.get('MSTR', []))}
}};"""

    # Replace the window._chartData object
    old_chart = r"window\._chartData = window\._chartData \|\| \{\};"
    content = re.sub(old_chart, chart_js, content)

    # Update TODAY date in the script
    content = re.sub(
        r"var TODAY = new Date\('[0-9-]+'\);",
        f"var TODAY = new Date('{today_str}');",
        content
    )

    with open(INDEX_FILE, 'w') as f:
        f.write(content)

    print(f"[{datetime.now()}] Updated {INDEX_FILE}")
    for t in ['STRC', 'STRK', 'STRD', 'STRF']:
        pts = len(chart_data.get(t, []))
        print(f"  {t}: {pts} daily points")

def commit_and_push():
    try:
        subprocess.run(['git', 'config', 'user.email', 'tradbot@traditionsales.com'], cwd=SCRIPT_DIR, check=True)
        subprocess.run(['git', 'config', 'user.name', 'TradBot'], cwd=SCRIPT_DIR, check=True)
        subprocess.run(['git', 'add', 'index.html', 'update_market_data.py'], cwd=SCRIPT_DIR, check=True)
        result = subprocess.run(
            ['git', 'commit', '-m', f'Auto-update daily prices {datetime.now().strftime("%Y-%m-%d %H:%M")}'],
            cwd=SCRIPT_DIR, capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"[{datetime.now()}] Committed")
        elif 'nothing to commit' in result.stdout or result.returncode == 0:
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

    prices = {}
    for t in TICKERS:
        p = get_price(t)
        if p:
            prices[t] = p
            print(f"[{datetime.now()}] {t}: ${p}")

    chart_data = {}
    for t in ['STRC', 'STRK', 'STRD', 'STRF', 'SPY', 'QQQ', 'BTC-USD', 'MSTR']:
        data = get_daily_data(t, months=9)
        if data:
            chart_data[t] = data
            latest = data[-1]
            print(f"[{datetime.now()}] {t} chart: {len(data)} pts, last: ${latest['y']} ({latest['x'][:10]})")

    if prices:
        update_index_html(prices, chart_data)
        commit_and_push()
    else:
        print(f"[{datetime.now()}] WARNING: No data fetched")

    print(f"[{datetime.now()}] === Update complete ===")

if __name__ == '__main__':
    main()
