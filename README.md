# Mutual Fund Analytics

This project builds a mutual fund analytics pipeline using Python, Pandas, SQL, and dashboarding tools.

## Day 1 Goals

- Create project folder structure.
- Load 10 provided CSV datasets.
- Profile each dataset using shape, dtypes, and sample rows.
- Fetch live NAV data from MFapi.
- Explore fund master data.
- Validate AMFI scheme codes between fund_master and nav_history.
- Save data quality summary.

## Folder Structure

```text
data/raw/          Raw input CSV files
data/processed/    Cleaned and generated processed files
notebooks/         Jupyter notebooks
sql/               SQL scripts
dashboard/         Dashboard code
reports/           Reports and summaries