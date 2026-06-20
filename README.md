# Portfolio Stock Analyzer

Analyze your investment portfolio to see your **true exposure to individual stocks** across all ETFs, mutual funds, and direct holdings — in one ranked report.

If you hold VOO, QQQ, and NVDA directly, this tool tells you exactly how much NVDA exposure you actually have (and from which funds), sorted by dollar value.

---

## How It Works

```
Portfolio CSV/JSON  (ticker, type, quantity only)
       │
       ▼
Fetch live prices via yfinance          ← step 2
       │
       ▼
Fetch top-25 holdings per ETF/MF        ← stockanalysis.com → morningstar.com fallback (cached 24hr)
       │
       ▼
Calculate exposure per stock            ← position_value × weight%
       │
       ▼
Aggregate by ticker                     ← merge fund + direct holdings
       │
       ▼
output/{name}_{timestamp}.json + .html
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create your portfolio file

**CSV format** (`portfolio.csv`):
```csv
ticker,type,quantity
VOO,ETF,200
QQQ,ETF,200
SCHD,ETF,2000
NVDA,STOCK,50
FXAIX,MF,200
```

**JSON format** (`portfolio.json`):
```json
{
  "portfolio": [
    {"ticker": "VOO",   "type": "ETF",   "quantity": 200},
    {"ticker": "QQQ",   "type": "ETF",   "quantity": 200},
    {"ticker": "SCHD",  "type": "ETF",   "quantity": 2000},
    {"ticker": "NVDA",  "type": "STOCK", "quantity": 50},
    {"ticker": "FXAIX", "type": "MF",    "quantity": 200}
  ]
}
```

> Prices are fetched automatically — no need to supply them.

### 3. Run the analyzer

```bash
python3 -m src.main portfolio.json
# or
python3 -m src.main portfolio.csv
```

### 4. View reports

Reports are written to the `output/` folder with the input filename and a timestamp:
- `output/portfolio_20260620_112452.json` — structured data for programmatic use
- `output/portfolio_20260620_112452.html` — visual dashboard, open in any browser

---

## Sample Output

**Terminal:**
```
Portfolio Analyzer
==================================================

[1/5] Loading portfolio from portfolio.json
      7 positions loaded

[2/5] Fetching current prices
  VOO... $688.11
  QQQ... $740.62
  SCHD... $31.86
  NVDA... $210.69
  FXAIX... $261.21
  SMH... $659.88
  VTSNX... $186.39
      Portfolio total: $581,496.50

[3/5] Fetching ETF/MF holdings
  VOO... [stockanalysis.com] OK (25 holdings)
  QQQ... [stockanalysis.com] OK (25 holdings)
  SCHD... [stockanalysis.com] OK (25 holdings)
  FXAIX... [stockanalysis.com] OK (25 holdings)

[4/5] Calculating stock exposures
      95 unique stocks tracked

[5/5] Writing reports
      output/portfolio_20260620_112452.json
      output/portfolio_20260620_112452.html

==================================================
Top 10 exposures:
   1. NVDA   $ 55,719.42   9.58%  ###################
   2. AAPL   $ 23,323.19   4.01%  ########
   3. MU     $ 21,956.46   3.78%  #######
   4. AVGO   $ 18,680.21   3.21%  ######
   5. AMD    $ 17,428.62   3.00%  ######
   6. MSFT   $ 16,239.96   2.79%  #####
   7. INTC   $ 15,967.80   2.75%  #####
   8. AMZN   $ 13,938.35   2.40%  ####
   9. TSM    $ 12,418.94   2.14%  ####
  10. GOOGL  $ 11,596.94   1.99%  ###

  Coverage: $407,239.70 / $581,496.50 (70.0%)
```

**HTML Report:**

The `output/*.html` file renders a dashboard with:
- Summary cards (portfolio total, tracked exposure, coverage %, unique stocks)
- Interactive donut pie chart — top 10 stocks get individual wedges, everything else buckets into "All Other"; hover to highlight
- Full ranked table showing each stock's total exposure, % of portfolio, and per-fund breakdown

| # | Stock | Total Exposure | % Portfolio | Sources |
|---|-------|---------------|-------------|---------|
| 1 | NVDA | $55,719.42 | 9.58% | VOO: $10,840.70 (7.89%) \| QQQ: $12,066.42 (8.16%) \| Direct: $10,534.50 |
| 2 | AAPL | $23,323.19 | 4.01% | VOO: $9,097.49 (6.63%) \| QQQ: $10,756.86 (7.28%) |

---

## Portfolio Input Reference

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `ticker` | string | Yes | Symbol (case-insensitive, normalized to uppercase) |
| `type` | string | Yes | `ETF`, `MF`, `STOCK`, or `CASH` |
| `quantity` | number | Yes | Number of shares/units, must be > 0 |

**Type behaviour:**
- `STOCK` — treated as a direct holding; no fund lookup, price fetched via yfinance
- `ETF` / `MF` — holdings fetched from stockanalysis.com (Morningstar fallback); price fetched via yfinance
- `CASH` — included in portfolio total; no holdings lookup

---

## Data Sources

| Data | Primary | Fallback |
|------|---------|----------|
| Live prices | yfinance | — |
| ETF/MF holdings | stockanalysis.com | morningstar.com |

- **yfinance** — free, no API key, covers all US-listed stocks, ETFs, and mutual funds
- **stockanalysis.com** — free, no auth required, top-25 holdings by weight per fund
- **morningstar.com** — automatic fallback if stockanalysis.com is unreachable or returns no data
- The terminal output shows `[stockanalysis.com]` or `[morningstar.com]` so you can see which source was used

**Caching:** holdings data is cached in `cache/` for **24 hours**. To force a refresh for a specific fund, delete `cache/TICKER.json`.

---

## Project Structure

```
stock-analyzer/
├── src/
│   ├── models.py       # Core dataclasses (PortfolioItem, StockExposure, etc.)
│   ├── validator.py    # Input loading and validation (CSV + JSON)
│   ├── fetcher.py      # Price fetch (yfinance) + holdings scraper + cache
│   ├── calculator.py   # Decimal-precision exposure calculation engine
│   ├── reporter.py     # JSON and HTML report generation (incl. pie chart)
│   └── main.py         # CLI entry point
├── tests/
│   ├── test_calculator.py   # 12 unit tests for calculation logic
│   └── test_validator.py    # 14 unit tests for input validation
├── output/             # Generated reports (git-ignored)
├── cache/              # Holdings cache files (git-ignored)
├── portfolio.json      # Sample portfolio (JSON)
├── portfolio.csv       # Sample portfolio (CSV)
└── requirements.txt
```

---

## Running Tests

```bash
python3 -m pytest tests/ -v
```

```
26 passed in 0.02s
```

Tests cover:
- Position value calculation with Decimal precision
- Stock exposure aggregation across multiple funds
- Direct stock + fund holding merging
- Sort order (descending by exposure value)
- Input validation (type, quantity, duplicates)
- `current_price` defaults to zero until price fetch runs
- CSV and JSON loading

---

## Requirements

- Python 3.10+
- `requests` — HTTP client for scraping
- `beautifulsoup4` + `lxml` — HTML parsing
- `yfinance` — live price fetching
- `pytest` — test runner

No API keys or paid subscriptions required.

---

## Limitations

- **Coverage is partial:** Only the top 25 holdings per ETF/MF are fetched. Holdings outside the top 25 are not counted. The report shows your actual coverage percentage (typically 60–80% for broad-market ETFs).
- **Holdings data lag:** Published holdings may be 1–30 days behind the actual fund composition, depending on the fund provider's disclosure schedule.
- **Price fetch failures:** If yfinance cannot retrieve a price for a ticker, that position is skipped with a warning and excluded from the analysis.
- **Morningstar scraping:** Morningstar's page structure can change; if the fallback fails, a warning is printed and the fund is excluded from exposure calculations.
