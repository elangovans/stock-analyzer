# Portfolio Stock Analyzer - Technical Specification

## 1. SYSTEM OVERVIEW

### Purpose
Analyze investment portfolio to identify individual stock exposure across all holdings (ETFs, Mutual Funds, Direct Stocks).

### Key Feature: ZERO-ERROR CALCULATIONS
- All calculations use decimal precision (no floating-point rounding)
- Unit tests validate every calculation
- Reconciliation checks ensure input totals match output totals

---

## 2. INPUT SPECIFICATION

### Portfolio Input Format (CSV or JSON)

**CSV Format:**
```
ticker,type,quantity,current_price
VOO,ETF,200,686.19
QQQ,ETF,200,739.36
SCHD,ETF,2000,31.93
NVDA,STOCK,50,125.45
```

**JSON Format:**
```json
{
  "portfolio": [
    {
      "ticker": "VOO",
      "type": "ETF",
      "quantity": 200,
      "current_price": 686.19
    },
    {
      "ticker": "QQQ",
      "type": "ETF",
      "quantity": 200,
      "current_price": 739.36
    }
  ]
}
```

### Input Validation Rules
```
✓ ticker: non-empty string, uppercase
✓ type: "ETF" | "MF" | "STOCK"
✓ quantity: positive number > 0
✓ current_price: positive number > 0
✓ No duplicate tickers
✓ Price precision: max 4 decimal places
```

---

## 3. DATA FLOW ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│  INPUT: Portfolio (Ticker, Type, Qty, Price)                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Fetch Holdings Data                                │
│  - For each ETF/MF: Query holdings API                      │
│  - Store: holding_ticker, weight%, holding_price            │
│  - Cache results (TTL: 24 hours)                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Calculate Position Values                          │
│  - For each portfolio item:                                 │
│    position_value = quantity × current_price                │
│  - Create position tracking table                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Calculate Individual Stock Exposure                │
│  - For each stock across all holdings:                      │
│    stock_value = position_value × (holding_weight / 100)    │
│  - Aggregate by stock ticker                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Validation & Reconciliation                        │
│  - Sum of all individual stocks = portfolio total           │
│  - Check for calculation errors                             │
│  - Flag warnings if present                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  OUTPUT: Stock Exposure Report                              │
│  - Sorted by exposure value (descending)                    │
│  - Include fund/ETF sources for each stock                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. CORE DATA STRUCTURES

### PortfolioItem
```python
@dataclass
class PortfolioItem:
    ticker: str
    type: Literal["ETF", "MF", "STOCK"]
    quantity: Decimal
    current_price: Decimal
    position_value: Decimal  # calculated: qty × price
```

### Holding
```python
@dataclass
class Holding:
    stock_ticker: str
    etf_ticker: str
    weight_percent: Decimal  # 0-100
    holding_price: Decimal
    data_source: str  # "yahoo_finance", "fund_api", etc.
    last_updated: datetime
```

### StockExposure
```python
@dataclass
class StockExposure:
    stock_ticker: str
    total_exposure_value: Decimal
    percent_of_portfolio: Decimal
    sources: List[ExposureSource]
    
@dataclass
class ExposureSource:
    fund_ticker: str
    fund_type: str  # "ETF", "MF"
    fund_position_value: Decimal
    stock_weight_in_fund: Decimal
    stock_exposure_from_fund: Decimal
```

### PortfolioAnalysis
```python
@dataclass
class PortfolioAnalysis:
    portfolio_total_value: Decimal
    analysis_timestamp: datetime
    stock_exposures: List[StockExposure]
    direct_stocks: List[StockExposure]  # Direct holdings
    validation_status: ValidationResult
    warnings: List[str]
```

---

## 5. CALCULATION ENGINE (CRITICAL: ZERO ERROR)

### Algorithm: Calculate Stock Exposure

**STEP A: Calculate Position Values**
```
For each portfolio item:
    position_value = quantity × current_price
    (Use Decimal for precision)
    
Example:
    VOO: 200 × 686.19 = 137,238.00
    QQQ: 200 × 739.36 = 147,872.00
    SCHD: 2000 × 31.93 = 63,860.00
    ─────────────────────────────
    TOTAL = 348,970.00
```

**STEP B: Fetch Fund Holdings**
```
For each ETF/MF:
    holdings = fetch_holdings_data(ticker)
    
    Store as:
    {
        "NVDA": {"weight": 7.89, "price": current_nvda_price},
        "AAPL": {"weight": 6.63, "price": current_aapl_price},
        ...
    }
```

**STEP C: Calculate Stock Exposure (CRITICAL)**
```
For each stock in each fund:
    
    stock_exposure = position_value × (weight_percent / 100)
    
Example (VOO + NVDA):
    position_value = 137,238.00
    weight_in_VOO = 7.89%
    exposure = 137,238.00 × (7.89 / 100)
             = 137,238.00 × 0.0789
             = 10,840.699 (rounded to 10,840.70)

Example (QQQ + NVDA):
    position_value = 147,872.00
    weight_in_QQQ = 8.16%
    exposure = 147,872.00 × (8.16 / 100)
             = 147,872.00 × 0.0816
             = 12,066.4192 (rounded to 12,066.42)
```

**STEP D: Aggregate by Stock Ticker**
```
For NVDA:
    From VOO: 10,840.70
    From QQQ: 12,066.42
    ─────────────────────
    Total NVDA: 22,907.12

Percentage of portfolio:
    22,907.12 / 348,970.00 = 0.06564 = 6.564%
```

**STEP E: Handle Direct Stock Holdings**
```
For direct STOCK holdings:
    exposure = quantity × current_price
    (no fund weight calculation needed)
```

### Validation: Reconciliation Check
```
SUM(all individual stock exposures) == portfolio_total_value

✓ PASS: Match within 0.01 (rounding acceptable)
✗ FAIL: Mismatch > 0.01 (calculation error)
```

---

## 6. DATA SOURCES & APIs

### ETF/MF Holdings Data Sources

| Source | API | Rate Limit | Cost | Coverage |
|--------|-----|-----------|------|----------|
| Yahoo Finance | yfinance | 2000/hour | FREE | ETFs, MFs, Stocks |
| IEX Cloud | REST API | 100/sec | $0-99/mo | US Stocks, ETFs |
| Alpha Vantage | REST API | 5/min free | FREE-paid | Limited |
| Fund Provider APIs | Varies | Varies | FREE | Vanguard, Schwab, etc. |
| Finnhub | REST API | 60/min | FREE-paid | Stocks, ETFs |

### Recommended Stack: yfinance + pandas
```python
import yfinance as yf
from decimal import Decimal

# Fetch ETF holdings
etf = yf.Ticker("VOO")
holdings = etf.info  # Get basic info
# Note: yfinance has limited holdings data
# Alternative: Use fund provider's official API
```

---

## 7. ERROR HANDLING & VALIDATION

### Input Validation
```python
class ValidationError(Exception):
    """Raised when portfolio input is invalid"""
    pass

def validate_portfolio(portfolio: List[dict]) -> None:
    for item in portfolio:
        if not item.get('ticker'):
            raise ValidationError("Ticker is required")
        if item['quantity'] <= 0:
            raise ValidationError(f"Quantity must be > 0: {item['ticker']}")
        if item['current_price'] <= 0:
            raise ValidationError(f"Price must be > 0: {item['ticker']}")
        if item['type'] not in ['ETF', 'MF', 'STOCK']:
            raise ValidationError(f"Invalid type: {item['type']}")
```

### Holdings Fetch Errors
```python
class FetchError(Exception):
    """Raised when unable to fetch fund holdings"""
    pass

def fetch_holdings_with_retry(ticker: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return fetch_holdings(ticker)
        except Exception as e:
            if attempt == max_retries - 1:
                raise FetchError(f"Failed to fetch {ticker}: {str(e)}")
            time.sleep(2 ** attempt)  # exponential backoff
```

### Calculation Validation
```python
def validate_reconciliation(stock_exposures: List[StockExposure], 
                           portfolio_total: Decimal) -> ValidationResult:
    """
    Ensure sum of stock exposures = portfolio total
    """
    total_exposure = sum(s.total_exposure_value for s in stock_exposures)
    
    difference = abs(total_exposure - portfolio_total)
    
    if difference > Decimal('0.01'):
        return ValidationResult(
            is_valid=False,
            error=f"Reconciliation failed: {difference} discrepancy",
            total_exposure=total_exposure,
            portfolio_total=portfolio_total
        )
    return ValidationResult(is_valid=True)
```

---

## 8. OUTPUT SPECIFICATION

### Report Format 1: JSON (Programmatic)
```json
{
  "portfolio_summary": {
    "total_value": 348970.00,
    "analysis_date": "2026-06-19",
    "stock_count": 500,
    "etf_count": 3,
    "validation": "PASSED"
  },
  "stock_exposures": [
    {
      "rank": 1,
      "stock_ticker": "NVDA",
      "total_exposure_value": 22907.12,
      "percent_of_portfolio": 6.56,
      "sources": [
        {
          "fund_ticker": "VOO",
          "fund_type": "ETF",
          "fund_position_value": 137238.00,
          "stock_weight_in_fund": 7.89,
          "stock_exposure_from_fund": 10840.70
        },
        {
          "fund_ticker": "QQQ",
          "fund_type": "ETF",
          "fund_position_value": 147872.00,
          "stock_weight_in_fund": 8.16,
          "stock_exposure_from_fund": 12066.42
        }
      ]
    },
    {
      "rank": 2,
      "stock_ticker": "AAPL",
      "total_exposure_value": 21450.35,
      "percent_of_portfolio": 6.15,
      "sources": [
        {
          "fund_ticker": "VOO",
          "fund_type": "ETF",
          "fund_position_value": 137238.00,
          "stock_weight_in_fund": 6.63,
          "stock_exposure_from_fund": 9097.49
        },
        {
          "fund_ticker": "QQQ",
          "fund_type": "ETF",
          "fund_position_value": 147872.00,
          "stock_weight_in_fund": 7.28,
          "stock_exposure_from_fund": 10756.86
        }
      ]
    }
  ],
  "direct_holdings": [
    {
      "stock_ticker": "NVDA",
      "shares": 50,
      "exposure_value": 6272.50,
      "percent_of_portfolio": 1.80,
      "note": "Direct stock holding"
    }
  ]
}
```

### Report Format 2: HTML Table (Visual)
```html
<table>
  <thead>
    <tr>
      <th>Rank</th>
      <th>Stock</th>
      <th>Total Exposure</th>
      <th>% Portfolio</th>
      <th>Sources (Fund → Exposure)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>NVDA</td>
      <td>$22,907.12</td>
      <td>6.56%</td>
      <td>VOO: $10,840.70 | QQQ: $12,066.42</td>
    </tr>
    <tr>
      <td>2</td>
      <td>AAPL</td>
      <td>$21,450.35</td>
      <td>6.15%</td>
      <td>VOO: $9,097.49 | QQQ: $10,756.86</td>
    </tr>
  </tbody>
</table>
```

### Report Format 3: CSV (Export)
```csv
rank,stock_ticker,total_exposure_value,percent_of_portfolio,sources_json
1,NVDA,22907.12,6.56,"[{""fund"":""VOO"",""exposure"":10840.70},{""fund"":""QQQ"",""exposure"":12066.42}]"
2,AAPL,21450.35,6.15,"[{""fund"":""VOO"",""exposure"":9097.49},{""fund"":""QQQ"",""exposure"":10756.86}]"
```

---

## 9. TESTING SPECIFICATION

### Unit Test Cases

**Test 1: Position Value Calculation**
```python
def test_position_value_calculation():
    item = PortfolioItem(ticker="VOO", type="ETF", 
                         quantity=Decimal("200"), 
                         current_price=Decimal("686.19"))
    assert item.position_value == Decimal("137238.00")
```

**Test 2: Stock Exposure Calculation**
```python
def test_stock_exposure():
    position_value = Decimal("137238.00")
    weight = Decimal("7.89")
    exposure = position_value * (weight / 100)
    assert exposure == Decimal("10840.6982")  # Full precision
```

**Test 3: Reconciliation**
```python
def test_reconciliation():
    portfolio_total = Decimal("348970.00")
    exposures = [
        StockExposure(ticker="NVDA", value=Decimal("22907.12")),
        # ... more stocks
    ]
    total = sum(e.value for e in exposures)
    assert abs(total - portfolio_total) <= Decimal("0.01")
```

**Test 4: Edge Cases**
```python
def test_single_etf():
    # Portfolio with only 1 ETF
    
def test_direct_stocks_only():
    # Portfolio with no ETFs/MFs
    
def test_duplicate_stock_aggregation():
    # Same stock in multiple funds should aggregate correctly
    
def test_zero_weight_holdings():
    # Handle funds that don't hold certain stocks
```

---

## 10. TECHNOLOGY STACK RECOMMENDATIONS

### Option A: Python (Recommended for Simplicity)
```
Language: Python 3.10+
Backend: FastAPI (REST API)
Database: SQLite (local) or PostgreSQL (cloud)
Data: pandas, Decimal
API: yfinance, requests
Frontend: Streamlit (simple) or React (advanced)
Deployment: Docker + AWS Lambda / Heroku
```

### Option B: JavaScript/TypeScript (Full-Stack)
```
Frontend: React + TypeScript
Backend: Node.js + Express
Database: PostgreSQL
Libraries: decimal.js, axios
APIs: yfinance API, Finnhub
Deployment: Vercel / AWS
```

### Option C: Excel/Google Sheets (Quick & Dirty)
```
Tool: Google Apps Script or VBA
Data: Import from CSV
Formulas: Structured calculation sheets
Limitations: Limited to ~5000 stocks, slower APIs
```

---

## 11. IMPLEMENTATION PHASES

### Phase 1: MVP (Week 1-2)
- [ ] Input validation
- [ ] Manual holdings data entry (CSV)
- [ ] Calculation engine with Decimal precision
- [ ] JSON output
- [ ] Unit tests (80% coverage)

### Phase 2: API Integration (Week 3-4)
- [ ] Fetch live holdings from Yahoo Finance
- [ ] Cache management (24-hour TTL)
- [ ] Error handling for API failures
- [ ] Rate limiting

### Phase 3: UI & Export (Week 5-6)
- [ ] Web interface (Streamlit or React)
- [ ] HTML report generation
- [ ] CSV/Excel export
- [ ] Visualization (charts)

### Phase 4: Advanced (Week 7+)
- [ ] Historical analysis
- [ ] Portfolio optimization suggestions
- [ ] Tax impact analysis
- [ ] Rebalancing recommendations

---

## 12. SAMPLE TEST DATA

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

**Expected Output (Sample):**
```
NVDA: $22,907.12 (6.56%) 
  └─ VOO: $10,840.70
  └─ QQQ: $12,066.42
  └─ Direct: $6,272.50

AAPL: $21,450.35 (6.15%)
  └─ VOO: $9,097.49
  └─ QQQ: $10,756.86

... (more stocks)

RECONCILIATION: ✓ PASSED
Total Exposure: $348,970.00 = Portfolio Total
```

---

## 13. SUCCESS CRITERIA

✓ **Accuracy:** All calculations verified to 0.01 cents  
✓ **Zero Errors:** Unit test coverage > 90%  
✓ **Speed:** Analysis completes in < 10 seconds  
✓ **Validation:** 100% reconciliation checks pass  
✓ **Usability:** Single-click analysis from portfolio CSV  
✓ **Scalability:** Handles 100+ funds / 500+ unique stocks  
✓ **Reliability:** 99.9% uptime for API calls  
