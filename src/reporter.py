import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

from .models import PortfolioAnalysis

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _output_paths(input_path: str, timestamp: str) -> tuple[Path, Path]:
    stem = Path(input_path).stem
    name = f"{stem}_{timestamp}"
    OUTPUT_DIR.mkdir(exist_ok=True)
    return OUTPUT_DIR / f"{name}.json", OUTPUT_DIR / f"{name}.html"


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


def _build_html(analysis: PortfolioAnalysis, sectors: Dict[str, str]) -> str:
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
        sector = sectors.get(e.stock_ticker, "Unknown")
        rows.append(f"""
        <tr>
            <td class="rank">{i + 1}</td>
            <td class="ticker">{e.stock_ticker} {direct_badge}</td>
            <td class="sector">{sector}</td>
            <td class="value">${e.total_exposure_value:,.2f}</td>
            <td class="pct">{e.percent_of_portfolio:.2f}%</td>
            <td class="sources">{sources_html}</td>
        </tr>""")

    rows_html = "\n".join(rows)
    warnings_html = ""
    if analysis.warnings:
        items = "".join(f"<li>{w}</li>" for w in analysis.warnings)
        warnings_html = f"<div class='warnings'><strong>Warnings:</strong><ul>{items}</ul></div>"

    # ── Stock pie: top 25 + "All Other (N stocks)" ────────────────────────────
    STOCK_COLORS = [
        "#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed",
        "#0891b2", "#be185d", "#65a30d", "#ea580c", "#4f46e5",
        "#0d9488", "#b45309", "#9333ea", "#0284c7", "#15803d",
        "#c2410c", "#7e22ce", "#0369a1", "#166534", "#b91c1c",
        "#1d4ed8", "#047857", "#a16207", "#6d28d9", "#0e7490",
        "#94a3b8",  # All Other
    ]
    top25 = analysis.stock_exposures[:25]
    other_stocks = analysis.stock_exposures[25:]
    other_value = sum(e.total_exposure_value for e in other_stocks)
    stock_slices = [
        {"label": e.stock_ticker, "value": float(e.total_exposure_value)}
        for e in top25
    ]
    if other_value > 0:
        stock_slices.append({"label": f"All Other ({len(other_stocks)} stocks)", "value": float(other_value)})

    stock_total = sum(s["value"] for s in stock_slices)
    stock_pie_js = json.dumps([
        {**s, "color": STOCK_COLORS[i], "pct": s["value"] / stock_total * 100 if stock_total else 0}
        for i, s in enumerate(stock_slices)
    ])

    # ── Sector pie ─────────────────────────────────────────────────────────────
    SECTOR_COLORS = [
        "#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed",
        "#0891b2", "#be185d", "#65a30d", "#ea580c", "#4f46e5",
        "#0d9488", "#94a3b8",
    ]
    sector_totals: Dict[str, float] = defaultdict(float)
    for e in analysis.stock_exposures:
        s = sectors.get(e.stock_ticker, "Unknown")
        sector_totals[s] += float(e.total_exposure_value)

    sector_slices_sorted = sorted(sector_totals.items(), key=lambda x: x[1], reverse=True)
    sector_total = sum(v for _, v in sector_slices_sorted)
    sector_pie_js = json.dumps([
        {"label": name, "value": val, "color": SECTOR_COLORS[i % len(SECTOR_COLORS)],
         "pct": val / sector_total * 100 if sector_total else 0}
        for i, (name, val) in enumerate(sector_slices_sorted)
    ])

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
  .warnings {{ background: #fff3cd; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px; font-size: 0.9rem; }}
  .warnings ul {{ margin-top: 6px; padding-left: 16px; }}
  /* Charts row */
  .charts-row {{ display: flex; gap: 20px; margin-bottom: 24px; flex-wrap: wrap; }}
  .chart-section {{ background: #fff; border-radius: 10px; padding: 24px; flex: 1; min-width: 340px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .chart-section h2 {{ font-size: 1rem; font-weight: 600; margin-bottom: 20px; color: #1a1a2e; }}
  .chart-layout {{ display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }}
  .legend {{ display: flex; flex-direction: column; gap: 6px; flex: 1; min-width: 160px; max-height: 320px; overflow-y: auto; }}
  .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 0.82rem; cursor: pointer; padding: 3px 5px; border-radius: 5px; transition: background 0.15s; }}
  .legend-item:hover {{ background: #f1f5f9; }}
  .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
  .legend-label {{ font-weight: 600; flex: 1; }}
  .legend-pct {{ color: #2563eb; font-weight: 700; min-width: 42px; text-align: right; }}
  .legend-val {{ color: #888; font-size: 0.75rem; min-width: 60px; text-align: right; }}
  /* Table */
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  thead {{ background: #1a1a2e; color: #fff; }}
  th {{ padding: 12px 16px; text-align: left; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }}
  td {{ padding: 11px 16px; border-bottom: 1px solid #f0f0f0; font-size: 0.875rem; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f9fafb; }}
  .rank {{ color: #aaa; font-size: 0.8rem; width: 40px; }}
  .ticker {{ font-weight: 700; font-size: 1rem; white-space: nowrap; }}
  .sector {{ color: #555; font-size: 0.82rem; white-space: nowrap; }}
  .value {{ font-variant-numeric: tabular-nums; font-weight: 600; white-space: nowrap; }}
  .pct {{ color: #2563eb; font-weight: 600; white-space: nowrap; }}
  .sources {{ color: #555; font-size: 0.82rem; line-height: 1.8; }}
  .src-tag {{ background: #e8f0fe; color: #1d4ed8; border-radius: 4px; padding: 1px 6px; font-weight: 600; font-size: 0.78rem; }}
  .weight {{ color: #aaa; }}
  .badge-direct {{ background: #dcfce7; color: #15803d; border-radius: 4px; padding: 1px 6px; font-size: 0.7rem; font-weight: 700; vertical-align: middle; margin-left: 6px; }}
  .section-title {{ font-size: 1rem; font-weight: 600; margin-bottom: 14px; color: #1a1a2e; }}
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

  <div class="charts-row">
    <div class="chart-section">
      <h2>Top Stock Exposure</h2>
      <div class="chart-layout">
        <canvas id="stock-pie" width="260" height="260"></canvas>
        <div class="legend" id="stock-legend"></div>
      </div>
    </div>
    <div class="chart-section">
      <h2>Exposure by Sector</h2>
      <div class="chart-layout">
        <canvas id="sector-pie" width="260" height="260"></canvas>
        <div class="legend" id="sector-legend"></div>
      </div>
    </div>
  </div>

  <p class="section-title">Full Exposure Table</p>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Stock</th>
        <th>Sector</th>
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

<script>
function makeDonut(canvasId, legendId, slices, centerLabel) {{
  const canvas = document.getElementById(canvasId);
  const ctx = canvas.getContext('2d');
  const cx = canvas.width / 2, cy = canvas.height / 2, r = 108, hole = 50;

  const total = slices.reduce((s, d) => s + d.value, 0);
  let startAngle = -Math.PI / 2;
  const arcs = slices.map(d => {{
    const sweep = (d.value / total) * 2 * Math.PI;
    const arc = {{ start: startAngle, end: startAngle + sweep, ...d }};
    startAngle += sweep;
    return arc;
  }});

  function draw(highlightIdx) {{
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    arcs.forEach((a, i) => {{
      const expand = (i === highlightIdx) ? 7 : 0;
      const mid = (a.start + a.end) / 2;
      const ox = Math.cos(mid) * expand, oy = Math.sin(mid) * expand;
      ctx.beginPath();
      ctx.moveTo(cx + ox, cy + oy);
      ctx.arc(cx + ox, cy + oy, r, a.start, a.end);
      ctx.arc(cx + ox, cy + oy, hole, a.end, a.start, true);
      ctx.closePath();
      ctx.fillStyle = a.color;
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }});
    ctx.fillStyle = '#1a1a2e';
    ctx.font = 'bold 12px system-ui';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    if (highlightIdx != null) {{
      const a = arcs[highlightIdx];
      const lbl = a.label.length > 12 ? a.label.slice(0, 11) + '…' : a.label;
      ctx.fillText(lbl, cx, cy - 9);
      ctx.font = '12px system-ui';
      ctx.fillStyle = '#2563eb';
      ctx.fillText(a.pct.toFixed(1) + '%', cx, cy + 9);
    }} else {{
      ctx.fillText(centerLabel[0], cx, cy - 9);
      ctx.font = '11px system-ui';
      ctx.fillStyle = '#888';
      ctx.fillText(centerLabel[1], cx, cy + 9);
    }}
  }}

  const legend = document.getElementById(legendId);
  arcs.forEach((a, i) => {{
    const item = document.createElement('div');
    item.className = 'legend-item';
    item.innerHTML = `
      <span class="legend-dot" style="background:${{a.color}}"></span>
      <span class="legend-label">${{a.label}}</span>
      <span class="legend-pct">${{a.pct.toFixed(1)}}%</span>
      <span class="legend-val">$${{a.value.toLocaleString('en-US',{{maximumFractionDigits:0}})}}</span>`;
    item.addEventListener('mouseenter', () => draw(i));
    item.addEventListener('mouseleave', () => draw(null));
    legend.appendChild(item);
  }});

  canvas.addEventListener('mousemove', e => {{
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left - cx, my = e.clientY - rect.top - cy;
    const dist = Math.sqrt(mx*mx + my*my);
    if (dist < hole || dist > r) {{ draw(null); return; }}
    const angle = Math.atan2(my, mx);
    const norm = angle < -Math.PI/2 ? angle + 2*Math.PI : angle;
    const idx = arcs.findIndex(a => {{
      const s = a.start < -Math.PI/2 ? a.start + 2*Math.PI : a.start;
      const en = a.end < -Math.PI/2 ? a.end + 2*Math.PI : a.end;
      return norm >= s && norm <= en;
    }});
    draw(idx >= 0 ? idx : null);
  }});
  canvas.addEventListener('mouseleave', () => draw(null));
  draw(null);
}}

makeDonut('stock-pie', 'stock-legend', {stock_pie_js}, ['Exposure', 'by stock']);
makeDonut('sector-pie', 'sector-legend', {sector_pie_js}, ['Exposure', 'by sector']);
</script>
</body>
</html>"""


def write_reports(analysis: PortfolioAnalysis, sectors: Dict[str, str], input_path: str) -> tuple[Path, Path]:
    timestamp = analysis.analysis_timestamp.strftime("%Y%m%d_%H%M%S")
    json_path, html_path = _output_paths(input_path, timestamp)

    json_path.write_text(
        json.dumps(_build_json(analysis), indent=2, default=_decimal_default)
    )
    html_path.write_text(_build_html(analysis, sectors))

    return json_path, html_path
