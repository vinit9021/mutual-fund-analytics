from pathlib import Path
import re
import pandas as pd
import numpy as np


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_col_name(col: str) -> str:
    """
    Convert column name into normalized format:
    lowercase + remove spaces, underscores, hyphens.
    Example:
    'Scheme Code' -> 'schemecode'
    'scheme_code' -> 'schemecode'
    """
    return re.sub(r"[\s_\-]+", "", str(col).strip().lower())


def find_column(df: pd.DataFrame, possible_names: list[str]) -> str | None:
    """
    Find a column using flexible matching.
    """
    normalized_map = {normalize_col_name(col): col for col in df.columns}

    for name in possible_names:
        key = normalize_col_name(name)
        if key in normalized_map:
            return normalized_map[key]

    return None


def get_top_level_raw_csv_files() -> list[Path]:
    """
    Load only the 10 provided CSV datasets from data/raw.

    It intentionally ignores:
    - data/raw/mfapi_nav/
    - CSV files inside subfolders
    """
    csv_files = sorted(RAW_DIR.glob("*.csv"))
    return csv_files


def detect_basic_anomalies(df: pd.DataFrame, file_name: str) -> list[str]:
    """
    Detect simple data quality issues.
    """
    anomalies = []

    if df.empty:
        anomalies.append("Dataset is empty.")

    if df.shape[1] == 0:
        anomalies.append("Dataset has zero columns.")

    duplicate_rows = df.duplicated().sum()
    if duplicate_rows > 0:
        anomalies.append(f"Contains {duplicate_rows} duplicate rows.")

    duplicate_cols = df.columns[df.columns.duplicated()].tolist()
    if duplicate_cols:
        anomalies.append(f"Contains duplicate columns: {duplicate_cols}")

    missing_counts = df.isna().sum()
    high_missing_cols = missing_counts[
        missing_counts > 0.40 * len(df)
    ].index.tolist()

    if high_missing_cols:
        anomalies.append(
            f"Columns with more than 40% missing values: {high_missing_cols}"
        )

    unnamed_cols = [col for col in df.columns if str(col).lower().startswith("unnamed")]
    if unnamed_cols:
        anomalies.append(f"Possible index columns found: {unnamed_cols}")

    # Check object columns that may actually be dates or numbers
    object_cols = df.select_dtypes(include=["object"]).columns.tolist()

    possible_date_cols = [
        col for col in object_cols
        if "date" in str(col).lower()
    ]

    if possible_date_cols:
        anomalies.append(f"Possible date columns stored as object: {possible_date_cols}")

    possible_nav_cols = [
        col for col in df.columns
        if "nav" in str(col).lower()
    ]

    for col in possible_nav_cols:
        converted = pd.to_numeric(df[col], errors="coerce")
        invalid_count = converted.isna().sum() - df[col].isna().sum()
        if invalid_count > 0:
            anomalies.append(
                f"Column '{col}' has {invalid_count} non-numeric values."
            )

    if not anomalies:
        anomalies.append("No major basic anomalies detected.")

    return anomalies


def load_and_profile_csvs() -> dict[str, pd.DataFrame]:
    """
    Load all provided CSV files and print shape, dtypes, head, anomalies.
    """
    csv_files = get_top_level_raw_csv_files()

    print("\n" + "=" * 80)
    print("STEP 1: LOADING PROVIDED CSV DATASETS")
    print("=" * 80)

    if not csv_files:
        print("ERROR: No CSV files found in data/raw/")
        print("Please copy your 10 provided CSV datasets into data/raw/")
        return {}

    if len(csv_files) != 10:
        print(f"WARNING: Expected 10 provided CSV datasets, but found {len(csv_files)}.")
        print("Files found:")
        for file in csv_files:
            print(f"- {file.name}")

    datasets = {}
    inventory_rows = []
    anomaly_report = []

    for file_path in csv_files:
        print("\n" + "-" * 80)
        print(f"FILE: {file_path.name}")
        print("-" * 80)

        try:
            df = pd.read_csv(file_path)
            datasets[file_path.stem] = df

            print("\nShape:")
            print(df.shape)

            print("\nDtypes:")
            print(df.dtypes)

            print("\nHead:")
            print(df.head())

            anomalies = detect_basic_anomalies(df, file_path.name)

            print("\nAnomalies / Notes:")
            for item in anomalies:
                print(f"- {item}")

            inventory_rows.append({
                "file_name": file_path.name,
                "rows": df.shape[0],
                "columns": df.shape[1],
                "duplicate_rows": int(df.duplicated().sum()),
                "missing_values_total": int(df.isna().sum().sum()),
            })

            for anomaly in anomalies:
                anomaly_report.append({
                    "file_name": file_path.name,
                    "note": anomaly
                })

        except Exception as e:
            print(f"ERROR reading {file_path.name}: {e}")
            anomaly_report.append({
                "file_name": file_path.name,
                "note": f"ERROR reading file: {e}"
            })

    inventory_df = pd.DataFrame(inventory_rows)
    inventory_path = PROCESSED_DIR / "csv_inventory.csv"
    inventory_df.to_csv(inventory_path, index=False)

    anomaly_df = pd.DataFrame(anomaly_report)
    anomaly_path = PROCESSED_DIR / "basic_anomaly_report.csv"
    anomaly_df.to_csv(anomaly_path, index=False)

    print("\nSaved inventory to:", inventory_path)
    print("Saved anomaly report to:", anomaly_path)

    return datasets


def identify_fund_master(datasets: dict[str, pd.DataFrame]) -> tuple[str | None, pd.DataFrame | None]:
    """
    Try to identify fund_master dataset.
    Priority:
    1. File name contains both 'fund' and 'master'
    2. File contains likely fund master columns
    """
    for name, df in datasets.items():
        lower = name.lower()
        if "fund" in lower and "master" in lower:
            return name, df

    for name, df in datasets.items():
        fund_house_col = find_column(df, ["fund_house", "fund house", "amc", "amc_name"])
        scheme_code_col = find_column(df, ["scheme_code", "scheme code", "amfi_code", "amfi code"])
        if fund_house_col and scheme_code_col:
            return name, df

    return None, None


def identify_nav_history(datasets: dict[str, pd.DataFrame]) -> tuple[str | None, pd.DataFrame | None]:
    """
    Try to identify nav_history dataset.
    Priority:
    1. File name contains both 'nav' and 'history'
    2. File contains likely scheme code, nav, and date columns
    """
    for name, df in datasets.items():
        lower = name.lower()
        if "nav" in lower and "history" in lower:
            return name, df

    for name, df in datasets.items():
        scheme_code_col = find_column(df, ["scheme_code", "scheme code", "amfi_code", "amfi code"])
        nav_col = find_column(df, ["nav", "net_asset_value", "net asset value"])
        date_col = find_column(df, ["date", "nav_date", "nav date"])

        if scheme_code_col and nav_col and date_col:
            return name, df

    return None, None


def print_unique_values(df: pd.DataFrame, label: str, possible_columns: list[str]) -> str:
    """
    Print unique values for a selected column.
    """
    col = find_column(df, possible_columns)

    if col is None:
        message = f"{label}: Column not found. Tried {possible_columns}"
        print(message)
        return message

    unique_values = sorted(df[col].dropna().astype(str).unique())

    print(f"\n{label}")
    print(f"Column used: {col}")
    print(f"Unique count: {len(unique_values)}")

    if len(unique_values) <= 50:
        for value in unique_values:
            print(f"- {value}")
    else:
        print("Showing first 50 values:")
        for value in unique_values[:50]:
            print(f"- {value}")

    return f"{label}: column={col}, unique_count={len(unique_values)}"


def understand_amfi_scheme_code_structure(fund_master_df: pd.DataFrame) -> list[str]:
    """
    Study scheme code format in fund_master.
    AMFI scheme codes should be treated as identifier keys, not mathematical numbers.
    """
    print("\n" + "=" * 80)
    print("STEP 3: AMFI SCHEME CODE STRUCTURE")
    print("=" * 80)

    notes = []

    scheme_code_col = find_column(
        fund_master_df,
        ["scheme_code", "scheme code", "amfi_code", "amfi code", "code"]
    )

    if scheme_code_col is None:
        note = "Scheme code column not found in fund_master."
        print(note)
        return [note]

    codes = fund_master_df[scheme_code_col].dropna().astype(str).str.strip()

    numeric_count = codes.str.fullmatch(r"\d+").sum()
    total_count = len(codes)

    code_lengths = codes.str.len().value_counts().sort_index()

    print(f"Scheme code column used: {scheme_code_col}")
    print(f"Total non-null scheme codes: {total_count}")
    print(f"Numeric-only scheme codes: {numeric_count}")
    print("\nScheme code length distribution:")
    print(code_lengths)

    print("\nSample AMFI scheme codes:")
    print(codes.head(10).to_list())

    duplicate_codes = codes.duplicated().sum()
    print(f"\nDuplicate scheme codes in fund_master: {duplicate_codes}")

    notes.append(f"Scheme code column used: {scheme_code_col}")
    notes.append(f"Total non-null scheme codes: {total_count}")
    notes.append(f"Numeric-only scheme codes: {numeric_count}")
    notes.append(f"Duplicate scheme codes in fund_master: {duplicate_codes}")
    notes.append("AMFI scheme codes should be treated as string identifiers.")
    notes.append("Do not infer fund house/category from the digits of the scheme code.")

    return notes


def explore_fund_master(datasets: dict[str, pd.DataFrame]) -> list[str]:
    """
    Explore fund master dataset.
    """
    print("\n" + "=" * 80)
    print("STEP 2: FUND MASTER EXPLORATION")
    print("=" * 80)

    fund_master_name, fund_master_df = identify_fund_master(datasets)

    notes = []

    if fund_master_df is None:
        note = "Could not identify fund_master dataset automatically."
        print(note)
        return [note]

    print(f"Fund master dataset identified as: {fund_master_name}")
    print(f"Shape: {fund_master_df.shape}")

    notes.append(f"Fund master dataset identified as: {fund_master_name}")
    notes.append(f"Fund master shape: {fund_master_df.shape}")

    notes.append(
        print_unique_values(
            fund_master_df,
            "Unique fund houses",
            ["fund_house", "fund house", "amc", "amc_name", "fundhouse"]
        )
    )

    notes.append(
        print_unique_values(
            fund_master_df,
            "Unique categories",
            ["category", "scheme_category", "scheme category", "scheme_type", "scheme type"]
        )
    )

    notes.append(
        print_unique_values(
            fund_master_df,
            "Unique sub-categories",
            ["sub_category", "sub-category", "subcategory", "scheme_sub_category", "scheme sub category"]
        )
    )

    notes.append(
        print_unique_values(
            fund_master_df,
            "Unique risk grades",
            ["risk_grade", "risk grade", "riskometer", "risk", "risk_level", "risk level"]
        )
    )

    amfi_notes = understand_amfi_scheme_code_structure(fund_master_df)
    notes.extend(amfi_notes)

    return notes


def validate_amfi_codes(datasets: dict[str, pd.DataFrame]) -> list[str]:
    """
    Confirm every AMFI scheme code in fund_master exists in nav_history.
    """
    print("\n" + "=" * 80)
    print("STEP 4: VALIDATING AMFI CODES")
    print("=" * 80)

    notes = []

    fund_master_name, fund_master_df = identify_fund_master(datasets)
    nav_history_name, nav_history_df = identify_nav_history(datasets)

    if fund_master_df is None:
        note = "Validation failed: fund_master dataset not found."
        print(note)
        return [note]

    if nav_history_df is None:
        note = "Validation failed: nav_history dataset not found."
        print(note)
        return [note]

    print(f"Fund master dataset: {fund_master_name}")
    print(f"NAV history dataset: {nav_history_name}")

    fund_code_col = find_column(
        fund_master_df,
        ["scheme_code", "scheme code", "amfi_code", "amfi code", "code"]
    )

    nav_code_col = find_column(
        nav_history_df,
        ["scheme_code", "scheme code", "amfi_code", "amfi code", "code"]
    )

    if fund_code_col is None:
        note = "Validation failed: scheme code column not found in fund_master."
        print(note)
        return [note]

    if nav_code_col is None:
        note = "Validation failed: scheme code column not found in nav_history."
        print(note)
        return [note]

    fund_codes = set(
        fund_master_df[fund_code_col]
        .dropna()
        .astype(str)
        .str.strip()
    )

    nav_codes = set(
        nav_history_df[nav_code_col]
        .dropna()
        .astype(str)
        .str.strip()
    )

    missing_in_nav = sorted(fund_codes - nav_codes)
    extra_in_nav = sorted(nav_codes - fund_codes)

    duplicate_fund_codes = (
        fund_master_df[fund_code_col]
        .dropna()
        .astype(str)
        .str.strip()
        .duplicated()
        .sum()
    )

    duplicate_nav_code_rows = (
        nav_history_df[nav_code_col]
        .dropna()
        .astype(str)
        .str.strip()
        .duplicated()
        .sum()
    )

    print(f"\nFund master code column: {fund_code_col}")
    print(f"NAV history code column: {nav_code_col}")

    print(f"\nUnique codes in fund_master: {len(fund_codes)}")
    print(f"Unique codes in nav_history: {len(nav_codes)}")

    print(f"\nCodes in fund_master missing from nav_history: {len(missing_in_nav)}")
    if missing_in_nav:
        print("First 30 missing codes:")
        print(missing_in_nav[:30])

    print(f"\nCodes in nav_history not present in fund_master: {len(extra_in_nav)}")
    if extra_in_nav:
        print("First 30 extra codes:")
        print(extra_in_nav[:30])

    print(f"\nDuplicate scheme codes in fund_master: {duplicate_fund_codes}")
    print(f"Duplicate scheme code rows in nav_history: {duplicate_nav_code_rows}")

    if len(missing_in_nav) == 0:
        validation_status = "PASS: Every fund_master scheme code exists in nav_history."
    else:
        validation_status = "FAIL: Some fund_master scheme codes are missing from nav_history."

    print("\nValidation status:")
    print(validation_status)

    notes.append(f"Fund master dataset: {fund_master_name}")
    notes.append(f"NAV history dataset: {nav_history_name}")
    notes.append(f"Fund master code column: {fund_code_col}")
    notes.append(f"NAV history code column: {nav_code_col}")
    notes.append(f"Unique codes in fund_master: {len(fund_codes)}")
    notes.append(f"Unique codes in nav_history: {len(nav_codes)}")
    notes.append(f"Codes in fund_master missing from nav_history: {len(missing_in_nav)}")
    notes.append(f"Codes in nav_history not present in fund_master: {len(extra_in_nav)}")
    notes.append(f"Duplicate scheme codes in fund_master: {duplicate_fund_codes}")
    notes.append(f"Duplicate scheme code rows in nav_history: {duplicate_nav_code_rows}")
    notes.append(validation_status)

    validation_df = pd.DataFrame({
        "missing_fund_master_codes_in_nav_history": pd.Series(missing_in_nav),
    })

    validation_path = PROCESSED_DIR / "missing_codes_validation.csv"
    validation_df.to_csv(validation_path, index=False)

    print(f"\nSaved missing code validation to: {validation_path}")

    return notes


def write_data_quality_summary(
    loading_notes: list[str],
    fund_master_notes: list[str],
    validation_notes: list[str]
):
    """
    Write final Day 1 data quality summary.
    """
    summary_path = REPORTS_DIR / "data_quality_summary.md"

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Day 1 Data Quality Summary\n\n")

        f.write("## 1. CSV Loading Summary\n\n")
        for note in loading_notes:
            f.write(f"- {note}\n")

        f.write("\n## 2. Fund Master Exploration\n\n")
        for note in fund_master_notes:
            f.write(f"- {note}\n")

        f.write("\n## 3. AMFI Code Validation\n\n")
        for note in validation_notes:
            f.write(f"- {note}\n")

        f.write("\n## 4. Short Conclusion\n\n")
        f.write(
            "The Day 1 ingestion pipeline loads all provided CSV datasets, "
            "profiles their structure, checks basic anomalies, explores the fund master, "
            "and validates AMFI scheme codes between fund_master and nav_history. "
            "Any missing codes, duplicate rows, or schema issues should be reviewed "
            "before moving to transformation, SQL modeling, and dashboard development.\n"
        )

    print(f"\nData quality summary saved to: {summary_path}")


def main():
    datasets = load_and_profile_csvs()

    if not datasets:
        return

    loading_notes = [
        f"Total provided CSV datasets loaded: {len(datasets)}",
        "Printed shape, dtypes, and head for each dataset.",
        "Saved CSV inventory to data/processed/csv_inventory.csv.",
        "Saved basic anomaly report to data/processed/basic_anomaly_report.csv.",
    ]

    fund_master_notes = explore_fund_master(datasets)

    validation_notes = validate_amfi_codes(datasets)

    write_data_quality_summary(
        loading_notes=loading_notes,
        fund_master_notes=fund_master_notes,
        validation_notes=validation_notes
    )


if __name__ == "__main__":
    main()