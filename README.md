# Portfolio Stock Analyzer

Analyze your investment portfolio to see your **true exposure to individual stocks** across all ETFs, mutual funds, and direct holdings — in one ranked report.

If you hold VOO, QQQ, and NVDA directly, this tool tells you exactly how much NVDA exposure you actually have (and from which funds), sorted by dollar value.

---

## Installation

### For users (no Python required)

Download the zip for your platform from the [Releases page](../../releases/latest), unzip it, and follow the setup steps below.

| Platform | File to download |
|----------|-----------------|
| macOS (Apple Silicon) | `stock-analyzer-*-macos-arm64.zip` |
| macOS (Intel) | `stock-analyzer-*-macos-x86_64.zip` |
| Windows | `stock-analyzer-*-windows.zip` |

**macOS setup (one time only):**

```bash
# 1. Unzip and enter the folder
unzip stock-analyzer-*-macos-arm64.zip
cd stock-analyzer-*-macos-arm64

# 2. Remove the quarantine flag (macOS blocks unsigned binaries by default)
xattr -dr com.apple.quarantine stock-analyzer

# Alternatively: right-click the file → Open → click "Open" in the dialog.
```

**Windows setup:**

```
1. Unzip stock-analyzer-*-windows.zip
2. Open the folder
```

Double-click `stock-analyzer.exe` or run it from Command Prompt. Windows Defender may show a SmartScreen warning on first run — click **"More info" → "Run anyway"**.

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

### 2. Edit your portfolio file

Replace the contents of `portfolio.csv` (or `portfolio.json`) with your own holdings.

### 3. (Optional) Enable News Briefs

The **News Briefs** tab is powered by Claude AI and requires an Anthropic API key. It is completely optional — the rest of the report works without it.

**Option A — drop a `.env` file next to the binary:**
```bash
cp .env.example .env
# open .env and replace the placeholder with your key
```

```
# .env
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Option B — set a shell environment variable (applies to all terminals):**
```bash
# Add to ~/.zshrc or ~/.bash_profile
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Get your API key at [console.anthropic.com](https://console.anthropic.com). Without a key the News Briefs tab simply doesn't appear — no errors.

### 4. Run the analyzer

**macOS:**
```bash
./stock-analyzer portfolio.csv
```

**Windows:**
```
stock-analyzer-windows.exe portfolio.csv
```

### 5. View your reports

Reports are saved to an `output/` folder created next to where you run the tool:

- `output/portfolio_20260620_112452.html` — open in any browser (dashboard + charts)
- `output/portfolio_20260620_112452.json` — raw data

---

## Sample Output

**Terminal (with News Briefs enabled):**
```
Portfolio Analyzer
==================================================

[1/8] Loading portfolio from portfolio.json
      7 positions loaded

[2/8] Fetching current prices (batch)
  VOO      $688.11
  QQQ      $740.62
  SCHD     $31.86
  NVDA     $210.69
  FXAIX    $261.21
  SMH      $659.88
  VTSNX    $186.39
      Portfolio total: $581,496.50

[3/8] Fetching ETF/MF holdings
  VOO... [stockanalysis.com] OK (25 holdings)
  QQQ... [stockanalysis.com] OK (25 holdings)
  SCHD... [stockanalysis.com] OK (25 holdings)
  FXAIX... [stockanalysis.com] OK (25 holdings)

[4/8] Calculating stock exposures
      95 unique stocks tracked

[5/8] Fetching sectors (batch)
      9 sectors identified

[6/8] Fetching earnings dates
      2 stock(s) reporting in next 10 days

[7/8] Fetching & classifying news (Claude AI)
      Fetching headlines for 1 ticker(s):
      NVDA... 8 article(s)
      Classifying 8 article(s) in 1 batch(es) via Claude...
      Batch 1/1... done
      3 notable/high-stake item(s) found

[8/8] Writing reports
      output/portfolio_20260620_112452.json
      output/portfolio_20260620_112452.html

==================================================
Top 10 exposures:
   1. NVDA   $ 55,719.42   9.58%  ###################
   2. AAPL   $ 23,323.19   4.01%  ########
   ...

  Coverage: $407,239.70 / $581,496.50 (70.0%)
```

**HTML Report — three tabs:**

| Tab | Contents |
|-----|----------|
| **Stock Exposure** | Full ranked table with sortable columns — stock, sector, total exposure, % of portfolio, earnings date (highlighted if ≤10 days), per-fund breakdown |
| **Earnings Calendar** | Stocks reporting in the next 10 days; rows color-coded by urgency; DIRECT vs VIA FUND badge |
| **📰 News Briefs** | AI-classified news grouped by category (Leadership, M&A, Regulatory, Financial, Legal, Product); 1–5 star criticality rating; noise filtered out. Tab only appears if `ANTHROPIC_API_KEY` is configured. |

Charts on every run (no API key needed):
- **Stock exposure donut** — top 25 stocks, hover to highlight
- **Sector breakdown donut** — exposure aggregated by sector

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
       │                                    cached 24hr in cache/
       ▼
Calculate stock exposure per holding     ← position_value × weight%
       │
       ▼
Aggregate by ticker                      ← merge fund exposures + direct holdings
       │
       ▼
Batch-fetch sector for each stock        ← yfinance, cached 7 days
       │
       ▼
Fetch next earnings date per stock       ← yfinance, cached 24hr
       │
       ▼
Fetch & classify news (optional)         ← yfinance headlines → Claude AI batch call
       │                                    cached 6hr in cache/
       ▼
output/{name}_{timestamp}.json + .html
```

---

## Data Sources

| Data | Source | Cache | Requires |
|------|--------|-------|----------|
| Live prices | yfinance | none (always live) | — |
| ETF/MF holdings | stockanalysis.com → morningstar.com | 24 hours | — |
| Stock sectors | yfinance | 7 days | — |
| Earnings dates | yfinance | 24 hours | — |
| News headlines | yfinance | 6 hours | — |
| News classification & summaries | Claude AI (Haiku) | 6 hours (shared with headlines) | `ANTHROPIC_API_KEY` |

Core features require no API keys. News Briefs requires an Anthropic subscription.

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
│   ├── fetcher.py        # Prices, holdings scraper, sectors, earnings, cache
│   ├── calculator.py     # Decimal-precision exposure calculation
│   ├── news.py           # News fetch + Claude AI classification (optional)
│   ├── reporter.py       # JSON + HTML report with charts and tabs
│   └── main.py           # CLI entry point
├── tests/
│   ├── test_calculator.py
│   └── test_validator.py
├── .github/workflows/
│   └── release.yml       # Automated Mac + Windows builds on git tag
├── stock-analyzer.spec   # PyInstaller build config
├── run.py                # PyInstaller entry point
├── pyproject.toml        # Package metadata
├── .env.example          # API key template — copy to .env to enable News Briefs
├── portfolio.csv         # Sample portfolio
└── portfolio.json        # Sample portfolio
```

---

## Limitations

- **Coverage is partial:** Top-25 holdings per ETF/MF typically cover 60–80% of the fund. The report shows your exact coverage percentage.
- **Holdings data lag:** Published holdings may be 1–30 days behind actual fund composition depending on the provider's disclosure schedule.
- **Non-US tickers:** Some foreign-listed stocks (e.g. UMG on Euronext) have no yfinance data and will show sector as "Unknown".
- **Morningstar fallback:** If Morningstar's page structure changes, the fallback may stop working. A warning is printed and the fund is excluded.
- **Earnings dates:** Only available for individual stocks — ETFs and mutual funds have no earnings date.
- **News Briefs scope:** News is fetched for direct STOCK holdings only (not ETF sub-holdings). Claude classifies and filters noise; accuracy depends on headline quality from Yahoo Finance.
- **News Briefs cost:** Each run that is not cached makes one Claude API call (Haiku tier). Results are cached for 6 hours to minimise cost.
