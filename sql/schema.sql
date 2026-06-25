-- Mutual Fund Analytics - Starter SQL Schema

CREATE TABLE fund_master (
    scheme_code VARCHAR(20) PRIMARY KEY,
    scheme_name TEXT,
    fund_house TEXT,
    scheme_type TEXT,
    scheme_category TEXT,
    category TEXT,
    sub_category TEXT,
    risk_grade TEXT,
    plan_type TEXT,
    option_type TEXT
);

CREATE TABLE nav_history (
    scheme_code VARCHAR(20),
    scheme_name TEXT,
    nav_date DATE,
    nav NUMERIC,
    fund_house TEXT,
    scheme_type TEXT,
    scheme_category TEXT,
    FOREIGN KEY (scheme_code) REFERENCES fund_master(scheme_code)
);

CREATE TABLE daily_returns (
    scheme_code VARCHAR(20),
    scheme_name TEXT,
    return_date DATE,
    nav NUMERIC,
    daily_return NUMERIC,
    daily_return_percent NUMERIC,
    FOREIGN KEY (scheme_code) REFERENCES fund_master(scheme_code)
);

CREATE TABLE risk_metrics (
    scheme_code VARCHAR(20),
    scheme_name TEXT,
    observations INTEGER,
    mean_daily_return NUMERIC,
    daily_volatility NUMERIC,
    annualized_return NUMERIC,
    annualized_volatility NUMERIC,
    sharpe_ratio NUMERIC,
    FOREIGN KEY (scheme_code) REFERENCES fund_master(scheme_code)
);