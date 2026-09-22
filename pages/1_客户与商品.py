from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from retail_finance.dashboard import page_data

st.set_page_config(page_title="客户与商品", layout="wide")
st.title("客户与商品")
st.caption("使用固定历史归档；本页控件不改变其他页面的观察窗口。")

tables = page_data()
product_tab, customer_tab, rfm_tab = st.tabs(
    ["商品结构", "客户集中", "RFM分群"]
)

with product_tab:
    st.caption("全期：2009-12-01至2011-12-09。排名不是利润排名。")

    metric_label = st.selectbox(
        "商品排名口径", ["交易净额", "正向交易金额"]
    )
    top_n = st.selectbox("展示数量", [5, 10, 20], index=1)

    metric = {
        "交易净额": "net_amount",
        "正向交易金额": "gross_amount",
    }[metric_label]

    top = tables["products"].nlargest(top_n, metric).copy()
    top.index = top.index.astype(str)
    top.index.name = "商品编号"

    st.bar_chart(
        top[[metric]].rename(columns={metric: metric_label}),
        horizontal=True,
        sort=False,
        height=420,
    )

    st.dataframe(
        top[
            [
                "description_example", "gross_amount",
                "cancel_amount", "net_amount", "sales_orders",
            ]
        ].rename(columns={
            "description_example": "商品描述",
            "gross_amount": "正向金额",
            "cancel_amount": "取消金额",
            "net_amount": "交易净额",
            "sales_orders": "正向订单数",
        }).round(2),
        width="stretch",
    )

    st.info(
        "切换正向金额与净额排名，可观察大额冲销对商品排名的影响。"
        "金额单位GBP。"
    )

with customer_tab:
    concentration = tables["customer_concentration"].copy()
    concentration.index = concentration.index.astype(str)

    month = st.selectbox(
        "观察月份", concentration.index.tolist()
    )
    row = concentration.loc[month]

    columns = st.columns(3)
    columns[0].metric(
        "客户金额识别覆盖率",
        f"{row['identified_coverage_pct']:.2f}%",
    )
    columns[1].metric(
        "前10名占已识别金额",
        f"{row['top10_share_identified_pct']:.2f}%",
    )
    columns[2].metric(
        "前10名占全部正向金额",
        f"{row['top10_share_all_pct']:.2f}%",
    )

    st.write(
        "当月已识别购买客户数：",
        int(row["active_identified_customers"]),
    )

    if not bool(row["assessment_available"]):
        st.warning("该月不满足规则评估条件，不等于已经确认没有信号。")
    elif bool(row["customer_concentration_signal"]):
        st.warning("触发客户集中观察规则，需结合识别覆盖率及交易明细核查。")
    else:
        st.info("未触发本项目客户集中观察规则，不代表不存在其他风险。")

    st.caption(
        "规则：前10名占已识别正向金额至少30%，"
        "已识别客户至少20名，且月份未被边界截断。"
        "这是项目观察阈值，不是行业风险评级。"
    )
    st.caption(
        "2011年1月客户集中与大额冲销案例有关，"
        "不能把相关信号当成独立风险累计。"
    )

with rfm_tab:
    segments = tables["segments"]

    st.caption("固定窗口：2010-12-01至2011-12-01，不含结束日。")
    st.metric("RFM客户数", f"{int(segments['customer_count'].sum()):,}")

    selected = st.radio(
        "分群图指标", ["客户数", "历史交易净额"], horizontal=True
    )
    column = {
        "客户数": "customer_count",
        "历史交易净额": "net_amount",
    }[selected]

    st.bar_chart(
        segments[[column]].rename(columns={column: selected}),
        horizontal=True,
        height=380,
    )

    st.dataframe(
        segments[
            ["customer_count", "customer_share_pct", "net_amount"]
        ].rename(columns={
            "customer_count": "客户数",
            "customer_share_pct": "客户占比%",
            "net_amount": "历史交易净额_GBP",
        }).round(2),
        width="stretch",
    )

    st.info(
        "分群描述历史购买行为，不是流失预测。"
        "分群使用了金额指标，高贡献结果不构成独立预测验证。"
    )