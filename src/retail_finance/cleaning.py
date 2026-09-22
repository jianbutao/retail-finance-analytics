"""Pure classification and audited cross-sheet removal; no output writes."""
import numpy as np
import pandas as pd

COLUMN_MAPPING = {
    "Invoice": "invoice_no", "StockCode": "stock_code",
    "Description": "description", "Quantity": "quantity",
    "InvoiceDate": "invoice_date", "Price": "unit_price",
    "Customer ID": "customer_id", "Country": "country",
}
BUSINESS_COLUMNS = list(COLUMN_MAPPING.values())
SHEETS = ["Year 2009-2010", "Year 2010-2011"]


def read_raw(path):
    frames = []
    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        if set(workbook.sheet_names) != set(SHEETS):
            raise ValueError("Unexpected worksheet names")
        for sheet in SHEETS:
            part = pd.read_excel(workbook, sheet_name=sheet, dtype={
                "Invoice": "string", "StockCode": "string", "Customer ID": "string",
            })
            if set(part.columns) != set(COLUMN_MAPPING):
                raise ValueError(f"Unexpected raw columns in {sheet}")
            part = part.rename(columns=COLUMN_MAPPING)
            part["source_sheet"] = sheet
            part["source_excel_row"] = range(2, len(part) + 2)
            frames.append(part)
    raw = pd.concat(frames, ignore_index=True)
    raw["invoice_date"] = pd.to_datetime(raw["invoice_date"], errors="raise")
    if raw["invoice_date"].isna().any():
        raise ValueError("Missing invoice dates")
    return raw


def remove_cross_sheet_copies(raw):
    if raw.empty or not raw.index.is_unique:
        raise ValueError("Expected nonempty raw data with a unique index")
    if not set(raw["source_sheet"]).issubset(SHEETS):
        raise ValueError("Unknown source sheet")
    if raw.duplicated(["source_sheet", "source_excel_row"]).any():
        raise ValueError("Duplicate source row identifiers")
    candidates = raw.loc[raw.duplicated(BUSINESS_COLUMNS, keep=False)]
    sources = candidates.groupby(BUSINESS_COLUMNS, dropna=False)["source_sheet"].transform("nunique")
    overlap = candidates.loc[sources > 1]
    if not overlap.empty:
        counts = overlap.groupby(BUSINESS_COLUMNS + ["source_sheet"], dropna=False).size()
        counts = counts.unstack("source_sheet", fill_value=0).reindex(columns=SHEETS, fill_value=0)
        if not counts[SHEETS[0]].eq(counts[SHEETS[1]]).all():
            raise ValueError("Cross-sheet multiplicities differ; manual review required")
    excluded = overlap.index[overlap["source_sheet"].eq(SHEETS[1])]
    audited = raw.copy()
    audited["excluded_cross_sheet_duplicate"] = audited.index.isin(excluded)
    return (audited.loc[~audited["excluded_cross_sheet_duplicate"]].copy(),
            audited.loc[audited["excluded_cross_sheet_duplicate"]].copy())


def classify_transactions(base, rules):
    result = base.copy()
    code = result["stock_code"].astype("string").str.strip().str.upper()
    result["item_type"] = code.map(rules["special_code_map"])
    result.loc[code.str.startswith("GIFT_", na=False), "item_type"] = "礼券"
    product = code.str.match(r"^\d", na=False) | code.isin(rules["reviewed_product_codes"])
    result.loc[result["item_type"].isna() & product, "item_type"] = "商品候选"
    result["item_type"] = result["item_type"].fillna("编码待核查")
    cancel = result["invoice_no"].astype("string").str.strip().str.upper().str.startswith("C", na=False)
    qty, price = result["quantity"], result["unit_price"]
    result["transaction_type"] = "待核查"
    for mask, label in [
        (~cancel & (qty > 0) & (price > 0), "正向交易"),
        (cancel & (qty < 0) & (price > 0), "取消或冲销"),
        (~cancel & (qty < 0) & (price > 0), "非取消负数量"),
        (price == 0, "零单价记录"),
        (price < 0, "负单价记录"),
    ]:
        result.loc[mask, "transaction_type"] = label
    result["line_amount"] = qty * price
    product = result["item_type"].eq("商品候选")
    result["include_product_sales"] = product & result["transaction_type"].eq("正向交易")
    result["include_product_cancellations"] = product & result["transaction_type"].eq("取消或冲销")
    result["include_customer_sales"] = result["include_product_sales"] & result["customer_id"].notna()
    result["description"] = result["description"].astype("string")
    return result


def amount_milliunits(data):
    """Exact thousandths for audit, preserving genuine 0.001 unit prices."""
    prices = data["unit_price"].to_numpy(dtype=float) * 1000
    quantities = data["quantity"].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or not np.isfinite(quantities).all():
        raise ValueError("Non-finite amount inputs")
    if not np.allclose(prices, np.rint(prices), rtol=0, atol=1e-6):
        raise ValueError("Unit price has precision beyond thousandths")
    if not np.equal(quantities, np.rint(quantities)).all():
        raise ValueError("Quantity must be integral")
    # Python integer arithmetic avoids silent int64 multiplication overflow.
    return pd.Series([int(round(p)) * int(q) for p, q in zip(prices, quantities)],
                     index=data.index, dtype=object)
