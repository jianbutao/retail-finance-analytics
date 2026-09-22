-- Execute in retail_finance. Run CREATE TABLE only if the table is absent.
-- line_amount is generated; omit it from imports.
CREATE TABLE analytics.transactions (
    source_batch TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    source_excel_row INTEGER NOT NULL,
    invoice_no TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    description TEXT,
    customer_id TEXT,
    country TEXT NOT NULL,
    invoice_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(18, 3) NOT NULL,
    line_amount NUMERIC(20, 3)
        GENERATED ALWAYS AS (quantity * unit_price) STORED,
    item_type TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    excluded_cross_sheet_duplicate BOOLEAN NOT NULL,
    include_product_sales BOOLEAN NOT NULL,
    include_product_cancellations BOOLEAN NOT NULL,
    include_customer_sales BOOLEAN NOT NULL,
    CONSTRAINT transactions_pk PRIMARY KEY (
        source_batch, source_sheet, source_excel_row
    ),
    CONSTRAINT valid_source_row CHECK (source_excel_row >= 2),
    CONSTRAINT no_excluded_cross_sheet_rows
        CHECK (excluded_cross_sheet_duplicate = FALSE),
    CONSTRAINT customer_sales_scope_valid CHECK (
        NOT include_customer_sales
        OR (include_product_sales AND customer_id IS NOT NULL)
    ),
    CONSTRAINT sales_and_cancellations_disjoint CHECK (
        NOT (include_product_sales AND include_product_cancellations)
    )
);
