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