from decimal import Decimal
from datetime import datetime

import pytest

from src.models import Holding, PortfolioItem
from src.calculator import analyze


def _holding(stock: str, etf: str, weight: str) -> Holding:
    return Holding(
        stock_ticker=stock,
        etf_ticker=etf,
        weight_percent=Decimal(weight),
        data_source="test",
        last_updated=datetime.now(),
    )


def _item(ticker: str, itype: str, qty: str, price: str) -> PortfolioItem:
    item = PortfolioItem(ticker=ticker, type=itype, quantity=Decimal(qty))
    item.current_price = Decimal(price)
    return item


class TestPositionValue:
    def test_basic(self):
        item = _item("VOO", "ETF", "200", "686.19")
        assert item.position_value == Decimal("137238.00")

    def test_decimal_precision(self):
        item = _item("QQQ", "ETF", "200", "739.36")
        assert item.position_value == Decimal("147872.00")

    def test_fractional_quantity(self):
        item = _item("SCHD", "ETF", "2000", "31.93")
        assert item.position_value == Decimal("63860.00")


class TestStockExposure:
    def test_single_fund_single_stock(self):
        portfolio = [_item("VOO", "ETF", "200", "686.19")]
        holdings_map = {
            "VOO": [_holding("NVDA", "VOO", "7.89")]
        }
        analysis = analyze(portfolio, holdings_map, [])
        nvda = next(e for e in analysis.stock_exposures if e.stock_ticker == "NVDA")
        expected = Decimal("137238.00") * Decimal("7.89") / Decimal("100")
        assert nvda.total_exposure_value == expected

    def test_same_stock_aggregated_across_funds(self):
        portfolio = [
            _item("VOO", "ETF", "200", "686.19"),
            _item("QQQ", "ETF", "200", "739.36"),
        ]
        holdings_map = {
            "VOO": [_holding("NVDA", "VOO", "7.89")],
            "QQQ": [_holding("NVDA", "QQQ", "8.16")],
        }
        analysis = analyze(portfolio, holdings_map, [])
        nvda = next(e for e in analysis.stock_exposures if e.stock_ticker == "NVDA")
        from_voo = Decimal("137238.00") * Decimal("7.89") / Decimal("100")
        from_qqq = Decimal("147872.00") * Decimal("8.16") / Decimal("100")
        assert nvda.total_exposure_value == from_voo + from_qqq
        assert len(nvda.sources) == 2

    def test_direct_stock_exposure(self):
        portfolio = [_item("NVDA", "STOCK", "50", "125.45")]
        analysis = analyze(portfolio, {}, [])
        nvda = next(e for e in analysis.stock_exposures if e.stock_ticker == "NVDA")
        assert nvda.total_exposure_value == Decimal("6272.50")
        assert nvda.is_direct is True

    def test_direct_stock_and_fund_aggregated(self):
        portfolio = [
            _item("VOO", "ETF", "200", "686.19"),
            _item("NVDA", "STOCK", "50", "125.45"),
        ]
        holdings_map = {
            "VOO": [_holding("NVDA", "VOO", "7.89")]
        }
        analysis = analyze(portfolio, holdings_map, [])
        nvda = next(e for e in analysis.stock_exposures if e.stock_ticker == "NVDA")
        from_voo = Decimal("137238.00") * Decimal("7.89") / Decimal("100")
        direct = Decimal("6272.50")
        assert nvda.total_exposure_value == from_voo + direct
        assert len(nvda.sources) == 2

    def test_sorted_by_exposure_descending(self):
        portfolio = [_item("VOO", "ETF", "200", "686.19")]
        holdings_map = {
            "VOO": [
                _holding("AAPL", "VOO", "6.63"),
                _holding("NVDA", "VOO", "7.89"),
                _holding("MSFT", "VOO", "5.00"),
            ]
        }
        analysis = analyze(portfolio, holdings_map, [])
        values = [e.total_exposure_value for e in analysis.stock_exposures]
        assert values == sorted(values, reverse=True)

    def test_percent_of_portfolio(self):
        portfolio = [_item("VOO", "ETF", "200", "686.19")]
        holdings_map = {"VOO": [_holding("NVDA", "VOO", "7.89")]}
        analysis = analyze(portfolio, holdings_map, [])
        nvda = next(e for e in analysis.stock_exposures if e.stock_ticker == "NVDA")
        expected_pct = (Decimal("7.89") * Decimal("137238.00") / Decimal("100") / Decimal("137238.00") * 100).quantize(Decimal("0.01"))
        assert nvda.percent_of_portfolio == expected_pct

    def test_no_holdings_returns_empty(self):
        portfolio = [_item("VOO", "ETF", "200", "686.19")]
        analysis = analyze(portfolio, {}, [])
        assert analysis.stock_exposures == []

    def test_warnings_passed_through(self):
        portfolio = [_item("VOO", "ETF", "200", "686.19")]
        analysis = analyze(portfolio, {}, ["Could not fetch VOO"])
        assert "Could not fetch VOO" in analysis.warnings

    def test_duplicate_fund_lots_consolidated(self):
        # Same fund (VOOG) held in two accounts — should appear once per stock, not twice
        portfolio = [
            _item("VOOG", "ETF", "100", "100.00"),  # account 1
            _item("VOOG", "ETF", "50", "100.00"),   # account 2
        ]
        holdings_map = {"VOOG": [_holding("NVDA", "VOOG", "14.25")]}
        analysis = analyze(portfolio, holdings_map, [])
        nvda = next(e for e in analysis.stock_exposures if e.stock_ticker == "NVDA")
        # Should have exactly one source for VOOG, not two
        assert len(nvda.sources) == 1
        assert nvda.sources[0].fund_ticker == "VOOG"
        # Combined position value = 100*100 + 50*100 = 15,000
        assert nvda.sources[0].fund_position_value == Decimal("15000.00")
        # Combined exposure = 15,000 * 14.25% = 2,137.50
        assert nvda.sources[0].stock_exposure_from_fund == Decimal("2137.5000")

    def test_portfolio_total_value(self):
        portfolio = [
            _item("VOO", "ETF", "200", "686.19"),
            _item("QQQ", "ETF", "200", "739.36"),
            _item("SCHD", "ETF", "2000", "31.93"),
            _item("NVDA", "STOCK", "50", "125.45"),
        ]
        analysis = analyze(portfolio, {}, [])
        assert analysis.portfolio_total_value == Decimal("348970.00") + Decimal("50") * Decimal("125.45")
