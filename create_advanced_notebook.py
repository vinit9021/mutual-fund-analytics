from pathlib import Path
import json

Path("notebooks").mkdir(exist_ok=True)

def md(src):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": src.splitlines(True)
    }

def code(src):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src.splitlines(True)
    }

cells = []

cells.append(md("""# Advanced Mutual Fund Analytics

This notebook performs advanced analytics for the Bluestock Mutual Fund Analytics project.

Covered topics:

1. Historical VaR and CVaR at 95% confidence  
2. Rolling 90-day Sharpe ratio  
3. Investor cohort analysis  
4. SIP continuity and at-risk investor detection  
5. Simple fund recommender  
6. Sector HHI concentration analysis  
7. Advanced business insights  
"""))

cells.append(code("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from IPython.display import Markdown, display

BASE_DIR = Path.cwd()
DATA_DIR = BASE_DIR / "data" / "processed"
EDA_DIR = DATA_DIR / "eda"
PERF_DIR = DATA_DIR / "performance"
POWERBI_DIR = DATA_DIR / "powerbi"
ADV_DIR = DATA_DIR / "advanced"
CHART_DIR = BASE_DIR / "reports" / "charts"

ADV_DIR.mkdir(parents=True, exist_ok=True)
CHART_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams["figure.figsize"] = (14, 7)
pd.set_option("display.max_columns", None)

print("Advanced analytics setup completed.")
"""))

cells.append(md("""## 1. Load Required Data"""))

cells.append(code("""nav_path = EDA_DIR / "eda_nav_40_schemes.csv"
scheme_path = EDA_DIR / "eda_scheme_master_40.csv"
holdings_path = EDA_DIR / "portfolio_holdings.csv"

transactions_candidates = [
    POWERBI_DIR / "fact_transactions.csv",
    DATA_DIR / "clean_investor_transactions.csv",
    BASE_DIR / "data" / "raw" / "investor_transactions.csv"
]

fund_candidates = [
    POWERBI_DIR / "dim_fund.csv",
    PERF_DIR / "fund_scorecard.csv",
    scheme_path
]

nav = pd.read_csv(nav_path)
schemes = pd.read_csv(scheme_path)
holdings = pd.read_csv(holdings_path)

transactions = None
for p in transactions_candidates:
    if p.exists():
        transactions = pd.read_csv(p)
        print("Loaded transactions from:", p)
        break

funds = None
for p in fund_candidates:
    if p.exists():
        funds = pd.read_csv(p)
        print("Loaded fund data from:", p)
        break

nav.columns = nav.columns.str.strip().str.lower()
schemes.columns = schemes.columns.str.strip().str.lower()
holdings.columns = holdings.columns.str.strip().str.lower()

if transactions is not None:
    transactions.columns = transactions.columns.str.strip().str.lower()

if funds is not None:
    funds.columns = funds.columns.str.strip().str.lower()

nav["date"] = pd.to_datetime(nav["date"])

print("NAV shape:", nav.shape)
print("Schemes shape:", schemes.shape)
print("Holdings shape:", holdings.shape)
if transactions is not None:
    print("Transactions shape:", transactions.shape)
if funds is not None:
    print("Funds shape:", funds.shape)
"""))

cells.append(md("""## 2. Historical VaR and CVaR Report

Historical VaR at 95% is calculated as the 5th percentile of the daily return distribution.

CVaR is calculated as the average of returns below the VaR threshold.
"""))

cells.append(code("""# Detect important columns
scheme_col = "short_scheme_name" if "short_scheme_name" in nav.columns else "scheme_name"
code_col = "amfi_code" if "amfi_code" in nav.columns else "scheme_code"

if "daily_return" not in nav.columns:
    nav = nav.sort_values([code_col, "date"])
    nav["daily_return"] = nav.groupby(code_col)["nav"].pct_change()

returns = nav.dropna(subset=["daily_return"]).copy()

var_rows = []

for key, g in returns.groupby(code_col):
    fund_name = g[scheme_col].iloc[0] if scheme_col in g.columns else str(key)
    r = g["daily_return"].dropna()

    var_95 = np.percentile(r, 5)
    cvar_95 = r[r <= var_95].mean()

    var_rows.append({
        code_col: key,
        "scheme_name": fund_name,
        "var_95_daily": var_95,
        "cvar_95_daily": cvar_95,
        "var_95_percent": var_95 * 100,
        "cvar_95_percent": cvar_95 * 100,
        "observations": len(r)
    })

var_cvar_report = pd.DataFrame(var_rows)
var_cvar_report = var_cvar_report.sort_values("var_95_daily")

var_output = ADV_DIR / "var_cvar_report.csv"
var_cvar_report.to_csv(var_output, index=False)

print("Saved:", var_output)
var_cvar_report.head(10)
"""))

cells.append(md("""## 3. Rolling 90-Day Sharpe Ratio

Rolling Sharpe Ratio:

\\[
Sharpe = \\frac{Rolling\\ Mean\\ Return}{Rolling\\ Std\\ Return} \\times \\sqrt{252}
\\]

Calculated using 90 trading-day rolling window.
"""))

cells.append(code("""returns_pivot = (
    returns.pivot_table(
        index="date",
        columns=scheme_col,
        values="daily_return",
        aggfunc="mean"
    )
    .sort_index()
)

rolling_sharpe = (
    returns_pivot.rolling(90).mean()
    / returns_pivot.rolling(90).std()
) * np.sqrt(252)

# Select 5 key funds using availability and latest Sharpe
latest_sharpe = rolling_sharpe.dropna(how="all").iloc[-1].sort_values(ascending=False)
key_funds = latest_sharpe.head(5).index.tolist()

plt.figure(figsize=(15, 7))

for fund in key_funds:
    plt.plot(rolling_sharpe.index, rolling_sharpe[fund], label=fund)

plt.axhline(0, linestyle="--", linewidth=1)
plt.title("Rolling 90-Day Sharpe Ratio for 5 Key Funds")
plt.xlabel("Date")
plt.ylabel("Rolling Sharpe Ratio")
plt.legend(loc="best")
plt.tight_layout()

rolling_chart_path = CHART_DIR / "rolling_sharpe_chart.png"
plt.savefig(rolling_chart_path, dpi=300, bbox_inches="tight")
plt.show()

print("Saved:", rolling_chart_path)
"""))

cells.append(md("""## 4. Investor Cohort Analysis

Investors are grouped by their first transaction year.

For every cohort, we calculate:

- Number of investors  
- Average SIP amount  
- Total invested amount  
- Top preferred fund  
"""))

cells.append(code("""cohort_summary = pd.DataFrame()

if transactions is not None:
    tx = transactions.copy()

    date_col = "date" if "date" in tx.columns else "transaction_date"
    investor_col = "investor_id" if "investor_id" in tx.columns else None

    if investor_col is None:
        tx["investor_id"] = ["INV" + str(i).zfill(5) for i in range(len(tx))]
        investor_col = "investor_id"

    tx[date_col] = pd.to_datetime(tx[date_col])

    amount_col = "transaction_amount" if "transaction_amount" in tx.columns else None
    sip_col = "monthly_sip_amount" if "monthly_sip_amount" in tx.columns else amount_col

    fund_pref_col = None
    for c in ["short_scheme_name", "scheme_name", "fund_house", "amfi_code", "scheme_code"]:
        if c in tx.columns:
            fund_pref_col = c
            break

    first_year = tx.groupby(investor_col)[date_col].min().dt.year.rename("cohort_year")
    tx = tx.merge(first_year, on=investor_col, how="left")

    def top_pref(x):
        if fund_pref_col:
            return x[fund_pref_col].mode().iloc[0]
        return "Not Available"

    cohort_summary = (
        tx.groupby("cohort_year")
        .apply(lambda g: pd.Series({
            "investors": g[investor_col].nunique(),
            "avg_sip_amount": g[sip_col].mean() if sip_col else np.nan,
            "total_invested": g[amount_col].sum() if amount_col else np.nan,
            "top_fund_preference": top_pref(g)
        }))
        .reset_index()
        .sort_values("cohort_year")
    )

    display(cohort_summary)
else:
    print("Transactions data not found. Cohort analysis skipped.")
"""))

cells.append(md("""## 5. SIP Continuity Analysis

For investors with 6 or more SIP transactions:

- Average gap between SIP dates is calculated  
- Investors with average gap greater than 35 days are flagged as **At-Risk**  
"""))

cells.append(code("""sip_continuity = pd.DataFrame()

if transactions is not None:
    tx = transactions.copy()
    date_col = "date" if "date" in tx.columns else "transaction_date"
    investor_col = "investor_id" if "investor_id" in tx.columns else "investor_id"

    if investor_col not in tx.columns:
        tx[investor_col] = ["INV" + str(i).zfill(5) for i in range(len(tx))]

    tx[date_col] = pd.to_datetime(tx[date_col])

    if "transaction_type" in tx.columns:
        sip_tx = tx[tx["transaction_type"].astype(str).str.contains("SIP", case=False, na=False)].copy()
    elif "monthly_sip_amount" in tx.columns:
        sip_tx = tx[tx["monthly_sip_amount"].fillna(0) > 0].copy()
    else:
        sip_tx = tx.copy()

    sip_tx = sip_tx.sort_values([investor_col, date_col])
    sip_tx["gap_days"] = sip_tx.groupby(investor_col)[date_col].diff().dt.days

    sip_counts = sip_tx.groupby(investor_col).size().rename("sip_transaction_count")
    avg_gap = sip_tx.groupby(investor_col)["gap_days"].mean().rename("avg_gap_days")

    sip_continuity = pd.concat([sip_counts, avg_gap], axis=1).reset_index()
    sip_continuity = sip_continuity[sip_continuity["sip_transaction_count"] >= 6].copy()
    sip_continuity["risk_status"] = np.where(
        sip_continuity["avg_gap_days"] > 35,
        "At-Risk",
        "Continuous"
    )

    continuity_rate = (
        (sip_continuity["risk_status"] == "Continuous").mean() * 100
        if len(sip_continuity) else 0
    )

    print("SIP investors with 6+ transactions:", len(sip_continuity))
    print("SIP continuity rate:", round(continuity_rate, 2), "%")

    display(sip_continuity.head(10))
else:
    print("Transactions data not found. SIP continuity analysis skipped.")
"""))

cells.append(md("""## 6. Simple Fund Recommender

Risk appetite input:

- Low  
- Moderate  
- High  

The recommender returns the top 3 funds by Sharpe Ratio within the matching risk grade.
"""))

cells.append(code("""def recommend_funds(risk_appetite="Moderate"):
    risk_appetite = risk_appetite.strip().capitalize()

    df = funds.copy()

    if "short_scheme_name" not in df.columns:
        if "scheme_name" in df.columns:
            df["short_scheme_name"] = df["scheme_name"]
        else:
            df["short_scheme_name"] = "Unknown Fund"

    if "risk_grade" not in df.columns:
        vol_col = "annualized_volatility" if "annualized_volatility" in df.columns else None
        if vol_col:
            df["risk_grade"] = pd.qcut(
                df[vol_col].rank(method="first"),
                q=3,
                labels=["Low", "Moderate", "High"]
            )
        else:
            df["risk_grade"] = "Moderate"

    if "sharpe_ratio" not in df.columns:
        raise ValueError("sharpe_ratio column not found.")

    result = (
        df[df["risk_grade"].astype(str).str.lower() == risk_appetite.lower()]
        .sort_values("sharpe_ratio", ascending=False)
        .head(3)
    )

    cols = [
        "short_scheme_name",
        "fund_house",
        "category",
        "risk_grade",
        "sharpe_ratio",
        "cagr_3yr_percent",
        "max_drawdown_percent",
        "fund_score"
    ]

    cols = [c for c in cols if c in result.columns]

    return result[cols].reset_index(drop=True)

recommendation_table = recommend_funds("Moderate")
recommendation_table
"""))

cells.append(md("""## 7. Sector HHI Concentration Analysis

Herfindahl-Hirschman Index:

\\[
HHI = \\sum weight_i^2
\\]

Higher HHI means the fund portfolio is more concentrated.
"""))

cells.append(code("""h = holdings.copy()

fund_col = None
for c in ["short_scheme_name", "scheme_name", "amfi_code", "scheme_code"]:
    if c in h.columns:
        fund_col = c
        break

sector_col = "sector" if "sector" in h.columns else None

weight_col = None
for c in ["weight", "weight_percent", "holding_percent", "sector_weight", "allocation_percent"]:
    if c in h.columns:
        weight_col = c
        break

if fund_col is None or sector_col is None or weight_col is None:
    print("Required holdings columns not found.")
    print("Available columns:", h.columns.tolist())
    hhi_report = pd.DataFrame()
else:
    h[weight_col] = pd.to_numeric(h[weight_col], errors="coerce")
    sector_weights = (
        h.groupby([fund_col, sector_col])[weight_col]
        .sum()
        .reset_index()
    )

    # Convert percentage weights to decimals if needed
    if sector_weights[weight_col].max() > 1:
        sector_weights["weight_decimal"] = sector_weights[weight_col] / 100
    else:
        sector_weights["weight_decimal"] = sector_weights[weight_col]

    hhi_report = (
        sector_weights.groupby(fund_col)
        .apply(lambda g: pd.Series({
            "sector_hhi": np.sum(g["weight_decimal"] ** 2),
            "top_sector": g.sort_values("weight_decimal", ascending=False)[sector_col].iloc[0],
            "top_sector_weight_percent": g["weight_decimal"].max() * 100,
            "sector_count": g[sector_col].nunique()
        }))
        .reset_index()
        .sort_values("sector_hhi", ascending=False)
    )

    display(hhi_report.head(10))

    plt.figure(figsize=(14, 7))
    plt.barh(hhi_report[fund_col].astype(str).head(15), hhi_report["sector_hhi"].head(15))
    plt.gca().invert_yaxis()
    plt.title("Top 15 Funds by Sector HHI Concentration")
    plt.xlabel("Sector HHI")
    plt.ylabel("Fund")
    plt.tight_layout()
    plt.show()
"""))

cells.append(md("""## 8. Advanced Insights"""))

cells.append(code("""insights = []

# Insight 1: Highest VaR risk
if not var_cvar_report.empty:
    worst_var = var_cvar_report.iloc[0]
    insights.append(
        f"1. **Highest downside VaR risk:** {worst_var['scheme_name']} has the lowest 95% VaR at "
        f"{worst_var['var_95_percent']:.2f}%, meaning it has the largest one-day downside loss threshold among the analysed schemes."
    )

# Insight 2: Highest CVaR risk
if not var_cvar_report.empty:
    worst_cvar = var_cvar_report.sort_values("cvar_95_daily").iloc[0]
    insights.append(
        f"2. **Highest tail-risk fund:** {worst_cvar['scheme_name']} has the worst CVaR at "
        f"{worst_cvar['cvar_95_percent']:.2f}%, showing that losses beyond the VaR threshold are more severe for this fund."
    )

# Insight 3: Cohort
if not cohort_summary.empty:
    top_cohort = cohort_summary.sort_values("total_invested", ascending=False).iloc[0]
    insights.append(
        f"3. **Strongest investor cohort:** The {int(top_cohort['cohort_year'])} cohort invested the highest total amount of "
        f"{top_cohort['total_invested']:.2f}, with average SIP amount of {top_cohort['avg_sip_amount']:.2f}."
    )

# Insight 4: SIP continuity
if not sip_continuity.empty:
    continuity_rate = (sip_continuity["risk_status"] == "Continuous").mean() * 100
    at_risk_count = (sip_continuity["risk_status"] == "At-Risk").sum()
    insights.append(
        f"4. **SIP continuity:** {continuity_rate:.2f}% of regular SIP investors are continuous, while "
        f"{at_risk_count} investors are flagged as at-risk due to average SIP gaps above 35 days."
    )

# Insight 5: HHI concentration
if not hhi_report.empty:
    high_hhi = hhi_report.iloc[0]
    insights.append(
        f"5. **Highest sector concentration:** {high_hhi[fund_col]} has the highest sector HHI of "
        f"{high_hhi['sector_hhi']:.3f}, mainly concentrated in {high_hhi['top_sector']}."
    )

insights_md = "## Final 5 Advanced Insights\\n\\n" + "\\n\\n".join(insights)
display(Markdown(insights_md))
"""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.12"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

out = Path("notebooks") / "Advanced_Analytics.ipynb"
out.write_text(json.dumps(nb, indent=2), encoding="utf-8")
print("Created:", out)
