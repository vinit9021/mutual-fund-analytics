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