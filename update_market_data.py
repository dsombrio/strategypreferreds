#!/usr/bin/env python3
"""
Fetch DAILY market data for Strategy Preferreds tracker.
- Updates CUR prices in index.html with live Yahoo Finance prices
- Updates buildChartData() with real DAILY closes for each preferred stock
- Commits and pushes to GitHub
"""

import yfinance as yf
import json
import os
import re
import subprocess
from datetime import datetime, timedelta

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
    """Get daily close data for chart series."""
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

    # 1. Update CUR object with live prices
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

    # 2. Update TODAY date
    content = re.sub(
        r"var TODAY = new Date\('[0-9-]+'\);",
        f"var TODAY = new Date('{datetime.now().strftime('%Y-%m-%d')}');",
        content
    )

    # 3. Update buildChartData function with real daily data
    def make_series(weekly_data):
        if not weekly_data:
            return "[]"
        items = []
        for pt in weekly_data:
            items.append(f"{{x: new Date('{pt['x'][:10]}'), y: {pt['y']}}}")
        return "[" + ", ".join(items) + "]"

    strc = make_series(chart_data.get('STRC', []))
    strk = make_series(chart_data.get('STRK', []))
    strd = make_series(chart_data.get('STRD', []))
    strf = make_series(chart_data.get('STRF', []))
    spy  = make_series(chart_data.get('SPY', []))

    new_chart_func = f"""function buildChartData() {{
  var spy = {spy};
  var today = new Date('{datetime.now().strftime('%Y-%m-%d')}');
  var start = new Date('{datetime.now().strftime('%Y-%m-%d')}');
  start.setFullYear(start.getFullYear() - 1);
  var par100 = spy.filter(p => p.x >= start && p.x <= today).map(function() {{ return {{x: new Date(0), y: 100}}; }});
  par100 = par100.length ? par100 : [{'{datetime.now().strftime("%Y-%m-%d")}' + 'T00:00:00'}, 100];
  return {{
    STRC:  {strc},
    STRK:  {strk},
    STRD:  {strd},
    STRF:  {strf},
    STRE:  [],
    '$100 Par': par100
  }};
}}"""

    # Replace the buildChartData function
    pattern = r'function buildChartData\(\) \{[\s\S]*?\n\}'
    content = re.sub(pattern, new_chart_func, content, count=1)

    with open(INDEX_FILE, 'w') as f:
        f.write(content)

    print(f"[{datetime.now()}] Updated {INDEX_FILE}")
    print(f"  STRK daily points: {len(chart_data.get('STRK', []))}")
    print(f"  STRD daily points: {len(chart_data.get('STRD', []))}")

def commit_and_push():
    try:
        subprocess.run(['git', 'config', 'user.email', 'tradbot@traditionsales.com'], cwd=SCRIPT_DIR, check=True)
        subprocess.run(['git', 'config', 'user.name', 'TradBot'], cwd=SCRIPT_DIR, check=True)
        subprocess.run(['git', 'add', 'index.html', 'update_market_data.py'], cwd=SCRIPT_DIR, check=True)
        result = subprocess.run(['git', 'commit', '-m', f'Auto-update daily prices {datetime.now().strftime("%Y-%m-%d %H:%M")}'], cwd=SCRIPT_DIR, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[{datetime.now()}] Committed")
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

    prices = {}
    for t in TICKERS:
        p = get_price(t)
        if p:
            prices[t] = p
            print(f"[{datetime.now()}] {t}: ${p}")

    chart_data = {}
    for t in ['STRC', 'STRK', 'STRD', 'STRF', 'SPY']:
        data = get_daily_data(t, months=9)
        if data:
            chart_data[t] = data
            latest = data[-1]
            print(f"[{datetime.now()}] {t} chart: {len(data)} daily points, last: ${latest['y']} ({latest['x'][:10]})")

    if prices:
        update_index_html(prices, chart_data)
        commit_and_push()
    else:
        print(f"[{datetime.now()}] WARNING: No data fetched")

    print(f"[{datetime.now()}] === Update complete ===")

if __name__ == '__main__':
    main()
