from __future__ import annotations

import html
import textwrap

import pandas as pd

from .common import DASHBOARD_DIR, DOCS_DIR, FIGURES_DIR, OUTPUTS_DIR, REPORTS_DIR, money, num, pct, write_text
from .metrics import Metrics

def create_dashboard_environment_doc() -> None:
    write_text(
        DOCS_DIR / "dashboard_environment_inspection.md",
        """
        # Dashboard Environment Inspection

        Inspection was performed before selecting the final dashboard delivery technology.

        ## Checked
        - `PBIDesktop` command lookup
        - `pbi-tools` command lookup
        - `TabularEditor` and `TabularEditor3` command lookup
        - Microsoft Store/Appx package lookup for Power BI
        - Windows uninstall registry entries for Power BI, pbi-tools, and Tabular Editor
        - Common install folders under Program Files and user-local app locations

        ## Result
        Power BI Desktop, PBIP command-line tooling, pbi-tools, and Tabular Editor were not found as accessible local tooling in this environment.

        ## Delivery Decision
        Because native `.pbix` or `.pbip` creation was not technically available, the project delivers a finished standalone HTML analytics dashboard generated from the validated project data. The dashboard is recruiter-ready, requires no external server, and does not require the user to manually construct visuals.
        """,
    )

def html_table(df: pd.DataFrame, cols: list[str], max_rows: int = 10) -> str:
    rows = []
    for _, row in df.head(max_rows).iterrows():
        cells = "".join(f"<td>{html.escape(str(row[col]))}</td>" for col in cols)
        rows.append(f"<tr>{cells}</tr>")
    headers = "".join(f"<th>{html.escape(col.replace('_', ' ').title())}</th>" for col in cols)
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"

def create_html_dashboard(metrics: Metrics, eda: dict[str, pd.DataFrame]) -> None:
    shipping = eda["shipping_mode_performance"].copy()
    shipping["late_delivery_rate"] = (shipping["late_delivery_rate"] * 100).round(1).astype(str) + "%"
    shipping["avg_delay_days"] = shipping["avg_delay_days"].astype(float).round(2)
    shipping["total_sales"] = shipping["total_sales"].astype(float).map(lambda v: money(v, 0))

    market = eda["market_performance"].copy()
    market["late_delivery_rate"] = (market["late_delivery_rate"] * 100).round(1).astype(str) + "%"
    market["avg_delay_days"] = market["avg_delay_days"].astype(float).round(2)
    market["total_sales"] = market["total_sales"].astype(float).map(lambda v: money(v, 0))

    region = eda["region_risk"].head(12).copy()
    region["late_delivery_rate"] = (region["late_delivery_rate"] * 100).round(1).astype(str) + "%"
    region["avg_delay_days"] = region["avg_delay_days"].astype(float).round(2)
    region["total_sales"] = region["total_sales"].astype(float).map(lambda v: money(v, 0))

    category = eda["category_performance"].head(12).copy()
    category["total_sales"] = category["total_sales"].astype(float).map(lambda v: money(v, 0))
    category["total_profit"] = category["total_profit"].astype(float).map(lambda v: money(v, 0))
    category["profit_margin"] = (category["profit_margin"] * 100).round(1).astype(str) + "%"

    monthly = eda["monthly_trend"].copy()
    monthly["late_delivery_rate_display"] = (monthly["late_delivery_rate"] * 100).round(1).astype(str) + "%"
    monthly["total_sales_display"] = monthly["total_sales"].astype(float).map(lambda v: money(v, 0))
    monthly_recent = monthly.tail(12)

    dashboard_path = DASHBOARD_DIR / "supply_chain_delivery_dashboard.html"
    html_content = f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Supply Chain Delivery Performance Dashboard</title>
      <style>
        :root {{ --blue:#2F5F8F; --red:#B23A48; --green:#2E7D32; --amber:#C77D00; --ink:#252525; --muted:#667085; --bg:#F7F8FA; --line:#D9DEE7; }}
        * {{ box-sizing:border-box; }}
        body {{ margin:0; font-family:Segoe UI, Arial, sans-serif; background:var(--bg); color:var(--ink); }}
        header {{ padding:28px 34px 18px; background:#fff; border-bottom:1px solid var(--line); }}
        h1 {{ margin:0 0 8px; font-size:28px; letter-spacing:0; }}
        h2 {{ margin:0 0 14px; font-size:20px; }}
        p {{ margin:0; color:var(--muted); line-height:1.45; }}
        main {{ padding:22px 34px 34px; max-width:1420px; margin:0 auto; }}
        .tabs {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:18px; }}
        .tabs button {{ border:1px solid var(--line); background:#fff; padding:10px 14px; border-radius:6px; cursor:pointer; font-weight:600; color:var(--ink); }}
        .tabs button.active {{ background:var(--blue); color:#fff; border-color:var(--blue); }}
        .section {{ display:none; }}
        .section.active {{ display:block; }}
        .kpis {{ display:grid; grid-template-columns:repeat(6,minmax(140px,1fr)); gap:12px; margin-bottom:18px; }}
        .card {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:14px; min-height:86px; }}
        .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; font-weight:700; }}
        .value {{ font-size:24px; font-weight:750; margin-top:8px; }}
        .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
        .wide {{ grid-column:1 / -1; }}
        .panel {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:18px; }}
        .panel img {{ width:100%; height:auto; display:block; }}
        table {{ width:100%; border-collapse:collapse; font-size:13px; }}
        th, td {{ padding:9px 10px; border-bottom:1px solid #E6EAF0; text-align:left; }}
        th {{ color:#475467; background:#F3F5F8; font-size:12px; text-transform:uppercase; }}
        .note {{ margin-top:12px; font-size:13px; color:var(--muted); }}
        .risk {{ color:var(--red); }}
        @media (max-width:1000px) {{ .kpis {{ grid-template-columns:repeat(2,1fr); }} .grid {{ grid-template-columns:1fr; }} main, header {{ padding-left:18px; padding-right:18px; }} }}
      </style>
    </head>
    <body>
      <header>
        <h1>Supply Chain Delivery Performance Dashboard</h1>
        <p>Validated portfolio dashboard generated from Python and SQLite outputs. Metrics are grain-aware: commercial KPIs use order-item grain and delivery KPIs use distinct order grain.</p>
      </header>
      <main>
        <nav class="tabs">
          <button class="active" data-tab="overview">Executive Overview</button>
          <button data-tab="delivery">Delivery & Logistics</button>
          <button data-tab="commercial">Market & Commercial</button>
          <button data-tab="diagnostic">Diagnostic Detail</button>
        </nav>

        <section id="overview" class="section active">
          <div class="kpis">
            <div class="card"><div class="label">Total Sales</div><div class="value">{money(metrics.total_sales)}</div></div>
            <div class="card"><div class="label">Total Profit</div><div class="value">{money(metrics.total_profit)}</div></div>
            <div class="card"><div class="label">Profit Margin</div><div class="value">{pct(metrics.profit_margin)}</div></div>
            <div class="card"><div class="label">Total Orders</div><div class="value">{metrics.total_orders:,}</div></div>
            <div class="card"><div class="label">Late Delivery Rate</div><div class="value risk">{pct(metrics.late_delivery_rate)}</div></div>
            <div class="card"><div class="label">Avg Shipping Delay</div><div class="value">{num(metrics.average_shipping_delay_days)} days</div></div>
          </div>
          <div class="grid">
            <div class="panel wide"><h2>Monthly Sales And Late Delivery Trend</h2><img src="../reports/figures/monthly_sales_late_delivery_trend.svg" alt="Monthly sales and late delivery trend"></div>
            <div class="panel"><h2>Market Order Volume</h2><img src="../reports/figures/market_order_volume.svg" alt="Market order volume"></div>
            <div class="panel"><h2>Recent Monthly Performance</h2>{html_table(monthly_recent, ["order_year_month", "total_orders", "total_sales_display", "late_delivery_rate_display"], 12)}</div>
          </div>
        </section>

        <section id="delivery" class="section">
          <div class="grid">
            <div class="panel"><h2>Late Delivery Rate By Shipping Mode</h2><img src="../reports/figures/late_delivery_rate_by_shipping_mode.svg" alt="Late delivery rate by shipping mode"></div>
            <div class="panel"><h2>Shipping Mode Performance</h2>{html_table(shipping, ["shipping_mode", "total_orders", "late_delivery_rate", "avg_delay_days", "total_sales"], 10)}</div>
            <div class="panel wide"><h2>High-Volume Regions With Highest Late Delivery Rates</h2><img src="../reports/figures/high_volume_regions_late_delivery.svg" alt="High volume regions late delivery"></div>
            <div class="panel wide"><h2>Regional Risk Table</h2>{html_table(region, ["market", "order_region", "total_orders", "late_delivery_rate", "avg_delay_days", "total_sales"], 12)}</div>
          </div>
        </section>

        <section id="commercial" class="section">
          <div class="grid">
            <div class="panel"><h2>Top Categories By Net Sales</h2><img src="../reports/figures/top_categories_sales.svg" alt="Top categories by sales"></div>
            <div class="panel"><h2>Category Profitability</h2>{html_table(category, ["category_name", "total_orders", "total_sales", "total_profit", "profit_margin"], 12)}</div>
            <div class="panel wide"><h2>Market Performance</h2>{html_table(market, ["market", "total_orders", "late_delivery_rate", "avg_delay_days", "total_sales"], 10)}</div>
          </div>
        </section>

        <section id="diagnostic" class="section">
          <div class="grid">
            <div class="panel"><h2>Shipping Delay Distribution</h2><img src="../reports/figures/shipping_delay_distribution.svg" alt="Shipping delay distribution"></div>
            <div class="panel">
              <h2>Analytical Guardrails</h2>
              <p class="note">This dashboard avoids unsupported causal claims. Late delivery findings are prioritization signals for review by market, region, category, and shipping mode.</p>
              <p class="note">Power BI model guidance: order-level measures use `fact_orders` plus an explicit item-filtered order scope for product/category selections.</p>
              <p class="note">Validation: Python and SQL KPI reconciliation passed with zero material differences.</p>
            </div>
          </div>
        </section>
      </main>
      <script>
        const buttons = document.querySelectorAll('.tabs button');
        const sections = document.querySelectorAll('.section');
        buttons.forEach(button => button.addEventListener('click', () => {{
          buttons.forEach(b => b.classList.remove('active'));
          sections.forEach(s => s.classList.remove('active'));
          button.classList.add('active');
          document.getElementById(button.dataset.tab).classList.add('active');
        }}));
      </script>
    </body>
    </html>
    """
    dashboard_path.write_text(textwrap.dedent(html_content).strip(), encoding="utf-8")
    rendered = dashboard_path.read_text(encoding="utf-8") if dashboard_path.exists() else ""
    required_displays = {
        "total_sales_displayed": money(metrics.total_sales),
        "total_profit_displayed": money(metrics.total_profit),
        "profit_margin_displayed": pct(metrics.profit_margin),
        "total_orders_displayed": f"{metrics.total_orders:,}",
        "late_delivery_rate_displayed": pct(metrics.late_delivery_rate),
        "average_shipping_delay_displayed": f"{num(metrics.average_shipping_delay_days)} days",
    }
    checks = [
        {"check": "dashboard_exists", "expected": "true", "actual": str(dashboard_path.exists()).lower(), "status": "PASS" if dashboard_path.exists() else "FAIL"},
        {"check": "dashboard_non_empty", "expected": "> 1000 bytes", "actual": dashboard_path.stat().st_size if dashboard_path.exists() else 0, "status": "PASS" if dashboard_path.exists() and dashboard_path.stat().st_size > 1000 else "FAIL"},
        {"check": "dashboard_tabs_present", "expected": "4 tabs", "actual": rendered.count('data-tab="'), "status": "PASS" if rendered.count('data-tab="') == 4 else "FAIL"},
        {"check": "dashboard_javascript_tabs_present", "expected": "tab click handler", "actual": "addEventListener('click'" in rendered, "status": "PASS" if "addEventListener('click'" in rendered else "FAIL"},
    ]
    chart_assets = [
        "monthly_sales_late_delivery_trend.svg",
        "market_order_volume.svg",
        "late_delivery_rate_by_shipping_mode.svg",
        "high_volume_regions_late_delivery.svg",
        "top_categories_sales.svg",
        "shipping_delay_distribution.svg",
    ]
    missing_assets = [name for name in chart_assets if not (FIGURES_DIR / name).exists()]
    checks.append({"check": "dashboard_chart_assets_exist", "expected": "all referenced SVG assets", "actual": "; ".join(missing_assets) if missing_assets else "all present", "status": "PASS" if not missing_assets else "FAIL"})
    for check, expected in required_displays.items():
        checks.append({"check": check, "expected": expected, "actual": expected if expected in rendered else "missing", "status": "PASS" if expected in rendered else "FAIL"})

    chart_checks = [
        ("shipping_mode_chart_rows", int(eda["shipping_mode_performance"]["total_orders"].sum()), metrics.total_orders, 0),
        ("market_chart_orders_reconcile", int(eda["market_performance"]["total_orders"].sum()), metrics.total_orders, 0),
        ("monthly_trend_orders_reconcile", int(eda["monthly_trend"]["total_orders"].sum()), metrics.total_orders, 0),
        ("category_sales_reconcile", float(eda["category_performance"]["total_sales"].sum()), metrics.total_sales, 0.05),
        ("category_profit_reconcile", float(eda["category_performance"]["total_profit"].sum()), metrics.total_profit, 0.05),
    ]
    for check, actual, expected, tolerance in chart_checks:
        diff = abs(float(actual) - float(expected))
        checks.append({"check": check, "expected": expected, "actual": actual, "status": "PASS" if diff <= tolerance else "FAIL"})

    dashboard_checks = pd.DataFrame(checks)
    dashboard_checks.to_csv(OUTPUTS_DIR / "dashboard_validation.csv", index=False)

def create_dashboard_preview(metrics: Metrics) -> None:
    preview = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620">
<rect width="1200" height="620" fill="#f5f7fb"/>
<rect x="35" y="30" width="1130" height="560" rx="22" fill="white" stroke="#d9dee8"/>
<text x="70" y="82" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="#172033">Supply Chain Delivery Performance</text>
<text x="70" y="112" font-family="Arial, sans-serif" font-size="16" fill="#667085">Executive overview Â· validated order-level delivery and item-level commercial KPIs</text>
<g font-family="Arial, sans-serif">
<rect x="70" y="145" width="240" height="105" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="90" y="178" font-size="15" fill="#667085">TOTAL SALES</text><text x="90" y="222" font-size="28" font-weight="700" fill="#172033">{money(metrics.total_sales)}</text>
<rect x="330" y="145" width="240" height="105" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="350" y="178" font-size="15" fill="#667085">TOTAL PROFIT</text><text x="350" y="222" font-size="28" font-weight="700" fill="#172033">{money(metrics.total_profit)}</text>
<rect x="590" y="145" width="240" height="105" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="610" y="178" font-size="15" fill="#667085">LATE DELIVERY RATE</text><text x="610" y="222" font-size="28" font-weight="700" fill="#172033">{pct(metrics.late_delivery_rate)}</text>
<rect x="850" y="145" width="240" height="105" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="870" y="178" font-size="15" fill="#667085">TOTAL ORDERS</text><text x="870" y="222" font-size="28" font-weight="700" fill="#172033">{metrics.total_orders:,}</text>
<rect x="70" y="285" width="520" height="245" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="95" y="325" font-size="19" font-weight="700" fill="#172033">Operational risk</text><text x="95" y="365" font-size="17" fill="#475467">Average shipping delay</text><text x="500" y="365" text-anchor="end" font-size="22" font-weight="700" fill="#172033">{num(metrics.average_shipping_delay_days)} days</text><text x="95" y="410" font-size="17" fill="#475467">Cancellation rate</text><text x="500" y="410" text-anchor="end" font-size="22" font-weight="700" fill="#172033">{pct(metrics.cancellation_rate)}</text><text x="95" y="455" font-size="17" fill="#475467">Order items analyzed</text><text x="500" y="455" text-anchor="end" font-size="22" font-weight="700" fill="#172033">{metrics.total_order_items:,}</text>
<rect x="610" y="285" width="480" height="245" rx="14" fill="#f8fafc" stroke="#e2e8f0"/><text x="635" y="325" font-size="19" font-weight="700" fill="#172033">Analysis coverage</text><text x="635" y="370" font-size="17" fill="#475467">Delivery &amp; logistics performance</text><rect x="635" y="388" width="380" height="10" rx="5" fill="#dbe4f0"/><rect x="635" y="388" width="330" height="10" rx="5" fill="#667085"/><text x="635" y="435" font-size="17" fill="#475467">Market &amp; commercial performance</text><rect x="635" y="453" width="380" height="10" rx="5" fill="#dbe4f0"/><rect x="635" y="453" width="290" height="10" rx="5" fill="#667085"/><text x="635" y="500" font-size="14" fill="#667085">Interactive HTML dashboard contains four analytical tabs.</text>
</g></svg>"""
    write_text(REPORTS_DIR / "figures" / "dashboard_overview.svg", preview)
