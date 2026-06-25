from pathlib import Path
import pandas as pd
import numpy as np


RAW_DIR = Path("data/raw")
API_DIR = RAW_DIR / "mfapi_nav"
INPUT_FILE = API_DIR / "all_schemes_nav_history.csv"

RAW_DIR.mkdir(parents=True, exist_ok=True)


def load_nav_data():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"{INPUT_FILE} not found. First run: python live_nav_fetch.py"
        )

    df = pd.read_csv(INPUT_FILE)

    df["scheme_code"] = df["scheme_code"].astype(str)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")

    df = df.dropna(subset=["scheme_code", "date", "nav"])
    df = df.sort_values(["scheme_code", "date"])

    return df


def create_fund_master(nav_df):
    fund_master = (
        nav_df[
            [
                "scheme_code",
                "scheme_name",
                "fund_house",
                "scheme_type",
                "scheme_category",
            ]
        ]
        .drop_duplicates(subset=["scheme_code"])
        .copy()
    )

    fund_master["category"] = "Equity"
    fund_master["sub_category"] = "Large Cap"
    fund_master["risk_grade"] = "Very High"
    fund_master["plan_type"] = "Direct"
    fund_master["option_type"] = "Growth"

    return fund_master


def create_nav_history(nav_df):
    return nav_df[
        [
            "scheme_code",
            "scheme_name",
            "date",
            "nav",
            "fund_house",
            "scheme_type",
            "scheme_category",
        ]
    ].copy()


def create_latest_nav(nav_df):
    latest_nav = (
        nav_df.sort_values(["scheme_code", "date"])
        .groupby("scheme_code")
        .tail(1)
        .copy()
    )

    return latest_nav[
        [
            "scheme_code",
            "scheme_name",
            "date",
            "nav",
            "fund_house",
            "scheme_type",
            "scheme_category",
        ]
    ]


def create_daily_returns(nav_df):
    daily_returns = nav_df[
        ["scheme_code", "scheme_name", "date", "nav"]
    ].copy()

    daily_returns["daily_return"] = (
        daily_returns.groupby("scheme_code")["nav"].pct_change()
    )

    daily_returns["daily_return_percent"] = daily_returns["daily_return"] * 100

    return daily_returns


def create_monthly_returns(nav_df):
    temp = nav_df[["scheme_code", "scheme_name", "date", "nav"]].copy()
    temp["month"] = temp["date"].dt.to_period("M")

    month_end_nav = (
        temp.sort_values(["scheme_code", "date"])
        .groupby(["scheme_code", "scheme_name", "month"])
        .tail(1)
        .copy()
    )

    month_end_nav["monthly_return"] = (
        month_end_nav.groupby("scheme_code")["nav"].pct_change()
    )

    month_end_nav["monthly_return_percent"] = month_end_nav["monthly_return"] * 100
    month_end_nav["month"] = month_end_nav["month"].astype(str)

    return month_end_nav[
        [
            "scheme_code",
            "scheme_name",
            "month",
            "date",
            "nav",
            "monthly_return",
            "monthly_return_percent",
        ]
    ]


def create_yearly_returns(nav_df):
    temp = nav_df[["scheme_code", "scheme_name", "date", "nav"]].copy()
    temp["year"] = temp["date"].dt.year

    year_end_nav = (
        temp.sort_values(["scheme_code", "date"])
        .groupby(["scheme_code", "scheme_name", "year"])
        .tail(1)
        .copy()
    )

    year_end_nav["yearly_return"] = (
        year_end_nav.groupby("scheme_code")["nav"].pct_change()
    )

    year_end_nav["yearly_return_percent"] = year_end_nav["yearly_return"] * 100

    return year_end_nav[
        [
            "scheme_code",
            "scheme_name",
            "year",
            "date",
            "nav",
            "yearly_return",
            "yearly_return_percent",
        ]
    ]


def create_risk_metrics(nav_df):
    daily_returns = create_daily_returns(nav_df)

    risk = (
        daily_returns.groupby(["scheme_code", "scheme_name"])
        .agg(
            observations=("daily_return", "count"),
            mean_daily_return=("daily_return", "mean"),
            daily_volatility=("daily_return", "std"),
            min_daily_return=("daily_return", "min"),
            max_daily_return=("daily_return", "max"),
        )
        .reset_index()
    )

    risk["annualized_return"] = risk["mean_daily_return"] * 252
    risk["annualized_volatility"] = risk["daily_volatility"] * np.sqrt(252)

    risk_free_rate = 0.06
    risk["sharpe_ratio"] = (
        risk["annualized_return"] - risk_free_rate
    ) / risk["annualized_volatility"]

    return risk


def create_rolling_volatility(nav_df):
    daily_returns = create_daily_returns(nav_df)

    daily_returns["rolling_30d_volatility"] = (
        daily_returns.groupby("scheme_code")["daily_return"]
        .rolling(window=30)
        .std()
        .reset_index(level=0, drop=True)
    )

    daily_returns["rolling_30d_annualized_volatility"] = (
        daily_returns["rolling_30d_volatility"] * np.sqrt(252)
    )

    return daily_returns[
        [
            "scheme_code",
            "scheme_name",
            "date",
            "daily_return",
            "rolling_30d_volatility",
            "rolling_30d_annualized_volatility",
        ]
    ]


def create_fund_house_summary(nav_df):
    latest_nav = create_latest_nav(nav_df)

    summary = (
        latest_nav.groupby("fund_house")
        .agg(
            number_of_schemes=("scheme_code", "nunique"),
            average_latest_nav=("nav", "mean"),
            min_latest_nav=("nav", "min"),
            max_latest_nav=("nav", "max"),
        )
        .reset_index()
    )

    return summary


def create_scheme_code_mapping(nav_df):
    mapping = (
        nav_df[
            [
                "scheme_code",
                "scheme_name",
                "fund_house",
                "scheme_type",
                "scheme_category",
            ]
        ]
        .drop_duplicates(subset=["scheme_code"])
        .copy()
    )

    mapping["code_length"] = mapping["scheme_code"].astype(str).str.len()
    mapping["is_numeric_code"] = mapping["scheme_code"].astype(str).str.isnumeric()
    mapping["source"] = "MFapi"

    return mapping


def save_dataset(df, file_name):
    output_path = RAW_DIR / file_name
    df.to_csv(output_path, index=False)
    print(f"Saved {file_name}: shape={df.shape}")


def main():
    print("Loading API NAV data...")
    nav_df = load_nav_data()
    print(f"Loaded NAV data: {nav_df.shape}")

    datasets = {
        "fund_master.csv": create_fund_master(nav_df),
        "nav_history.csv": create_nav_history(nav_df),
        "latest_nav.csv": create_latest_nav(nav_df),
        "daily_returns.csv": create_daily_returns(nav_df),
        "monthly_returns.csv": create_monthly_returns(nav_df),
        "yearly_returns.csv": create_yearly_returns(nav_df),
        "risk_metrics.csv": create_risk_metrics(nav_df),
        "rolling_volatility.csv": create_rolling_volatility(nav_df),
        "fund_house_summary.csv": create_fund_house_summary(nav_df),
        "scheme_code_mapping.csv": create_scheme_code_mapping(nav_df),
    }

    print("\nCreating 10 starter datasets in data/raw/...\n")

    for file_name, df in datasets.items():
        save_dataset(df, file_name)

    print("\nDone. You now have 10 CSV datasets inside data/raw/.")
    print("Next run: python data_ingestion.py")


if __name__ == "__main__":
    main()