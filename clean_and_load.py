from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SQL_DIR = PROJECT_ROOT / "sql"
REPORTS_DIR = PROJECT_ROOT / "reports"

DB_PATH = PROJECT_ROOT / "bluestock_mf.db"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
SQL_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Utility functions
# ---------------------------------------------------------

def read_csv_required(file_name: str) -> pd.DataFrame:
    file_path = RAW_DIR / file_name

    if not file_path.exists():
        raise FileNotFoundError(f"Required file not found: {file_path}")

    return pd.read_csv(file_path)


def save_processed(df: pd.DataFrame, file_name: str):
    output_path = PROCESSED_DIR / file_name
    df.to_csv(output_path, index=False)
    print(f"Saved {file_name}: shape={df.shape}")


def standardize_code_column(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "amfi_code" not in df.columns:
        if "scheme_code" in df.columns:
            df = df.rename(columns={"scheme_code": "amfi_code"})
        elif "code" in df.columns:
            df = df.rename(columns={"code": "amfi_code"})

    if "amfi_code" in df.columns:
        df["amfi_code"] = df["amfi_code"].astype(str).str.strip()

    return df


def parse_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=False)


# ---------------------------------------------------------
# Generate missing starter Day 2 datasets
# ---------------------------------------------------------

def generate_investor_transactions_if_missing():
    """
    If official investor_transactions.csv is not available,
    generate a starter transaction dataset from existing fund data.
    """

    output_file = RAW_DIR / "investor_transactions.csv"

    if output_file.exists():
        print("investor_transactions.csv already exists. Using existing file.")
        return

    print("investor_transactions.csv not found. Generating starter file...")

    fund_master = read_csv_required("fund_master.csv")
    nav_history = read_csv_required("nav_history.csv")

    fund_master = standardize_code_column(fund_master)
    nav_history = standardize_code_column(nav_history)

    nav_history["date"] = parse_date_series(nav_history["date"])
    nav_history = nav_history.dropna(subset=["date"])

    rng = np.random.default_rng(42)

    schemes = fund_master["amfi_code"].dropna().unique()
    dates = nav_history["date"].dropna().unique()

    states = [
        "Maharashtra",
        "Karnataka",
        "Delhi",
        "Gujarat",
        "Tamil Nadu",
        "Telangana",
        "West Bengal",
        "Rajasthan",
        "Uttar Pradesh",
        "Punjab",
    ]

    transaction_variants = [
        "sip",
        "SIP",
        "Systematic Investment Plan",
        "lumpsum",
        "Lump Sum",
        "LUMPSUM",
        "redemption",
        "Redeem",
        "REDEMPTION",
    ]

    kyc_variants = [
        "verified",
        "Verified",
        "KYC Verified",
        "pending",
        "Pending",
        "rejected",
        "Rejected",
    ]

    rows = []

    for i in range(1, 1201):
        amfi_code = rng.choice(schemes)
        txn_date = pd.Timestamp(rng.choice(dates))

        txn_type = rng.choice(
            transaction_variants,
            p=[0.20, 0.20, 0.10, 0.15, 0.10, 0.05, 0.08, 0.06, 0.06],
        )

        amount = round(float(rng.lognormal(mean=9.2, sigma=0.7)), 2)

        rows.append(
            {
                "transaction_id": f"TXN{i:06d}",
                "investor_id": f"INV{rng.integers(1000, 9999)}",
                "amfi_code": amfi_code,
                "transaction_date": txn_date.strftime("%Y-%m-%d"),
                "transaction_type": txn_type,
                "amount": amount,
                "state": rng.choice(states),
                "kyc_status": rng.choice(kyc_variants),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(output_file, index=False)

    print(f"Generated starter investor_transactions.csv: {df.shape}")


def calculate_period_return(nav_df, amfi_code, latest_date, days):
    fund_df = nav_df[nav_df["amfi_code"] == amfi_code].copy()
    fund_df = fund_df.sort_values("date")

    if fund_df.empty:
        return np.nan

    latest_nav = fund_df[fund_df["date"] <= latest_date].tail(1)["nav"]

    if latest_nav.empty:
        return np.nan

    latest_nav = latest_nav.iloc[0]

    target_date = latest_date - pd.Timedelta(days=days)
    past_df = fund_df[fund_df["date"] <= target_date]

    if past_df.empty:
        return np.nan

    past_nav = past_df.tail(1)["nav"].iloc[0]

    if past_nav <= 0:
        return np.nan

    return ((latest_nav / past_nav) - 1) * 100


def generate_scheme_performance_if_missing():
    """
    If official scheme_performance.csv is not available,
    generate starter performance dataset using NAV history.
    """

    output_file = RAW_DIR / "scheme_performance.csv"

    if output_file.exists():
        print("scheme_performance.csv already exists. Using existing file.")
        return

    print("scheme_performance.csv not found. Generating starter file...")

    fund_master = read_csv_required("fund_master.csv")
    nav_history = read_csv_required("nav_history.csv")

    fund_master = standardize_code_column(fund_master)
    nav_history = standardize_code_column(nav_history)

    nav_history["date"] = parse_date_series(nav_history["date"])
    nav_history["nav"] = pd.to_numeric(nav_history["nav"], errors="coerce")
    nav_history = nav_history.dropna(subset=["amfi_code", "date", "nav"])

    rng = np.random.default_rng(7)

    rows = []

    for _, fund in fund_master.iterrows():
        amfi_code = str(fund["amfi_code"])

        fund_nav = nav_history[nav_history["amfi_code"] == amfi_code]

        if fund_nav.empty:
            continue

        latest_date = fund_nav["date"].max()

        rows.append(
            {
                "amfi_code": amfi_code,
                "scheme_name": fund.get("scheme_name"),
                "as_of_date": latest_date.strftime("%Y-%m-%d"),
                "return_1m": calculate_period_return(nav_history, amfi_code, latest_date, 30),
                "return_3m": calculate_period_return(nav_history, amfi_code, latest_date, 90),
                "return_6m": calculate_period_return(nav_history, amfi_code, latest_date, 180),
                "return_1y": calculate_period_return(nav_history, amfi_code, latest_date, 365),
                "return_3y": calculate_period_return(nav_history, amfi_code, latest_date, 365 * 3),
                "return_5y": calculate_period_return(nav_history, amfi_code, latest_date, 365 * 5),
                "expense_ratio": round(float(rng.uniform(0.35, 1.35)), 2),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(output_file, index=False)

    print(f"Generated starter scheme_performance.csv: {df.shape}")


def generate_aum_history_if_missing():
    """
    Generate starter AUM data because Day 2 SQL requires fact_aum.
    """

    output_file = RAW_DIR / "aum_history.csv"

    if output_file.exists():
        print("aum_history.csv already exists. Using existing file.")
        return

    print("aum_history.csv not found. Generating starter file...")

    fund_master = read_csv_required("fund_master.csv")
    nav_history = read_csv_required("nav_history.csv")

    fund_master = standardize_code_column(fund_master)
    nav_history = standardize_code_column(nav_history)

    nav_history["date"] = parse_date_series(nav_history["date"])
    nav_history = nav_history.dropna(subset=["date"])

    rng = np.random.default_rng(99)

    rows = []

    for _, fund in fund_master.iterrows():
        amfi_code = str(fund["amfi_code"])
        scheme_name = fund.get("scheme_name")

        fund_nav = nav_history[nav_history["amfi_code"] == amfi_code].copy()

        if fund_nav.empty:
            continue

        fund_nav["month"] = fund_nav["date"].dt.to_period("M")

        month_end_dates = (
            fund_nav.sort_values("date")
            .groupby("month")
            .tail(1)["date"]
            .sort_values()
            .tolist()
        )

        base_aum = float(rng.uniform(8000, 35000))

        for i, dt in enumerate(month_end_dates):
            growth_factor = 1 + (i * rng.uniform(0.001, 0.004))
            noise = rng.normal(0, 300)
            aum = max(base_aum * growth_factor + noise, 1000)

            rows.append(
                {
                    "amfi_code": amfi_code,
                    "scheme_name": scheme_name,
                    "aum_date": pd.Timestamp(dt).strftime("%Y-%m-%d"),
                    "aum_crore": round(float(aum), 2),
                }
            )

    df = pd.DataFrame(rows)
    df.to_csv(output_file, index=False)

    print(f"Generated starter aum_history.csv: {df.shape}")


# ---------------------------------------------------------
# Cleaning functions
# ---------------------------------------------------------

def clean_fund_master() -> pd.DataFrame:
    df = read_csv_required("fund_master.csv")
    df = standardize_code_column(df)

    required_cols = [
        "amfi_code",
        "scheme_name",
        "fund_house",
        "scheme_type",
        "scheme_category",
        "category",
        "sub_category",
        "risk_grade",
        "plan_type",
        "option_type",
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    df["amfi_code"] = df["amfi_code"].astype(str).str.strip()
    df["scheme_name"] = df["scheme_name"].astype(str).str.strip()
    df["fund_house"] = df["fund_house"].astype(str).str.strip()

    df = df.drop_duplicates(subset=["amfi_code"])
    df = df[df["amfi_code"].notna()]

    return df[required_cols]


def clean_nav_history() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Day 2 nav_history cleaning:
    - Parse dates
    - Rename scheme_code to amfi_code
    - Sort by amfi_code and date
    - Remove duplicate amfi_code-date rows
    - Validate NAV > 0
    - Forward-fill missing NAV across daily calendar
    """

    raw = read_csv_required("nav_history.csv")
    df = standardize_code_column(raw)

    quality_rows = []

    df["date"] = parse_date_series(df["date"])
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")

    before_rows = len(df)

    invalid_date_count = df["date"].isna().sum()
    invalid_nav_count = df["nav"].isna().sum()
    non_positive_nav_count = (df["nav"] <= 0).sum()

    quality_rows.append(
        {
            "dataset": "nav_history",
            "check_name": "invalid_dates",
            "issue_count": int(invalid_date_count),
            "action": "Rows with invalid dates removed",
        }
    )

    quality_rows.append(
        {
            "dataset": "nav_history",
            "check_name": "invalid_nav",
            "issue_count": int(invalid_nav_count),
            "action": "Rows with invalid NAV removed",
        }
    )

    quality_rows.append(
        {
            "dataset": "nav_history",
            "check_name": "non_positive_nav",
            "issue_count": int(non_positive_nav_count),
            "action": "Rows with NAV <= 0 removed",
        }
    )

    df = df.dropna(subset=["amfi_code", "date", "nav"])
    df = df[df["nav"] > 0]

    duplicate_count = df.duplicated(subset=["amfi_code", "date"]).sum()

    quality_rows.append(
        {
            "dataset": "nav_history",
            "check_name": "duplicate_amfi_code_date",
            "issue_count": int(duplicate_count),
            "action": "Duplicates removed, last value kept",
        }
    )

    df = df.drop_duplicates(subset=["amfi_code", "date"], keep="last")
    df = df.sort_values(["amfi_code", "date"])

    filled_groups = []

    metadata_cols = [
        col for col in [
            "amfi_code",
            "scheme_name",
            "fund_house",
            "scheme_type",
            "scheme_category",
        ]
        if col in df.columns
    ]

    for amfi_code, group in df.groupby("amfi_code"):
        group = group.sort_values("date").set_index("date")

        full_dates = pd.date_range(
            start=group.index.min(),
            end=group.index.max(),
            freq="D",
        )

        reindexed = group.reindex(full_dates)
        reindexed.index.name = "date"

        reindexed["is_forward_filled"] = reindexed["nav"].isna()

        for col in metadata_cols:
            reindexed[col] = reindexed[col].ffill().bfill()

        reindexed["amfi_code"] = amfi_code
        reindexed["nav"] = reindexed["nav"].ffill()

        filled_groups.append(reindexed.reset_index())

    clean_df = pd.concat(filled_groups, ignore_index=True)
    clean_df = clean_df.sort_values(["amfi_code", "date"])

    filled_count = clean_df["is_forward_filled"].sum()

    quality_rows.append(
        {
            "dataset": "nav_history",
            "check_name": "forward_filled_missing_calendar_dates",
            "issue_count": int(filled_count),
            "action": "Missing daily NAV values forward-filled for weekends/holidays",
        }
    )

    quality_rows.append(
        {
            "dataset": "nav_history",
            "check_name": "rows_before_after_cleaning",
            "issue_count": int(before_rows),
            "action": f"Rows before cleaning={before_rows}, rows after daily forward-fill={len(clean_df)}",
        }
    )

    clean_df["date"] = clean_df["date"].dt.strftime("%Y-%m-%d")

    selected_cols = [
        "amfi_code",
        "scheme_name",
        "date",
        "nav",
        "fund_house",
        "scheme_type",
        "scheme_category",
        "is_forward_filled",
    ]

    for col in selected_cols:
        if col not in clean_df.columns:
            clean_df[col] = None

    return clean_df[selected_cols], pd.DataFrame(quality_rows)


def clean_investor_transactions() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = read_csv_required("investor_transactions.csv")
    df = standardize_code_column(raw)

    quality_rows = []

    if "transaction_date" not in df.columns and "date" in df.columns:
        df = df.rename(columns={"date": "transaction_date"})

    df["transaction_date"] = parse_date_series(df["transaction_date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    invalid_date_count = df["transaction_date"].isna().sum()
    invalid_amount_count = df["amount"].isna().sum()
    non_positive_amount_count = (df["amount"] <= 0).sum()

    quality_rows.append(
        {
            "dataset": "investor_transactions",
            "check_name": "invalid_dates",
            "issue_count": int(invalid_date_count),
            "action": "Rows with invalid transaction dates removed",
        }
    )

    quality_rows.append(
        {
            "dataset": "investor_transactions",
            "check_name": "invalid_or_non_positive_amount",
            "issue_count": int(invalid_amount_count + non_positive_amount_count),
            "action": "Rows with invalid or amount <= 0 removed",
        }
    )

    df = df.dropna(subset=["transaction_date", "amount", "amfi_code"])
    df = df[df["amount"] > 0]

    def standardize_transaction_type(value):
        value = str(value).strip().lower()

        if "sip" in value or "systematic" in value:
            return "SIP"

        if "lump" in value:
            return "Lumpsum"

        if "redeem" in value or "redemption" in value:
            return "Redemption"

        return "Invalid"

    df["transaction_type"] = df["transaction_type"].apply(standardize_transaction_type)

    invalid_transaction_type_count = (df["transaction_type"] == "Invalid").sum()

    quality_rows.append(
        {
            "dataset": "investor_transactions",
            "check_name": "invalid_transaction_type",
            "issue_count": int(invalid_transaction_type_count),
            "action": "Invalid transaction_type rows removed",
        }
    )

    df = df[df["transaction_type"] != "Invalid"]

    def standardize_kyc(value):
        value = str(value).strip().lower()

        if "verified" in value or "approved" in value:
            return "Verified"

        if "pending" in value:
            return "Pending"

        if "rejected" in value or "failed" in value:
            return "Rejected"

        return "Invalid"

    df["kyc_status"] = df["kyc_status"].apply(standardize_kyc)

    invalid_kyc_count = (df["kyc_status"] == "Invalid").sum()

    quality_rows.append(
        {
            "dataset": "investor_transactions",
            "check_name": "invalid_kyc_status",
            "issue_count": int(invalid_kyc_count),
            "action": "Invalid KYC rows removed",
        }
    )

    df = df[df["kyc_status"] != "Invalid"]

    if "transaction_id" not in df.columns:
        df["transaction_id"] = [f"TXN{i:06d}" for i in range(1, len(df) + 1)]

    if "investor_id" not in df.columns:
        df["investor_id"] = "UNKNOWN"

    if "state" not in df.columns:
        df["state"] = "Unknown"

    df["transaction_date"] = df["transaction_date"].dt.strftime("%Y-%m-%d")

    selected_cols = [
        "transaction_id",
        "investor_id",
        "amfi_code",
        "transaction_date",
        "transaction_type",
        "amount",
        "state",
        "kyc_status",
    ]

    return df[selected_cols], pd.DataFrame(quality_rows)


def clean_scheme_performance() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = read_csv_required("scheme_performance.csv")
    df = standardize_code_column(raw)

    quality_rows = []

    if "as_of_date" not in df.columns and "date" in df.columns:
        df = df.rename(columns={"date": "as_of_date"})

    df["as_of_date"] = parse_date_series(df["as_of_date"])

    numeric_cols = [
        "return_1m",
        "return_3m",
        "return_6m",
        "return_1y",
        "return_3y",
        "return_5y",
        "expense_ratio",
    ]

    for col in numeric_cols:
        if col not in df.columns:
            df[col] = np.nan

        before_invalid = df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        after_invalid = df[col].isna().sum()

        quality_rows.append(
            {
                "dataset": "scheme_performance",
                "check_name": f"numeric_validation_{col}",
                "issue_count": int(after_invalid - before_invalid),
                "action": "Non-numeric values converted to NaN",
            }
        )

    df["anomaly_flag"] = False
    df["anomaly_reason"] = ""

    return_cols = [
        "return_1m",
        "return_3m",
        "return_6m",
        "return_1y",
        "return_3y",
        "return_5y",
    ]

    for col in return_cols:
        mask = df[col].abs() > 150
        df.loc[mask, "anomaly_flag"] = True
        df.loc[mask, "anomaly_reason"] += f"{col} outside expected range; "

    expense_mask = (df["expense_ratio"] < 0.1) | (df["expense_ratio"] > 2.5)
    df.loc[expense_mask, "anomaly_flag"] = True
    df.loc[expense_mask, "anomaly_reason"] += "expense_ratio outside 0.1%-2.5%; "

    quality_rows.append(
        {
            "dataset": "scheme_performance",
            "check_name": "expense_ratio_range",
            "issue_count": int(expense_mask.sum()),
            "action": "Rows flagged where expense_ratio is outside 0.1%-2.5%",
        }
    )

    quality_rows.append(
        {
            "dataset": "scheme_performance",
            "check_name": "return_anomaly_check",
            "issue_count": int(df["anomaly_flag"].sum()),
            "action": "Extreme return values flagged as anomalies",
        }
    )

    df = df.dropna(subset=["amfi_code", "as_of_date"])

    df["as_of_date"] = df["as_of_date"].dt.strftime("%Y-%m-%d")

    selected_cols = [
        "amfi_code",
        "scheme_name",
        "as_of_date",
        "return_1m",
        "return_3m",
        "return_6m",
        "return_1y",
        "return_3y",
        "return_5y",
        "expense_ratio",
        "anomaly_flag",
        "anomaly_reason",
    ]

    return df[selected_cols], pd.DataFrame(quality_rows)


def clean_aum_history() -> pd.DataFrame:
    raw = read_csv_required("aum_history.csv")
    df = standardize_code_column(raw)

    if "aum_date" not in df.columns and "date" in df.columns:
        df = df.rename(columns={"date": "aum_date"})

    df["aum_date"] = parse_date_series(df["aum_date"])
    df["aum_crore"] = pd.to_numeric(df["aum_crore"], errors="coerce")

    df = df.dropna(subset=["amfi_code", "aum_date", "aum_crore"])
    df = df[df["aum_crore"] > 0]
    df = df.drop_duplicates(subset=["amfi_code", "aum_date"], keep="last")
    df = df.sort_values(["amfi_code", "aum_date"])

    df["aum_date"] = df["aum_date"].dt.strftime("%Y-%m-%d")

    selected_cols = [
        "amfi_code",
        "scheme_name",
        "aum_date",
        "aum_crore",
    ]

    for col in selected_cols:
        if col not in df.columns:
            df[col] = None

    return df[selected_cols]


def clean_simple_existing_files():
    """
    Clean simple Day 1 generated files for deliverable completeness.
    """

    files = {
        "latest_nav.csv": "clean_latest_nav.csv",
        "daily_returns.csv": "clean_daily_returns.csv",
        "monthly_returns.csv": "clean_monthly_returns.csv",
        "yearly_returns.csv": "clean_yearly_returns.csv",
        "rolling_volatility.csv": "clean_rolling_volatility.csv",
    }

    cleaned = {}

    for input_name, output_name in files.items():
        df = read_csv_required(input_name)
        df = standardize_code_column(df)

        for col in df.columns:
            if "date" in col.lower():
                df[col] = parse_date_series(df[col]).dt.strftime("%Y-%m-%d")

        df = df.drop_duplicates()

        cleaned[output_name] = df

    return cleaned


# ---------------------------------------------------------
# Star schema creation
# ---------------------------------------------------------

def build_dim_date(*date_series_list) -> pd.DataFrame:
    all_dates = []

    for series in date_series_list:
        dates = pd.to_datetime(series, errors="coerce").dropna()
        all_dates.extend(dates.tolist())

    min_date = min(all_dates)
    max_date = max(all_dates)

    calendar = pd.date_range(min_date, max_date, freq="D")

    dim_date = pd.DataFrame({"full_date": calendar})
    dim_date["date_key"] = dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["year"] = dim_date["full_date"].dt.year
    dim_date["quarter"] = dim_date["full_date"].dt.quarter
    dim_date["month"] = dim_date["full_date"].dt.month
    dim_date["month_name"] = dim_date["full_date"].dt.month_name()
    dim_date["day"] = dim_date["full_date"].dt.day
    dim_date["day_of_week"] = dim_date["full_date"].dt.day_name()
    dim_date["is_weekend"] = dim_date["full_date"].dt.dayofweek >= 5

    dim_date["full_date"] = dim_date["full_date"].dt.strftime("%Y-%m-%d")

    return dim_date[
        [
            "date_key",
            "full_date",
            "year",
            "quarter",
            "month",
            "month_name",
            "day",
            "day_of_week",
            "is_weekend",
        ]
    ]


def add_date_key(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df["date_key"] = df[date_col].dt.strftime("%Y%m%d").astype(int)
    df[date_col] = df[date_col].dt.strftime("%Y-%m-%d")
    return df


def build_star_schema_dataframes(
    clean_fund_master_df,
    clean_nav_df,
    clean_transactions_df,
    clean_performance_df,
    clean_aum_df,
):
    dim_fund = clean_fund_master_df.copy()

    dim_date = build_dim_date(
        clean_nav_df["date"],
        clean_transactions_df["transaction_date"],
        clean_performance_df["as_of_date"],
        clean_aum_df["aum_date"],
    )

    fact_nav = add_date_key(clean_nav_df, "date")
    fact_nav = fact_nav[
        [
            "amfi_code",
            "date_key",
            "nav",
            "is_forward_filled",
        ]
    ]

    fact_transactions = add_date_key(clean_transactions_df, "transaction_date")
    fact_transactions = fact_transactions[
        [
            "transaction_id",
            "investor_id",
            "amfi_code",
            "date_key",
            "transaction_type",
            "amount",
            "state",
            "kyc_status",
        ]
    ]

    fact_performance = add_date_key(clean_performance_df, "as_of_date")
    fact_performance = fact_performance[
        [
            "amfi_code",
            "date_key",
            "return_1m",
            "return_3m",
            "return_6m",
            "return_1y",
            "return_3y",
            "return_5y",
            "expense_ratio",
            "anomaly_flag",
            "anomaly_reason",
        ]
    ]

    fact_aum = add_date_key(clean_aum_df, "aum_date")
    fact_aum = fact_aum[
        [
            "amfi_code",
            "date_key",
            "aum_crore",
        ]
    ]

    return {
        "dim_fund": dim_fund,
        "dim_date": dim_date,
        "fact_nav": fact_nav,
        "fact_transactions": fact_transactions,
        "fact_performance": fact_performance,
        "fact_aum": fact_aum,
    }


# ---------------------------------------------------------
# SQL files
# ---------------------------------------------------------

def write_schema_sql():
    schema_sql = """
DROP TABLE IF EXISTS fact_aum;
DROP TABLE IF EXISTS fact_performance;
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS fact_nav;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_fund;

CREATE TABLE dim_fund (
    amfi_code TEXT PRIMARY KEY,
    scheme_name TEXT NOT NULL,
    fund_house TEXT,
    scheme_type TEXT,
    scheme_category TEXT,
    category TEXT,
    sub_category TEXT,
    risk_grade TEXT,
    plan_type TEXT,
    option_type TEXT
);

CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL,
    year INTEGER,
    quarter INTEGER,
    month INTEGER,
    month_name TEXT,
    day INTEGER,
    day_of_week TEXT,
    is_weekend BOOLEAN
);

CREATE TABLE fact_nav (
    nav_id INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code TEXT NOT NULL,
    date_key INTEGER NOT NULL,
    nav NUMERIC NOT NULL CHECK (nav > 0),
    is_forward_filled BOOLEAN,
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
);

CREATE TABLE fact_transactions (
    transaction_id TEXT PRIMARY KEY,
    investor_id TEXT,
    amfi_code TEXT NOT NULL,
    date_key INTEGER NOT NULL,
    transaction_type TEXT CHECK (transaction_type IN ('SIP', 'Lumpsum', 'Redemption')),
    amount NUMERIC NOT NULL CHECK (amount > 0),
    state TEXT,
    kyc_status TEXT CHECK (kyc_status IN ('Verified', 'Pending', 'Rejected')),
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
);

CREATE TABLE fact_performance (
    performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code TEXT NOT NULL,
    date_key INTEGER NOT NULL,
    return_1m NUMERIC,
    return_3m NUMERIC,
    return_6m NUMERIC,
    return_1y NUMERIC,
    return_3y NUMERIC,
    return_5y NUMERIC,
    expense_ratio NUMERIC CHECK (expense_ratio >= 0.1 AND expense_ratio <= 2.5),
    anomaly_flag BOOLEAN,
    anomaly_reason TEXT,
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
);

CREATE TABLE fact_aum (
    aum_id INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code TEXT NOT NULL,
    date_key INTEGER NOT NULL,
    aum_crore NUMERIC NOT NULL CHECK (aum_crore > 0),
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
);
"""

    output_path = SQL_DIR / "schema.sql"
    output_path.write_text(schema_sql.strip(), encoding="utf-8")
    print(f"Saved schema.sql to {output_path}")


def write_queries_sql():
    queries_sql = """
-- 1. Top 5 funds by latest AUM
WITH latest_aum_date AS (
    SELECT amfi_code, MAX(date_key) AS latest_date_key
    FROM fact_aum
    GROUP BY amfi_code
)
SELECT
    f.scheme_name,
    f.fund_house,
    a.aum_crore,
    d.full_date
FROM fact_aum a
JOIN latest_aum_date l
    ON a.amfi_code = l.amfi_code
   AND a.date_key = l.latest_date_key
JOIN dim_fund f
    ON a.amfi_code = f.amfi_code
JOIN dim_date d
    ON a.date_key = d.date_key
ORDER BY a.aum_crore DESC
LIMIT 5;


-- 2. Average NAV per month
SELECT
    f.scheme_name,
    d.year,
    d.month,
    ROUND(AVG(n.nav), 4) AS average_nav
FROM fact_nav n
JOIN dim_fund f
    ON n.amfi_code = f.amfi_code
JOIN dim_date d
    ON n.date_key = d.date_key
GROUP BY f.scheme_name, d.year, d.month
ORDER BY f.scheme_name, d.year, d.month;


-- 3. SIP YoY growth
WITH yearly_sip AS (
    SELECT
        d.year,
        SUM(t.amount) AS total_sip_amount
    FROM fact_transactions t
    JOIN dim_date d
        ON t.date_key = d.date_key
    WHERE t.transaction_type = 'SIP'
    GROUP BY d.year
),
growth AS (
    SELECT
        year,
        total_sip_amount,
        LAG(total_sip_amount) OVER (ORDER BY year) AS previous_year_sip
    FROM yearly_sip
)
SELECT
    year,
    ROUND(total_sip_amount, 2) AS total_sip_amount,
    ROUND(previous_year_sip, 2) AS previous_year_sip,
    ROUND(
        ((total_sip_amount - previous_year_sip) / previous_year_sip) * 100,
        2
    ) AS yoy_growth_percent
FROM growth;


-- 4. Transactions by state
SELECT
    state,
    transaction_type,
    COUNT(*) AS transaction_count,
    ROUND(SUM(amount), 2) AS total_amount
FROM fact_transactions
GROUP BY state, transaction_type
ORDER BY total_amount DESC;


-- 5. Funds with expense ratio less than 1%
SELECT
    f.scheme_name,
    f.fund_house,
    p.expense_ratio,
    p.return_1y
FROM fact_performance p
JOIN dim_fund f
    ON p.amfi_code = f.amfi_code
WHERE p.expense_ratio < 1
ORDER BY p.expense_ratio ASC;


-- 6. Best funds by 1-year return
SELECT
    f.scheme_name,
    f.fund_house,
    p.return_1y,
    p.expense_ratio
FROM fact_performance p
JOIN dim_fund f
    ON p.amfi_code = f.amfi_code
ORDER BY p.return_1y DESC
LIMIT 5;


-- 7. Highest volatility funds based on NAV movement
WITH nav_returns AS (
    SELECT
        amfi_code,
        date_key,
        nav,
        (nav / LAG(nav) OVER (PARTITION BY amfi_code ORDER BY date_key)) - 1 AS daily_return
    FROM fact_nav
)
SELECT
    f.scheme_name,
    ROUND(AVG(ABS(nr.daily_return)) * 100, 4) AS avg_absolute_daily_movement_percent
FROM nav_returns nr
JOIN dim_fund f
    ON nr.amfi_code = f.amfi_code
WHERE nr.daily_return IS NOT NULL
GROUP BY f.scheme_name
ORDER BY avg_absolute_daily_movement_percent DESC;


-- 8. Monthly transaction amount by transaction type
SELECT
    d.year,
    d.month,
    t.transaction_type,
    ROUND(SUM(t.amount), 2) AS total_amount
FROM fact_transactions t
JOIN dim_date d
    ON t.date_key = d.date_key
GROUP BY d.year, d.month, t.transaction_type
ORDER BY d.year, d.month, t.transaction_type;


-- 9. Fund-wise redemption amount
SELECT
    f.scheme_name,
    ROUND(SUM(t.amount), 2) AS total_redemption_amount,
    COUNT(*) AS redemption_count
FROM fact_transactions t
JOIN dim_fund f
    ON t.amfi_code = f.amfi_code
WHERE t.transaction_type = 'Redemption'
GROUP BY f.scheme_name
ORDER BY total_redemption_amount DESC;


-- 10. NAV CAGR approximation from first NAV to latest NAV
WITH nav_bounds AS (
    SELECT
        amfi_code,
        MIN(date_key) AS first_date_key,
        MAX(date_key) AS last_date_key
    FROM fact_nav
    GROUP BY amfi_code
),
nav_values AS (
    SELECT
        b.amfi_code,
        first_nav.nav AS first_nav,
        last_nav.nav AS last_nav,
        first_date.full_date AS first_date,
        last_date.full_date AS last_date,
        (julianday(last_date.full_date) - julianday(first_date.full_date)) / 365.25 AS years
    FROM nav_bounds b
    JOIN fact_nav first_nav
        ON b.amfi_code = first_nav.amfi_code
       AND b.first_date_key = first_nav.date_key
    JOIN fact_nav last_nav
        ON b.amfi_code = last_nav.amfi_code
       AND b.last_date_key = last_nav.date_key
    JOIN dim_date first_date
        ON b.first_date_key = first_date.date_key
    JOIN dim_date last_date
        ON b.last_date_key = last_date.date_key
)
SELECT
    f.scheme_name,
    first_date,
    last_date,
    ROUND(first_nav, 4) AS first_nav,
    ROUND(last_nav, 4) AS last_nav,
    ROUND((POWER(last_nav / first_nav, 1.0 / years) - 1) * 100, 2) AS cagr_percent
FROM nav_values nv
JOIN dim_fund f
    ON nv.amfi_code = f.amfi_code
ORDER BY cagr_percent DESC;
"""

    output_path = SQL_DIR / "queries.sql"
    output_path.write_text(queries_sql.strip(), encoding="utf-8")
    print(f"Saved queries.sql to {output_path}")


# ---------------------------------------------------------
# SQLite loading
# ---------------------------------------------------------

def execute_schema(engine):
    schema_path = SQL_DIR / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    statements = [
        statement.strip()
        for statement in schema_sql.split(";")
        if statement.strip()
    ]

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON;"))

        for statement in statements:
            conn.execute(text(statement))


def load_to_sqlite(star_tables: dict[str, pd.DataFrame]):
    if DB_PATH.exists():
        DB_PATH.unlink()

    engine = create_engine(f"sqlite:///{DB_PATH}")

    execute_schema(engine)

    load_order = [
        "dim_fund",
        "dim_date",
        "fact_nav",
        "fact_transactions",
        "fact_performance",
        "fact_aum",
    ]

    verification_rows = []

    for table_name in load_order:
        df = star_tables[table_name]

        df.to_sql(
            table_name,
            con=engine,
            if_exists="append",
            index=False,
        )

        with engine.connect() as conn:
            db_count = conn.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            ).scalar()

        source_count = len(df)

        verification_rows.append(
            {
                "table_name": table_name,
                "source_rows": source_count,
                "db_rows": db_count,
                "status": "PASS" if source_count == db_count else "FAIL",
            }
        )

        print(
            f"Loaded {table_name}: source_rows={source_count}, db_rows={db_count}"
        )

    verification_df = pd.DataFrame(verification_rows)
    save_processed(verification_df, "sqlite_load_verification.csv")

    print(f"\nSQLite database created: {DB_PATH}")


# ---------------------------------------------------------
# Data dictionary
# ---------------------------------------------------------

def write_data_dictionary():
    data_dictionary = """
# Mutual Fund Analytics Data Dictionary

## Overview

This document describes the cleaned datasets, SQLite star schema tables, column definitions, business meanings, and source references used in the Mutual Fund Analytics project.

## Source References

| Source | Description |
|---|---|
| MFapi NAV data | NAV history fetched from `https://api.mfapi.in/mf/{scheme_code}` |
| fund_master.csv | Fund metadata generated from MFapi scheme metadata |
| nav_history.csv | Historical NAV data generated from MFapi NAV response |
| investor_transactions.csv | Starter investor transaction data generated if official file is not available |
| scheme_performance.csv | Derived performance dataset generated from NAV history if official file is not available |
| aum_history.csv | Starter AUM history generated for analytical SQL use |

## Dimension Tables

### dim_fund

| Column | Data Type | Business Definition |
|---|---|---|
| amfi_code | TEXT | Unique AMFI mutual fund scheme code |
| scheme_name | TEXT | Name of mutual fund scheme |
| fund_house | TEXT | Asset management company / fund house |
| scheme_type | TEXT | Scheme type, such as open ended |
| scheme_category | TEXT | SEBI/AMFI scheme category |
| category | TEXT | Broad category such as Equity |
| sub_category | TEXT | Sub-category such as Large Cap |
| risk_grade | TEXT | Risk classification |
| plan_type | TEXT | Direct or Regular |
| option_type | TEXT | Growth, IDCW, or other option |

### dim_date

| Column | Data Type | Business Definition |
|---|---|---|
| date_key | INTEGER | Date key in YYYYMMDD format |
| full_date | DATE | Calendar date |
| year | INTEGER | Calendar year |
| quarter | INTEGER | Calendar quarter |
| month | INTEGER | Calendar month number |
| month_name | TEXT | Calendar month name |
| day | INTEGER | Day of month |
| day_of_week | TEXT | Name of weekday |
| is_weekend | BOOLEAN | True if Saturday or Sunday |

## Fact Tables

### fact_nav

| Column | Data Type | Business Definition |
|---|---|---|
| nav_id | INTEGER | Surrogate primary key |
| amfi_code | TEXT | Foreign key to dim_fund |
| date_key | INTEGER | Foreign key to dim_date |
| nav | NUMERIC | Net Asset Value of the fund |
| is_forward_filled | BOOLEAN | True if NAV was forward-filled for missing calendar date |

### fact_transactions

| Column | Data Type | Business Definition |
|---|---|---|
| transaction_id | TEXT | Unique transaction identifier |
| investor_id | TEXT | Investor identifier |
| amfi_code | TEXT | Foreign key to dim_fund |
| date_key | INTEGER | Foreign key to dim_date |
| transaction_type | TEXT | SIP, Lumpsum, or Redemption |
| amount | NUMERIC | Transaction amount, must be positive |
| state | TEXT | Investor state |
| kyc_status | TEXT | Verified, Pending, or Rejected |

### fact_performance

| Column | Data Type | Business Definition |
|---|---|---|
| performance_id | INTEGER | Surrogate primary key |
| amfi_code | TEXT | Foreign key to dim_fund |
| date_key | INTEGER | Foreign key to dim_date |
| return_1m | NUMERIC | 1-month return percentage |
| return_3m | NUMERIC | 3-month return percentage |
| return_6m | NUMERIC | 6-month return percentage |
| return_1y | NUMERIC | 1-year return percentage |
| return_3y | NUMERIC | 3-year return percentage |
| return_5y | NUMERIC | 5-year return percentage |
| expense_ratio | NUMERIC | Expense ratio percentage, expected range 0.1% to 2.5% |
| anomaly_flag | BOOLEAN | True if return or expense ratio anomaly is detected |
| anomaly_reason | TEXT | Explanation of anomaly |

### fact_aum

| Column | Data Type | Business Definition |
|---|---|---|
| aum_id | INTEGER | Surrogate primary key |
| amfi_code | TEXT | Foreign key to dim_fund |
| date_key | INTEGER | Foreign key to dim_date |
| aum_crore | NUMERIC | Assets under management in crore rupees |

## Data Quality Rules

| Dataset | Rule |
|---|---|
| nav_history | NAV must be numeric and greater than 0 |
| nav_history | Dates must be valid and parsed to datetime |
| nav_history | Duplicate AMFI code + date rows are removed |
| nav_history | Missing calendar NAV values are forward-filled |
| investor_transactions | Transaction type must be SIP, Lumpsum, or Redemption |
| investor_transactions | Amount must be numeric and greater than 0 |
| investor_transactions | KYC status must be Verified, Pending, or Rejected |
| scheme_performance | Return fields must be numeric |
| scheme_performance | Expense ratio must be between 0.1% and 2.5% |
| scheme_performance | Extreme return values are flagged as anomalies |
"""

    output_path = REPORTS_DIR / "data_dictionary.md"
    output_path.write_text(data_dictionary.strip(), encoding="utf-8")
    print(f"Saved data dictionary to {output_path}")


# ---------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------

def main():
    print("\n" + "=" * 90)
    print("CLEANING + SQLITE STAR SCHEMA PIPELINE")
    print("=" * 90)

    generate_investor_transactions_if_missing()
    generate_scheme_performance_if_missing()
    generate_aum_history_if_missing()

    print("\nCleaning datasets...\n")

    clean_fund_master_df = clean_fund_master()
    clean_nav_df, nav_quality = clean_nav_history()
    clean_transactions_df, txn_quality = clean_investor_transactions()
    clean_performance_df, perf_quality = clean_scheme_performance()
    clean_aum_df = clean_aum_history()

    simple_cleaned_files = clean_simple_existing_files()

    quality_df = pd.concat(
        [nav_quality, txn_quality, perf_quality],
        ignore_index=True,
    )

    print("\nSaving cleaned CSV files...\n")

    save_processed(clean_fund_master_df, "clean_fund_master.csv")
    save_processed(clean_nav_df, "clean_nav_history.csv")
    save_processed(clean_transactions_df, "clean_investor_transactions.csv")
    save_processed(clean_performance_df, "clean_scheme_performance.csv")
    save_processed(clean_aum_df, "clean_aum_history.csv")

    for output_name, df in simple_cleaned_files.items():
        save_processed(df, output_name)

    save_processed(quality_df, "data_quality_flags.csv")

    print("\nBuilding star schema dataframes...\n")

    star_tables = build_star_schema_dataframes(
        clean_fund_master_df=clean_fund_master_df,
        clean_nav_df=clean_nav_df,
        clean_transactions_df=clean_transactions_df,
        clean_performance_df=clean_performance_df,
        clean_aum_df=clean_aum_df,
    )

    for table_name, df in star_tables.items():
        save_processed(df, f"{table_name}.csv")

    print("\nWriting SQL files...\n")

    write_schema_sql()
    write_queries_sql()

    print("\nLoading SQLite database...\n")

    load_to_sqlite(star_tables)

    print("\nWriting data dictionary...\n")

    write_data_dictionary()

    print("\n" + "=" * 90)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 90)
    print("Created:")
    print("- Cleaned CSV files in data/processed/")
    print("- bluestock_mf.db")
    print("- sql/schema.sql")
    print("- sql/queries.sql")
    print("- reports/data_dictionary.md")


if __name__ == "__main__":
    main()