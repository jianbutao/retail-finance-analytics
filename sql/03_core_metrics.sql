-- Read-only queries. Execute each complete SELECT separately.
-- Aggregate at original precision; round only for display.
SELECT
    COUNT(*) AS retained_rows,
    ROUND(SUM(line_amount) FILTER (WHERE include_product_sales), 2)
        AS product_gross_amount,
    ROUND(-SUM(line_amount) FILTER (WHERE include_product_cancellations), 2)
        AS product_cancel_amount,
    ROUND(SUM(line_amount) FILTER (
        WHERE include_product_sales OR include_product_cancellations
    ), 2) AS product_net_amount,
    COUNT(DISTINCT invoice_no) FILTER (WHERE include_product_sales)
        AS product_sales_orders,
    COUNT(DISTINCT customer_id) FILTER (WHERE include_customer_sales)
        AS identified_buyers
FROM analytics.transactions
WHERE source_batch = '20260917T121850_455264Z';

SELECT
    DATE_TRUNC('month', invoice_date)::date AS month,
    ROUND(SUM(line_amount), 2) AS gross_amount,
    COUNT(DISTINCT invoice_no) AS sales_orders,
    COUNT(DISTINCT invoice_date::date) AS recorded_sales_days
FROM analytics.transactions
WHERE source_batch = '20260917T121850_455264Z'
  AND include_product_sales = TRUE
GROUP BY DATE_TRUNC('month', invoice_date)::date
ORDER BY month;
