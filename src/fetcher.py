import json
import time
import re
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import requests
import yfinance as yf
from bs4 import BeautifulSoup

from .models import Holding

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_TTL_HOURS = 24
TOP_N_HOLDINGS = 25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class FetchError(Exception):
    pass


# ── Price fetch ───────────────────────────────────────────────────────────────

def fetch_price(ticker: str) -> Decimal:
    """Fetch current market price via yfinance."""
    data = yf.Ticker(ticker)
    info = data.fast_info
    price = getattr(info, "last_price", None) or getattr(info, "regular_market_price", None)
    if not price:
        raise FetchError(f"Could not retrieve price for {ticker}")
    return Decimal(str(round(price, 4)))


# ── Cache ──────────────────────────────────────────────────────────────────────

def _cache_path(ticker: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{ticker.upper()}.json"


def _read_cache(ticker: str) -> Optional[List[dict]]:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    cached_at = datetime.fromisoformat(data["cached_at"])
    if datetime.now() - cached_at > timedelta(hours=CACHE_TTL_HOURS):
        return None
    return data["holdings"]


def _write_cache(ticker: str, holdings: List[dict], source: str) -> None:
    path = _cache_path(ticker)
    path.write_text(json.dumps({
        "ticker": ticker,
        "source": source,
        "cached_at": datetime.now().isoformat(),
        "holdings": holdings,
    }, indent=2))


def _parse_weight(text: str) -> Optional[Decimal]:
    text = text.strip().replace("%", "").replace(",", "")
    try:
        return Decimal(text)
    except Exception:
        return None


# ── Source 1: stockanalysis.com ───────────────────────────────────────────────

def _scrape_stockanalysis(ticker: str) -> List[dict]:
    url = f"https://stockanalysis.com/etf/{ticker.lower()}/holdings/"
    resp = requests.get(url, headers=HEADERS, timeout=15)

    if resp.status_code == 404:
        url = f"https://stockanalysis.com/quote/mutf/{ticker.lower()}/holdings/"
        resp = requests.get(url, headers=HEADERS, timeout=15)

    if resp.status_code != 200:
        raise FetchError(f"stockanalysis.com returned HTTP {resp.status_code} for {ticker}")

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        raise FetchError(f"stockanalysis.com: no holdings table found for {ticker}")

    headers = [th.get_text(strip=True).lower() for th in table.find("thead").find_all("th")]
    try:
        sym_idx = next(i for i, h in enumerate(headers) if "symbol" in h or "ticker" in h)
        wt_idx = next(i for i, h in enumerate(headers) if "%" in h or "weight" in h)
    except StopIteration:
        raise FetchError(f"stockanalysis.com: unexpected table format for {ticker}")

    holdings = []
    for row in table.find("tbody").find_all("tr"):
        cells = row.find_all("td")
        if len(cells) <= max(sym_idx, wt_idx):
            continue
        symbol = cells[sym_idx].get_text(strip=True).upper()
        weight = _parse_weight(cells[wt_idx].get_text(strip=True))
        if symbol and weight is not None and weight > 0:
            holdings.append({"ticker": symbol, "weight": str(weight)})
        if len(holdings) >= TOP_N_HOLDINGS:
            break

    if not holdings:
        raise FetchError(f"stockanalysis.com: parsed 0 holdings for {ticker}")

    return holdings


# ── Source 2: Morningstar.com (fallback) ──────────────────────────────────────

def _scrape_morningstar(ticker: str) -> List[dict]:
    # Morningstar search to resolve ticker → secId
    search_url = (
        f"https://www.morningstar.com/api/v2/search/securities"
        f"?q={ticker}&limit=1&autocomplete=true"
    )
    search_resp = requests.get(search_url, headers=HEADERS, timeout=15)
    if search_resp.status_code != 200:
        raise FetchError(f"Morningstar search returned HTTP {search_resp.status_code} for {ticker}")

    results = search_resp.json().get("results", [])
    if not results:
        raise FetchError(f"Morningstar: ticker {ticker} not found in search")

    sec_id = results[0].get("secId", "")
    if not sec_id:
        raise FetchError(f"Morningstar: no secId for {ticker}")

    holdings_url = (
        f"https://www.morningstar.com/funds/xnas/{ticker.lower()}/portfolio"
    )
    resp = requests.get(holdings_url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        raise FetchError(f"Morningstar portfolio page returned HTTP {resp.status_code} for {ticker}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Morningstar embeds portfolio data as JSON in a script tag
    script = soup.find("script", string=re.compile(r'"holdingList"'))
    if script:
        raw_json = re.search(r'\{.*"holdingList".*\}', script.string, re.DOTALL)
        if raw_json:
            data = json.loads(raw_json.group())
            holding_list = data.get("holdingList", [])
            holdings = []
            for h in holding_list:
                symbol = (h.get("ticker") or h.get("symbol") or "").upper()
                weight = _parse_weight(str(h.get("weighting", "") or h.get("weight", "")))
                if symbol and weight is not None and weight > 0:
                    holdings.append({"ticker": symbol, "weight": str(weight)})
                if len(holdings) >= TOP_N_HOLDINGS:
                    break
            if holdings:
                return holdings

    # Fallback: parse the holdings table from the page HTML
    table = soup.find("table", {"data-test": re.compile(r"holding", re.I)}) or soup.find("table")
    if not table:
        raise FetchError(f"Morningstar: no holdings table found for {ticker}")

    headers_row = table.find("thead")
    if not headers_row:
        raise FetchError(f"Morningstar: table has no header for {ticker}")

    col_headers = [th.get_text(strip=True).lower() for th in headers_row.find_all("th")]
    try:
        sym_idx = next(i for i, h in enumerate(col_headers) if "ticker" in h or "symbol" in h)
        wt_idx = next(i for i, h in enumerate(col_headers) if "weight" in h or "%" in h)
    except StopIteration:
        raise FetchError(f"Morningstar: unexpected table columns for {ticker}: {col_headers}")

    holdings = []
    for row in table.find("tbody").find_all("tr"):
        cells = row.find_all("td")
        if len(cells) <= max(sym_idx, wt_idx):
            continue
        symbol = cells[sym_idx].get_text(strip=True).upper()
        weight = _parse_weight(cells[wt_idx].get_text(strip=True))
        if symbol and weight is not None and weight > 0:
            holdings.append({"ticker": symbol, "weight": str(weight)})
        if len(holdings) >= TOP_N_HOLDINGS:
            break

    if not holdings:
        raise FetchError(f"Morningstar: parsed 0 holdings for {ticker}")

    return holdings


# ── Public fetch with fallback chain ──────────────────────────────────────────

_SOURCES = [
    ("stockanalysis.com", _scrape_stockanalysis),
    ("morningstar.com", _scrape_morningstar),
]


def fetch_holdings(ticker: str, max_retries: int = 3) -> List[Holding]:
    cached = _read_cache(ticker)
    if cached is not None:
        return _hydrate(ticker, cached)

    last_exc: Exception = FetchError(f"No sources attempted for {ticker}")

    for source_name, scrape_fn in _SOURCES:
        for attempt in range(max_retries):
            try:
                raw = scrape_fn(ticker)
                _write_cache(ticker, raw, source_name)
                print(f"[{source_name}]", end=" ", flush=True)
                return _hydrate(ticker, raw)
            except Exception as e:
                last_exc = e
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    # Source exhausted — try next source without retrying
                    break

    raise FetchError(f"All sources failed for {ticker}: {last_exc}")


def _hydrate(etf_ticker: str, raw: List[dict]) -> List[Holding]:
    now = datetime.now()
    return [
        Holding(
            stock_ticker=h["ticker"],
            etf_ticker=etf_ticker.upper(),
            weight_percent=Decimal(h["weight"]),
            data_source="stockanalysis.com",
            last_updated=now,
        )
        for h in raw
    ]
