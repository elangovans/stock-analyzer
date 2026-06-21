# Portfolio Stock Analyzer

Analyze your investment portfolio to see your **true exposure to individual stocks** across all ETFs, mutual funds, and direct holdings — in one ranked report.

If you hold VOO, QQQ, and NVDA directly, this tool tells you exactly how much NVDA exposure you actually have (and from which funds), sorted by dollar value.

---

## Installation

### For users (no Python required)

Download the pre-built binary for your platform from the [Releases page](../../releases/latest):

| Platform | File to download |
|----------|-----------------|
| macOS | `stock-analyzer-mac` |
| Windows | `stock-analyzer-windows.exe` |

**macOS setup (one time only):**

```bash
# 1. Make it executable
chmod +x stock-analyzer-mac

# 2. First run: macOS will block it because it's not from the App Store.
#    Right-click the file → Open → click "Open" in the dialog.
#    After that first approval it runs normally.
```

**Windows setup:**

Just double-click `stock-analyzer-windows.exe` or run it from Command Prompt. Windows Defender may show a SmartScreen warning on first run — click **"More info" → "Run anyway"**.

---

## Usage

### 1. Create your portfolio file

Create a CSV or JSON file listing your holdings. Prices are fetched automatically — you only need ticker, type, and quantity.

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

| Field | Values | Notes |
|-------|--------|-------|
| `ticker` | Any symbol | Case-insensitive. Use the same ticker as on Yahoo Finance (e.g. `BRK-B`) |
| `type` | `ETF` `MF` `STOCK` `CASH` | ETF and MF trigger a fund holdings lookup |
| `quantity` | Any number > 0 | Shares or units you hold |

### 2. Run the analyzer

**macOS:**
```bash
./stock-analyzer-mac portfolio.csv
```

**Windows:**
```
stock-analyzer-windows.exe portfolio.csv
```

### 3. View your reports

Reports are saved to an `output/` folder created next to where you run the tool:

- `output/portfolio_20260620_112452.html` — open in any browser (dashboard + charts)
- `output/portfolio_20260620_112452.json` — raw data

---

## Sample Output

**Terminal:**
```
Portfolio Analyzer
==================================================

[1/6] Loading portfolio from portfolio.json
      7 positions loaded

[2/6] Fetching current prices (batch)
  VOO      $688.11
  QQQ      $740.62
  SCHD     $31.86
  NVDA     $210.69
  FXAIX    $261.21
  SMH      $659.88
  VTSNX    $186.39
      Portfolio total: $581,496.50

[3/6] Fetching ETF/MF holdings
  VOO... [stockanalysis.com] OK (25 holdings)
  QQQ... [stockanalysis.com] OK (25 holdings)
  SCHD... [stockanalysis.com] OK (25 holdings)
  FXAIX... [stockanalysis.com] OK (25 holdings)

[4/6] Calculating stock exposures
      95 unique stocks tracked

[5/6] Fetching sectors (batch)
      9 sectors identified

[6/6] Writing reports
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

The `output/*.html` file opens in any browser and shows:
- Summary cards (portfolio total, tracked exposure, coverage %, unique stocks)
- **Stock exposure donut chart** — top 25 stocks with individual wedges, rest bucketed as "All Other (N stocks)"; hover to highlight
- **Sector breakdown donut chart** — exposure aggregated by sector side by side
- Full ranked table with stock, sector, total exposure, % of portfolio, and per-fund breakdown

---

## Troubleshooting

**macOS: "cannot be opened because the developer cannot be verified"**
Right-click the file → **Open** → click **Open** in the dialog. This only happens once.

**Windows: SmartScreen warning**
Click **"More info"** → **"Run anyway"**. This appears because the binary isn't signed with a paid certificate.

**"Could not retrieve price for TICKER"**
The ticker symbol wasn't found on Yahoo Finance. Check the symbol matches exactly — e.g. use `BRK-B` not `BRK/B`.

**"Could not fetch holdings for FUND"**
Both stockanalysis.com and Morningstar failed for that fund. The fund is excluded from exposure calculations. A warning is printed at the end of the run. Try again later or check your internet connection.

**Output folder location**
The `output/` folder is created in whichever directory you run the command from, not where the binary lives.

---

## How It Works

```
Portfolio CSV/JSON  (ticker, type, quantity only)
       │
       ▼
Batch-fetch live prices via yfinance     ← one network call for all tickers
       │
       ▼
Fetch top-25 holdings per ETF/MF         ← stockanalysis.com → morningstar.com fallback
       │                                    results cached 24hr in cache/
       ▼
Calculate stock exposure per holding     ← position_value × weight%
       │
       ▼
Aggregate by ticker                      ← merge fund exposures + direct holdings
       │
       ▼
Batch-fetch sector for each stock        ← one yfinance call, cached 7 days
       │
       ▼
output/{name}_{timestamp}.json + .html
```

---

## Data Sources

| Data | Primary | Fallback | Cache |
|------|---------|----------|-------|
| Live prices | yfinance | — | none (always live) |
| ETF/MF holdings | stockanalysis.com | morningstar.com | 24 hours |
| Stock sectors | yfinance | — | 7 days |

No API keys or paid subscriptions required.

---

## For Developers

### Running from source

Requires Python 3.10+.

```bash
git clone https://github.com/elangovans/stock-analyzer.git
cd stock-analyzer
pip install -r requirements.txt
python3 -m src.main portfolio.csv
```

### Running tests

```bash
python3 -m pytest tests/ -v
# 26 passed
```

### Building binaries locally

```bash
pip install pyinstaller
pyinstaller stock-analyzer.spec
# Output: dist/stock-analyzer  (Mac) or dist/stock-analyzer.exe  (Windows)
```

### Releasing a new version

```bash
git tag v1.0.1
git push origin v1.0.1
# GitHub Actions builds Mac + Windows binaries and publishes a Release automatically
```

### Project structure

```
stock-analyzer/
├── src/
│   ├── models.py         # Core dataclasses
│   ├── validator.py      # CSV/JSON loading and validation
│   ├── fetcher.py        # Prices, holdings scraper, sectors, cache
│   ├── calculator.py     # Decimal-precision exposure calculation
│   ├── reporter.py       # JSON + HTML report with charts
│   └── main.py           # CLI entry point
├── tests/
│   ├── test_calculator.py
│   └── test_validator.py
├── .github/workflows/
│   └── release.yml       # Automated Mac + Windows builds on git tag
├── stock-analyzer.spec   # PyInstaller build config
├── run.py                # PyInstaller entry point
├── pyproject.toml        # Package metadata
├── portfolio.csv         # Sample portfolio
└── portfolio.json        # Sample portfolio
```

---

## Limitations

- **Coverage is partial:** Top-25 holdings per ETF/MF typically cover 60–80% of the fund. The report shows your exact coverage percentage.
- **Holdings data lag:** Published holdings may be 1–30 days behind actual fund composition depending on the provider's disclosure schedule.
- **Non-US tickers:** Some foreign-listed stocks (e.g. UMG on Euronext) have no yfinance data and will show sector as "Unknown".
- **Morningstar fallback:** If Morningstar's page structure changes, the fallback may stop working. A warning is printed and the fund is excluded.
