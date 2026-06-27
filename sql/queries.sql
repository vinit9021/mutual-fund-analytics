-- 1. Top 5 funds by latest AUM
WITH latest_aum_date AS (
    SELECT amfi_code, MAX(date_key) AS latest_date_key
    FROM fact_aum
    GROUP BY amfi_code
)
SELECT
    f.scheme_name,
    f.fund_house,
    a.aum_crore,
    d.full_date
FROM fact_aum a
JOIN latest_aum_date l
    ON a.amfi_code = l.amfi_code
   AND a.date_key = l.latest_date_key
JOIN dim_fund f
    ON a.amfi_code = f.amfi_code
JOIN dim_date d
    ON a.date_key = d.date_key
ORDER BY a.aum_crore DESC
LIMIT 5;


-- 2. Average NAV per month
SELECT
    f.scheme_name,
    d.year,
    d.month,
    ROUND(AVG(n.nav), 4) AS average_nav
FROM fact_nav n
JOIN dim_fund f
    ON n.amfi_code = f.amfi_code
JOIN dim_date d
    ON n.date_key = d.date_key
GROUP BY f.scheme_name, d.year, d.month
ORDER BY f.scheme_name, d.year, d.month;


-- 3. SIP YoY growth
WITH yearly_sip AS (
    SELECT
        d.year,
        SUM(t.amount) AS total_sip_amount
    FROM fact_transactions t
    JOIN dim_date d
        ON t.date_key = d.date_key
    WHERE t.transaction_type = 'SIP'
    GROUP BY d.year
),
growth AS (
    SELECT
        year,
        total_sip_amount,
        LAG(total_sip_amount) OVER (ORDER BY year) AS previous_year_sip
    FROM yearly_sip
)
SELECT
    year,
    ROUND(total_sip_amount, 2) AS total_sip_amount,
    ROUND(previous_year_sip, 2) AS previous_year_sip,
    ROUND(
        ((total_sip_amount - previous_year_sip) / previous_year_sip) * 100,
        2
    ) AS yoy_growth_percent
FROM growth;


-- 4. Transactions by state
SELECT
    state,
    transaction_type,
    COUNT(*) AS transaction_count,
    ROUND(SUM(amount), 2) AS total_amount
FROM fact_transactions
GROUP BY state, transaction_type
ORDER BY total_amount DESC;


-- 5. Funds with expense ratio less than 1%
SELECT
    f.scheme_name,
    f.fund_house,
    p.expense_ratio,
    p.return_1y
FROM fact_performance p
JOIN dim_fund f
    ON p.amfi_code = f.amfi_code
WHERE p.expense_ratio < 1
ORDER BY p.expense_ratio ASC;


-- 6. Best funds by 1-year return
SELECT
    f.scheme_name,
    f.fund_house,
    p.return_1y,
    p.expense_ratio
FROM fact_performance p
JOIN dim_fund f
    ON p.amfi_code = f.amfi_code
ORDER BY p.return_1y DESC
LIMIT 5;


-- 7. Highest volatility funds based on NAV movement
WITH nav_returns AS (
    SELECT
        amfi_code,
        date_key,
        nav,
        (nav / LAG(nav) OVER (PARTITION BY amfi_code ORDER BY date_key)) - 1 AS daily_return
    FROM fact_nav
)
SELECT
    f.scheme_name,
    ROUND(AVG(ABS(nr.daily_return)) * 100, 4) AS avg_absolute_daily_movement_percent
FROM nav_returns nr
JOIN dim_fund f
    ON nr.amfi_code = f.amfi_code
WHERE nr.daily_return IS NOT NULL
GROUP BY f.scheme_name
ORDER BY avg_absolute_daily_movement_percent DESC;


-- 8. Monthly transaction amount by transaction type
SELECT
    d.year,
    d.month,
    t.transaction_type,
    ROUND(SUM(t.amount), 2) AS total_amount
FROM fact_transactions t
JOIN dim_date d
    ON t.date_key = d.date_key
GROUP BY d.year, d.month, t.transaction_type
ORDER BY d.year, d.month, t.transaction_type;


-- 9. Fund-wise redemption amount
SELECT
    f.scheme_name,
    ROUND(SUM(t.amount), 2) AS total_redemption_amount,
    COUNT(*) AS redemption_count
FROM fact_transactions t
JOIN dim_fund f
    ON t.amfi_code = f.amfi_code
WHERE t.transaction_type = 'Redemption'
GROUP BY f.scheme_name
ORDER BY total_redemption_amount DESC;


-- 10. NAV CAGR approximation from first NAV to latest NAV
WITH nav_bounds AS (
    SELECT
        amfi_code,
        MIN(date_key) AS first_date_key,
        MAX(date_key) AS last_date_key
    FROM fact_nav
    GROUP BY amfi_code
),
nav_values AS (
    SELECT
        b.amfi_code,
        first_nav.nav AS first_nav,
        last_nav.nav AS last_nav,
        first_date.full_date AS first_date,
        last_date.full_date AS last_date,
        (julianday(last_date.full_date) - julianday(first_date.full_date)) / 365.25 AS years
    FROM nav_bounds b
    JOIN fact_nav first_nav
        ON b.amfi_code = first_nav.amfi_code
       AND b.first_date_key = first_nav.date_key
    JOIN fact_nav last_nav
        ON b.amfi_code = last_nav.amfi_code
       AND b.last_date_key = last_nav.date_key
    JOIN dim_date first_date
        ON b.first_date_key = first_date.date_key
    JOIN dim_date last_date
        ON b.last_date_key = last_date.date_key
)
SELECT
    f.scheme_name,
    first_date,
    last_date,
    ROUND(first_nav, 4) AS first_nav,
    ROUND(last_nav, 4) AS last_nav,
    ROUND((POWER(last_nav / first_nav, 1.0 / years) - 1) * 100, 2) AS cagr_percent
FROM nav_values nv
JOIN dim_fund f
    ON nv.amfi_code = f.amfi_code
ORDER BY cagr_percent DESC;