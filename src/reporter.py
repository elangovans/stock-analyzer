import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import PortfolioAnalysis
from .news import NewsItem

def _output_paths(input_path: str, timestamp: str) -> tuple[Path, Path]:
    output_dir = Path.cwd() / "output"
    output_dir.mkdir(exist_ok=True)
    stem = Path(input_path).stem
    name = f"{stem}_{timestamp}"
    return output_dir / f"{name}.json", output_dir / f"{name}.html"


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


def _earnings_label(date: Optional[datetime], today: datetime) -> tuple[str, str]:
    """Return (display_text, css_class) for an earnings date."""
    if date is None:
        return ("—", "")
    days = (date.date() - today.date()).days
    if days < 0:
        return ("—", "")
    label = date.strftime("%b %d")
    if days == 0:
        return (f"{label} ⚡ Today", "earnings-today")
    if days <= 3:
        return (f"{label} 🔴 {days}d", "earnings-imminent")
    if days <= 10:
        return (f"{label} 🟡 {days}d", "earnings-soon")
    return (label, "earnings-future")


def _build_earnings_calendar(
    analysis: PortfolioAnalysis,
    sectors: Dict[str, str],
    earnings_dates: Dict[str, Optional[datetime]],
    today: datetime,
) -> str:
    """Build the earnings calendar tab HTML (stocks reporting in next 10 days)."""
    upcoming = []
    for e in analysis.stock_exposures:
        d = earnings_dates.get(e.stock_ticker)
        if d is None:
            continue
        days = (d.date() - today.date()).days
        if 0 <= days <= 10:
            upcoming.append((days, d, e))

    upcoming.sort(key=lambda x: x[0])

    if not upcoming:
        return "<p class='no-earnings'>No earnings announcements found in the next 10 days for tracked stocks.</p>"

    rows = []
    for days, d, e in upcoming:
        sector = sectors.get(e.stock_ticker, "Unknown")
        exposure_type = (
            "<span class='badge-direct'>DIRECT</span>"
            if e.is_direct
            else "<span class='badge-fund'>VIA FUND</span>"
        )
        day_label = "Today" if days == 0 else ("Tomorrow" if days == 1 else f"in {days} days")
        urgency_cls = "row-today" if days == 0 else ("row-imminent" if days <= 3 else "row-soon")
        rows.append(f"""
        <tr class="{urgency_cls}">
            <td class="earn-days">{day_label}</td>
            <td class="earn-date">{d.strftime("%a, %b %d")}</td>
            <td class="ticker">{e.stock_ticker} {exposure_type}</td>
            <td class="sector">{sector}</td>
            <td class="value">${e.total_exposure_value:,.2f}</td>
            <td class="pct">{e.percent_of_portfolio:.2f}%</td>
        </tr>""")

    rows_html = "\n".join(rows)
    return f"""
    <table id="tbl-earnings">
      <thead>
        <tr>
          <th data-sort="num">When</th>
          <th data-sort="str">Date</th>
          <th data-sort="str">Stock</th>
          <th data-sort="str">Sector</th>
          <th data-sort="num">Your Exposure</th>
          <th data-sort="num">% Portfolio</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>"""


def _build_news_tab(news_items: List[NewsItem]) -> str:
    if not news_items:
        return ""

    CATEGORY_ICONS = {
        "Leadership": "👤",
        "M&A": "🤝",
        "Regulatory": "⚖️",
        "Financial": "💰",
        "Legal": "🏛️",
        "Product": "🚀",
        "Other": "📰",
    }
    STAR_COLORS = {5: "#dc2626", 4: "#ea580c", 3: "#d97706", 2: "#6b7280", 1: "#9ca3af"}

    # Group by category
    by_category: Dict[str, List[NewsItem]] = defaultdict(list)
    for item in news_items:
        by_category[item.category].append(item)

    # Sort categories by their highest-starred item
    sorted_categories = sorted(
        by_category.items(),
        key=lambda x: max(i.stars for i in x[1]),
        reverse=True,
    )

    cards_html = []
    for category, items in sorted_categories:
        icon = CATEGORY_ICONS.get(category, "📰")
        item_cards = []
        for item in items:
            stars_filled = "★" * item.stars
            stars_empty = "☆" * (5 - item.stars)
            star_color = STAR_COLORS.get(item.stars, "#9ca3af")
            date_str = item.published_at.strftime("%b %d, %H:%M") if item.published_at else ""
            classification_badge = (
                "<span class='badge-highstake'>HIGH-STAKE</span>"
                if item.classification == "high-stake"
                else "<span class='badge-notable'>NOTABLE</span>"
            )
            item_cards.append(f"""
            <div class="news-card stars-{item.stars}">
              <div class="news-card-header">
                <span class="news-ticker">{item.ticker}</span>
                {classification_badge}
                <span class="news-stars" style="color:{star_color}" title="{item.stars}/5 criticality">
                  {stars_filled}<span class="stars-empty">{stars_empty}</span>
                </span>
                <span class="news-date">{date_str}</span>
              </div>
              <a class="news-title" href="{item.url}" target="_blank" rel="noopener">{item.title}</a>
              {f'<p class="news-summary">{item.summary}</p>' if item.summary else ""}
              <span class="news-publisher">{item.publisher}</span>
            </div>""")

        cards_html.append(f"""
        <div class="news-category-group">
          <h3 class="news-category-title">{icon} {category}</h3>
          {"".join(item_cards)}
        </div>""")

    return f"""
    <p class="section-title">AI-Classified News — Notable &amp; High-Stake Only
      <span class="news-powered">powered by Claude AI</span>
    </p>
    <div class="news-grid">
      {"".join(cards_html)}
    </div>"""


def _build_html(analysis: PortfolioAnalysis, sectors: Dict[str, str], earnings_dates: Dict[str, Optional[datetime]], news_items: List[NewsItem]) -> str:
    summary = analysis.portfolio_total_value
    date_str = analysis.analysis_timestamp.strftime("%Y-%m-%d %H:%M:%S")
    tracked = analysis.validation_status.total_exposure or Decimal("0")
    coverage_pct = float(tracked / summary * 100) if summary else 0

    today = analysis.analysis_timestamp
    rows = []
    for i, e in enumerate(analysis.stock_exposures):
        sources_html = " &nbsp;|&nbsp; ".join(
            f"<span class='src-tag'>{s.fund_ticker}</span> ${s.stock_exposure_from_fund:,.2f} "
            f"<span class='weight'>({s.stock_weight_in_fund:.2f}%)</span>"
            for s in e.sources
        )
        direct_badge = "<span class='badge-direct'>DIRECT</span>" if e.is_direct else ""
        sector = sectors.get(e.stock_ticker, "Unknown")
        earn_label, earn_cls = _earnings_label(earnings_dates.get(e.stock_ticker), today)
        rows.append(f"""
        <tr>
            <td class="rank">{i + 1}</td>
            <td class="ticker">{e.stock_ticker} {direct_badge}</td>
            <td class="sector">{sector}</td>
            <td class="value">${e.total_exposure_value:,.2f}</td>
            <td class="pct">{e.percent_of_portfolio:.2f}%</td>
            <td class="earnings {earn_cls}">{earn_label}</td>
            <td class="sources">{sources_html}</td>
        </tr>""")

    rows_html = "\n".join(rows)
    earnings_calendar_html = _build_earnings_calendar(analysis, sectors, earnings_dates, today)
    news_tab_html = _build_news_tab(news_items)
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
  .badge-fund {{ background: #e0f2fe; color: #0369a1; border-radius: 4px; padding: 1px 6px; font-size: 0.7rem; font-weight: 700; vertical-align: middle; margin-left: 6px; }}
  .section-title {{ font-size: 1rem; font-weight: 600; margin-bottom: 14px; color: #1a1a2e; }}
  /* Earnings column */
  .earnings {{ font-size: 0.82rem; white-space: nowrap; }}
  .earnings-today {{ color: #7c3aed; font-weight: 700; }}
  .earnings-imminent {{ color: #dc2626; font-weight: 700; }}
  .earnings-soon {{ color: #d97706; font-weight: 600; }}
  .earnings-future {{ color: #555; }}
  /* Tabs */
  .tabs {{ display: flex; gap: 4px; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0; }}
  .tab-btn {{ padding: 10px 20px; border: none; background: none; cursor: pointer; font-size: 0.9rem; font-weight: 600; color: #888; border-bottom: 3px solid transparent; margin-bottom: -2px; transition: all 0.15s; }}
  .tab-btn.active {{ color: #1a1a2e; border-bottom-color: #2563eb; }}
  .tab-btn:hover:not(.active) {{ color: #555; }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  /* Earnings calendar */
  .earn-days {{ font-weight: 700; white-space: nowrap; font-size: 0.85rem; }}
  .earn-date {{ color: #555; white-space: nowrap; font-size: 0.85rem; }}
  .row-today td {{ background: #f3e8ff !important; }}
  .row-imminent td {{ background: #fef2f2 !important; }}
  .row-soon td {{ background: #fffbeb !important; }}
  .no-earnings {{ color: #888; padding: 24px 0; font-size: 0.9rem; }}
  /* News tab */
  .news-grid {{ display: flex; flex-direction: column; gap: 28px; }}
  .news-category-group {{ background: #fff; border-radius: 10px; padding: 20px 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .news-category-title {{ font-size: 1rem; font-weight: 700; color: #1a1a2e; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; }}
  .news-card {{ border: 1px solid #f0f0f0; border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; transition: box-shadow 0.15s; }}
  .news-card:last-child {{ margin-bottom: 0; }}
  .news-card:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  .news-card.stars-5 {{ border-left: 4px solid #dc2626; background: #fff5f5; }}
  .news-card.stars-4 {{ border-left: 4px solid #ea580c; background: #fff8f5; }}
  .news-card.stars-3 {{ border-left: 4px solid #d97706; }}
  .news-card-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }}
  .news-ticker {{ background: #1a1a2e; color: #fff; border-radius: 4px; padding: 2px 8px; font-size: 0.78rem; font-weight: 700; }}
  .news-stars {{ font-size: 1.05rem; font-weight: 700; letter-spacing: 1px; }}
  .stars-empty {{ color: #d1d5db; }}
  .news-date {{ color: #aaa; font-size: 0.78rem; margin-left: auto; }}
  .news-title {{ display: block; font-size: 0.92rem; font-weight: 600; color: #1a1a2e; text-decoration: none; margin-bottom: 5px; line-height: 1.4; }}
  .news-title:hover {{ color: #2563eb; text-decoration: underline; }}
  .news-summary {{ font-size: 0.85rem; color: #444; margin-bottom: 5px; line-height: 1.5; }}
  .news-publisher {{ font-size: 0.75rem; color: #aaa; }}
  .badge-highstake {{ background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; border-radius: 4px; padding: 1px 7px; font-size: 0.7rem; font-weight: 700; }}
  .badge-notable {{ background: #fffbeb; color: #d97706; border: 1px solid #fde68a; border-radius: 4px; padding: 1px 7px; font-size: 0.7rem; font-weight: 700; }}
  .news-powered {{ font-size: 0.72rem; font-weight: 400; color: #aaa; margin-left: 10px; vertical-align: middle; }}
  /* Sortable headers */
  th[data-sort] {{ cursor: pointer; user-select: none; }}
  th[data-sort]:hover {{ background: #2d3a5a; }}
  th[data-sort]::after {{ content: " ⇅"; opacity: 0.4; font-size: 0.75rem; }}
  th[data-sort].asc::after {{ content: " ↑"; opacity: 1; }}
  th[data-sort].desc::after {{ content: " ↓"; opacity: 1; }}
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

  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('exposure', this)">Stock Exposure</button>
    <button class="tab-btn" onclick="switchTab('earnings', this)">Earnings Calendar (Next 10 Days)</button>
    {f'<button class="tab-btn" onclick="switchTab(\'news\', this)">📰 News Briefs</button>' if news_tab_html else ""}
  </div>

  <div id="tab-exposure" class="tab-panel active">
    <p class="section-title">Full Exposure Table</p>
    <table id="tbl-exposure">
      <thead>
        <tr>
          <th data-sort="num">#</th>
          <th data-sort="str">Stock</th>
          <th data-sort="str">Sector</th>
          <th data-sort="num">Total Exposure</th>
          <th data-sort="num">% Portfolio</th>
          <th data-sort="str">Earnings Date</th>
          <th>Sources (Fund → Weight → Exposure)</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

  <div id="tab-earnings" class="tab-panel">
    <p class="section-title">Upcoming Earnings — Stocks You Are Exposed To</p>
    {earnings_calendar_html}
  </div>

  {f'<div id="tab-news" class="tab-panel">{news_tab_html}</div>' if news_tab_html else ""}
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

function switchTab(id, btn) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
}}

(function() {{
  function parseCell(td, type) {{
    const txt = td.innerText.trim();
    if (type === 'num') {{
      const n = parseFloat(txt.replace(/[^0-9.\\-]/g, ''));
      return isNaN(n) ? -Infinity : n;
    }}
    return txt.toLowerCase();
  }}

  function sortTable(th) {{
    const table = th.closest('table');
    const tbody = table.querySelector('tbody');
    const ths = Array.from(th.closest('tr').querySelectorAll('th[data-sort]'));
    const colIndex = Array.from(th.closest('tr').children).indexOf(th);
    const type = th.dataset.sort;
    const asc = !th.classList.contains('asc');

    ths.forEach(h => h.classList.remove('asc', 'desc'));
    th.classList.add(asc ? 'asc' : 'desc');

    const rows = Array.from(tbody.querySelectorAll('tr'));
    rows.sort((a, b) => {{
      const av = parseCell(a.children[colIndex], type);
      const bv = parseCell(b.children[colIndex], type);
      if (av < bv) return asc ? -1 : 1;
      if (av > bv) return asc ? 1 : -1;
      return 0;
    }});
    rows.forEach(r => tbody.appendChild(r));
  }}

  document.querySelectorAll('th[data-sort]').forEach(th => {{
    th.addEventListener('click', () => sortTable(th));
  }});
}})();
</script>
</body>
</html>"""


def write_reports(
    analysis: PortfolioAnalysis,
    sectors: Dict[str, str],
    earnings_dates: Dict[str, Optional[datetime]],
    news_items: List[NewsItem],
    input_path: str,
) -> tuple[Path, Path]:
    timestamp = analysis.analysis_timestamp.strftime("%Y%m%d_%H%M%S")
    json_path, html_path = _output_paths(input_path, timestamp)

    json_path.write_text(
        json.dumps(_build_json(analysis), indent=2, default=_decimal_default)
    )
    html_path.write_text(_build_html(analysis, sectors, earnings_dates, news_items))

    return json_path, html_path
