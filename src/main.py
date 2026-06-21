import argparse
import sys
from typing import Dict, List

from .fetcher import FetchError, fetch_holdings, fetch_prices_batch, fetch_sectors
from .models import Holding, PortfolioItem
from .calculator import analyze
from .reporter import write_reports
from .validator import ValidationError, load_portfolio


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

    print(f"\n[1/6] Loading portfolio from {portfolio_path}")
    try:
        portfolio = load_portfolio(portfolio_path)
    except (ValidationError, FileNotFoundError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    print(f"      {len(portfolio)} positions loaded")

    warnings: List[str] = []

    print("\n[2/6] Fetching current prices (batch)")
    _fetch_prices(portfolio, warnings)

    valid = [p for p in portfolio if p.current_price > 0]
    skipped = len(portfolio) - len(valid)
    if skipped:
        print(f"      {skipped} position(s) skipped — no price available")

    total = sum(p.position_value for p in valid)
    print(f"      Portfolio total: ${float(total):,.2f}")

    print("\n[3/6] Fetching ETF/MF holdings")
    holdings_map = _fetch_all_holdings(valid, warnings)

    print("\n[4/6] Calculating stock exposures")
    analysis = analyze(valid, holdings_map, warnings)
    print(f"      {len(analysis.stock_exposures)} unique stocks tracked")

    print("\n[5/6] Fetching sectors (batch)")
    all_tickers = [e.stock_ticker for e in analysis.stock_exposures]
    sectors = fetch_sectors(all_tickers)
    unique_sectors = len(set(v for v in sectors.values() if v not in ("Unknown", "ETF / Mutual Fund")))
    print(f"      {unique_sectors} sectors identified")

    print("\n[6/6] Writing reports")
    json_path, html_path = write_reports(analysis, sectors, portfolio_path)
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
