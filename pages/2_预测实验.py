from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from retail_finance.dashboard import page_data

st.set_page_config(page_title="预测实验", layout="wide")
st.title("交易金额预测实验")
st.caption(
    "历史回测，不是当前企业未来销售预测。"
    "每周更新已知历史，预测下一周的商品正向交易金额。"
)

tables = page_data()

st.subheader("方法选择：依据验证集")
st.dataframe(
    tables["forecast_validation"].round(2),
    width="stretch",
)
st.info(
    "四周移动平均在本轮验证集上误差最低，因此被选定。"
    "岭回归保留为未胜出的实验，不重新按测试集选择方法。"
)

st.subheader("独立测试期表现")
test_metrics = tables["forecast_test"]
selected = test_metrics.loc["前四周平均（已选定）"]

columns = st.columns(3)
columns[0].metric("MAE", f"£{selected['MAE_GBP']:,.2f}")
columns[1].metric("WAPE", f"{selected['WAPE_pct']:.2f}%")
columns[2].metric(
    "平均偏差", f"£{selected['平均偏差_GBP']:,.2f}"
)

st.dataframe(test_metrics.round(2), width="stretch")

errors = tables["forecast_errors"].copy()
errors.index = pd.to_datetime(
    errors.index.astype(str).str.split("/").str[0]
)
errors.index.name = "周起始日"

st.caption(
    "测试范围：2011-09-05至2011-11-27，共12周。"
    "下面的切换只改变图表，不改变评估范围和指标。"
)

view = st.radio(
    "图表内容", ["实际与预测", "逐周预测误差"], horizontal=True
)

if view == "实际与预测":
    st.line_chart(
        errors[["actual", "predicted"]].rename(columns={
            "actual": "实际正向交易金额",
            "predicted": "四周移动平均预测",
        }),
        x_label="周起始日",
        y_label="金额（GBP）",
        height=380,
    )
else:
    st.bar_chart(
        errors[["error"]].rename(columns={
            "error": "预测金额减实际金额",
        }),
        x_label="周起始日",
        y_label="误差（GBP）",
        height=380,
    )

with st.expander("查看逐周结果"):
    detail = errors.rename(columns={
        "actual": "实际金额",
        "predicted": "预测金额",
        "error": "预测减实际",
        "absolute_error": "绝对误差",
    })
    detail.index = detail.index.strftime("%Y-%m-%d")
    st.dataframe(detail.round(2), width="stretch")

st.warning(
    "负偏差表示平均低估，不代表实际经营损失。"
    "WAPE不能转换成预测准确率。"
    "只有一个历史测试区间，结果不保证跨季节或未来稳定。"
)