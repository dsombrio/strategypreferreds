from flask import Flask, render_template_string, request, jsonify
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from sklearn.linear_model import Ridge
from datetime import datetime, timedelta
import os
import warnings
warnings.filterwarnings('ignore')

# Inline HTML template to avoid folder issues
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DRIP Calculator - Synthetic BTC Exposure</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-card: #161b22;
            --border: #30363d;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --accent: #58a6ff;
            --accent-hover: #79b8ff;
            --success: #3fb950;
            --warning: #d29922;
            --error: #f85149;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-primary);
            background-image: 
                linear-gradient(rgba(88, 166, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(88, 166, 255, 0.03) 1px, transparent 1px);
            background-size: 50px 50px;
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container { width: 100%; max-width: 600px; }
        
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 32px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }
        
        h1 { font-size: 24px; font-weight: 600; margin-bottom: 8px; text-align: center; }
        .subtitle { color: var(--text-secondary); text-align: center; font-size: 14px; margin-bottom: 28px; }
        
        .form-group { margin-bottom: 20px; }
        label { display: block; font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-bottom: 8px; }
        
        input[type="text"], input[type="number"], select {
            width: 100%;
            padding: 12px 16px;
            background: var(--bg-primary);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 16px;
        }
        
        input:focus, select:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15); }
        
        .input-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        
        button {
            width: 100%;
            padding: 14px 24px;
            background: var(--accent);
            border: none;
            border-radius: 8px;
            color: #fff;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
        }
        
        button:hover { background: var(--accent-hover); }
        button:disabled { opacity: 0.6; cursor: not-allowed; }
        
        .results { margin-top: 28px; padding-top: 28px; border-top: 1px solid var(--border); display: none; }
        .results.visible { display: block; }
        
        .results-header { font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.5px; }
        
        .weights-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 24px; }
        
        .weight-item { background: var(--bg-primary); border: 1px solid var(--border); border-radius: 8px; padding: 14px; text-align: center; }
        .weight-ticker { font-size: 18px; font-weight: 700; color: var(--accent); margin-bottom: 4px; }
        .weight-value { font-size: 20px; font-weight: 600; }
        
        .metrics-row { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
        .metric { background: var(--bg-primary); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
        .metric-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
        .metric-value { font-size: 24px; font-weight: 600; }
        .metric-value.positive { color: var(--success); }
        .metric-value.negative { color: var(--error); }
        
        .r-squared { font-size: 12px; color: var(--text-secondary); text-align: center; margin-top: 16px; }
        
        .error { background: rgba(248, 81, 73, 0.1); border: 1px solid var(--error); border-radius: 8px; padding: 16px; color: var(--error); text-align: center; margin-top: 20px; display: none; }
        .error.visible { display: block; }
        
        .loading { display: none; text-align: center; margin-top: 20px; color: var(--text-secondary); }
        .loading.visible { display: block; }
        
        .advanced-toggle { text-align: center; margin-top: 20px; }
        .advanced-toggle button { background: transparent; border: none; color: var(--text-secondary); font-size: 13px; cursor: pointer; text-decoration: underline; width: auto; padding: 8px; }
        
        .advanced-panel { display: none; margin-top: 20px; padding: 16px; background: var(--bg-primary); border-radius: 8px; font-size: 13px; color: var(--text-secondary); }
        .advanced-panel.visible { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>DRIP Calculator</h1>
            <p class="subtitle">Match any stock's return profile with BTC-linked securities</p>
            
            <form id="calcForm">
                <div class="form-group">
                    <label for="symbol">Stock Symbol</label>
                    <input type="text" id="symbol" placeholder="e.g., AAPL, NVDA, GOOGL" required>
                </div>
                
                <div class="input-row">
                    <div class="form-group">
                        <label for="period">Timeline</label>
                        <select id="period">
                            <option value="1mo">1 Month</option>
                            <option value="3mo">3 Months</option>
                            <option value="6mo">6 Months</option>
                            <option value="YTD">Year to Date</option>
                            <option value="1y">1 Year</option>
                            <option value="MAX" selected>MAX (Available)</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="btc_appreciation">Expected BTC Appreciation (%)</label>
                        <input type="number" id="btc_appreciation" value="0" step="1" min="-100">
                    </div>
                </div>
                
                <button type="submit" id="calcBtn">Calculate</button>
            </form>
            
            <div class="loading" id="loading">Calculating</div>
            <div class="error" id="error"></div>
            
            <div class="results" id="results">
                <div class="results-header">Optimal Weights</div>
                <div class="weights-grid" id="weightsGrid"></div>
                
                <div class="metrics-row">
                    <div class="metric">
                        <div class="metric-label">Weighted Dividend Yield</div>
                        <div class="metric-value" id="dividendYield">—</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Projected Return</div>
                        <div class="metric-value" id="projectedReturn">—</div>
                    </div>
                </div>
                
                <div class="metrics-row" style="margin-top: 16px;">
                    <div class="metric">
                        <div class="metric-label">Actual Stock Return</div>
                        <div class="metric-value" id="stockReturn">—</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Data Points</div>
                        <div class="metric-value" id="dataPoints" style="font-size: 18px;">—</div>
                    </div>
                </div>
                
                <div class="r-squared">R² = <span id="rSquared">—</span> (model fit)</div>
                
                <div class="advanced-toggle">
                    <button type="button" onclick="toggleAdvanced()">Show Advanced Details</button>
                </div>
                
                <div class="advanced-panel" id="advancedPanel">
                    <p><strong>Method:</strong> Constrained linear regression to minimize squared error.</p>
                    <p style="margin-top: 8px;"><strong>Assets:</strong> <span id="availableAssets"></span></p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function toggleAdvanced() {
            const panel = document.getElementById('advancedPanel');
            const btn = document.querySelector('.advanced-toggle button');
            panel.classList.toggle('visible');
            btn.textContent = panel.classList.contains('visible') ? 'Hide Advanced Details' : 'Show Advanced Details';
        }
        
        function formatPercent(value) {
            const sign = value >= 0 ? '+' : '';
            return sign + value.toFixed(2) + '%';
        }
        
        document.getElementById('calcForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const symbol = document.getElementById('symbol').value.trim();
            const period = document.getElementById('period').value;
            const btcAppreciation = parseFloat(document.getElementById('btc_appreciation').value) || 0;
            
            if (!symbol) { showError('Please enter a stock symbol'); return; }
            
            document.getElementById('loading').classList.add('visible');
            document.getElementById('results').classList.remove('visible');
            document.getElementById('error').classList.remove('visible');
            document.getElementById('calcBtn').disabled = true;
            
            try {
                const response = await fetch('/calculate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol: symbol, period: period, btc_appreciation: btcAppreciation })
                });
                
                const data = await response.json();
                
                if (!response.ok) { showError(data.error || 'An error occurred'); return; }
                displayResults(data);
            } catch (err) { showError('Failed to connect to server'); }
            finally {
                document.getElementById('loading').classList.remove('visible');
                document.getElementById('calcBtn').disabled = false;
            }
        });
        
        function showError(message) {
            const errorEl = document.getElementById('error');
            errorEl.textContent = message;
            errorEl.classList.add('visible');
            document.getElementById('results').classList.remove('visible');
        }
        
        function displayResults(data) {
            const weightsGrid = document.getElementById('weightsGrid');
            weightsGrid.innerHTML = '';
            
            const sortedWeights = Object.entries(data.weights).sort((a, b) => b[1] - a[1]);
            
            for (const [ticker, weight] of sortedWeights) {
                const item = document.createElement('div');
                item.className = 'weight-item';
                item.innerHTML = `<div class="weight-ticker">${ticker}</div><div class="weight-value">${weight.toFixed(1)}%</div>`;
                weightsGrid.appendChild(item);
            }
            
            document.getElementById('dividendYield').textContent = data.dividend_yield.toFixed(2) + '%';
            document.getElementById('dividendYield').className = 'metric-value positive';
            
            const projReturn = document.getElementById('projectedReturn');
            projReturn.textContent = formatPercent(data.projected_return);
            projReturn.className = 'metric-value ' + (data.projected_return >= 0 ? 'positive' : 'negative');
            
            const stockRet = document.getElementById('stockReturn');
            stockRet.textContent = formatPercent(data.stock_return);
            stockRet.className = 'metric-value ' + (data.stock_return >= 0 ? 'positive' : 'negative');
            
            document.getElementById('dataPoints').textContent = data.data_points;
            document.getElementById('rSquared').textContent = (data.r_squared / 100).toFixed(2);
            document.getElementById('availableAssets').textContent = data.available_assets.join(', ');
            
            document.getElementById('results').classList.add('visible');
        }
    </script>
</body>
</html>"""

app = Flask(__name__)

# Strategy preferred tickers with their dividend rates
PREFERREDS = {
    'MSTR': {'dividend_rate': 0.0, 'mstr_beta': True},  # No fixed dividend, tracks BTC
    'STRC': {'dividend_rate': 0.1125},  # 11.25%
    'STRD': {'dividend_rate': 0.10},     # 10%
    'STRF': {'dividend_rate': 0.10},     # 10%
    'STRK': {'dividend_rate': 0.08},     # 8%
    'BTC-USD': {'dividend_rate': 0.0},   # No dividend
}

DEFAULT_MSTR_BETA = 1.5  # Conservative estimate

def get_period_end_date(period):
    """Convert period string to start and end dates"""
    end_date = datetime.now()
    
    if period == 'MAX':
        start_date = datetime(2020, 1, 1)  # MSTR has data from ~2020
    elif period == 'YTD':
        start_date = datetime(end_date.year, 1, 1)
    elif period == '1y':
        start_date = end_date - timedelta(days=365)
    elif period == '6mo':
        start_date = end_date - timedelta(days=180)
    elif period == '3mo':
        start_date = end_date - timedelta(days=90)
    elif period == '1mo':
        start_date = end_date - timedelta(days=30)
    else:
        start_date = datetime(2020, 1, 1)
    
    return start_date, end_date

def fetch_data(tickers, period):
    """Fetch historical data for given tickers"""
    start_date, end_date = get_period_end_date(period)
    
    try:
        data = yf.download(tickers, start=start_date, end=end_date, progress=False)
        
        if len(tickers) == 1:
            # Single ticker returns differently
            close_prices = data['Close'].dropna()
        else:
            # Multiple tickers - need to handle MultiIndex columns
            close_prices = data['Close'].dropna(axis=1, how='all')
            # Flatten if needed
            if isinstance(close_prices.columns, pd.MultiIndex):
                close_prices.columns = [c[0] if isinstance(c, tuple) else c for c in close_prices.columns]
        
        return close_prices
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def calculate_returns(prices):
    """Calculate daily returns"""
    if prices is None or prices.empty:
        return None
    
    returns = prices.pct_change().dropna()
    return returns

def optimize_weights(target_returns, asset_returns):
    """
    Find optimal weights to replicate target returns using constrained optimization.
    Falls back to ridge regression if optimization fails.
    """
    assets = asset_returns.columns.tolist()
    n_assets = len(assets)
    
    if target_returns.empty or asset_returns.empty:
        return None, None, None
    
    # Align dates
    common_dates = target_returns.index.intersection(asset_returns.index)
    n_common = len(common_dates)
    
    if n_common < 15:
        return None, None, None
    
    target = target_returns.loc[common_dates].values.flatten()
    X = asset_returns.loc[common_dates].values
    
    # First try: constrained optimization
    def objective(weights):
        predicted = X @ weights
        return np.sum((target - predicted) ** 2)
    
    constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
    bounds = [(0, 1) for _ in range(n_assets)]
    x0 = np.ones(n_assets) / n_assets
    
    result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints)
    
    if result.success and result.x.max() > 0:
        weights = dict(zip(assets, result.x))
    else:
        # Fallback: Ridge regression with normalization
        from sklearn.linear_model import Ridge
        ridge = Ridge(alpha=0.1, positive=True)
        ridge.fit(X, target)
        weights_raw = ridge.coef_
        
        # Normalize to sum to 1
        weight_sum = weights_raw.sum()
        if weight_sum > 0:
            weights_raw = weights_raw / weight_sum
        else:
            weights_raw = np.ones(n_assets) / n_assets
        
        # Clip to [0, 1]
        weights_raw = np.clip(weights_raw, 0, 1)
        weights = dict(zip(assets, weights_raw))
    
    # Calculate R-squared
    weights_arr = np.array([weights[a] for a in assets])
    predicted = X @ weights_arr
    ss_res = np.sum((target - predicted) ** 2)
    ss_tot = np.sum((target - np.mean(target)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    return weights, r_squared, predicted

def calculate_dividend_yield(weights):
    """Calculate weighted average dividend yield (weights in percentage form 0-100)"""
    total_yield = 0
    for ticker, weight in weights.items():
        if ticker in PREFERREDS:
            # weight is already a percentage (e.g., 50 = 50%), dividend_rate is decimal (e.g., 0.10 = 10%)
            total_yield += (PREFERREDS[ticker]['dividend_rate'] * weight)
    return total_yield / 100  # Convert from percentage-yield to actual percentage

def calculate_projected_return(weights, btc_appreciation, mstr_beta=DEFAULT_MSTR_BETA):
    """
    Calculate projected return based on expected BTC appreciation.
    - MSTR scales with BTC (mstr_beta multiplier)
    - Preferreds have fixed upside (their price correlates with MSTR/BTC)
    - BTC is direct 1:1
    """
    projected = 0
    
    for ticker, weight in weights.items():
        if ticker == 'MSTR':
            # MSTR typically outperforms BTC by mstr_beta
            projected += weight * (btc_appreciation * mstr_beta)
        elif ticker == 'BTC-USD':
            projected += weight * btc_appreciation
        elif ticker in ['STRC', 'STRD', 'STRF', 'STRK']:
            # Preferreds track MSTR (convertible or perpetual)
            # STRK is directly convertible to MSTR, others track MSTR
            preferred_upside = btc_appreciation * 0.5  # Moderate correlation to MSTR
            projected += weight * preferred_upside
        else:
            projected += weight * 0  # No projection for unknown
    
    return projected

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.get_json()
    
    symbol = data.get('symbol', '').strip().upper()
    period = data.get('period', 'MAX')
    btc_appreciation = float(data.get('btc_appreciation', 0)) / 100  # Convert from percentage
    
    if not symbol:
        return jsonify({'error': 'Please enter a stock symbol'}), 400
    
    # Fetch data
    all_tickers = [symbol, 'MSTR', 'BTC-USD']
    
    # Add preferreds that are likely available
    # These are newer, may not all have data
    preferred_tickers = ['STRC', 'STRD', 'STRF', 'STRK']
    
    prices = fetch_data(all_tickers + preferred_tickers, period)
    
    if prices is None or prices.empty:
        return jsonify({'error': f'Could not fetch data for {symbol}'}), 400
    
    # Check which columns we actually got
    available_assets = []
    for t in ['MSTR', 'STRC', 'STRD', 'STRF', 'STRK', 'BTC-USD']:
        if t in prices.columns and len(prices[t].dropna()) > 0:
            available_assets.append(t)
    
    if not available_assets:
        return jsonify({'error': 'No BTC-linked assets available for analysis'}), 400
    
    # Calculate returns
    returns = calculate_returns(prices)
    
    if returns is None:
        return jsonify({'error': 'Could not calculate returns'}), 400
    
    target_returns = returns[symbol]
    asset_returns = returns[[c for c in available_assets if c != symbol]]
    
    # Optimize
    weights, r_squared, predicted = optimize_weights(target_returns, asset_returns)
    
    if weights is None:
        return jsonify({'error': 'Could not find optimal weights. Try a shorter period.'}), 400
    
    # Filter out zero weights for cleaner output
    weights = {k: round(v * 100, 2) for k, v in weights.items() if v > 0.01}
    
    # Calculate metrics
    dividend_yield = calculate_dividend_yield(weights)  # Returns percentage directly now
    projected_return = calculate_projected_return(weights, btc_appreciation) * 100
    
    # Get actual stock performance
    stock_return = (1 + target_returns.sum()) - 1  # Total return over period
    
    return jsonify({
        'symbol': symbol,
        'weights': weights,
        'r_squared': round(r_squared * 100, 2),
        'dividend_yield': round(dividend_yield, 2),
        'stock_return': round(stock_return * 100, 2),
        'projected_return': round(projected_return, 2),
        'available_assets': available_assets,
        'data_points': len(target_returns)
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
