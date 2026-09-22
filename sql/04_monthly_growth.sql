-- Read-only. Missing consecutive months and the partial final month have no MoM.
WITH monthly_sales AS (
    SELECT
        DATE_TRUNC('month', invoice_date)::date AS month,
        SUM(line_amount) AS gross_amount
    FROM analytics.transactions
    WHERE source_batch = '20260917T121850_455264Z'
      AND include_product_sales = TRUE
    GROUP BY DATE_TRUNC('month', invoice_date)::date
),
with_previous AS (
    SELECT
        month,
        gross_amount,
        LAG(month) OVER (ORDER BY month) AS previous_month,
        LAG(gross_amount) OVER (ORDER BY month) AS previous_amount
    FROM monthly_sales
)
SELECT
    month,
    ROUND(gross_amount, 2) AS gross_amount,
    ROUND(previous_amount, 2) AS previous_amount,
    CASE
        WHEN month = DATE '2011-12-01' THEN NULL
        WHEN previous_month IS NULL THEN NULL
        WHEN month <> (previous_month + INTERVAL '1 month')::date THEN NULL
        ELSE ROUND(
            (gross_amount / NULLIF(previous_amount, 0) - 1) * 100, 2
        )
    END AS gross_mom_pct
FROM with_previous
ORDER BY month;
