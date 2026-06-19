import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .models import PortfolioAnalysis

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _decimal_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _build_json(analysis: PortfolioAnalysis) -> dict:
    return {
        "portfolio_summary": {
            "total_value": float(analysis.portfolio_total_value),
            "analysis_date": analysis.analysis_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "stock_count": len(analysis.stock_exposures),
            "validation": "PASSED" if analysis.validation_status.is_valid else "FAILED",
            "total_tracked_exposure": float(analysis.validation_status.total_exposure or 0),
            "warnings": analysis.warnings,
        },
        "stock_exposures": [
            {
                "rank": i + 1,
                "stock_ticker": e.stock_ticker,
                "total_exposure_value": float(e.total_exposure_value),
                "percent_of_portfolio": float(e.percent_of_portfolio),
                "is_direct_holding": e.is_direct,
                "sources": [
                    {
                        "fund_ticker": s.fund_ticker,
                        "fund_type": s.fund_type,
                        "fund_position_value": float(s.fund_position_value),
                        "stock_weight_in_fund": float(s.stock_weight_in_fund),
                        "stock_exposure_from_fund": float(s.stock_exposure_from_fund),
                    }
                    for s in e.sources
                ],
            }
            for i, e in enumerate(analysis.stock_exposures)
        ],
    }


def _build_html(analysis: PortfolioAnalysis) -> str:
    summary = analysis.portfolio_total_value
    date_str = analysis.analysis_timestamp.strftime("%Y-%m-%d %H:%M:%S")
    tracked = analysis.validation_status.total_exposure or Decimal("0")
    coverage_pct = float(tracked / summary * 100) if summary else 0

    rows = []
    for i, e in enumerate(analysis.stock_exposures):
        sources_html = " &nbsp;|&nbsp; ".join(
            f"<span class='src-tag'>{s.fund_ticker}</span> ${s.stock_exposure_from_fund:,.2f} "
            f"<span class='weight'>({s.stock_weight_in_fund:.2f}%)</span>"
            for s in e.sources
        )
        direct_badge = "<span class='badge-direct'>DIRECT</span>" if e.is_direct else ""
        rows.append(f"""
        <tr>
            <td class="rank">{i + 1}</td>
            <td class="ticker">{e.stock_ticker} {direct_badge}</td>
            <td class="value">${e.total_exposure_value:,.2f}</td>
            <td class="pct">{e.percent_of_portfolio:.2f}%</td>
            <td class="sources">{sources_html}</td>
        </tr>""")

    rows_html = "\n".join(rows)
    warnings_html = ""
    if analysis.warnings:
        items = "".join(f"<li>{w}</li>" for w in analysis.warnings)
        warnings_html = f"<div class='warnings'><strong>Warnings:</strong><ul>{items}</ul></div>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Portfolio Stock Exposure Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f7fa; color: #1a1a2e; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
  h1 {{ font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }}
  .subtitle {{ color: #666; font-size: 0.9rem; margin-bottom: 20px; }}
  .summary-cards {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
  .card {{ background: #fff; border-radius: 10px; padding: 18px 24px; flex: 1; min-width: 180px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .card-label {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 6px; }}
  .card-value {{ font-size: 1.5rem; font-weight: 700; color: #1a1a2e; }}
  .card-value.green {{ color: #16a34a; }}
  .warnings {{ background: #fff3cd; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px; font-size: 0.9rem; }}
  .warnings ul {{ margin-top: 6px; padding-left: 16px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  thead {{ background: #1a1a2e; color: #fff; }}
  th {{ padding: 12px 16px; text-align: left; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }}
  td {{ padding: 11px 16px; border-bottom: 1px solid #f0f0f0; font-size: 0.875rem; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f9fafb; }}
  .rank {{ color: #aaa; font-size: 0.8rem; width: 40px; }}
  .ticker {{ font-weight: 700; font-size: 1rem; white-space: nowrap; }}
  .value {{ font-variant-numeric: tabular-nums; font-weight: 600; white-space: nowrap; }}
  .pct {{ color: #2563eb; font-weight: 600; white-space: nowrap; }}
  .sources {{ color: #555; font-size: 0.82rem; line-height: 1.8; }}
  .src-tag {{ background: #e8f0fe; color: #1d4ed8; border-radius: 4px; padding: 1px 6px; font-weight: 600; font-size: 0.78rem; }}
  .weight {{ color: #aaa; }}
  .badge-direct {{ background: #dcfce7; color: #15803d; border-radius: 4px; padding: 1px 6px; font-size: 0.7rem; font-weight: 700; vertical-align: middle; margin-left: 6px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Portfolio Stock Exposure Report</h1>
  <p class="subtitle">Generated {date_str} &mdash; Top 25 holdings per fund</p>
  {warnings_html}
  <div class="summary-cards">
    <div class="card">
      <div class="card-label">Portfolio Total</div>
      <div class="card-value">${float(summary):,.2f}</div>
    </div>
    <div class="card">
      <div class="card-label">Tracked Exposure</div>
      <div class="card-value">${float(tracked):,.2f}</div>
    </div>
    <div class="card">
      <div class="card-label">Coverage</div>
      <div class="card-value">{coverage_pct:.1f}%</div>
    </div>
    <div class="card">
      <div class="card-label">Unique Stocks Tracked</div>
      <div class="card-value">{len(analysis.stock_exposures)}</div>
    </div>
  </div>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Stock</th>
        <th>Total Exposure</th>
        <th>% Portfolio</th>
        <th>Sources (Fund → Weight → Exposure)</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</div>
</body>
</html>"""


def write_reports(analysis: PortfolioAnalysis) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(exist_ok=True)

    json_path = OUTPUT_DIR / "report.json"
    html_path = OUTPUT_DIR / "report.html"

    json_path.write_text(
        json.dumps(_build_json(analysis), indent=2, default=_decimal_default)
    )
    html_path.write_text(_build_html(analysis))

    return json_path, html_path
