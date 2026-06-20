from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import List, Literal, Optional


@dataclass
class PortfolioItem:
    ticker: str
    type: Literal["ETF", "MF", "STOCK", "CASH"]
    quantity: Decimal
    current_price: Decimal = Decimal("0")  # populated after price fetch

    @property
    def position_value(self) -> Decimal:
        return self.quantity * self.current_price


@dataclass
class Holding:
    stock_ticker: str
    etf_ticker: str
    weight_percent: Decimal  # 0-100
    data_source: str
    last_updated: datetime


@dataclass
class ExposureSource:
    fund_ticker: str
    fund_type: str
    fund_position_value: Decimal
    stock_weight_in_fund: Decimal
    stock_exposure_from_fund: Decimal


@dataclass
class StockExposure:
    stock_ticker: str
    total_exposure_value: Decimal
    percent_of_portfolio: Decimal
    sources: List[ExposureSource] = field(default_factory=list)
    is_direct: bool = False


@dataclass
class ValidationResult:
    is_valid: bool
    error: Optional[str] = None
    total_exposure: Optional[Decimal] = None
    portfolio_total: Optional[Decimal] = None


@dataclass
class PortfolioAnalysis:
    portfolio_total_value: Decimal
    analysis_timestamp: datetime
    stock_exposures: List[StockExposure]
    warnings: List[str]
    validation_status: ValidationResult
