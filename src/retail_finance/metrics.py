"""Shared business metrics; amounts are transactions, not recognised revenue."""
import numpy as np
import pandas as pd
from .cleaning import amount_milliunits


def overview(data):
    sales = data["include_product_sales"]
    cancel = data["include_product_cancellations"]
    identified = sales & data["customer_id"].notna()
    milli = amount_milliunits(data)
    gross, cancellations = int(milli[sales].sum()), -int(milli[cancel].sum())
    return {"rows": len(data), "gross_milli": gross, "cancel_milli": cancellations,
            "net_milli": gross - cancellations,
            "sales_orders": int(data.loc[sales, "invoice_no"].nunique()),
            "identified_customers": int(data.loc[identified, "customer_id"].nunique()),
            "cancel_amount_pct": cancellations / gross * 100 if gross else None,
            "identified_coverage_pct": int(milli[identified].sum()) / gross * 100 if gross else None}


def monthly_metrics(data):
    if data.empty:
        raise ValueError("Cannot infer calendar coverage from empty data")
    dates = data["invoice_date"].dt.normalize()
    first, last = dates.min(), dates.max()
    calendar = pd.date_range(first.to_period("M").start_time,
                             last.to_period("M").end_time.normalize(), freq="D")
    sales = data.loc[data["include_product_sales"]]
    cancel = data.loc[data["include_product_cancellations"]]
    daily = pd.DataFrame(index=calendar)
    daily["recorded"] = data.groupby(dates).size().reindex(calendar, fill_value=0) > 0
    daily["sales"] = sales.groupby(sales["invoice_date"].dt.normalize()).size().reindex(calendar, fill_value=0) > 0
    result = daily.groupby(daily.index.to_period("M")).agg(
        calendar_days=("recorded", "size"), days_with_records=("recorded", "sum"),
        days_with_product_sales=("sales", "sum"))
    positive = sales.groupby(sales["invoice_date"].dt.to_period("M")).agg(
        gross_amount=("line_amount", "sum"), sales_orders=("invoice_no", "nunique"))
    result = result.join(positive)
    result["cancel_amount"] = cancel.groupby(cancel["invoice_date"].dt.to_period("M"))["line_amount"].sum().mul(-1).reindex(result.index).fillna(0)
    result["net_amount"] = result["gross_amount"] - result["cancel_amount"]
    result["amount_per_recorded_sales_day"] = result["gross_amount"] / result["days_with_product_sales"].replace(0, np.nan)
    result["month_boundary_truncated"] = (result.index.start_time < first) | (result.index.end_time.normalize() > last)
    return result


def customer_structure(data):
    sales = data.loc[data["include_product_sales"] & data["customer_id"].notna()]
    result = sales.groupby("customer_id").agg(gross_amount=("line_amount", "sum"),
        order_count=("invoice_no", "nunique"), first_purchase=("invoice_date", "min"),
        last_purchase=("invoice_date", "max"))
    # Deterministic customer-ID tie break.
    result = result.reset_index().sort_values(["gross_amount", "customer_id"], ascending=[False, True]).set_index("customer_id")
    total = result["gross_amount"].sum()
    result["share_of_identified_pct"] = result["gross_amount"] / total * 100 if total else np.nan
    result["cumulative_share_pct"] = result["share_of_identified_pct"].cumsum()
    return result


def product_structure(data):
    sales = data.loc[data["include_product_sales"]]
    cancel = data.loc[data["include_product_cancellations"]]
    positive = sales.groupby("stock_code").agg(gross_amount=("line_amount", "sum"),
        sales_orders=("invoice_no", "nunique"), units_sold=("quantity", "sum"))
    negative = cancel.groupby("stock_code")["line_amount"].sum().mul(-1).rename("cancel_amount")
    result = positive.join(negative, how="outer").fillna(0)
    result["sales_orders"] = result["sales_orders"].astype("int64")
    result["net_amount"] = result["gross_amount"] - result["cancel_amount"]
    result["cancel_to_gross_pct"] = result["cancel_amount"] / result["gross_amount"].replace(0, np.nan) * 100
    # Same display-only selection as the archived experiment.
    description = sales.loc[sales["description"].notna()].sort_values("invoice_date").drop_duplicates("stock_code", keep="last").set_index("stock_code")["description"]
    return result.join(description.rename("description_example"))
