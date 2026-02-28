# DRIP Calculator - Synthetic BTC Exposure Matcher

## Project Overview
- **Name**: DRIP Calculator
- **Type**: Single-page web application
- **Core functionality**: Given a publicly traded stock, calculate the optimal mix of MSTR, STRC, STRD, STRF, STRK, and BTC that replicates its beta and return profile
- **Target users**: Investors wanting to understand BTC-linked securities exposure

## Data Architecture

### Tickers
- **Reference assets**: MSTR, STRC, STRD, STRF, STRK, BTC-USD
- **User input**: Any Yahoo Finance symbol

### Data Handling
- **Source**: Yahoo Finance via `yfinance` Python library
- **Timeline**: User-selectable (1mo, 3mo, 6mo, YTD, 1y, MAX). Default: MAX
- **Constraint**: If preferreds have shorter history than selected period, use their available history
- **Returns**: Daily percentage returns for regression

## UI/UX Specification

### Layout
- Single centered card (max-width: 600px)
- Clean, minimal design with dark mode support

### Visual Design
- **Background**: Dark charcoal (#0d1117) with subtle grid pattern
- **Card**: Dark gray (#161b22) with 1px border (#30363d)
- **Accent**: Electric blue (#58a6ff) for primary actions
- **Text**: White (#f0f6fc) primary, gray (#8b949e) secondary
- **Font**: System sans-serif (SF Pro, -apple-system, Segoe UI)

### Components
1. **Stock Input** — Text field with "Calculate" button
2. **Timeline Dropdown** — Options: 1mo, 3mo, 6mo, YTD, 1y, MAX
3. **BTC Appreciation Input** — Number field (percentage) for projected BTC gain
4. **Results Panel** — Shows weights, dividend yield, projected return
5. **Advanced Toggle** — Expands to show regression details (R², beta per asset)

### Interaction Flow
1. User enters stock symbol (e.g., AAPL)
2. Selects timeline (default MAX)
3. Enters expected BTC appreciation (default 0%)
4. Clicks "Calculate"
5. Results display with weights and projected returns

## Functionality Specification

### Core Algorithm
1. Fetch historical prices for all assets (selected period)
2. Calculate daily returns for each
3. Run constrained linear regression: minimize squared error between portfolio returns and stock returns
4. Constraints: weights >= 0, weights sum <= 1 (allow cash buffer)
5. Output optimal weights normalized to sum to 1

### Dividend Calculation
- Weighted average of stated dividend rates:
  - STRC: 11.25%
  - STRD: 10%
  - STRF: 10%
  - STRK: 8%
- Note: MSTR and BTC don't pay dividends (MSTR issues optional distributions)

### Projection Logic
- User inputs expected BTC appreciation (e.g., +50%)
- MSTR beta to BTC is approximately 1.5-2x (we'll calculate from data or default to 1.5)
- Apply weighted returns: (BTC change × MSTR beta × MSTR weight) + (other weights × their returns)

### Edge Cases
- **Insufficient data**: If preferreds have <30 days of data, show warning
- **No solution**: If R² < 0.3, show "Low correlation - poor match"
- **Invalid symbol**: Show "Symbol not found"

## Acceptance Criteria
1. ✓ Accepts any valid Yahoo Finance ticker
2. ✓ Returns valid weights for MSTR, STRC, STRD, STRF, STRK, BTC
3. ✓ Timeline dropdown changes data lookback period
4. ✓ BTC appreciation input affects projected return calculation
5. ✓ Shows dividend yield for the mix
6. ✓ Works with new user-preferred dark theme
7. ✓ Handles errors gracefully (invalid symbols, no data)
