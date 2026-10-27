from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression

REPORTS = Path(__file__).resolve().parents[1] / "reports"
REPORTS.mkdir(exist_ok=True)

df = pd.read_csv(REPORTS / "dataset.csv")
X = df.drop(columns=["customer_id", "churn"])
y = df["churn"]

# 全量训练最终模型
pipe = Pipeline([("sc", StandardScaler()),
                 ("lr", LogisticRegression(max_iter=1000, class_weight="balanced"))])
pipe.fit(X, y)
df["churn_prob"] = pipe.predict_proba(X)[:, 1].round(4)

# 风险分层
df["risk"] = pd.cut(df["churn_prob"], bins=[-0.01, 0.4, 0.7, 1.01],
                    right=False, labels=["low", "mid", "high"])
# 价值分层（金额中位数）
value_med = df["monetary"].median()
df["high_value"] = df["monetary"] >= value_med

# 召回建议（风险 x 价值）
def action(r):
    if r["risk"] == "high" and r["high_value"]:
        return "人工客服+大额券，重点挽留"
    if r["risk"] == "high":
        return "自动邮件/短信+小额券，低成本触达"
    if r["risk"] == "mid":
        return "常规促销/激活推送"
    return "维护，不打扰"
df["retention_action"] = df.apply(action, axis=1)

cols = ["customer_id", "churn_prob", "risk", "high_value", "monetary",
        "recency_days", "frequency", "active_days", "retention_action"]
df[cols].sort_values("churn_prob", ascending=False).to_csv(
    REPORTS / "churn_risk_all.csv", index=False)                       # 全量
df[cols].sort_values("churn_prob", ascending=False).head(200).to_csv(
    REPORTS / "churn_top200.csv", index=False)                        # TOP200
key = df[(df["risk"] == "high") & df["high_value"]]
key[cols].sort_values("monetary", ascending=False).to_csv(
    REPORTS / "churn_key_retain.csv", index=False)                    # 重点挽留

print("===== 客户流失预警结果 =====")
print(f"总客户: {len(df)}  高风险: {(df['risk']=='high').sum()}  "
      f"中风险: {(df['risk']=='mid').sum()}  低风险: {(df['risk']=='low').sum()}")
print(f"高风险客户涉及金额: {df[df['risk']=='high']['monetary'].sum():,.0f}")
print(f"重点挽留(高风险高价值): {len(key)} 人, 金额 {key['monetary'].sum():,.0f}")
print("已生成: churn_risk_all.csv / churn_top200.csv / churn_key_retain.csv")
