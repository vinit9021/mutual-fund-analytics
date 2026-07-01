import pandas as pd
import numpy as np
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent

def load_funds():
    paths = [
        BASE_DIR / "data" / "processed" / "powerbi" / "dim_fund.csv",
        BASE_DIR / "data" / "processed" / "performance" / "fund_scorecard.csv"
    ]

    df = None
    for p in paths:
        if p.exists():
            df = pd.read_csv(p)
            print(f"Loaded data from: {p}")
            break

    if df is None:
        raise FileNotFoundError("No fund data file found.")

    df.columns = df.columns.str.strip().str.lower()

    if "short_scheme_name" not in df.columns:
        df["short_scheme_name"] = df["scheme_name"] if "scheme_name" in df.columns else "Unknown Fund"

    if "sharpe_ratio" not in df.columns:
        raise ValueError("sharpe_ratio column not found.")

    df["sharpe_ratio"] = pd.to_numeric(df["sharpe_ratio"], errors="coerce")

    vol_col = None
    for c in ["annualized_volatility", "annualized_volatility_percent", "volatility"]:
        if c in df.columns:
            vol_col = c
            break

    if vol_col is not None:
        df[vol_col] = pd.to_numeric(df[vol_col], errors="coerce")
        df["risk_grade_clean"] = pd.qcut(
            df[vol_col].rank(method="first"),
            q=3,
            labels=["Low", "Moderate", "High"]
        )
    else:
        df["risk_grade_clean"] = "Moderate"

    return df

def recommend_funds(risk_appetite):
    risk_appetite = risk_appetite.strip().capitalize()

    if risk_appetite not in ["Low", "Moderate", "High"]:
        raise ValueError("Risk appetite must be Low, Moderate, or High.")

    df = load_funds()

    filtered = df[df["risk_grade_clean"].astype(str).str.lower() == risk_appetite.lower()].copy()

    cols = [
        "short_scheme_name",
        "fund_house",
        "category",
        "risk_grade_clean",
        "sharpe_ratio",
        "cagr_3yr_percent",
        "max_drawdown_percent",
        "fund_score"
    ]

    cols = [c for c in cols if c in filtered.columns]

    result = (
        filtered.dropna(subset=["sharpe_ratio"])
        .sort_values("sharpe_ratio", ascending=False)
        .head(3)[cols]
        .reset_index(drop=True)
    )

    print(f"\nTop 3 Recommended Funds for {risk_appetite} Risk Appetite")
    print("=" * 90)

    if result.empty:
        print("No funds found.")
    else:
        print(result.to_string(index=False))

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        risk = sys.argv[1]
    else:
        risk = input("Enter risk appetite (Low / Moderate / High): ")

    recommend_funds(risk)
