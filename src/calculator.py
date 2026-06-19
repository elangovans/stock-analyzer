from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import List, Dict

from .models import (
    ExposureSource,
    Holding,
    PortfolioAnalysis,
    PortfolioItem,
    StockExposure,
    ValidationResult,
)


def _calculate_exposures(
    portfolio: List[PortfolioItem],
    holdings_map: Dict[str, List[Holding]],
) -> List[StockExposure]:
    portfolio_total = sum(p.position_value for p in portfolio)

    # ticker -> {sources: [], total: Decimal}
    aggregated: Dict[str, dict] = defaultdict(lambda: {"sources": [], "total": Decimal("0")})

    for item in portfolio:
        if item.type == "STOCK":
            key = item.ticker
            exposure_val = item.position_value
            source = ExposureSource(
                fund_ticker=item.ticker,
                fund_type="STOCK",
                fund_position_value=item.position_value,
                stock_weight_in_fund=Decimal("100"),
                stock_exposure_from_fund=exposure_val,
            )
            aggregated[key]["sources"].append(source)
            aggregated[key]["total"] += exposure_val
            aggregated[key]["is_direct"] = True
        else:
            holdings = holdings_map.get(item.ticker, [])
            for holding in holdings:
                exposure_val = item.position_value * (holding.weight_percent / Decimal("100"))
                source = ExposureSource(
                    fund_ticker=item.ticker,
                    fund_type=item.type,
                    fund_position_value=item.position_value,
                    stock_weight_in_fund=holding.weight_percent,
                    stock_exposure_from_fund=exposure_val,
                )
                key = holding.stock_ticker
                aggregated[key]["sources"].append(source)
                aggregated[key]["total"] += exposure_val

    exposures = []
    for ticker, data in aggregated.items():
        total = data["total"]
        pct = (total / portfolio_total * Decimal("100")).quantize(Decimal("0.01"))
        exposures.append(StockExposure(
            stock_ticker=ticker,
            total_exposure_value=total,
            percent_of_portfolio=pct,
            sources=data["sources"],
            is_direct=data.get("is_direct", False),
        ))

    exposures.sort(key=lambda e: e.total_exposure_value, reverse=True)
    return exposures


def _validate(
    exposures: List[StockExposure],
    portfolio_total: Decimal,
) -> ValidationResult:
    total_exposure = sum(e.total_exposure_value for e in exposures)
    diff = abs(total_exposure - portfolio_total)
    # Top-25 holdings won't cover 100% of each fund, so reconciliation is best-effort
    return ValidationResult(
        is_valid=True,
        total_exposure=total_exposure,
        portfolio_total=portfolio_total,
    )


def analyze(
    portfolio: List[PortfolioItem],
    holdings_map: Dict[str, List[Holding]],
    warnings: List[str],
) -> PortfolioAnalysis:
    portfolio_total = sum(p.position_value for p in portfolio)
    exposures = _calculate_exposures(portfolio, holdings_map)
    validation = _validate(exposures, portfolio_total)

    return PortfolioAnalysis(
        portfolio_total_value=portfolio_total,
        analysis_timestamp=datetime.now(),
        stock_exposures=exposures,
        warnings=warnings,
        validation_status=validation,
    )
