from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from retail_finance.dashboard import page_data

st.set_page_config(page_title="风险信号", layout="wide")
tables = page_data()

st.title("经营信号与核查线索")
st.caption(
    "历史分析演示。阈值是项目观察规则，不是行业风险标准；"
    "触发信号不等于经营恶化，各模块不能简单相加。"
)

monthly_tab, customer_tab, quality_tab, case_tab = st.tabs(
    ["月度观察", "客户跟进", "数据质量", "大额冲销案例"]
)

with monthly_tab:
    signals = tables["monthly_signals"]
    st.subheader("月度规则触发记录")
    st.caption(
        "金额下降相对前三个月均值；取消占比变化使用百分点。"
        "规则未进行季节性调整，“待核查”表示业务原因尚未确认。"
    )
    st.dataframe(
        signals[
            [
                "observation_month", "signal_name",
                "observed_value", "unit", "status",
            ]
        ].rename(columns={
            "observation_month": "观察月份",
            "signal_name": "信号",
            "observed_value": "观察值",
            "unit": "单位",
            "status": "状态",
        }),
        hide_index=True,
        width="stretch",
    )

    if not signals.empty:
        selected_id = st.selectbox(
            "查看信号依据", signals["signal_id"].tolist()
        )
        selected = signals.loc[
            signals["signal_id"].eq(selected_id)
        ].iloc[0]

        st.write(
            f"比较基准：{selected['baseline_start_month']} 至 "
            f"{selected['baseline_end_month']}"
        )
        st.write(
            f"触发条件：观察值 {selected['comparison_operator']} "
            f"{selected['threshold']:g} {selected['unit']}"
        )
        st.info(f"适用限制：{selected['limitation']}")
        st.write(f"建议核查：{selected['suggested_action']}")

with customer_tab:
    concentration = tables["customer_concentration"]
    triggered = concentration.loc[
        concentration["customer_concentration_signal"].fillna(False)
    ].copy()
    triggered.index = triggered.index.astype(str)

    st.subheader("客户金额集中月份")
    st.caption(
        "观察条件：前10名占已识别客户正向金额至少30%，"
        "且已识别购买客户至少20名；排除边界截断月份。"
    )
    st.dataframe(
        triggered[
            [
                "active_identified_customers",
                "identified_coverage_pct",
                "top10_share_identified_pct",
                "top10_share_all_pct",
            ]
        ].rename(columns={
            "active_identified_customers": "已识别购买客户数",
            "identified_coverage_pct": "客户金额识别覆盖率%",
            "top10_share_identified_pct": "前10名占已识别金额%",
            "top10_share_all_pct": "前10名占全部正向金额%",
        }),
        width="stretch",
    )

    inactive = tables["inactive_customers"]
    st.subheader("较高历史净贡献、较久未购买的客户")
    st.caption(
        "固定窗口：2010-12-01 至 2011-12-01，不含结束日。"
        "条件：交易净额为正、M评分至少3、超过146天未购买。"
    )
    left, right = st.columns(2)
    left.metric("符合观察条件的客户数", f"{len(inactive):,}")
    right.metric(
        "这些客户窗口内的历史交易净额",
        f"£{inactive['monetary_net'].sum():,.2f}",
    )
    st.warning("久未购买不等于已流失；历史交易净额不是预计损失。")
    st.dataframe(inactive, width="stretch")

with quality_tab:
    st.subheader("影响分析解释的数据质量提示")
    st.dataframe(
        tables["quality_notes"].rename(columns={
            "note_id": "提示编号",
            "period": "期间",
            "note_type": "提示类型",
            "observed_value": "观察值",
            "unit": "单位",
            "explanation": "说明",
        }),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "边界截断提示的观察值为空，表示不适用，不是零。"
        "完整日历周无记录，不能据此区分停业与数据缺失。"
    )

with case_tab:
    st.subheader("2011年1月：客户12346的大额冲销案例")
    st.write(
        "同一客户、同一商品的一组正向与取消记录，"
        "金额各为£77,183.60，相隔16分钟。"
    )
    st.dataframe(tables["cancellation_case"], width="stretch")
    st.info(
        "同时排除两条案例记录后，取消占比下降、交易净额不变。"
        "这是敏感性分析：不删除原始记录，不替换正式指标。"
    )
    st.caption(
        "该案例同时影响客户正向金额排名与取消占比，"
        "相关信号不能当作相互独立的风险累加；"
        "记录不能证明实际付款、退款或取消原因。"
    )