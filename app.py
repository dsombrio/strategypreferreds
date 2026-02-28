from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from sklearn.linear_model import Ridge
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

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
    return render_template('index.html')

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
    app.run(debug=True, host='0.0.0.0', port=5000)
