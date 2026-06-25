from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.io as pio


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
OUTPUT_DIR = DASHBOARD_DIR / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Input files
# ---------------------------------------------------------

LATEST_NAV_FILE = RAW_DIR / "latest_nav.csv"
NAV_HISTORY_FILE = RAW_DIR / "nav_history.csv"
MONTHLY_RETURNS_FILE = RAW_DIR / "monthly_returns.csv"
RISK_METRICS_FILE = RAW_DIR / "risk_metrics.csv"


# ---------------------------------------------------------
# Helper function
# ---------------------------------------------------------

def check_file_exists(file_path):
    if not file_path.exists():
        raise FileNotFoundError(
            f"{file_path} not found. "
            "First run: python live_nav_fetch.py, "
            "then python create_sample_datasets.py"
        )


def load_data():
    """
    Load all dashboard input datasets.
    """

    required_files = [
        LATEST_NAV_FILE,
        NAV_HISTORY_FILE,
        MONTHLY_RETURNS_FILE,
        RISK_METRICS_FILE,
    ]

    for file_path in required_files:
        check_file_exists(file_path)

    latest_nav = pd.read_csv(LATEST_NAV_FILE)
    nav_history = pd.read_csv(NAV_HISTORY_FILE)
    monthly_returns = pd.read_csv(MONTHLY_RETURNS_FILE)
    risk_metrics = pd.read_csv(RISK_METRICS_FILE)

    latest_nav["date"] = pd.to_datetime(latest_nav["date"], errors="coerce")
    nav_history["date"] = pd.to_datetime(nav_history["date"], errors="coerce")
    monthly_returns["date"] = pd.to_datetime(monthly_returns["date"], errors="coerce")

    return latest_nav, nav_history, monthly_returns, risk_metrics


def shorten_scheme_name(name):
    """
    Make long mutual fund names shorter for charts.
    """

    name = str(name)

    replacements = {
        "Fund - Growth Option - Direct Plan": "",
        "FUND-DIRECT PLAN -GROWTH": "",
        "Fund (erstwhile Bluechip Fund) - Direct Plan - Growth": "",
        "Fund - Direct Plan Growth Plan - Growth Option": "",
        "Fund - Direct Plan - Growth": "",
        "Fund - Growth - Direct": "",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    return name.strip()


# ---------------------------------------------------------
# Dashboard creation
# ---------------------------------------------------------

def create_dashboard():
    latest_nav, nav_history, monthly_returns, risk_metrics = load_data()

    latest_nav["short_name"] = latest_nav["scheme_name"].apply(shorten_scheme_name)
    nav_history["short_name"] = nav_history["scheme_name"].apply(shorten_scheme_name)
    monthly_returns["short_name"] = monthly_returns["scheme_name"].apply(shorten_scheme_name)
    risk_metrics["short_name"] = risk_metrics["scheme_name"].apply(shorten_scheme_name)

    # -----------------------------------------------------
    # Chart 1: Latest NAV comparison
    # -----------------------------------------------------

    fig_latest_nav = px.bar(
        latest_nav,
        x="short_name",
        y="nav",
        title="Latest NAV Comparison",
        labels={
            "short_name": "Mutual Fund Scheme",
            "nav": "Latest NAV",
        },
        text="nav",
    )

    fig_latest_nav.update_layout(
        xaxis_tickangle=-30,
        height=500,
    )

    # -----------------------------------------------------
    # Chart 2: NAV trend over time
    # -----------------------------------------------------

    fig_nav_trend = px.line(
        nav_history,
        x="date",
        y="nav",
        color="short_name",
        title="NAV Trend Over Time",
        labels={
            "date": "Date",
            "nav": "NAV",
            "short_name": "Scheme",
        },
    )

    fig_nav_trend.update_layout(height=600)

    # -----------------------------------------------------
    # Chart 3: Monthly returns
    # -----------------------------------------------------

    fig_monthly_returns = px.line(
        monthly_returns,
        x="date",
        y="monthly_return_percent",
        color="short_name",
        title="Monthly Return (%) Trend",
        labels={
            "date": "Date",
            "monthly_return_percent": "Monthly Return (%)",
            "short_name": "Scheme",
        },
    )

    fig_monthly_returns.update_layout(height=600)

    # -----------------------------------------------------
    # Chart 4: Risk-return scatter
    # -----------------------------------------------------

    fig_risk_return = px.scatter(
        risk_metrics,
        x="annualized_volatility",
        y="annualized_return",
        size="observations",
        color="short_name",
        hover_name="scheme_name",
        title="Risk vs Return",
        labels={
            "annualized_volatility": "Annualized Volatility",
            "annualized_return": "Annualized Return",
            "short_name": "Scheme",
        },
    )

    fig_risk_return.update_layout(height=550)

    # -----------------------------------------------------
    # Summary table
    # -----------------------------------------------------

    summary_table = latest_nav[
        [
            "scheme_code",
            "scheme_name",
            "fund_house",
            "scheme_category",
            "date",
            "nav",
        ]
    ].copy()

    summary_table["date"] = summary_table["date"].dt.strftime("%Y-%m-%d")

    table_html = summary_table.to_html(
        index=False,
        border=0,
        classes="summary-table"
    )

    # -----------------------------------------------------
    # Convert Plotly charts to HTML
    # -----------------------------------------------------

    latest_nav_html = pio.to_html(fig_latest_nav, full_html=False, include_plotlyjs="cdn")
    nav_trend_html = pio.to_html(fig_nav_trend, full_html=False, include_plotlyjs=False)
    monthly_returns_html = pio.to_html(fig_monthly_returns, full_html=False, include_plotlyjs=False)
    risk_return_html = pio.to_html(fig_risk_return, full_html=False, include_plotlyjs=False)

    # -----------------------------------------------------
    # Final HTML dashboard
    # -----------------------------------------------------

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mutual Fund Analytics Dashboard</title>

        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 30px;
                background-color: #f7f9fc;
                color: #222;
            }}

            h1 {{
                text-align: center;
                color: #1f2937;
            }}

            h2 {{
                color: #374151;
                margin-top: 40px;
            }}

            .card {{
                background-color: white;
                padding: 25px;
                margin-bottom: 30px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            }}

            .summary-table {{
                border-collapse: collapse;
                width: 100%;
                font-size: 14px;
            }}

            .summary-table th {{
                background-color: #1f2937;
                color: white;
                padding: 10px;
                text-align: left;
            }}

            .summary-table td {{
                padding: 10px;
                border-bottom: 1px solid #ddd;
            }}

            .footer {{
                text-align: center;
                margin-top: 40px;
                color: #666;
                font-size: 13px;
            }}
        </style>
    </head>

    <body>

        <h1>Mutual Fund Analytics Dashboard</h1>

        <div class="card">
            <h2>Latest NAV Summary</h2>
            {table_html}
        </div>

        <div class="card">
            {latest_nav_html}
        </div>

        <div class="card">
            {nav_trend_html}
        </div>

        <div class="card">
            {monthly_returns_html}
        </div>

        <div class="card">
            {risk_return_html}
        </div>

        <div class="footer">
            Generated using Pandas and Plotly from MFapi NAV data.
        </div>

    </body>
    </html>
    """

    output_file = OUTPUT_DIR / "mutual_fund_dashboard.html"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print("Dashboard created successfully.")
    print(f"Open this file in browser: {output_file}")


if __name__ == "__main__":
    create_dashboard()