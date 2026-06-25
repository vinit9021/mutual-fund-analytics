import requests
import pandas as pd
from pathlib import Path


SEARCH_URL = "https://api.mfapi.in/mf/search"

OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


SEARCH_TERMS = {
    "hdfc_top_100_or_large_cap": [
        "HDFC",
        "HDFC Top 100",
        "HDFC Large Cap",
        "HDFC Direct Growth",
    ],
    "sbi_bluechip": [
        "SBI",
        "SBI Blue",
        "SBI Blue Chip",
        "SBI Bluechip",
        "SBI Direct Growth",
    ],
    "icici_bluechip_or_large_cap": [
        "ICICI Prudential Bluechip",
        "ICICI Prudential Blue Chip",
        "ICICI Prudential Large Cap",
    ],
    "nippon_large_cap": [
        "Nippon India Large Cap",
        "Nippon Large Cap",
    ],
    "axis_bluechip_or_large_cap": [
        "Axis",
        "Axis Bluechip",
        "Axis Blue Chip",
        "Axis Large Cap",
    ],
    "kotak_bluechip_or_large_cap": [
        "Kotak",
        "Kotak Bluechip",
        "Kotak Blue Chip",
        "Kotak Large Cap",
    ],
}


def get_value(item, possible_keys):
    for key in possible_keys:
        if key in item:
            return item[key]
    return None


def search_one_query(query):
    response = requests.get(SEARCH_URL, params={"q": query}, timeout=30)
    response.raise_for_status()
    return response.json()


def normalize_text(text):
    return str(text).lower().replace("-", " ").replace("_", " ").strip()


def is_good_candidate(target_key, scheme_name):
    """
    Filter candidates so that we do not print too many irrelevant schemes.
    """
    name = normalize_text(scheme_name)

    if target_key == "hdfc_top_100_or_large_cap":
        return (
            "hdfc" in name
            and ("top 100" in name or "large cap" in name)
            and "direct" in name
            and "growth" in name
        )

    if target_key == "sbi_bluechip":
        return (
            "sbi" in name
            and ("blue chip" in name or "bluechip" in name or "large cap" in name)
            and "direct" in name
            and "growth" in name
        )

    if target_key == "icici_bluechip_or_large_cap":
        return (
            "icici" in name
            and ("bluechip" in name or "blue chip" in name or "large cap" in name)
            and "direct" in name
            and "growth" in name
        )

    if target_key == "nippon_large_cap":
        return (
            "nippon" in name
            and "large cap" in name
            and "direct" in name
            and "growth" in name
        )

    if target_key == "axis_bluechip_or_large_cap":
        return (
            "axis" in name
            and ("bluechip" in name or "blue chip" in name or "large cap" in name)
            and "direct" in name
            and "growth" in name
        )

    if target_key == "kotak_bluechip_or_large_cap":
        return (
            "kotak" in name
            and ("bluechip" in name or "blue chip" in name or "large cap" in name)
            and "direct" in name
            and "growth" in name
        )

    return False


def main():
    all_rows = []

    for target_key, queries in SEARCH_TERMS.items():
        print("\n" + "=" * 110)
        print(f"TARGET: {target_key}")
        print("=" * 110)

        seen_codes = set()
        target_rows = []

        for query in queries:
            print(f"\nSearching query: {query}")

            try:
                results = search_one_query(query)

                if not results:
                    print("No results found.")
                    continue

                for item in results:
                    scheme_code = get_value(item, ["schemeCode", "scheme_code", "code"])
                    scheme_name = get_value(item, ["schemeName", "scheme_name", "name"])

                    if scheme_code is None or scheme_name is None:
                        continue

                    scheme_code = str(scheme_code)

                    if scheme_code in seen_codes:
                        continue

                    seen_codes.add(scheme_code)

                    row = {
                        "target": target_key,
                        "query_used": query,
                        "scheme_code": scheme_code,
                        "scheme_name": scheme_name,
                        "is_good_candidate": is_good_candidate(target_key, scheme_name),
                    }

                    target_rows.append(row)
                    all_rows.append(row)

            except Exception as e:
                print(f"Error for query '{query}': {e}")

        good_candidates = [row for row in target_rows if row["is_good_candidate"]]

        if good_candidates:
            print("\nBest candidates:")
            for i, row in enumerate(good_candidates[:10], start=1):
                print(f"{i}. Code: {row['scheme_code']}")
                print(f"   Name: {row['scheme_name']}")
        else:
            print("\nNo strong candidate found. Showing first 15 broad results:")
            for i, row in enumerate(target_rows[:15], start=1):
                print(f"{i}. Code: {row['scheme_code']}")
                print(f"   Name: {row['scheme_name']}")

    if all_rows:
        df = pd.DataFrame(all_rows)
        output_path = OUTPUT_DIR / "scheme_code_search_results.csv"
        df.to_csv(output_path, index=False)
        print("\n" + "=" * 110)
        print(f"Saved all search results to: {output_path}")
        print("=" * 110)


if __name__ == "__main__":
    main()