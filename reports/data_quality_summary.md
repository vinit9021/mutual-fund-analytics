# Day 1 Data Quality Summary

## 1. CSV Loading Summary

- Total provided CSV datasets loaded: 10
- Printed shape, dtypes, and head for each dataset.
- Saved CSV inventory to data/processed/csv_inventory.csv.
- Saved basic anomaly report to data/processed/basic_anomaly_report.csv.

## 2. Fund Master Exploration

- Fund master dataset identified as: fund_master
- Fund master shape: (6, 10)
- Unique fund houses: column=fund_house, unique_count=6
- Unique categories: column=category, unique_count=1
- Unique sub-categories: column=sub_category, unique_count=1
- Unique risk grades: column=risk_grade, unique_count=1
- Scheme code column used: scheme_code
- Total non-null scheme codes: 6
- Numeric-only scheme codes: 6
- Duplicate scheme codes in fund_master: 0
- AMFI scheme codes should be treated as string identifiers.
- Do not infer fund house/category from the digits of the scheme code.

## 3. AMFI Code Validation

- Fund master dataset: fund_master
- NAV history dataset: nav_history
- Fund master code column: scheme_code
- NAV history code column: scheme_code
- Unique codes in fund_master: 6
- Unique codes in nav_history: 6
- Codes in fund_master missing from nav_history: 0
- Codes in nav_history not present in fund_master: 0
- Duplicate scheme codes in fund_master: 0
- Duplicate scheme code rows in nav_history: 19902
- PASS: Every fund_master scheme code exists in nav_history.

## 4. Short Conclusion

The Day 1 ingestion pipeline loads all provided CSV datasets, profiles their structure, checks basic anomalies, explores the fund master, and validates AMFI scheme codes between fund_master and nav_history. Any missing codes, duplicate rows, or schema issues should be reviewed before moving to transformation, SQL modeling, and dashboard development.
