import json
import tempfile
import os
from decimal import Decimal

import pytest

from src.validator import ValidationError, load_from_csv, load_from_json, validate_portfolio


VALID_ROWS = [
    {"ticker": "VOO", "type": "ETF", "quantity": "200"},
    {"ticker": "NVDA", "type": "STOCK", "quantity": "50"},
]


class TestValidatePortfolio:
    def test_valid_input(self):
        items = validate_portfolio(VALID_ROWS)
        assert len(items) == 2
        assert items[0].ticker == "VOO"
        assert items[0].quantity == Decimal("200")

    def test_empty_portfolio(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_portfolio([])

    def test_missing_ticker(self):
        with pytest.raises(ValidationError, match="Ticker is required"):
            validate_portfolio([{"ticker": "", "type": "ETF", "quantity": "100"}])

    def test_invalid_type(self):
        with pytest.raises(ValidationError, match="Invalid type"):
            validate_portfolio([{"ticker": "FOO", "type": "BOND", "quantity": "100"}])

    def test_zero_quantity(self):
        with pytest.raises(ValidationError, match="Quantity must be > 0"):
            validate_portfolio([{"ticker": "VOO", "type": "ETF", "quantity": "0"}])

    def test_negative_quantity(self):
        with pytest.raises(ValidationError, match="Quantity must be > 0"):
            validate_portfolio([{"ticker": "VOO", "type": "ETF", "quantity": "-10"}])

    def test_duplicate_tickers_allowed(self):
        rows = [
            {"ticker": "VOO", "type": "ETF", "quantity": "100"},
            {"ticker": "VOO", "type": "ETF", "quantity": "50"},
        ]
        items = validate_portfolio(rows)
        assert len(items) == 2

    def test_ticker_normalized_uppercase(self):
        items = validate_portfolio([{"ticker": "voo", "type": "etf", "quantity": "100"}])
        assert items[0].ticker == "VOO"
        assert items[0].type == "ETF"

    def test_mf_type_accepted(self):
        items = validate_portfolio([{"ticker": "VTSAX", "type": "MF", "quantity": "100"}])
        assert items[0].type == "MF"

    def test_price_defaults_to_zero(self):
        items = validate_portfolio([{"ticker": "VOO", "type": "ETF", "quantity": "100"}])
        assert items[0].current_price == Decimal("0")

    def test_cash_type_accepted(self):
        items = validate_portfolio([{"ticker": "CASH", "type": "CASH", "quantity": "1000"}])
        assert items[0].type == "CASH"


class TestLoadFromJson:
    def test_load_portfolio_key(self):
        data = {"portfolio": VALID_ROWS}
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(data, f)
            f.flush()
            items = load_from_json(f.name)
        os.unlink(f.name)
        assert len(items) == 2

    def test_load_flat_list(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(VALID_ROWS, f)
            f.flush()
            items = load_from_json(f.name)
        os.unlink(f.name)
        assert len(items) == 2


class TestLoadFromCsv:
    def test_load_csv(self):
        content = "ticker,type,quantity\nVOO,ETF,200\nNVDA,STOCK,50\n"
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
            f.write(content)
            f.flush()
            items = load_from_csv(f.name)
        os.unlink(f.name)
        assert len(items) == 2
        assert items[0].ticker == "VOO"
