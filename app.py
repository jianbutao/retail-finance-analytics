from pathlib import Path
import sys
import json
import pandas as pd
import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parent
source_dir = str(PROJECT_DIR / "src")
if source_dir not in sys.path:
    sys.path.insert(0, source_dir)

from retail_finance.config import resolve_path


st.set_page_config(
    page_title="零售经营分析",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(show_spinner="加载经营指标……", max_entries=2)
def load_overview(
    snapshot_path, monthly_path, snapshot_mtime, monthly_mtime
):
    snapshot = json.loads(
        Path(snapshot_path).read_text(encoding="utf-8")
    )
    if snapshot["schema_version"] != 1:
        raise ValueError("不支持的总览快照版本")

    totals = snapshot["totals"]
    monthly = pd.read_csv(monthly_path, index_col=0)
    monthly.index = pd.to_datetime(monthly.index, format="%Y-%m")
    monthly.index.name = "月份"

    if monthly.empty:
        raise ValueError("月度报告为空")

    for column, key in (
        ("gross_amount", "gross_milli"),
        ("cancel_amount", "cancel_milli"),
        ("net_amount", "net_milli"),
    ):
        if abs(monthly[column].sum() - totals[key] / 1000) > 0.01:
            raise ValueError(f"月度表与总览快照不一致：{column}")

    return totals, monthly


st.title("零售交易数据驱动的经营分析与风险信号识别")
st.caption(
    "历史分析演示 · 金额单位 GBP · "
    "交易金额不等于会计收入、利润或到账现金流"
)

try:
    # 仅用于显示来源批次，不再读取该目录中的交易明细。
    batch_dir = resolve_path("cleaned_batch")
    business_dir = resolve_path("business_report")

    if not (business_dir / "SUCCESS.txt").is_file():
        raise FileNotFoundError("经营分析归档缺少成功标记")

    snapshot_path = business_dir / "dashboard_overview.json"
    monthly_path = business_dir / "monthly_metrics.csv"

    totals, monthly = load_overview(
        str(snapshot_path),
        str(monthly_path),
        snapshot_path.stat().st_mtime_ns,
        monthly_path.stat().st_mtime_ns,
    )
except (OSError, ValueError, KeyError, TypeError) as error:
    st.error(f"数据加载失败：{error}")
    st.stop()

st.sidebar.header("数据版本")
st.sidebar.write("清洗批次")
st.sidebar.code(batch_dir.name)
st.sidebar.caption("当前页面仅读取本地数据，不调用AI或数据库。")

st.subheader("全期经营指标")
st.caption(
    "固定范围：2009-12-01至2011-12-09。"
    "下方图表选项不改变这些全期指标。"
)

first_row = st.columns(3)
first_row[0].metric(
    "商品正向交易金额", f"£{totals['gross_milli'] / 1000:,.2f}"
)
first_row[1].metric(
    "商品取消／冲销金额", f"£{totals['cancel_milli'] / 1000:,.2f}"
)
first_row[2].metric(
    "商品交易净额", f"£{totals['net_milli'] / 1000:,.2f}"
)

second_row = st.columns(3)
second_row[0].metric("正向订单数", f"{totals['sales_orders']:,}")
second_row[1].metric(
    "已识别购买客户数", f"{totals['identified_customers']:,}"
)
second_row[2].metric(
    "取消金额占正向金额比例", f"{totals['cancel_amount_pct']:.2f}%"
)

st.caption(
    f"已识别客户金额覆盖率：{totals['identified_coverage_pct']:.2f}%。"
    "取消记录未逐笔匹配原订单，该比例不是实际退款率。"
)

st.subheader("月度交易趋势")
st.caption("以下筛选仅作用于趋势图和下方明细，不改变顶部全期指标。")

month_options = monthly.index.strftime("%Y-%m").tolist()

control_left, control_right = st.columns([2, 1])

with control_left:
    selected_start, selected_end = st.select_slider(
        "选择月份范围",
        options=month_options,
        value=(month_options[0], month_options[-1]),
    )

with control_right:
    metric_choice = st.selectbox(
        "选择趋势指标",
        ["交易金额", "正向订单数", "取消金额占比"],
    )

exclude_partial = st.checkbox(
    "趋势图排除数据边界截断月份",
    value=True,
)

selected_mask = (
    monthly.index >= pd.Timestamp(selected_start)
) & (
    monthly.index <= pd.Timestamp(selected_end)
)

plot_data = monthly.loc[selected_mask].copy()

if exclude_partial:
    plot_data = plot_data.loc[
        ~plot_data["month_boundary_truncated"]
    ]

if plot_data.empty:
    st.info(
        "当前条件下没有可展示的月份。"
        "请扩大月份范围，或取消排除截断月份。"
    )
else:
    if metric_choice == "交易金额":
        chart_data = plot_data[
            ["gross_amount", "net_amount"]
        ].rename(columns={
            "gross_amount": "商品正向交易金额",
            "net_amount": "商品交易净额",
        })
        y_label = "金额（GBP）"

    elif metric_choice == "正向订单数":
        chart_data = plot_data[
            ["sales_orders"]
        ].rename(columns={"sales_orders": "正向订单数"})
        y_label = "订单数"

    else:
        denominator = plot_data["gross_amount"].where(
            plot_data["gross_amount"] > 0
        )
        chart_data = (
            plot_data["cancel_amount"] / denominator * 100
        ).to_frame("取消金额占正向金额比例")
        y_label = "比例（%）"

    st.caption(
        f"实际展示：{plot_data.index.min():%Y-%m} "
        f"至 {plot_data.index.max():%Y-%m}，"
        f"共 {len(plot_data)} 个月。"
    )

    # 只有一个月时使用柱图，避免单个点在折线图中不明显
    if len(chart_data) == 1:
        st.bar_chart(
            chart_data,
            x_label="月份",
            y_label=y_label,
            height=380,
        )
    else:
        st.line_chart(
            chart_data,
            x_label="月份",
            y_label=y_label,
            height=380,
        )

st.warning(
    "2011年12月仅记录至9日，默认不纳入趋势图。"
    "其他月份未被边界截断，也不代表每日数据完整。"
)

with st.expander("查看月度明细与记录覆盖"):
    detail = plot_data[
        [
            "gross_amount", "cancel_amount", "net_amount",
            "sales_orders", "days_with_product_sales",
            "month_boundary_truncated",
        ]
    ].rename(columns={
        "gross_amount": "正向金额",
        "cancel_amount": "取消金额",
        "net_amount": "交易净额",
        "sales_orders": "正向订单数",
        "days_with_product_sales": "有销售记录天数",
        "month_boundary_truncated": "边界截断",
    })
    detail.index = detail.index.strftime("%Y-%m")
    detail["边界截断"] = detail["边界截断"].map({
    True: "是（月份不完整）",
    False: "否",
})
    st.dataframe(detail.round(2), width="stretch")

with st.expander("指标口径"):
    st.markdown(
        "- 正向订单数：含商品正向明细的不同订单编号数。\n"
        "- 已识别客户数：正向交易中客户编号非空的去重客户数。\n"
        "- 交易净额：商品正向金额减去商品取消／冲销金额。\n"
        "- 有销售记录天数不等于已确认的营业天数。"
    )