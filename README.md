# Portfolio Stock Analyzer

Analyze your investment portfolio to see your **true exposure to individual stocks** across all ETFs, mutual funds, and direct holdings — in one ranked report.

If you hold VOO, QQQ, and NVDA directly, this tool tells you exactly how much NVDA exposure you actually have (and from which funds), sorted by dollar value.

---

## How It Works

```
Portfolio CSV/JSON
       │
       ▼
Fetch top-25 holdings per ETF/MF   ← stockanalysis.com (cached 24hr)
       │
       ▼
Calculate exposure per stock        ← position_value × weight%
       │
       ▼
Aggregate by ticker                 ← merge fund + direct holdings
       │
       ▼
output/report.json + report.html
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
ticker,type,quantity,current_price
VOO,ETF,200,686.19
QQQ,ETF,200,739.36
SCHD,ETF,2000,31.93
NVDA,STOCK,50,125.45
```

**JSON format** (`portfolio.json`):
```json
{
  "portfolio": [
    {"ticker": "VOO", "type": "ETF", "quantity": 200, "current_price": 686.19},
    {"ticker": "QQQ", "type": "ETF", "quantity": 200, "current_price": 739.36},
    {"ticker": "SCHD", "type": "ETF", "quantity": 2000, "current_price": 31.93},
    {"ticker": "NVDA", "type": "STOCK", "quantity": 50, "current_price": 125.45}
  ]
}
```

### 3. Run the analyzer

```bash
python3 -m src.main portfolio.json
# or
python3 -m src.main portfolio.csv
```

### 4. View reports

Reports are written to the `output/` folder:
- `output/report.json` — structured data for programmatic use
- `output/report.html` — visual table, open in any browser

---

## Sample Output

**Terminal:**
```
Portfolio Analyzer
==================================================

[1/4] Loading portfolio from portfolio.json
      4 positions loaded — total $355,242.50

[2/4] Fetching ETF/MF holdings
  Fetching holdings for VOO... OK (25 holdings)
  Fetching holdings for QQQ... OK (25 holdings)
  Fetching holdings for SCHD... OK (25 holdings)

[3/4] Calculating stock exposures
      57 unique stocks tracked

[4/4] Writing reports
      output/report.json
      output/report.html

==================================================
Top 10 exposures:
    1. NVDA   $ 29,093.00   8.19%  ################
    2. AAPL   $ 19,909.08   5.60%  ###########
    3. MSFT   $ 13,649.12   3.84%  #######
    4. AMZN   $ 11,723.34   3.30%  ######
    5. MU     $ 10,556.86   2.97%  #####
    6. GOOGL  $  9,678.95   2.72%  #####
    7. AVGO   $  9,043.20   2.55%  #####
    8. GOOG   $  8,406.69   2.37%  ####
    9. AMD    $  7,433.87   2.09%  ####
   10. TSLA   $  7,267.62   2.05%  ####

  Coverage: $236,264.53 / $355,242.50 (66.5%)
```

**HTML Report:**

The `output/report.html` file renders a dashboard with summary cards and a full ranked table. Each stock row shows which fund(s) contribute to it and the weight:

| # | Stock | Total Exposure | % Portfolio | Sources |
|---|-------|---------------|-------------|---------|
| 1 | NVDA | $29,093.00 | 8.19% | VOO: $10,840.70 (7.89%) \| QQQ: $12,066.42 (8.16%) \| Direct: $6,272.50 |
| 2 | AAPL | $19,909.08 | 5.60% | VOO: $9,097.49 (6.63%) \| QQQ: $10,756.86 (7.28%) |

---

## Portfolio Input Reference

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `ticker` | string | Yes | Stock/ETF/MF symbol (case-insensitive) |
| `type` | string | Yes | `ETF`, `MF`, or `STOCK` |
| `quantity` | number | Yes | Number of shares/units, must be > 0 |
| `current_price` | number | Yes | Current price per share, must be > 0, max 4 decimal places |

**Validation rules:**
- No duplicate tickers
- `STOCK` type holdings are treated as direct holdings (no fund lookup)
- `ETF` and `MF` types trigger a holdings fetch from stockanalysis.com

---

## Data Source & Caching

Holdings data is fetched from **[stockanalysis.com](https://stockanalysis.com)** (free, no API key required). The top 25 holdings by weight are used per fund.

Fetched holdings are cached locally in the `cache/` folder for **24 hours** to avoid repeated network requests. To force a refresh, delete the relevant file from `cache/` (e.g., `cache/VOO.json`).

> **Coverage note:** Top-25 holdings typically cover 60–80% of an ETF's total value. The HTML report shows a "Coverage" metric so you know what percentage of your portfolio is tracked.

---

## Project Structure

```
stock-analyzer/
├── src/
│   ├── models.py       # Core dataclasses (PortfolioItem, StockExposure, etc.)
│   ├── validator.py    # Input loading and validation (CSV + JSON)
│   ├── fetcher.py      # stockanalysis.com scraper + 24hr file cache
│   ├── calculator.py   # Decimal-precision exposure calculation engine
│   ├── reporter.py     # JSON and HTML report generation
│   └── main.py         # CLI entry point
├── tests/
│   ├── test_calculator.py   # 12 unit tests for calculation logic
│   └── test_validator.py    # 13 unit tests for input validation
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
25 passed in 0.02s
```

Tests cover:
- Position value calculation with Decimal precision
- Stock exposure aggregation across multiple funds
- Direct stock + fund holding merging
- Sort order (descending by exposure value)
- Input validation (type, quantity, price, duplicates, decimal places)
- CSV and JSON loading

---

## Requirements

- Python 3.10+
- `requests` — HTTP client for scraping
- `beautifulsoup4` + `lxml` — HTML parsing
- `pytest` — test runner

No API keys or paid subscriptions required.

---

## Limitations

- **Coverage is partial:** Only the top 25 holdings per ETF/MF are fetched. Holdings outside the top 25 are not counted. The report shows your actual coverage percentage.
- **Prices are user-supplied:** The tool does not fetch live prices. You provide `current_price` in your portfolio file.
- **Holdings data lag:** stockanalysis.com reflects the fund's most recently published holdings, which may be 1–30 days behind depending on the fund provider's disclosure schedule.
- **No mutual fund support on some tickers:** stockanalysis.com may not carry all mutual funds. A warning is printed for any ticker that fails to fetch.
