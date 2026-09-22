"""Windowed RFM; cancelled-only customers are not positive purchasers."""
import numpy as np
import pandas as pd


def build_rfm(transactions, start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start >= end or end != end.normalize():
        raise ValueError("RFM requires start < end and a midnight exclusive end")
    window = transactions.loc[transactions["invoice_date"].ge(start)
                              & transactions["invoice_date"].lt(end)
                              & transactions["customer_id"].notna()]
    sales = window.loc[window["include_product_sales"]]
    if sales.empty:
        raise ValueError("No identified positive purchases in RFM window")
    rfm = sales.groupby("customer_id").agg(
        last_positive_transaction=("invoice_date", "max"),
        frequency=("invoice_no", "nunique"), monetary_gross=("line_amount", "sum"))
    rfm["recency_days"] = (end - rfm["last_positive_transaction"].dt.normalize()).dt.days
    cancels = window.loc[window["include_product_cancellations"]].groupby("customer_id")["line_amount"].sum().mul(-1)
    rfm["cancel_amount"] = cancels.reindex(rfm.index).fillna(0)
    rfm["monetary_net"] = rfm["monetary_gross"] - rfm["cancel_amount"]
    rfm["cancel_to_gross_pct"] = rfm["cancel_amount"] / rfm["monetary_gross"] * 100
    rfm["nonpositive_net"] = rfm["monetary_net"] <= 0
    return rfm


def score_rfm(rfm, r_thresholds=(16, 50, 146)):
    result = rfm.copy()
    if len(r_thresholds) != 3 or not all(a < b for a, b in zip(r_thresholds, r_thresholds[1:])):
        raise ValueError("R thresholds must be strictly increasing")
    r, f = result["recency_days"], result["frequency"]
    eligible = result["monetary_net"] > 0
    thresholds = result.loc[eligible, "monetary_net"].quantile([.25, .5, .75])
    q25, q50, q75 = thresholds.tolist()
    if not q25 < q50 < q75:
        raise ValueError("M quantiles overlap or no eligible customers; review bins")
    result["R_score"] = np.select([r <= t for t in r_thresholds], [4, 3, 2], default=1)
    result["F_score"] = np.select([f == 1, f == 2, f <= 4], [1, 2, 3], default=4)
    result["M_score"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    m = result.loc[eligible, "monetary_net"]
    result.loc[eligible, "M_score"] = 1 + (m > q25).astype(int) + (m > q50).astype(int) + (m > q75).astype(int)
    recent, long_gap = r <= r_thresholds[1], r > r_thresholds[2]
    high = recent & (f >= 3) & result["M_score"].ge(3).fillna(False)
    result["segment"] = np.select(
        [~eligible, eligible & high, eligible & recent & (f == 1),
         eligible & recent & (f != 1), eligible & long_gap],
        ["净额非正待核查", "近期多次高贡献", "近期单次购买", "近期其他复购", "较久未购买"],
        default="中等购买间隔")
    return result, thresholds


def segment_summary(rfm):
    result = rfm.groupby("segment").agg(
        customer_count=("frequency", "size"), median_recency=("recency_days", "median"),
        median_frequency=("frequency", "median"), gross_amount=("monetary_gross", "sum"),
        cancel_amount=("cancel_amount", "sum"), net_amount=("monetary_net", "sum"))
    result["customer_share_pct"] = result["customer_count"] / len(rfm) * 100
    return result
