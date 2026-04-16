#!/usr/bin/env python3
"""
Fetch latest market data for Strategy Preferreds tracker and update market-data.js
Run via cron: 0 * * * * /usr/bin/python3 /Users/tradbot/.openclaw/workspace/strategy-preferreds-deploy/update_market_data.py >> /Users/tradbot/.openclaw/workspace/strategy-preferreds-deploy/update.log 2>&1
"""

import yfinance as yf
import json
import os
import re
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, 'market-data.js')
REPO_DIR = SCRIPT_DIR

TICKERS = ['SPY', 'QQQ', 'BTC-USD', 'MSTR', 'STRC', 'STRK', 'STRD', 'STRF', 'STRE']

def get_latest_data():
    """Fetch weekly (or daily if not available) closes for all tickers."""
    result = {}
    for ticker in TICKERS:
        try:
            t = yf.Ticker(ticker)
            # Get last 18 months weekly data
            hist = t.history(period='18mo', interval='1wk')
            if hist.empty:
                hist = t.history(period='3mo', interval='1d')
            result[ticker] = [
                {
                    'x': str(date.date()),
                    'y': round(float(close), 2)
                }
                for date, close in hist['Close'].items()
            ]
            print(f"[{datetime.now()}] Fetched {ticker}: {len(result[ticker])} data points")
        except Exception as e:
            print(f"[{datetime.now()}] ERROR fetching {ticker}: {e}")
            result[ticker] = []
    return result

def update_data_file(data):
    """Read current market-data.js and update with new data."""
    with open(DATA_FILE, 'r') as f:
        content = f.read()

    new_data_str = json.dumps(data, separators=(',', ':'))

    # Pattern: const marketData = {...};
    pattern = r'(const marketData = )\{.*?\};'
    replacement = r'\1' + new_data_str + ';'

    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    with open(DATA_FILE, 'w') as f:
        f.write(new_content)

    print(f"[{datetime.now()}] Updated {DATA_FILE}")

def commit_and_push():
    """Commit and push updated data to GitHub."""
    import subprocess
    try:
        # Set git identity
        subprocess.run(['git', 'config', 'user.email', 'tradbot@traditionsales.com'], cwd=REPO_DIR, check=True)
        subprocess.run(['git', 'config', 'user.name', 'TradBot'], cwd=REPO_DIR, check=True)
        # Commit
        result = subprocess.run(['git', 'add', 'market-data.js', 'update_market_data.py'], cwd=REPO_DIR, capture_output=True, text=True)
        result = subprocess.run(['git', 'commit', '-m', f'Auto-update market data {datetime.now().strftime("%Y-%m-%d %H:%M")}'], cwd=REPO_DIR, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[{datetime.now()}] Committed: {result.stdout.strip()}")
        else:
            if 'nothing to commit' in result.stdout or result.returncode == 0:
                print(f"[{datetime.now()}] No changes to commit")
            else:
                print(f"[{datetime.now()}] Commit warning: {result.stderr}")
        # Push
        result = subprocess.run(['git', 'push', 'origin', 'main'], cwd=REPO_DIR, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[{datetime.now()}] Pushed to GitHub")
        else:
            print(f"[{datetime.now()}] Push: {result.stderr[:200]}")
    except Exception as e:
        print(f"[{datetime.now()}] Git error: {e}")

def main():
    print(f"[{datetime.now()}] === Starting market data update ===")
    data = get_latest_data()
    if any(v for v in data.values() if v):
        update_data_file(data)
        commit_and_push()
    else:
        print(f"[{datetime.now()}] WARNING: No data fetched, skipping file update")
    print(f"[{datetime.now()}] === Update complete ===")

if __name__ == '__main__':
    main()
