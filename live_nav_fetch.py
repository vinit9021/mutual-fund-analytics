from pathlib import Path
from datetime import datetime
import time
import requests
import pandas as pd


BASE_URL = "https://api.mfapi.in/mf"

RAW_API_DIR = Path("data/raw/mfapi_nav")
RAW_API_DIR.mkdir(parents=True, exist_ok=True)


SCHEMES = {
    "hdfc_large_cap_direct": "119018",
    "sbi_large_cap_direct": "119598",
    "icici_large_cap_direct": "120586",
    "nippon_large_cap_direct": "118632",
    "axis_large_cap_direct": "120465",
    "kotak_large_cap_direct": "120152",
}


def safe_filename(name: str) -> str:
    return (
        name.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace("__", "_")
    )


def request_with_retry(url: str, max_retries: int = 3, timeout: int = 90):
    """
    Try the API request multiple times.
    This helps when the server is slow or gives timeout.
    """
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            print(f"Attempt {attempt}/{max_retries}")
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            last_error = e
            print(f"Attempt {attempt} failed: {e}")

            if attempt < max_retries:
                print("Waiting 5 seconds before retrying...")
                time.sleep(5)

    raise last_error


def fetch_scheme_nav_history(scheme_name: str, scheme_code: str) -> pd.DataFrame:
    url = f"{BASE_URL}/{scheme_code}"

    print("\n" + "=" * 90)
    print(f"Fetching: {scheme_name} | Code: {scheme_code}")
    print(f"URL: {url}")
    print("=" * 90)

    response = request_with_retry(url, max_retries=3, timeout=90)
    payload = response.json()

    meta = payload.get("meta", {})
    data = payload.get("data", [])

    if not data:
        print(f"WARNING: No NAV data found for {scheme_name} ({scheme_code})")
        return pd.DataFrame()

    df = pd.DataFrame(data)

    df["scheme_code"] = str(meta.get("scheme_code", scheme_code))
    df["scheme_name"] = meta.get("scheme_name", scheme_name)
    df["fund_house"] = meta.get("fund_house")
    df["scheme_type"] = meta.get("scheme_type")
    df["scheme_category"] = meta.get("scheme_category")
    df["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    df["raw_date"] = df["date"]

    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")

    df = df.sort_values("date", ascending=False)

    return df


def main():
    all_dfs = []
    latest_rows = []
    failed_schemes = []

    for scheme_name, scheme_code in SCHEMES.items():
        try:
            df = fetch_scheme_nav_history(scheme_name, scheme_code)

            if df.empty:
                failed_schemes.append((scheme_name, scheme_code))
                continue

            file_name = f"{safe_filename(scheme_name)}_{scheme_code}_nav_history.csv"
            output_path = RAW_API_DIR / file_name
            df.to_csv(output_path, index=False)

            print(f"Saved NAV history: {output_path}")
            print(f"Shape: {df.shape}")
            print("Latest row:")
            print(df.head(1))

            all_dfs.append(df)
            latest_rows.append(df.head(1))

            time.sleep(1)

        except Exception as e:
            print(f"FINAL ERROR for {scheme_name} ({scheme_code}): {e}")
            failed_schemes.append((scheme_name, scheme_code))

    if all_dfs:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        combined_path = RAW_API_DIR / "all_schemes_nav_history.csv"
        combined_df.to_csv(combined_path, index=False)

        print("\n" + "=" * 90)
        print(f"Combined NAV history saved to: {combined_path}")
        print(f"Combined shape: {combined_df.shape}")
        print(f"Number of schemes in combined file: {combined_df['scheme_code'].nunique()}")
        print("=" * 90)

    if latest_rows:
        latest_df = pd.concat(latest_rows, ignore_index=True)
        latest_path = RAW_API_DIR / "all_latest_nav.csv"
        latest_df.to_csv(latest_path, index=False)

        print("\nLatest NAV summary saved to:", latest_path)
        print(latest_df[["scheme_code", "scheme_name", "date", "nav"]])

    if failed_schemes:
        print("\nFAILED SCHEMES:")
        for name, code in failed_schemes:
            print(f"- {name}: {code}")

        failed_df = pd.DataFrame(failed_schemes, columns=["scheme_name", "scheme_code"])
        failed_path = RAW_API_DIR / "failed_schemes.csv"
        failed_df.to_csv(failed_path, index=False)
        print(f"Failed schemes saved to: {failed_path}")

    else:
        print("\nAll schemes fetched successfully.")


if __name__ == "__main__":
    main()