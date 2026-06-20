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
        raise ValidationError(f"Invalid type '{item_type}' for {ticker}. Must be ETF, MF, STOCK, or CASH")

    quantity = _parse_decimal(raw.get("quantity"), "quantity", ticker)
    if quantity <= 0:
        raise ValidationError(f"Quantity must be > 0 for {ticker}")

    return PortfolioItem(
        ticker=ticker,
        type=item_type,
        quantity=quantity,
    )


def validate_portfolio(items: list) -> List[PortfolioItem]:
    if not items:
        raise ValidationError("Portfolio is empty")
    return [_build_item(r) for r in items]


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
