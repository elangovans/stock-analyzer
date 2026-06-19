import json
import time
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import requests
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


def _write_cache(ticker: str, holdings: List[dict]) -> None:
    path = _cache_path(ticker)
    path.write_text(json.dumps({
        "ticker": ticker,
        "cached_at": datetime.now().isoformat(),
        "holdings": holdings,
    }, indent=2))


def _parse_weight(text: str) -> Optional[Decimal]:
    text = text.strip().replace("%", "").replace(",", "")
    try:
        return Decimal(text)
    except Exception:
        return None


def _scrape_stockanalysis(ticker: str) -> List[dict]:
    url = f"https://stockanalysis.com/etf/{ticker.lower()}/holdings/"
    resp = requests.get(url, headers=HEADERS, timeout=15)

    # Try mutual fund path if ETF path fails
    if resp.status_code == 404:
        url = f"https://stockanalysis.com/quote/mutf/{ticker.lower()}/holdings/"
        resp = requests.get(url, headers=HEADERS, timeout=15)

    if resp.status_code != 200:
        raise FetchError(f"stockanalysis.com returned {resp.status_code} for {ticker}")

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        raise FetchError(f"No holdings table found for {ticker} on stockanalysis.com")

    # Find column indices from header
    headers = [th.get_text(strip=True).lower() for th in table.find("thead").find_all("th")]
    try:
        sym_idx = next(i for i, h in enumerate(headers) if "symbol" in h or "ticker" in h)
        wt_idx = next(i for i, h in enumerate(headers) if "%" in h or "weight" in h)
    except StopIteration:
        raise FetchError(f"Unexpected table format for {ticker}")

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

    return holdings


def fetch_holdings(ticker: str, max_retries: int = 3) -> List[Holding]:
    cached = _read_cache(ticker)
    if cached is not None:
        return _hydrate(ticker, cached)

    last_exc: Exception = FetchError(f"No attempts made for {ticker}")
    for attempt in range(max_retries):
        try:
            raw = _scrape_stockanalysis(ticker)
            _write_cache(ticker, raw)
            return _hydrate(ticker, raw)
        except Exception as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    raise FetchError(f"Failed to fetch holdings for {ticker}: {last_exc}")


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
