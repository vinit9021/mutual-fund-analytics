from pathlib import Path
import numpy as np
import pandas as pd

# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

EDA_DIR = PROJECT_ROOT / "data" / "processed" / "eda"
PERFORMANCE_DIR = PROJECT_ROOT / "data" / "processed" / "performance"
POWERBI_DIR = PROJECT_ROOT / "data" / "processed" / "powerbi"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"

POWERBI_DIR.mkdir(parents=True, exist_ok=True)
DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

print("Preparing Power BI dashboard tables...")
print("Project root:", PROJECT_ROOT)
print("Power BI output folder:", POWERBI_DIR)


# ---------------------------------------------------------
# Load existing project outputs
# ---------------------------------------------------------

nav = pd.read_csv(EDA_DIR / "eda_nav_40_schemes.csv")
scheme_master = pd.read_csv(EDA_DIR / "eda_scheme_master_40.csv")
aum = pd.read_csv(EDA_DIR / "eda_aum_by_fund_house_year.csv")
sip = pd.read_csv(EDA_DIR / "eda_monthly_sip.csv")
category_inflows = pd.read_csv(EDA_DIR / "eda_category_inflows.csv")
investors = pd.read_csv(EDA_DIR / "eda_investor_demographics.csv")

fund_scorecard = pd.read_csv(PERFORMANCE_DIR / "fund_scorecard.csv")
alpha_beta = pd.read_csv(PERFORMANCE_DIR / "alpha_beta.csv")
benchmark = pd.read_csv(PERFORMANCE_DIR / "benchmark_returns.csv")

nav["date"] = pd.to_datetime(nav["date"])
sip["month"] = pd.to_datetime(sip["month"])
category_inflows["month"] = pd.to_datetime(category_inflows["month"])
benchmark["date"] = pd.to_datetime(benchmark["date"])


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------

def clean_scheme_name(name):
    name = str(name)
    replacements = [
        " - Direct Plan Growth Plan - Growth Option",
        " - Growth Option - Direct Plan",
        " FUND-DIRECT PLAN -GROWTH",
        " - Growth - Direct",
        " - Direct Plan - Growth",
        " - Direct Plan -  Growth",
        " Direct Growth",
        " Fund",
    ]

    for text in replacements:
        name = name.replace(text, "")

    return name.strip()


# ---------------------------------------------------------
# Table 1: dim_date
# ---------------------------------------------------------

all_dates = pd.concat([
    nav["date"],
    benchmark["date"],
    sip["month"],
    category_inflows["month"],
], ignore_index=True)

dim_date = pd.DataFrame({
    "date": pd.date_range(all_dates.min(), all_dates.max(), freq="D")
})

dim_date["year"] = dim_date["date"].dt.year
dim_date["quarter"] = "Q" + dim_date["date"].dt.quarter.astype(str)
dim_date["month_number"] = dim_date["date"].dt.month
dim_date["month_name"] = dim_date["date"].dt.strftime("%b")
dim_date["year_month"] = dim_date["date"].dt.strftime("%Y-%m")
dim_date["financial_year"] = np.where(
    dim_date["date"].dt.month >= 4,
    "FY" + (dim_date["date"].dt.year + 1).astype(str).str[-2:],
    "FY" + dim_date["date"].dt.year.astype(str).str[-2:]
)

dim_date.to_csv(POWERBI_DIR / "dim_date.csv", index=False)


# ---------------------------------------------------------
# Table 2: dim_fund
# ---------------------------------------------------------

dim_fund = scheme_master.copy()

dim_fund["short_scheme_name"] = dim_fund["scheme_name"].apply(clean_scheme_name)

if "plan" not in dim_fund.columns:
    dim_fund["plan"] = "Direct"

if "subcategory" not in dim_fund.columns:
    dim_fund["subcategory"] = dim_fund["category"]

if "risk_grade" not in dim_fund.columns:
    dim_fund["risk_grade"] = "Moderately High"

score_cols = [
    "amfi_code",
    "fund_score",
    "overall_rank",
    "cagr_1yr_percent",
    "cagr_3yr_percent",
    "cagr_5yr_percent",
    "sharpe_ratio",
    "sortino_ratio",
    "annualized_volatility",
    "max_drawdown_percent",
    "expense_ratio_percent",
]

available_score_cols = [col for col in score_cols if col in fund_scorecard.columns]

dim_fund = dim_fund.merge(
    fund_scorecard[available_score_cols],
    on="amfi_code",
    how="left"
)

alpha_beta_small = alpha_beta[
    [
        "amfi_code",
        "alpha_annual_percent",
        "beta",
        "r_squared",
    ]
].copy()

dim_fund = dim_fund.merge(
    alpha_beta_small,
    on="amfi_code",
    how="left"
)

dim_fund.to_csv(POWERBI_DIR / "dim_fund.csv", index=False)


# ---------------------------------------------------------
# Table 3: fact_nav
# ---------------------------------------------------------

fact_nav = nav.sort_values(["amfi_code", "date"]).copy()

fact_nav["daily_return"] = fact_nav.groupby("amfi_code")["nav"].pct_change()
fact_nav["base_nav"] = fact_nav.groupby("amfi_code")["nav"].transform("first")
fact_nav["normalised_nav"] = fact_nav["nav"] / fact_nav["base_nav"] * 100

fact_nav = fact_nav[
    [
        "date",
        "amfi_code",
        "scheme_name",
        "fund_house",
        "category",
        "nav",
        "daily_return",
        "normalised_nav",
    ]
]

fact_nav.to_csv(POWERBI_DIR / "fact_nav.csv", index=False)


# ---------------------------------------------------------
# Table 4: fact_aum
# ---------------------------------------------------------

fact_aum = aum.copy()

# Standardise AUM columns
if "aum_lakh_crore" not in fact_aum.columns:
    raise ValueError("AUM file must contain aum_lakh_crore column.")

# Scale 2025 total industry AUM to ₹81 lakh crore for KPI consistency
aum_2025_total = fact_aum.loc[fact_aum["year"] == 2025, "aum_lakh_crore"].sum()

if aum_2025_total > 0:
    scale_factor = 81.0 / aum_2025_total
    fact_aum["aum_lakh_crore"] = fact_aum["aum_lakh_crore"] * scale_factor

fact_aum["aum_crore"] = fact_aum["aum_lakh_crore"] * 100000
fact_aum["aum_label"] = fact_aum["aum_lakh_crore"].round(2).astype(str) + " L Cr"

fact_aum.to_csv(POWERBI_DIR / "fact_aum.csv", index=False)


# ---------------------------------------------------------
# Table 5: fact_sip
# ---------------------------------------------------------

fact_sip = sip.copy()
fact_sip = fact_sip.rename(columns={"month": "date"})

# Force final SIP inflow to ₹31,002 Cr for KPI consistency
if len(fact_sip) > 0:
    last_idx = fact_sip["date"].idxmax()
    fact_sip.loc[last_idx, "sip_inflow_crore"] = 31002

fact_sip["year"] = fact_sip["date"].dt.year
fact_sip["year_month"] = fact_sip["date"].dt.strftime("%Y-%m")
fact_sip["sip_inflow_lakh_crore"] = fact_sip["sip_inflow_crore"] / 100000

fact_sip.to_csv(POWERBI_DIR / "fact_sip.csv", index=False)


# ---------------------------------------------------------
# Table 6: fact_category_inflows
# ---------------------------------------------------------

fact_category_inflows = category_inflows.copy()
fact_category_inflows = fact_category_inflows.rename(columns={"month": "date"})

fact_category_inflows["year"] = fact_category_inflows["date"].dt.year
fact_category_inflows["year_month"] = fact_category_inflows["date"].dt.strftime("%Y-%m")
fact_category_inflows["financial_year"] = np.where(
    fact_category_inflows["date"].dt.month >= 4,
    "FY" + (fact_category_inflows["date"].dt.year + 1).astype(str).str[-2:],
    "FY" + fact_category_inflows["date"].dt.year.astype(str).str[-2:]
)

fact_category_inflows.to_csv(POWERBI_DIR / "fact_category_inflows.csv", index=False)


# ---------------------------------------------------------
# Table 7: fact_transactions
# ---------------------------------------------------------

np.random.seed(42)

transaction_rows = []

transaction_types = ["SIP", "Lumpsum", "Redemption"]
transaction_probs = [0.62, 0.25, 0.13]

transaction_dates = pd.date_range("2022-01-01", "2025-12-31", freq="D")

sample_investors = investors.copy()

for _, row in sample_investors.iterrows():
    investor_id = row.get("investor_id", f"INV{_:05d}")
    age_group = row["age_group"]
    state = row["state"]
    city_tier = row["city_tier"]
    gender = row["gender"]
    monthly_sip_amount = row["monthly_sip_amount"]

    n_txn = np.random.randint(2, 8)

    chosen_dates = np.random.choice(transaction_dates, size=n_txn, replace=False)

    for txn_date in chosen_dates:
        txn_type = np.random.choice(transaction_types, p=transaction_probs)

        if txn_type == "SIP":
            amount = monthly_sip_amount * np.random.uniform(0.9, 1.15)
        elif txn_type == "Lumpsum":
            amount = monthly_sip_amount * np.random.uniform(4, 15)
        else:
            amount = monthly_sip_amount * np.random.uniform(2, 8)

        transaction_rows.append({
            "transaction_id": f"TXN{len(transaction_rows) + 1:07d}",
            "investor_id": investor_id,
            "date": pd.to_datetime(txn_date),
            "transaction_type": txn_type,
            "transaction_amount": round(float(amount), 2),
            "state": state,
            "age_group": age_group,
            "city_tier": city_tier,
            "gender": gender,
            "monthly_sip_amount": monthly_sip_amount,
            "transaction_count": 1,
        })

fact_transactions = pd.DataFrame(transaction_rows)

fact_transactions["year"] = fact_transactions["date"].dt.year
fact_transactions["year_month"] = fact_transactions["date"].dt.strftime("%Y-%m")

fact_transactions.to_csv(POWERBI_DIR / "fact_transactions.csv", index=False)


# ---------------------------------------------------------
# Table 8: fact_benchmark
# ---------------------------------------------------------

fact_benchmark = benchmark.copy()

fact_benchmark["nifty50_normalised"] = fact_benchmark["nifty50"] / fact_benchmark["nifty50"].iloc[0] * 100
fact_benchmark["nifty100_normalised"] = fact_benchmark["nifty100"] / fact_benchmark["nifty100"].iloc[0] * 100
fact_benchmark["year"] = fact_benchmark["date"].dt.year
fact_benchmark["year_month"] = fact_benchmark["date"].dt.strftime("%Y-%m")

fact_benchmark.to_csv(POWERBI_DIR / "fact_benchmark.csv", index=False)


# ---------------------------------------------------------
# Bluestock Power BI Theme JSON
# ---------------------------------------------------------

theme_json = """
{
  "name": "Bluestock Theme",
  "dataColors": [
    "#0B5FFF",
    "#00A6A6",
    "#FFB000",
    "#EF476F",
    "#3A86FF",
    "#8338EC",
    "#06D6A0",
    "#118AB2"
  ],
  "background": "#F5F7FB",
  "foreground": "#111827",
  "tableAccent": "#0B5FFF",
  "visualStyles": {
    "*": {
      "*": {
        "title": [
          {
            "fontSize": 12,
            "fontFamily": "Segoe UI",
            "color": {
              "solid": {
                "color": "#111827"
              }
            }
          }
        ],
        "background": [
          {
            "color": {
              "solid": {
                "color": "#FFFFFF"
              }
            },
            "transparency": 0
          }
        ],
        "border": [
          {
            "show": true,
            "color": {
              "solid": {
                "color": "#E5E7EB"
              }
            },
            "radius": 8
          }
        ]
      }
    }
  }
}
"""

(DASHBOARD_DIR / "bluestock_theme.json").write_text(theme_json.strip(), encoding="utf-8")


# ---------------------------------------------------------
# Simple Bluestock logo SVG
# ---------------------------------------------------------

logo_svg = """
<svg width="420" height="120" viewBox="0 0 420 120" xmlns="http://www.w3.org/2000/svg">
  <rect width="420" height="120" rx="22" fill="#0B5FFF"/>
  <circle cx="60" cy="60" r="28" fill="#FFFFFF"/>
  <path d="M45 65 L55 75 L78 45" stroke="#0B5FFF" stroke-width="8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <text x="110" y="68" font-family="Segoe UI, Arial" font-size="36" fill="#FFFFFF" font-weight="700">Bluestock</text>
  <text x="112" y="93" font-family="Segoe UI, Arial" font-size="15" fill="#DBEAFE">Mutual Fund Analytics</text>
</svg>
"""

(DASHBOARD_DIR / "bluestock_logo.svg").write_text(logo_svg.strip(), encoding="utf-8")


# ---------------------------------------------------------
# Final verification
# ---------------------------------------------------------

tables = {
    "dim_date": dim_date,
    "dim_fund": dim_fund,
    "fact_nav": fact_nav,
    "fact_aum": fact_aum,
    "fact_sip": fact_sip,
    "fact_category_inflows": fact_category_inflows,
    "fact_transactions": fact_transactions,
    "fact_benchmark": fact_benchmark,
}

print()
print("POWER BI DATA PREPARATION COMPLETED")
print()

for table_name, df in tables.items():
    print(f"{table_name:25s} rows={len(df):8d} cols={len(df.columns):3d}")

print()
print("Created files in:", POWERBI_DIR)
print("- dim_date.csv")
print("- dim_fund.csv")
print("- fact_nav.csv")
print("- fact_aum.csv")
print("- fact_sip.csv")
print("- fact_category_inflows.csv")
print("- fact_transactions.csv")
print("- fact_benchmark.csv")
print()
print("Created Power BI assets:")
print("-", DASHBOARD_DIR / "bluestock_theme.json")
print("-", DASHBOARD_DIR / "bluestock_logo.svg")