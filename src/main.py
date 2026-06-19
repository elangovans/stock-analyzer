import argparse
import sys
from typing import Dict, List

from .fetcher import FetchError, fetch_holdings
from .models import Holding, PortfolioItem
from .calculator import analyze
from .reporter import write_reports
from .validator import ValidationError, load_portfolio


def _fetch_all_holdings(
    portfolio: List[PortfolioItem],
) -> tuple[Dict[str, List[Holding]], List[str]]:
    holdings_map: Dict[str, List[Holding]] = {}
    warnings: List[str] = []

    funds = [p for p in portfolio if p.type in ("ETF", "MF")]
    for item in funds:
        print(f"  Fetching holdings for {item.ticker}...", end=" ", flush=True)
        try:
            holdings = fetch_holdings(item.ticker)
            holdings_map[item.ticker] = holdings
            print(f"OK ({len(holdings)} holdings)")
        except FetchError as e:
            msg = f"Could not fetch holdings for {item.ticker}: {e}"
            warnings.append(msg)
            print(f"FAILED — {e}")

    return holdings_map, warnings


def run(portfolio_path: str) -> None:
    print(f"\nPortfolio Analyzer")
    print("=" * 50)

    print(f"\n[1/4] Loading portfolio from {portfolio_path}")
    try:
        portfolio = load_portfolio(portfolio_path)
    except (ValidationError, FileNotFoundError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    total = sum(p.position_value for p in portfolio)
    print(f"      {len(portfolio)} positions loaded — total ${float(total):,.2f}")

    print("\n[2/4] Fetching ETF/MF holdings")
    holdings_map, warnings = _fetch_all_holdings(portfolio)

    print("\n[3/4] Calculating stock exposures")
    analysis = analyze(portfolio, holdings_map, warnings)
    print(f"      {len(analysis.stock_exposures)} unique stocks tracked")

    print("\n[4/4] Writing reports")
    json_path, html_path = write_reports(analysis)
    print(f"      {json_path}")
    print(f"      {html_path}")

    print("\n" + "=" * 50)
    print(f"Top 10 exposures:")
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
