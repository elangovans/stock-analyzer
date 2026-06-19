import csv
import json
from decimal import Decimal, InvalidOperation
from typing import List

from .models import PortfolioItem


class ValidationError(Exception):
    pass


def _parse_decimal(value, field: str, ticker: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValidationError(f"Invalid number for {field} on {ticker}: {value}")
    return d


def _build_item(raw: dict) -> PortfolioItem:
    ticker = str(raw.get("ticker", "")).strip().upper()
    if not ticker:
        raise ValidationError("Ticker is required")

    item_type = str(raw.get("type", "")).strip().upper()
    if item_type not in ("ETF", "MF", "STOCK", "CASH"):
        raise ValidationError(f"Invalid type '{item_type}' for {ticker}. Must be ETF, MF, or STOCK or CASH" )

    quantity = _parse_decimal(raw.get("quantity"), "quantity", ticker)
    if quantity <= 0:
        raise ValidationError(f"Quantity must be > 0 for {ticker}")

    price = _parse_decimal(raw.get("current_price"), "current_price", ticker)
    if price <= 0:
        raise ValidationError(f"Price must be > 0 for {ticker}")

    # Enforce max 4 decimal places on price
    if price != round(price, 4):
        raise ValidationError(f"Price for {ticker} exceeds 4 decimal places")

    return PortfolioItem(
        ticker=ticker,
        type=item_type,
        quantity=quantity,
        current_price=price,
    )


def validate_portfolio(items: list) -> List[PortfolioItem]:
    if not items:
        raise ValidationError("Portfolio is empty")

    portfolio = [_build_item(r) for r in items]

    tickers = [p.ticker for p in portfolio]
    #if len(tickers) != len(set(tickers)):
        #dupes = [t for t in tickers if tickers.count(t) > 1]
        #raise ValidationError(f"Duplicate tickers found: {set(dupes)}")

    return portfolio


def load_from_json(path: str) -> List[PortfolioItem]:
    with open(path) as f:
        data = json.load(f)
    items = data.get("portfolio", data) if isinstance(data, dict) else data
    return validate_portfolio(items)


def load_from_csv(path: str) -> List[PortfolioItem]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return validate_portfolio(rows)


def load_portfolio(path: str) -> List[PortfolioItem]:
    if path.endswith(".json"):
        return load_from_json(path)
    elif path.endswith(".csv"):
        return load_from_csv(path)
    else:
        raise ValidationError(f"Unsupported file format: {path}. Use .csv or .json")
