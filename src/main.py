import argparse
import sys
from typing import Dict, List

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def _load_env() -> None:
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return  # Option B: already set in shell environment
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
    load_dotenv(base / ".env")  # Option A: .env next to binary/project root (missing file is silently ignored)

_load_env()

from .fetcher import FetchError, fetch_holdings, fetch_prices_batch, fetch_sectors, fetch_earnings_dates
from .models import Holding, PortfolioItem
from .calculator import analyze
from .reporter import write_reports
from .validator import ValidationError, load_portfolio
from .news import fetch_news, is_enabled as news_enabled


def _fetch_prices(portfolio: List[PortfolioItem], warnings: List[str]) -> None:
    """Batch-fetch prices for all tickers in one yfinance call, populate in-place."""
    tickers = [p.ticker for p in portfolio]
    try:
        prices = fetch_prices_batch(tickers)
    except FetchError as e:
        warnings.append(f"Batch price fetch failed: {e}")
        print(f"  FAILED — {e}")
        return

    for item in portfolio:
        price = prices.get(item.ticker)
        if price:
            item.current_price = price
            print(f"  {item.ticker:<8} ${float(price):,.2f}")
        else:
            msg = f"Could not retrieve price for {item.ticker}"
            warnings.append(msg)
            print(f"  {item.ticker:<8} FAILED — no price returned")


def _fetch_all_holdings(
    portfolio: List[PortfolioItem],
    warnings: List[str],
) -> Dict[str, List[Holding]]:
    holdings_map: Dict[str, List[Holding]] = {}
    funds = [p for p in portfolio if p.type in ("ETF", "MF")]
    for item in funds:
        print(f"  {item.ticker}...", end=" ", flush=True)
        try:
            holdings = fetch_holdings(item.ticker)
            holdings_map[item.ticker] = holdings
            print(f"OK ({len(holdings)} holdings)")
        except FetchError as e:
            msg = f"Could not fetch holdings for {item.ticker}: {e}"
            warnings.append(msg)
            print(f"FAILED — {e}")
    return holdings_map


def run(portfolio_path: str) -> None:
    print(f"\nPortfolio Analyzer")
    print("=" * 50)

    total_steps = 8 if news_enabled() else 7
    print(f"\n[1/{total_steps}] Loading portfolio from {portfolio_path}")
    try:
        portfolio = load_portfolio(portfolio_path)
    except (ValidationError, FileNotFoundError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    print(f"      {len(portfolio)} positions loaded")

    warnings: List[str] = []

    print(f"\n[2/{total_steps}] Fetching current prices (batch)")
    _fetch_prices(portfolio, warnings)

    valid = [p for p in portfolio if p.current_price > 0]
    skipped = len(portfolio) - len(valid)
    if skipped:
        print(f"      {skipped} position(s) skipped — no price available")

    total = sum(p.position_value for p in valid)
    print(f"      Portfolio total: ${float(total):,.2f}")

    print(f"\n[3/{total_steps}] Fetching ETF/MF holdings")
    holdings_map = _fetch_all_holdings(valid, warnings)

    print(f"\n[4/{total_steps}] Calculating stock exposures")
    analysis = analyze(valid, holdings_map, warnings)
    print(f"      {len(analysis.stock_exposures)} unique stocks tracked")

    print(f"\n[5/{total_steps}] Fetching sectors (batch)")
    all_tickers = [e.stock_ticker for e in analysis.stock_exposures]
    sectors = fetch_sectors(all_tickers)
    unique_sectors = len(set(v for v in sectors.values() if v not in ("Unknown", "ETF / Mutual Fund")))
    print(f"      {unique_sectors} sectors identified")

    print(f"\n[6/{total_steps}] Fetching earnings dates")
    earnings_dates = fetch_earnings_dates(all_tickers)
    upcoming = sum(
        1 for t, d in earnings_dates.items()
        if d and 0 <= (d.date() - analysis.analysis_timestamp.date()).days <= 10
    )
    print(f"      {upcoming} stock(s) reporting in next 10 days")

    news_items = []
    if news_enabled():
        print(f"\n[7/{total_steps}] Fetching & classifying news (Claude AI)")
        direct_tickers = [p.ticker for p in valid if p.type == "STOCK"]
        try:
            news_items = fetch_news(direct_tickers if direct_tickers else all_tickers[:20])
            notable = sum(1 for n in news_items if n.stars >= 3)
            print(f"      {notable} notable/high-stake item(s) found")
        except Exception as e:
            warnings.append(f"News fetch failed: {e}")
            print(f"      FAILED — {e}")
    else:
        print(f"\n[7/{total_steps}] News briefs — skipped (no ANTHROPIC_API_KEY)")

    print(f"\n[{total_steps}/{total_steps}] Writing reports")
    json_path, html_path = write_reports(analysis, sectors, earnings_dates, news_items, portfolio_path)
    print(f"      {json_path}")
    print(f"      {html_path}")

    print("\n" + "=" * 50)
    print("Top 10 exposures:")
    for i, e in enumerate(analysis.stock_exposures[:10]):
        bar = "#" * int(float(e.percent_of_portfolio) * 2)
        print(f"  {i+1:>2}. {e.stock_ticker:<6} ${float(e.total_exposure_value):>10,.2f}  {float(e.percent_of_portfolio):>5.2f}%  {bar}")

    tracked = float(analysis.validation_status.total_exposure or 0)
    coverage = tracked / float(total) * 100 if total else 0
    print(f"\n  Coverage: ${tracked:,.2f} / ${float(total):,.2f} ({coverage:.1f}%)")

    if warnings:
        print(f"\n  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"    - {w}")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio Stock Exposure Analyzer")
    parser.add_argument("portfolio", help="Path to portfolio CSV or JSON file")
    args = parser.parse_args()
    run(args.portfolio)


if __name__ == "__main__":
    main()
