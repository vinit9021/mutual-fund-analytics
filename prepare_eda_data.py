from pathlib import Path
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
EDA_DIR = PROCESSED_DIR / "eda"
EDA_DIR.mkdir(parents=True, exist_ok=True)


RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)


def load_existing_fund_master():
    file_path = PROCESSED_DIR / "clean_fund_master.csv"

    if not file_path.exists():
        raise FileNotFoundError(
            "clean_fund_master.csv not found. First run: python clean_and_load.py"
        )

    return pd.read_csv(file_path)


def generate_40_scheme_master():
    existing_funds = load_existing_fund_master()

    fund_houses = [
        "SBI Mutual Fund",
        "HDFC Mutual Fund",
        "ICICI Prudential Mutual Fund",
        "Nippon India Mutual Fund",
        "Axis Mutual Fund",
        "Kotak Mahindra Mutual Fund",
        "Aditya Birla Sun Life Mutual Fund",
        "Mirae Asset Mutual Fund",
        "UTI Mutual Fund",
        "DSP Mutual Fund",
    ]

    categories = [
        "Large Cap",
        "Mid Cap",
        "Small Cap",
        "Flexi Cap",
        "ELSS",
        "Index Fund",
        "Sectoral Fund",
        "Hybrid Fund",
    ]

    rows = []

    # Keep existing 6 schemes first
    for _, row in existing_funds.iterrows():
        rows.append(
            {
                "amfi_code": str(row["amfi_code"]),
                "scheme_name": row["scheme_name"],
                "fund_house": row["fund_house"],
                "category": row.get("sub_category", "Large Cap"),
                "is_real_scheme": True,
            }
        )

    # Generate additional schemes until total reaches 40
    current_count = len(rows)

    for i in range(current_count + 1, 41):
        fund_house = fund_houses[(i - 1) % len(fund_houses)]
        category = categories[(i - 1) % len(categories)]

        short_house = (
            fund_house.replace(" Mutual Fund", "")
            .replace("ICICI Prudential", "ICICI")
            .replace("Aditya Birla Sun Life", "ABSL")
            .replace("Kotak Mahindra", "Kotak")
        )

        rows.append(
            {
                "amfi_code": f"90{i:04d}",
                "scheme_name": f"{short_house} {category} Direct Growth",
                "fund_house": fund_house,
                "category": category,
                "is_real_scheme": False,
            }
        )

    df = pd.DataFrame(rows)
    return df


def generate_nav_for_40_schemes(master_df):
    dates = pd.date_range("2022-01-03", "2026-06-24", freq="B")

    rows = []

    for idx, fund in master_df.iterrows():
        amfi_code = str(fund["amfi_code"])
        scheme_name = fund["scheme_name"]
        fund_house = fund["fund_house"]
        category = fund["category"]

        start_nav = rng.uniform(20, 450)

        category_risk = {
            "Large Cap": 0.010,
            "Mid Cap": 0.014,
            "Small Cap": 0.018,
            "Flexi Cap": 0.013,
            "ELSS": 0.014,
            "Index Fund": 0.011,
            "Sectoral Fund": 0.020,
            "Hybrid Fund": 0.007,
        }.get(category, 0.012)

        nav = start_nav

        for date in dates:
            year = date.year

            # Base daily return
            drift = 0.00020

            # 2023 bull run
            if year == 2023:
                drift += 0.00045

            # 2024 corrections
            if pd.Timestamp("2024-03-01") <= date <= pd.Timestamp("2024-04-30"):
                drift -= 0.00100

            if pd.Timestamp("2024-09-01") <= date <= pd.Timestamp("2024-10-31"):
                drift -= 0.00080

            # 2025 moderate growth
            if year == 2025:
                drift += 0.00025

            daily_return = rng.normal(drift, category_risk)
            nav = max(nav * (1 + daily_return), 1)

            rows.append(
                {
                    "amfi_code": amfi_code,
                    "scheme_name": scheme_name,
                    "fund_house": fund_house,
                    "category": category,
                    "date": date.strftime("%Y-%m-%d"),
                    "nav": round(nav, 4),
                }
            )

    return pd.DataFrame(rows)


def generate_aum_by_fund_house():
    fund_houses = [
        "SBI Mutual Fund",
        "HDFC Mutual Fund",
        "ICICI Prudential Mutual Fund",
        "Nippon India Mutual Fund",
        "Axis Mutual Fund",
        "Kotak Mahindra Mutual Fund",
        "Aditya Birla Sun Life Mutual Fund",
        "Mirae Asset Mutual Fund",
        "UTI Mutual Fund",
        "DSP Mutual Fund",
    ]

    rows = []

    base_values = {
        "SBI Mutual Fund": 7.8,
        "HDFC Mutual Fund": 5.1,
        "ICICI Prudential Mutual Fund": 4.8,
        "Nippon India Mutual Fund": 3.7,
        "Axis Mutual Fund": 2.9,
        "Kotak Mahindra Mutual Fund": 3.1,
        "Aditya Birla Sun Life Mutual Fund": 2.7,
        "Mirae Asset Mutual Fund": 1.9,
        "UTI Mutual Fund": 2.1,
        "DSP Mutual Fund": 1.5,
    }

    for fund_house in fund_houses:
        for year in [2022, 2023, 2024, 2025]:
            growth = 1 + 0.13 * (year - 2022)
            aum = base_values[fund_house] * growth + rng.normal(0, 0.15)

            if fund_house == "SBI Mutual Fund" and year == 2025:
                aum = 12.5

            rows.append(
                {
                    "fund_house": fund_house,
                    "year": year,
                    "aum_lakh_crore": round(max(aum, 0.5), 2),
                }
            )

    return pd.DataFrame(rows)


def generate_monthly_sip():
    dates = pd.date_range("2022-01-01", "2025-12-01", freq="MS")

    start_value = 11000
    end_value = 31002

    values = np.linspace(start_value, end_value, len(dates))

    rows = []

    for i, date in enumerate(dates):
        seasonality = 800 * np.sin(i / 3)
        noise = rng.normal(0, 500)
        sip = max(values[i] + seasonality + noise, 9000)

        if date == pd.Timestamp("2025-12-01"):
            sip = 31002

        rows.append(
            {
                "month": date.strftime("%Y-%m"),
                "sip_inflow_crore": round(float(sip), 2),
            }
        )

    return pd.DataFrame(rows)


def generate_category_inflows():
    months = pd.date_range("2022-01-01", "2025-12-01", freq="MS")

    categories = [
        "Large Cap",
        "Mid Cap",
        "Small Cap",
        "Flexi Cap",
        "ELSS",
        "Index Fund",
        "Sectoral Fund",
        "Hybrid Fund",
        "Debt Fund",
    ]

    rows = []

    for category in categories:
        base = rng.uniform(800, 4000)

        for i, month in enumerate(months):
            trend = i * rng.uniform(15, 45)
            seasonality = 300 * np.sin(i / 4)
            correction_effect = -700 if month.year == 2024 and month.month in [3, 4, 9, 10] else 0
            inflow = base + trend + seasonality + correction_effect + rng.normal(0, 250)

            rows.append(
                {
                    "month": month.strftime("%Y-%m"),
                    "category": category,
                    "net_inflow_crore": round(float(inflow), 2),
                }
            )

    return pd.DataFrame(rows)


def generate_investor_demographics():
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
        "Madhya Pradesh",
        "Kerala",
    ]

    age_groups = ["18-24", "25-34", "35-44", "45-54", "55+"]
    genders = ["Male", "Female", "Other"]
    city_tiers = ["T30", "B30"]

    rows = []

    for i in range(1, 3001):
        age_group = rng.choice(age_groups, p=[0.12, 0.38, 0.27, 0.15, 0.08])

        age_multiplier = {
            "18-24": 0.65,
            "25-34": 1.00,
            "35-44": 1.35,
            "45-54": 1.55,
            "55+": 1.20,
        }[age_group]

        amount = rng.lognormal(mean=9.0, sigma=0.65) * age_multiplier

        rows.append(
            {
                "investor_id": f"INV{i:05d}",
                "age_group": age_group,
                "gender": rng.choice(genders, p=[0.59, 0.39, 0.02]),
                "state": rng.choice(states),
                "city_tier": rng.choice(city_tiers, p=[0.68, 0.32]),
                "monthly_sip_amount": round(float(amount), 2),
            }
        )

    return pd.DataFrame(rows)


def generate_folio_growth():
    months = pd.date_range("2022-01-01", "2025-12-01", freq="MS")

    start = 13.26
    end = 26.12

    values = np.linspace(start, end, len(months))

    rows = []

    for i, month in enumerate(months):
        value = values[i] + 0.25 * np.sin(i / 3)

        if month == pd.Timestamp("2022-01-01"):
            value = 13.26

        if month == pd.Timestamp("2025-12-01"):
            value = 26.12

        rows.append(
            {
                "month": month.strftime("%Y-%m"),
                "folio_count_crore": round(float(value), 2),
            }
        )

    return pd.DataFrame(rows)


def generate_portfolio_holdings(master_df):
    sectors = [
        "Financial Services",
        "Information Technology",
        "Energy",
        "Healthcare",
        "Consumer Goods",
        "Automobile",
        "Industrials",
        "Telecom",
        "Metals",
        "Utilities",
    ]

    equity_master = master_df[
        master_df["category"].isin(
            [
                "Large Cap",
                "Mid Cap",
                "Small Cap",
                "Flexi Cap",
                "ELSS",
                "Index Fund",
                "Sectoral Fund",
            ]
        )
    ].copy()

    rows = []

    for _, fund in equity_master.iterrows():
        weights = rng.dirichlet(np.ones(len(sectors))) * 100

        for sector, weight in zip(sectors, weights):
            rows.append(
                {
                    "amfi_code": fund["amfi_code"],
                    "scheme_name": fund["scheme_name"],
                    "fund_house": fund["fund_house"],
                    "category": fund["category"],
                    "sector": sector,
                    "sector_weight_percent": round(float(weight), 2),
                }
            )

    return pd.DataFrame(rows)


def main():
    print("Preparing EDA datasets...")

    master_40 = generate_40_scheme_master()
    nav_40 = generate_nav_for_40_schemes(master_40)
    aum = generate_aum_by_fund_house()
    sip = generate_monthly_sip()
    inflows = generate_category_inflows()
    demographics = generate_investor_demographics()
    folio = generate_folio_growth()
    holdings = generate_portfolio_holdings(master_40)

    datasets = {
        "eda_scheme_master_40.csv": master_40,
        "eda_nav_40_schemes.csv": nav_40,
        "eda_aum_by_fund_house_year.csv": aum,
        "eda_monthly_sip.csv": sip,
        "eda_category_inflows.csv": inflows,
        "eda_investor_demographics.csv": demographics,
        "eda_folio_growth.csv": folio,
        "portfolio_holdings.csv": holdings,
    }

    for file_name, df in datasets.items():
        output_path = EDA_DIR / file_name
        df.to_csv(output_path, index=False)
        print(f"Saved {file_name}: shape={df.shape}")

    print("\nEDA data preparation complete.")
    print("Next create/run notebooks/EDA_Analysis.ipynb")


if __name__ == "__main__":
    main()