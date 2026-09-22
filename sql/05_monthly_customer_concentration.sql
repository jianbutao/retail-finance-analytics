-- Read-only. Rank identified customers separately within each month.
-- Positive product transactions only; cancellations are not deducted.
-- Unidentified customers contribute only to the all-sales denominator.
WITH monthly_totals AS (
    SELECT
        DATE_TRUNC('month', invoice_date)::date AS month,
        SUM(line_amount) AS all_gross_amount
    FROM analytics.transactions
    WHERE source_batch = '20260917T121850_455264Z'
      AND include_product_sales = TRUE
    GROUP BY DATE_TRUNC('month', invoice_date)::date
),
customer_monthly AS (
    SELECT
        DATE_TRUNC('month', invoice_date)::date AS month,
        customer_id,
        SUM(line_amount) AS customer_gross_amount
    FROM analytics.transactions
    WHERE source_batch = '20260917T121850_455264Z'
      AND include_customer_sales = TRUE
    GROUP BY DATE_TRUNC('month', invoice_date)::date, customer_id
),
ranked_customers AS (
    SELECT
        month, customer_id, customer_gross_amount,
        ROW_NUMBER() OVER (
            PARTITION BY month
            ORDER BY customer_gross_amount DESC, customer_id
        ) AS customer_rank
    FROM customer_monthly
),
concentration AS (
    SELECT
        month,
        COUNT(*) AS active_identified_customers,
        SUM(customer_gross_amount) AS identified_gross_amount,
        SUM(customer_gross_amount) FILTER (WHERE customer_rank = 1)
            AS top1_amount,
        SUM(customer_gross_amount) FILTER (WHERE customer_rank <= 10)
            AS top10_amount
    FROM ranked_customers
    GROUP BY month
)
SELECT
    t.month,
    c.active_identified_customers,
    ROUND(c.identified_gross_amount / NULLIF(t.all_gross_amount, 0) * 100, 2)
        AS identified_coverage_pct,
    ROUND(c.top1_amount / NULLIF(c.identified_gross_amount, 0) * 100, 2)
        AS top1_share_identified_pct,
    ROUND(c.top10_amount / NULLIF(c.identified_gross_amount, 0) * 100, 2)
        AS top10_share_identified_pct,
    ROUND(c.top10_amount / NULLIF(t.all_gross_amount, 0) * 100, 2)
        AS top10_share_all_pct,
    t.month = DATE '2011-12-01' AS boundary_truncated
FROM monthly_totals AS t
LEFT JOIN concentration AS c ON t.month = c.month
ORDER BY t.month;
