"""经营观察信号：触发不等于已确认的经营风险。"""

import pandas as pd


MONTHLY_RULES = {
    "version": "monthly_signals_v1",
    "baseline_months": 3,
    "sales_drop_pct": -30.0,
    "cancel_rise_pp": 5.0,
}


def assess_monthly_signals(monthly, rules=None):
    """返回月度基准和信号；不修改输入，不打印或保存文件。"""
    rules = MONTHLY_RULES if rules is None else rules
    result = monthly.copy()

    if result.empty:
        raise ValueError("月度数据不能为空。")

    expected = pd.period_range(
        result.index.min(), result.index.max(), freq="M"
    )
    if not result.index.equals(expected):
        raise ValueError("月度索引必须连续、有序且无重复。")

    window = rules["baseline_months"]
    if not isinstance(window, int) or window < 1:
        raise ValueError("基准窗口必须为正整数。")

    usable = (
        ~result["month_boundary_truncated"]
        & result["gross_amount"].gt(0)
        & result["cancel_amount"].notna()
    )

    gross = result["gross_amount"].where(usable)
    cancel = result["cancel_amount"].where(usable)
    days = result["days_with_product_sales"].where(usable)

    past_gross = gross.shift(1).rolling(window, min_periods=window)
    past_cancel = cancel.shift(1).rolling(window, min_periods=window)

    result["baseline_gross_amount"] = past_gross.mean()
    result["baseline_sales_days"] = (
        days.shift(1).rolling(window, min_periods=window).mean()
    )
    result["cancel_amount_pct"] = cancel / gross * 100
    result["baseline_cancel_pct"] = (
        past_cancel.sum() / past_gross.sum() * 100
    )
    result["gross_vs_baseline_pct"] = (
        gross / result["baseline_gross_amount"] - 1
    ) * 100
    result["cancel_vs_baseline_pp"] = (
        result["cancel_amount_pct"] - result["baseline_cancel_pct"]
    )

    available = (
        usable
        & result["baseline_gross_amount"].notna()
        & result["baseline_cancel_pct"].notna()
    )
    result["assessment_available"] = available

    conditions = {
        "sales_drop_signal": (
            result["gross_vs_baseline_pct"] <= rules["sales_drop_pct"]
        ),
        "cancel_rise_signal": (
            result["cancel_vs_baseline_pp"] >= rules["cancel_rise_pp"]
        ),
    }

    for name, condition in conditions.items():
        result[name] = (
            condition.astype("boolean").where(available, pd.NA)
        )

    return result
def assess_customer_concentration(
    transactions,
    monthly,
    threshold_pct=30.0,
    min_customers=20,
):
    """按月识别前10名已识别客户集中信号；使用商品正向交易。"""
    if not 0 <= threshold_pct <= 100:
        raise ValueError("占比阈值必须在0至100之间。")
    if min_customers < 10:
        raise ValueError("最低客户数不能小于排名客户数10。")

    identified = transactions.loc[
        transactions["include_product_sales"]
        & transactions["customer_id"].notna()
    ].copy()

    identified["month"] = (
        identified["invoice_date"].dt.to_period("M")
    )

    customer_amounts = (
        identified.groupby(["month", "customer_id"], as_index=False)
        .agg(gross_amount=("line_amount", "sum"))
        .sort_values(
            ["month", "gross_amount", "customer_id"],
            ascending=[True, False, True],
        )
    )

    customer_amounts["rank_in_month"] = (
        customer_amounts.groupby("month").cumcount() + 1
    )

    customer_totals = customer_amounts.groupby("month").agg(
        identified_amount=("gross_amount", "sum"),
        active_identified_customers=("customer_id", "size"),
    )

    top10 = (
        customer_amounts.loc[
            customer_amounts["rank_in_month"] <= 10
        ]
        .groupby("month")["gross_amount"]
        .sum()
        .rename("top10_amount")
    )

    result = monthly[
        ["gross_amount", "month_boundary_truncated"]
    ].join(customer_totals).join(top10)

    result["active_identified_customers"] = (
        result["active_identified_customers"]
        .fillna(0)
        .astype(int)
    )

    identified_denominator = result["identified_amount"].where(
        result["identified_amount"] > 0
    )
    all_denominator = result["gross_amount"].where(
        result["gross_amount"] > 0
    )

    result["identified_coverage_pct"] = (
        result["identified_amount"] / all_denominator * 100
    )
    result["top10_share_identified_pct"] = (
        result["top10_amount"] / identified_denominator * 100
    )
    result["top10_share_all_pct"] = (
        result["top10_amount"] / all_denominator * 100
    )

    result["assessment_available"] = (
        ~result["month_boundary_truncated"]
        & result["active_identified_customers"].ge(min_customers)
        & identified_denominator.notna()
        & all_denominator.notna()
    )

    result["customer_concentration_signal"] = (
        result["top10_share_identified_pct"]
        .ge(threshold_pct)
        .astype("boolean")
        .where(result["assessment_available"], pd.NA)
    )

    return result
def identify_high_value_inactive(rfm):
    """筛选已有RFM中的较高净贡献、较久未购买客户。"""
    required = [
        "recency_days", "frequency", "monetary_gross",
        "cancel_amount", "monetary_net", "M_score",
    ]

    missing = set(required) - set(rfm.columns)
    if missing:
        raise ValueError(f"RFM缺少字段：{sorted(missing)}")
    if not rfm.index.is_unique:
        raise ValueError("RFM客户编号必须唯一。")

    selected = (
        rfm["monetary_net"].gt(0)
        & rfm["M_score"].ge(3).fillna(False)
        & rfm["recency_days"].gt(146)
    )

    result = rfm.loc[selected, required].copy()
    result = (
        result.reset_index()
        .sort_values(
            ["monetary_net", "customer_id"],
            ascending=[False, True],
        )
        .set_index("customer_id")
    )

    return result
def identify_data_quality_notes(monthly, weekly, customers):
    """生成数据质量提示；不将无记录解释为零营业额。"""
    coverage_threshold = 80.0
    rows = []

    for month in monthly.index[
        monthly["month_boundary_truncated"]
    ]:
        rows.append({
            "note_id": f"PARTIAL_MONTH_{month}",
            "period": str(month),
            "note_type": "月份边界截断",
            "observed_value": None,
            "unit": "",
            "explanation": "数据起止边界截断月份，不宜直接比较整月金额。",
        })

    for week in weekly.index[weekly["recorded_days"].eq(0)]:
        rows.append({
            "note_id": f"NO_RECORD_WEEK_{week}",
            "period": str(week),
            "note_type": "完整日历周无记录",
            "observed_value": 0,
            "unit": "天",
            "explanation": "该周没有交易记录；停业与数据缺失尚无法区分。",
        })

    has_amount = customers["gross_amount"].gt(0)
    no_identified = (
        customers["active_identified_customers"].eq(0)
    )

    # 没有已识别客户但存在正向金额时，金额覆盖率为0，
    # 不把这个情况悄悄当成不可见的NaN。
    coverage = customers["identified_coverage_pct"].copy()
    coverage.loc[has_amount & no_identified] = 0.0

    low_coverage = has_amount & coverage.lt(coverage_threshold)

    for month in customers.index[low_coverage]:
        rows.append({
            "note_id": f"LOW_CUSTOMER_COVERAGE_{month}",
            "period": str(month),
            "note_type": "客户金额识别覆盖偏低",
            "observed_value": float(coverage.loc[month]),
            "unit": "%",
            "explanation": (
                "识别覆盖率低于项目观察阈值80%；"
                "已识别客户结构不一定代表全部客户。"
            ),
        })

    return pd.DataFrame(
        rows,
        columns=[
            "note_id", "period", "note_type",
            "observed_value", "unit", "explanation",
        ],
    )