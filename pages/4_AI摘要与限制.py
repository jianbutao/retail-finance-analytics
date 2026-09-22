from pathlib import Path
import hashlib
import json
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from retail_finance.config import resolve_path

st.set_page_config(page_title="AI摘要与限制", layout="wide")
st.title("AI经营分析摘要")
st.caption("人工对话生成并归档的历史分析演示，非实时报告，未接入在线生成API。")

try:
    archive = resolve_path("ai_summary_report")
    record = json.loads(
        (archive / "generation_record.json").read_text(encoding="utf-8")
    )

    contents = {}
    for filename in ("manual_summary_prompt.txt", "business_summary.md"):
        raw = (archive / filename).read_bytes()
        expected = record["files"][filename]
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise ValueError(f"{filename} 与生成记录中的哈希不一致")
        contents[filename] = raw.decode("utf-8")

except (OSError, ValueError, KeyError, TypeError) as error:
    st.error(f"摘要成果读取或完整性检查失败：{error}")
    st.stop()

summary = contents["business_summary.md"]
prompt = contents["manual_summary_prompt.txt"]
review = record.get("review", {})

st.info(
    f"作者人工复核状态：{review.get('human_review', '未记录')}。"
    "文件哈希检查通过仅表示文件与记录一致，不证明内容正确。"
)

summary_tab, evidence_tab, limits_tab = st.tabs(
    ["经营摘要", "证据与生成记录", "数据与模型限制"]
)

with summary_tab:
    st.markdown(summary)
    st.download_button(
        "下载经营摘要",
        data=summary.encode("utf-8"),
        file_name="business_summary.md",
        mime="text/markdown",
    )

with evidence_tab:
    st.write("归档批次：", archive.name)
    st.write("记录时间（UTC）：", record.get("created_at_utc", "未记录"))
    st.write("生成方式：", record.get("generation_mode", "未记录"))
    st.write("模型版本：", record.get("model_version") or "未记录确切版本")
    st.caption(
        "[E01]等编号用于追溯摘要所依据的证据，"
        "并不代表结论已获独立验证。"
    )
    st.text_area(
        "生成时使用的完整要求与证据",
        value=prompt,
        height=450,
        disabled=True,
    )
    with st.expander("查看生成记录"):
        st.json(record)

with limits_tab:
    st.markdown("""
- **样本范围**：单个零售商的历史交易样本，不能直接推广至所有企业。
- **金额口径**：商品交易金额不是会计确认收入、利润或到账现金流。
- **取消记录**：未逐笔匹配原销售，不能证明实际付款、退款或取消原因。
- **数据覆盖**：边界截断与无记录期间需要单独解释；无记录不自动等于零销售。
- **客户分析**：缺失客户编号影响结构解释；久未购买不等于已经流失。
- **分类与窗口**：商品候选存在分类不确定性；各模块窗口不同，不构成同一时点的实时判断。
- **预测范围**：四周移动平均逐周更新，预测下一周，不是一次预测未来十二周。
- **模型评估**：模型由验证集选定；已查看的测试集不再用于调参。WAPE不是准确率。
- **信号解释**：规则阈值属于项目设定，未进行季节性调整，触发不等于经营恶化。
- **AI边界**：摘要依赖所附证据，可能出现遗漏或解释偏差，需要人工复核。
""")